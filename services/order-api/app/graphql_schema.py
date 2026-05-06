from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import strawberry
from fastapi import Depends
from sqlalchemy.orm import Session, selectinload
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.scalars import JSON

from app.db import get_db
from app.models import Order, OrderItem, Shipment, WorkflowEvent
from app.observability import ORDERS_CREATED_TOTAL
from app.schemas import OrderCreate


def _load_order(db: Session, order_id: UUID) -> Order | None:
    return (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id)
        .one_or_none()
    )


def _list_orders(db: Session, limit: int) -> list[Order]:
    return (
        db.query(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )


def _create_order_record(
    *,
    customer_id: str,
    destination_zone: str,
    line_items: list[tuple[str, int, Decimal]],
    db: Session,
) -> Order:
    from app.main import _build_workflow_id

    workflow_id = _build_workflow_id()
    order = Order(
        customer_id=customer_id,
        destination_zone=destination_zone,
        workflow_id=workflow_id,
    )
    order.items = [
        OrderItem(sku=sku, quantity=quantity, unit_price=unit_price)
        for sku, quantity, unit_price in line_items
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    ORDERS_CREATED_TOTAL.inc()

    from app.main import _record_workflow_start_queued

    _record_workflow_start_queued(db, order.id, workflow_id)
    db.commit()

    created = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order.id)
        .one()
    )
    return created


@strawberry.type
class GraphQLOrderItem:
    id: str
    sku: str
    quantity: int
    unit_price: str

    @classmethod
    def from_model(cls, item: OrderItem) -> "GraphQLOrderItem":
        return cls(
            id=str(item.id),
            sku=item.sku,
            quantity=item.quantity,
            unit_price=str(item.unit_price),
        )


@strawberry.type
class GraphQLPlanAllocation:
    warehouse_id: str
    code: str
    sku: str
    quantity: int


@strawberry.type
class GraphQLCandidatePlan:
    warehouses_used: list[str]
    allocations: list[GraphQLPlanAllocation]
    shipping_cost: str
    eta_days: int
    sla_met: bool
    split_count: int
    load_penalty: str
    delay_penalty: str
    total_score: str

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "GraphQLCandidatePlan":
        return cls(
            warehouses_used=list(payload.get("warehouses_used", [])),
            allocations=[
                GraphQLPlanAllocation(
                    warehouse_id=str(allocation["warehouse_id"]),
                    code=str(allocation["code"]),
                    sku=str(allocation["sku"]),
                    quantity=int(allocation["quantity"]),
                )
                for allocation in payload.get("allocations", [])
            ],
            shipping_cost=str(payload.get("shipping_cost")),
            eta_days=int(payload.get("eta_days", 0)),
            sla_met=bool(payload.get("sla_met")),
            split_count=int(payload.get("split_count", 0)),
            load_penalty=str(payload.get("load_penalty")),
            delay_penalty=str(payload.get("delay_penalty")),
            total_score=str(payload.get("total_score")),
        )


@strawberry.type
class GraphQLFulfillmentPlan:
    selected_plan: GraphQLCandidatePlan
    candidate_plans: list[GraphQLCandidatePlan]

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "GraphQLFulfillmentPlan":
        return cls(
            selected_plan=GraphQLCandidatePlan.from_dict(payload["selected_plan"]),
            candidate_plans=[
                GraphQLCandidatePlan.from_dict(plan)
                for plan in payload.get("candidate_plans", [])
            ],
        )


@strawberry.type
class GraphQLWorkflowEvent:
    id: str
    order_id: str
    workflow_id: str
    event_type: str
    payload: JSON | None
    created_at: datetime

    @classmethod
    def from_model(cls, event: WorkflowEvent) -> "GraphQLWorkflowEvent":
        return cls(
            id=str(event.id),
            order_id=str(event.order_id),
            workflow_id=event.workflow_id,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )


@strawberry.type
class GraphQLShipment:
    id: str
    order_id: str
    warehouse_code: str
    tracking_id: str
    status: str
    payload: JSON | None
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def from_model(cls, shipment: Shipment) -> "GraphQLShipment":
        return cls(
            id=str(shipment.id),
            order_id=str(shipment.order_id),
            warehouse_code=shipment.warehouse_code,
            tracking_id=shipment.tracking_id,
            status=shipment.status.value,
            payload=shipment.payload,
            created_at=shipment.created_at,
            updated_at=shipment.updated_at,
        )


@strawberry.type
class GraphQLOrder:
    id: str
    customer_id: str
    destination_zone: str
    status: str
    total_cost: str | None
    eta_days: int | None
    fallback_triggered: bool
    workflow_id: str | None
    fulfillment_plan: GraphQLFulfillmentPlan | None
    created_at: datetime
    updated_at: datetime | None
    items: list[GraphQLOrderItem]

    @classmethod
    def from_model(cls, order: Order) -> "GraphQLOrder":
        return cls(
            id=str(order.id),
            customer_id=order.customer_id,
            destination_zone=order.destination_zone,
            status=order.status.value,
            total_cost=str(order.total_cost) if order.total_cost is not None else None,
            eta_days=order.eta_days,
            fallback_triggered=order.fallback_triggered,
            workflow_id=order.workflow_id,
            fulfillment_plan=(
                GraphQLFulfillmentPlan.from_dict(order.fulfillment_plan)
                if order.fulfillment_plan is not None
                else None
            ),
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[GraphQLOrderItem.from_model(item) for item in order.items],
        )


@strawberry.type
class GraphQLHealth:
    status: str
    service: str


@strawberry.input
class GraphQLOrderItemInput:
    sku: str
    quantity: int
    unit_price: float


@strawberry.input
class GraphQLOrderCreateInput:
    customer_id: str
    destination_zone: str
    line_items: list[GraphQLOrderItemInput]


@dataclass
class GraphQLContext(BaseContext):
    db: Session


def get_graphql_context(
    db: Session = Depends(get_db),
) -> GraphQLContext:
    return GraphQLContext(db=db)


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> GraphQLHealth:
        return GraphQLHealth(status="ok", service="order-api")

    @strawberry.field
    def order(self, info: strawberry.Info[GraphQLContext], order_id: str) -> GraphQLOrder | None:
        order = _load_order(info.context.db, UUID(order_id))
        return GraphQLOrder.from_model(order) if order is not None else None

    @strawberry.field
    def orders(self, info: strawberry.Info[GraphQLContext], limit: int = 25) -> list[GraphQLOrder]:
        return [GraphQLOrder.from_model(order) for order in _list_orders(info.context.db, limit)]

    @strawberry.field
    def order_events(self, info: strawberry.Info[GraphQLContext], order_id: str) -> list[GraphQLWorkflowEvent]:
        events = (
            info.context.db.query(WorkflowEvent)
            .filter(WorkflowEvent.order_id == UUID(order_id))
            .order_by(WorkflowEvent.created_at.asc())
            .all()
        )
        return [GraphQLWorkflowEvent.from_model(event) for event in events]

    @strawberry.field
    def order_shipments(self, info: strawberry.Info[GraphQLContext], order_id: str) -> list[GraphQLShipment]:
        shipments = (
            info.context.db.query(Shipment)
            .filter(Shipment.order_id == UUID(order_id))
            .order_by(Shipment.created_at.asc())
            .all()
        )
        return [GraphQLShipment.from_model(shipment) for shipment in shipments]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_order(self, info: strawberry.Info[GraphQLContext], payload: GraphQLOrderCreateInput) -> GraphQLOrder:
        normalized_payload = OrderCreate(
            customer_id=payload.customer_id,
            destination_zone=payload.destination_zone,
            line_items=[
                {
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": Decimal(str(item.unit_price)),
                }
                for item in payload.line_items
            ],
        )
        created = _create_order_record(
            customer_id=normalized_payload.customer_id,
            destination_zone=normalized_payload.destination_zone,
            line_items=[
                (item.sku, item.quantity, item.unit_price)
                for item in normalized_payload.line_items
            ],
            db=info.context.db,
        )

        from app.main import start_order_workflow

        asyncio.create_task(start_order_workflow(created.id, created.workflow_id or ""))
        return GraphQLOrder.from_model(created)


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=get_graphql_context)
