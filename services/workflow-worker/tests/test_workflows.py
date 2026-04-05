import asyncio
from datetime import timedelta

from app import workflows
from app.activities import (
    authorize_payment,
    build_inventory_snapshot,
    compute_routing_plan,
    create_shipments,
    load_order,
)


class FakeWorkflowInfo:
    workflow_id = "wf-test-123"


def run_async(coro):
    return asyncio.run(coro)


def test_workflow_happy_path_requests_expected_activities(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_execute_activity(fn, args=None, **kwargs):
        calls.append((fn.__name__, kwargs))
        if fn is load_order:
            return {
                "id": "order-1",
                "customer_id": "workflow-success",
                "destination_zone": "east",
                "line_items": [{"sku": "SKU-001", "quantity": 1, "unit_price": 12.5}],
            }
        if fn is build_inventory_snapshot:
            return [{"warehouse_id": "w1", "code": "NJ", "supported_zones": ["east"], "inventory": []}]
        if fn is compute_routing_plan:
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
        if fn is create_shipments:
            return [{"warehouse_code": "NJ", "tracking_id": "TRK-1", "status": "created"}]
        return None

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "info", lambda: FakeWorkflowInfo())

    result = run_async(workflows.OrderFulfillmentWorkflow().run("order-1"))

    assert result["status"] == "confirmed"
    assert [name for name, _ in calls] == [
        "record_event",
        "update_order_status",
        "load_order",
        "build_inventory_snapshot",
        "compute_routing_plan",
        "save_routing_plan",
        "reserve_inventory",
        "authorize_payment",
        "create_shipments",
        "confirm_order",
        "record_event",
    ]


def test_workflow_releases_inventory_and_marks_failure_on_downstream_error(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_execute_activity(fn, args=None, **kwargs):
        calls.append(fn.__name__)
        if fn is load_order:
            return {
                "id": "order-2",
                "customer_id": "workflow-failure",
                "destination_zone": "east",
                "line_items": [{"sku": "SKU-001", "quantity": 1, "unit_price": 12.5}],
            }
        if fn is build_inventory_snapshot:
            return [{"warehouse_id": "w1", "code": "NJ", "supported_zones": ["east"], "inventory": []}]
        if fn is compute_routing_plan:
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
        if fn is authorize_payment:
            raise RuntimeError("simulated payment failure")
        return None

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "info", lambda: FakeWorkflowInfo())

    try:
        run_async(workflows.OrderFulfillmentWorkflow().run("order-2"))
    except RuntimeError as exc:
        assert "simulated payment failure" in str(exc)
    else:
        raise AssertionError("Expected workflow to raise the downstream failure")

    assert calls[-2:] == ["release_inventory", "fail_order"]


def test_workflow_declares_retry_and_compensation_policies(monkeypatch) -> None:
    policies: dict[str, object] = {}

    async def fake_execute_activity(fn, args=None, **kwargs):
        if "retry_policy" in kwargs:
            policies[fn.__name__] = kwargs["retry_policy"]

        if fn is load_order:
            return {
                "id": "order-3",
                "customer_id": "workflow-success",
                "destination_zone": "east",
                "line_items": [{"sku": "SKU-001", "quantity": 1, "unit_price": 12.5}],
            }
        if fn is build_inventory_snapshot:
            return [{"warehouse_id": "w1", "code": "NJ", "supported_zones": ["east"], "inventory": []}]
        if fn is compute_routing_plan:
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
        if fn is create_shipments:
            return [{"warehouse_code": "NJ", "tracking_id": "TRK-1", "status": "created"}]
        return None

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "info", lambda: FakeWorkflowInfo())

    run_async(workflows.OrderFulfillmentWorkflow().run("order-3"))

    reserve_policy = policies["reserve_inventory"]
    payment_policy = policies["authorize_payment"]
    shipment_policy = policies["create_shipments"]

    assert reserve_policy.maximum_attempts == 1
    assert payment_policy.maximum_attempts == 1
    assert shipment_policy.maximum_attempts == 3
    assert shipment_policy.initial_interval == timedelta(seconds=1)
