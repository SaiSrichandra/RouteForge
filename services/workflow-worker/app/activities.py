import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy.orm import Session, selectinload
from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.config import settings
from app.db import SessionLocal
from app.metrics import (
    ACTIVITY_DURATION_SECONDS,
    COMPENSATIONS_TOTAL,
    PAYMENT_FAILURE_TOTAL,
    RESERVATION_FAILURE_TOTAL,
    SHIPMENT_RETRY_TOTAL,
    SPLIT_ORDERS_TOTAL,
    WORKFLOW_DURATION_SECONDS,
    WORKFLOW_FALLBACK_TOTAL,
    WORKFLOW_RESULTS_TOTAL,
)
from app.models import Order, OrderStatus, Shipment, ShipmentStatus, WorkflowEvent

WAREHOUSE_SHIPPING_PROFILES = {
    "NJ": {
        "base_shipping_cost": {"east": Decimal("6.00"), "northeast": Decimal("5.50"), "central": Decimal("8.00"), "south": Decimal("9.50"), "west": Decimal("12.00"), "southwest": Decimal("11.00")},
        "eta_days": {"east": 2, "northeast": 1, "central": 3, "south": 4, "west": 5, "southwest": 4},
    },
    "TX": {
        "base_shipping_cost": {"east": Decimal("7.00"), "northeast": Decimal("8.00"), "central": Decimal("5.00"), "south": Decimal("4.50"), "west": Decimal("8.50"), "southwest": Decimal("6.00")},
        "eta_days": {"east": 3, "northeast": 4, "central": 2, "south": 2, "west": 4, "southwest": 3},
    },
    "NV": {
        "base_shipping_cost": {"east": Decimal("10.50"), "northeast": Decimal("11.50"), "central": Decimal("7.50"), "south": Decimal("7.00"), "west": Decimal("5.00"), "southwest": Decimal("4.50")},
        "eta_days": {"east": 5, "northeast": 5, "central": 3, "south": 3, "west": 2, "southwest": 2},
    },
}


def _db_session() -> Session:
    return SessionLocal()


def _serialize_order(order: Order) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "customer_id": order.customer_id,
        "destination_zone": order.destination_zone,
        "workflow_id": order.workflow_id,
        "line_items": [
            {
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
            }
            for item in order.items
        ],
    }


@activity.defn
async def record_event(order_id: str, workflow_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    db = _db_session()
    try:
        db.add(
            WorkflowEvent(
                order_id=uuid.UUID(order_id),
                workflow_id=workflow_id,
                event_type=event_type,
                payload=payload,
            )
        )
        db.commit()
    finally:
        db.close()


@activity.defn
async def load_order(order_id: str) -> dict[str, Any]:
    db = _db_session()
    try:
        order = (
            db.query(Order)
            .options(selectinload(Order.items))
            .filter(Order.id == uuid.UUID(order_id))
            .one_or_none()
        )
        if order is None:
            raise ApplicationError(f"Order {order_id} not found", non_retryable=True)
        return _serialize_order(order)
    finally:
        db.close()


@activity.defn
async def update_order_status(order_id: str, status: str) -> None:
    db = _db_session()
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(order_id)).one_or_none()
        if order is None:
            raise ApplicationError(f"Order {order_id} not found", non_retryable=True)
        order.status = OrderStatus(status)
        db.commit()
    finally:
        db.close()


@activity.defn
async def build_inventory_snapshot(order: dict[str, Any]) -> list[dict[str, Any]]:
    started_at = perf_counter()
    destination_zone = str(order["destination_zone"])
    line_items = order["line_items"]

    async with httpx.AsyncClient(timeout=20.0) as client:
        warehouses_response = await client.get(f"{settings.inventory_service_url}/warehouses")
        warehouses_response.raise_for_status()
        warehouses = warehouses_response.json()

        inventory_by_sku: dict[str, list[dict[str, Any]]] = {}
        for item in line_items:
            sku = item["sku"]
            inventory_response = await client.get(f"{settings.inventory_service_url}/inventory/{sku}")
            inventory_response.raise_for_status()
            inventory_by_sku[sku] = inventory_response.json()

    snapshots: list[dict[str, Any]] = []
    for warehouse in warehouses:
        code = warehouse["code"]
        shipping_profile = WAREHOUSE_SHIPPING_PROFILES.get(code, {})
        snapshots.append(
            {
                "warehouse_id": warehouse["id"],
                "code": code,
                "supported_zones": warehouse["supported_zones"],
                "shipping_cost_multiplier": warehouse["shipping_cost_multiplier"],
                "daily_capacity": warehouse["daily_capacity"],
                "current_load": warehouse["current_load"],
                "base_shipping_cost": str(
                    shipping_profile.get("base_shipping_cost", {}).get(destination_zone, Decimal("9.00"))
                ),
                "eta_days": shipping_profile.get("eta_days", {}).get(destination_zone, settings.default_sla_days + 2),
                "inventory": [
                    {
                        "sku": sku,
                        "available_qty": next(
                            (
                                record["available_qty"]
                                for record in inventory_by_sku[sku]
                                if record["warehouse_id"] == warehouse["id"]
                            ),
                            0,
                        ),
                    }
                    for sku in (item["sku"] for item in line_items)
                ],
            }
        )

    ACTIVITY_DURATION_SECONDS.labels(activity="build_inventory_snapshot").observe(perf_counter() - started_at)
    return snapshots


@activity.defn
async def compute_routing_plan(order: dict[str, Any], warehouses: list[dict[str, Any]]) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        request = {
            "destination_zone": order["destination_zone"],
            "max_eta_days": settings.default_sla_days,
            "line_items": order["line_items"],
            "warehouses": warehouses,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(f"{settings.routing_service_url}/route-order", json=request)
            if response.status_code >= 400:
                raise ApplicationError(f"Routing failed: {response.text}", non_retryable=True)
            return response.json()
    finally:
        ACTIVITY_DURATION_SECONDS.labels(activity="compute_routing_plan").observe(perf_counter() - started_at)


@activity.defn
async def save_routing_plan(order_id: str, workflow_id: str, routing_result: dict[str, Any]) -> None:
    started_at = perf_counter()
    db = _db_session()
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(order_id)).one_or_none()
        if order is None:
            raise ApplicationError(f"Order {order_id} not found", non_retryable=True)

        selected_plan = routing_result["selected_plan"]
        if len(selected_plan["warehouses_used"]) > 1:
            SPLIT_ORDERS_TOTAL.inc()
        if not bool(selected_plan["sla_met"]):
            WORKFLOW_FALLBACK_TOTAL.inc()
        order.total_cost = Decimal(str(selected_plan["shipping_cost"]))
        order.eta_days = selected_plan["eta_days"]
        order.fallback_triggered = not bool(selected_plan["sla_met"])
        order.fulfillment_plan = routing_result
        db.add(
            WorkflowEvent(
                order_id=uuid.UUID(order_id),
                workflow_id=workflow_id,
                event_type="routing_completed",
                payload={
                    "selected_plan": selected_plan,
                    "candidate_count": len(routing_result.get("candidate_plans", [])),
                },
            )
        )
        db.commit()
    finally:
        db.close()
        ACTIVITY_DURATION_SECONDS.labels(activity="save_routing_plan").observe(perf_counter() - started_at)


def _group_allocations_by_warehouse(allocations: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for allocation in allocations:
        grouped[allocation["warehouse_id"]].append(
            {
                "sku": allocation["sku"],
                "quantity": allocation["quantity"],
            }
        )
    return grouped


@activity.defn
async def reserve_inventory(order_id: str, workflow_id: str, selected_plan: dict[str, Any]) -> list[dict[str, Any]]:
    started_at = perf_counter()
    try:
        grouped_allocations = _group_allocations_by_warehouse(selected_plan["allocations"])
        reservations: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for warehouse_id, items in grouped_allocations.items():
                response = await client.post(
                    f"{settings.inventory_service_url}/reservations",
                    json={
                        "order_id": order_id,
                        "warehouse_id": warehouse_id,
                        "items": items,
                    },
                )
                if response.status_code >= 400:
                    RESERVATION_FAILURE_TOTAL.inc()
                    raise ApplicationError(f"Reservation failed: {response.text}", non_retryable=True)
                reservations.extend(response.json())

        await record_event(order_id, workflow_id, "inventory_reserved", {"reservation_count": len(reservations)})
        return reservations
    finally:
        ACTIVITY_DURATION_SECONDS.labels(activity="reserve_inventory").observe(perf_counter() - started_at)


@activity.defn
async def release_inventory(order_id: str, workflow_id: str) -> None:
    started_at = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.inventory_service_url}/reservations/release",
                json={"order_id": order_id},
            )
            if response.status_code == 404:
                return
            if response.status_code >= 400:
                raise ApplicationError(f"Reservation release failed: {response.text}", non_retryable=True)
        await record_event(order_id, workflow_id, "inventory_released", {})
        COMPENSATIONS_TOTAL.labels(type="inventory_release").inc()
    finally:
        ACTIVITY_DURATION_SECONDS.labels(activity="release_inventory").observe(perf_counter() - started_at)


@activity.defn
async def authorize_payment(order: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        customer_id = str(order["customer_id"]).lower()
        if "fail-payment" in customer_id:
            PAYMENT_FAILURE_TOTAL.inc()
            raise ApplicationError("Simulated payment authorization failure", non_retryable=True)

        await record_event(str(order["id"]), workflow_id, "payment_authorized", {"customer_id": order["customer_id"]})
        return {"authorized": True}
    finally:
        ACTIVITY_DURATION_SECONDS.labels(activity="authorize_payment").observe(perf_counter() - started_at)


@activity.defn
async def create_shipments(order: dict[str, Any], workflow_id: str, selected_plan: dict[str, Any]) -> list[dict[str, Any]]:
    started_at = perf_counter()
    try:
        customer_id = str(order["customer_id"]).lower()
        attempt = activity.info().attempt
        if "delay-shipment" in customer_id and attempt < 3:
            SHIPMENT_RETRY_TOTAL.inc()
            await record_event(
                str(order["id"]),
                workflow_id,
                "shipment_retry_scheduled",
                {"attempt": attempt, "reason": "Simulated downstream shipment delay"},
            )
            raise RuntimeError("Simulated downstream shipment delay")

        db = _db_session()
        try:
            order_uuid = uuid.UUID(str(order["id"]))
            allocations = selected_plan["allocations"]
            warehouse_codes = sorted({allocation["code"] for allocation in allocations})

            existing_shipments = db.query(Shipment).filter(Shipment.order_id == order_uuid).all()
            if existing_shipments:
                return [
                    {
                        "warehouse_code": shipment.warehouse_code,
                        "tracking_id": shipment.tracking_id,
                        "status": shipment.status.value,
                    }
                    for shipment in existing_shipments
                ]

            shipments: list[dict[str, Any]] = []
            for code in warehouse_codes:
                tracking_id = f"TRK-{str(order_uuid)[:8]}-{code}"
                shipment = Shipment(
                    order_id=order_uuid,
                    warehouse_code=code,
                    tracking_id=tracking_id,
                    status=ShipmentStatus.created,
                    payload={"carrier": "simulated-carrier", "warehouse_code": code},
                )
                db.add(shipment)
                shipments.append(
                    {
                        "warehouse_code": code,
                        "tracking_id": tracking_id,
                        "status": ShipmentStatus.created.value,
                    }
                )

            db.add(
                WorkflowEvent(
                    order_id=order_uuid,
                    workflow_id=workflow_id,
                    event_type="shipments_created",
                    payload={"shipments": shipments, "attempt": attempt},
                )
            )
            db.commit()
            return shipments
        finally:
            db.close()
    finally:
        ACTIVITY_DURATION_SECONDS.labels(activity="create_shipments").observe(perf_counter() - started_at)


@activity.defn
async def confirm_order(order_id: str, workflow_id: str) -> None:
    started_at = perf_counter()
    db = _db_session()
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(order_id)).one_or_none()
        if order is None:
            raise ApplicationError(f"Order {order_id} not found", non_retryable=True)

        order.status = OrderStatus.confirmed
        if order.created_at is not None:
            WORKFLOW_DURATION_SECONDS.observe((datetime.now(timezone.utc) - order.created_at).total_seconds())
        WORKFLOW_RESULTS_TOTAL.labels(outcome="confirmed").inc()
        db.add(
            WorkflowEvent(
                order_id=uuid.UUID(order_id),
                workflow_id=workflow_id,
                event_type="order_confirmed",
                payload={"status": OrderStatus.confirmed.value},
            )
        )
        db.commit()
    finally:
        db.close()
        ACTIVITY_DURATION_SECONDS.labels(activity="confirm_order").observe(perf_counter() - started_at)


@activity.defn
async def fail_order(order_id: str, workflow_id: str, reason: str) -> None:
    started_at = perf_counter()
    db = _db_session()
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(order_id)).one_or_none()
        if order is None:
            raise ApplicationError(f"Order {order_id} not found", non_retryable=True)

        order.status = OrderStatus.failed
        if order.created_at is not None:
            WORKFLOW_DURATION_SECONDS.observe((datetime.now(timezone.utc) - order.created_at).total_seconds())
        WORKFLOW_RESULTS_TOTAL.labels(outcome="failed").inc()
        db.add(
            WorkflowEvent(
                order_id=uuid.UUID(order_id),
                workflow_id=workflow_id,
                event_type="order_failed",
                payload={"reason": reason},
            )
        )
        db.commit()
    finally:
        db.close()
        ACTIVITY_DURATION_SECONDS.labels(activity="fail_order").observe(perf_counter() - started_at)
