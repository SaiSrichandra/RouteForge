import asyncio

from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app import workflows


def run_async(coro):
    return asyncio.run(coro)


async def _run_real_workflow(monkeypatch, *, payment_should_fail: bool, shipment_failures_before_success: int):
    task_queue = "order-routing-test-queue"
    calls: list[tuple[str, str]] = []
    shipment_attempts = {"count": 0}

    @activity.defn
    async def record_event(order_id: str, workflow_id: str, event_type: str, payload: dict | None = None) -> None:
        calls.append(("record_event", event_type))

    @activity.defn
    async def update_order_status(order_id: str, status: str) -> None:
        calls.append(("update_order_status", status))

    @activity.defn
    async def load_order(order_id: str) -> dict:
        calls.append(("load_order", order_id))
        return {
            "id": order_id,
            "customer_id": "demo-fail-payment" if payment_should_fail else "demo-delay-shipment",
            "destination_zone": "east",
            "line_items": [{"sku": "SKU-001", "quantity": 1, "unit_price": 12.5}],
        }

    @activity.defn
    async def build_inventory_snapshot(order: dict) -> list[dict]:
        calls.append(("build_inventory_snapshot", order["id"]))
        return [{"warehouse_id": "w1", "code": "NJ", "supported_zones": ["east"], "inventory": []}]

    @activity.defn
    async def compute_routing_plan(order: dict, warehouses: list[dict]) -> dict:
        calls.append(("compute_routing_plan", order["id"]))
        return {
            "selected_plan": {
                "warehouses_used": ["NJ"],
                "allocations": [{"warehouse_id": "w1", "code": "NJ", "sku": "SKU-001", "quantity": 1}],
                "shipping_cost": 6.0,
                "eta_days": 2,
                "sla_met": True,
            },
            "candidate_plans": [],
        }

    @activity.defn
    async def save_routing_plan(order_id: str, workflow_id: str, routing_result: dict) -> None:
        calls.append(("save_routing_plan", order_id))

    @activity.defn
    async def reserve_inventory(order_id: str, workflow_id: str, selected_plan: dict) -> list[dict]:
        calls.append(("reserve_inventory", order_id))
        return [{"warehouse_id": "w1", "sku": "SKU-001", "quantity": 1}]

    @activity.defn
    async def release_inventory(order_id: str, workflow_id: str) -> None:
        calls.append(("release_inventory", order_id))

    @activity.defn
    async def authorize_payment(order: dict, workflow_id: str) -> dict:
        calls.append(("authorize_payment", order["id"]))
        if payment_should_fail:
            raise ApplicationError("Simulated payment authorization failure", non_retryable=True)
        return {"authorized": True}

    @activity.defn
    async def create_shipments(order: dict, workflow_id: str, selected_plan: dict) -> list[dict]:
        shipment_attempts["count"] += 1
        calls.append(("create_shipments", str(shipment_attempts["count"])))
        if shipment_attempts["count"] <= shipment_failures_before_success:
            raise RuntimeError("Simulated downstream shipment delay")
        return [{"warehouse_code": "NJ", "tracking_id": "TRK-TEST-NJ", "status": "created"}]

    @activity.defn
    async def confirm_order(order_id: str, workflow_id: str) -> None:
        calls.append(("confirm_order", order_id))

    @activity.defn
    async def fail_order(order_id: str, workflow_id: str, reason: str) -> None:
        calls.append(("fail_order", reason))

    monkeypatch.setattr(workflows, "record_event", record_event)
    monkeypatch.setattr(workflows, "update_order_status", update_order_status)
    monkeypatch.setattr(workflows, "load_order", load_order)
    monkeypatch.setattr(workflows, "build_inventory_snapshot", build_inventory_snapshot)
    monkeypatch.setattr(workflows, "compute_routing_plan", compute_routing_plan)
    monkeypatch.setattr(workflows, "save_routing_plan", save_routing_plan)
    monkeypatch.setattr(workflows, "reserve_inventory", reserve_inventory)
    monkeypatch.setattr(workflows, "release_inventory", release_inventory)
    monkeypatch.setattr(workflows, "authorize_payment", authorize_payment)
    monkeypatch.setattr(workflows, "create_shipments", create_shipments)
    monkeypatch.setattr(workflows, "confirm_order", confirm_order)
    monkeypatch.setattr(workflows, "fail_order", fail_order)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[workflows.OrderFulfillmentWorkflow],
            activities=[
                record_event,
                update_order_status,
                load_order,
                build_inventory_snapshot,
                compute_routing_plan,
                save_routing_plan,
                reserve_inventory,
                release_inventory,
                authorize_payment,
                create_shipments,
                confirm_order,
                fail_order,
            ],
        ):
            try:
                result = await env.client.execute_workflow(
                    workflows.OrderFulfillmentWorkflow.run,
                    "order-123",
                    id="wf-test-real",
                    task_queue=task_queue,
                )
                return result, calls, shipment_attempts["count"], None
            except Exception as exc:
                return None, calls, shipment_attempts["count"], exc


def test_real_temporal_environment_retries_shipments_until_success(monkeypatch) -> None:
    result, calls, shipment_attempts, error = run_async(
        _run_real_workflow(
            monkeypatch,
            payment_should_fail=False,
            shipment_failures_before_success=2,
        )
    )

    assert error is None
    assert result["status"] == "confirmed"
    assert shipment_attempts == 3
    assert ("confirm_order", "order-123") in calls
    assert [entry for entry in calls if entry[0] == "create_shipments"] == [
        ("create_shipments", "1"),
        ("create_shipments", "2"),
        ("create_shipments", "3"),
    ]


def test_real_temporal_environment_runs_compensation_on_failure(monkeypatch) -> None:
    result, calls, shipment_attempts, error = run_async(
        _run_real_workflow(
            monkeypatch,
            payment_should_fail=True,
            shipment_failures_before_success=0,
        )
    )

    assert result is None
    assert shipment_attempts == 0
    assert isinstance(error, WorkflowFailureError)
    assert ("release_inventory", "order-123") in calls
    assert any(entry[0] == "fail_order" for entry in calls)
