import asyncio

from app import activities


class FakeActivityInfo:
    def __init__(self, attempt: int) -> None:
        self.attempt = attempt


def run_async(coro):
    return asyncio.run(coro)


def test_create_shipments_raises_retryable_error_for_delayed_customer(monkeypatch) -> None:
    recorded_events: list[tuple[str, str, str, dict]] = []

    async def fake_record_event(order_id: str, workflow_id: str, event_type: str, payload: dict) -> None:
        recorded_events.append((order_id, workflow_id, event_type, payload))

    monkeypatch.setattr(activities, "record_event", fake_record_event)
    monkeypatch.setattr(activities.activity, "info", lambda: FakeActivityInfo(attempt=1))

    try:
        run_async(
            activities.create_shipments(
                order={"id": "order-delay", "customer_id": "demo-delay-shipment"},
                workflow_id="wf-delay",
                selected_plan={"allocations": [{"code": "NJ"}]},
            )
        )
    except RuntimeError as exc:
        assert "shipment delay" in str(exc)
    else:
        raise AssertionError("Expected a retryable shipment creation error")

    assert recorded_events == [
        (
            "order-delay",
            "wf-delay",
            "shipment_retry_scheduled",
            {"attempt": 1, "reason": "Simulated downstream shipment delay"},
        )
    ]
