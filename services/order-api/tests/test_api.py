import uuid
from collections.abc import Generator
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.models import Order, OrderStatus, WorkflowEvent


class FakeTemporalClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def start_workflow(self, workflow_name: str, order_id: str, *, id: str, task_queue: str) -> None:
        self.calls.append(
            {
                "workflow_name": workflow_name,
                "order_id": order_id,
                "id": id,
                "task_queue": task_queue,
            }
        )


def create_client(tmp_path, monkeypatch) -> tuple[TestClient, sessionmaker[Session], FakeTemporalClient]:
    database_path = tmp_path / "order-api-test.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", session_local)
    main.Base.metadata.drop_all(bind=engine)
    main.Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    temporal_client = FakeTemporalClient()

    async def fake_temporal_client() -> FakeTemporalClient:
        return temporal_client

    monkeypatch.setattr(main, "get_temporal_client", fake_temporal_client)
    main.app.dependency_overrides[main.get_db] = override_get_db

    client = TestClient(main.app)
    return client, session_local, temporal_client


def test_create_order_persists_and_starts_workflow(tmp_path, monkeypatch) -> None:
    client, session_local, temporal_client = create_client(tmp_path, monkeypatch)

    with client:
        response = client.post(
            "/orders",
            json={
                "customer_id": "integration-success-001",
                "destination_zone": "east",
                "line_items": [
                    {"sku": "SKU-001", "quantity": 2, "unit_price": "12.50"},
                    {"sku": "SKU-002", "quantity": 1, "unit_price": "20.00"},
                ],
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending"
    assert len(payload["items"]) == 2
    assert temporal_client.calls[0]["workflow_name"] == "OrderFulfillmentWorkflow"

    with session_local() as db:
        order = db.query(Order).filter(Order.id == uuid.UUID(payload["id"])).one()
        assert order.customer_id == "integration-success-001"
        assert order.status == OrderStatus.pending
        assert order.items[0].unit_price == Decimal("12.50")

        events = db.query(WorkflowEvent).filter(WorkflowEvent.order_id == order.id).order_by(WorkflowEvent.created_at.asc()).all()
        assert [event.event_type for event in events] == ["workflow_start_queued", "workflow_started"]


def test_create_order_marks_failure_when_workflow_start_fails(tmp_path, monkeypatch) -> None:
    client, session_local, _ = create_client(tmp_path, monkeypatch)

    class FakeTemporalStartError(main.TemporalError):
        pass

    async def broken_temporal_client():
        class BrokenClient:
            async def start_workflow(self, *_args, **_kwargs):
                raise FakeTemporalStartError("simulated temporal outage")

        return BrokenClient()

    monkeypatch.setattr(main, "get_temporal_client", broken_temporal_client)

    with client:
        response = client.post(
            "/orders",
            json={
                "customer_id": "integration-start-fail-001",
                "destination_zone": "east",
                "line_items": [{"sku": "SKU-009", "quantity": 1, "unit_price": "10.00"}],
            },
        )

    assert response.status_code == 201

    with session_local() as db:
        order = db.query(Order).filter(Order.customer_id == "integration-start-fail-001").one()
        assert order.status == OrderStatus.failed

        events = db.query(WorkflowEvent).filter(WorkflowEvent.order_id == order.id).all()
        assert [event.event_type for event in events] == ["workflow_start_queued", "workflow_start_failed"]
