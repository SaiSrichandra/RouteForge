import uuid
from collections.abc import Generator
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.cache import inventory_read_cache
from app.models import Inventory, Reservation, ReservationStatus, Warehouse


def create_client(tmp_path, monkeypatch) -> tuple[TestClient, sessionmaker[Session]]:
    database_path = tmp_path / "inventory-service-test.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(main, "engine", engine)
    main.Base.metadata.drop_all(bind=engine)
    main.Base.metadata.create_all(bind=engine)
    inventory_read_cache.clear()

    def override_get_db() -> Generator[Session, None, None]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    return TestClient(main.app), session_local


def seed_inventory(session_local: sessionmaker[Session]) -> tuple[str, str]:
    with session_local() as db:
        warehouse_nj = Warehouse(
            code="NJ",
            name="New Jersey",
            supported_zones=["east", "central"],
            shipping_cost_multiplier=Decimal("1.10"),
            daily_capacity=100,
            current_load=20,
            active=True,
        )
        warehouse_tx = Warehouse(
            code="TX",
            name="Texas",
            supported_zones=["east", "central", "south"],
            shipping_cost_multiplier=Decimal("0.95"),
            daily_capacity=100,
            current_load=30,
            active=True,
        )
        db.add_all([warehouse_nj, warehouse_tx])
        db.flush()

        db.add_all(
            [
                Inventory(warehouse_id=warehouse_nj.id, sku="SKU-001", available_qty=10, reserved_qty=0),
                Inventory(warehouse_id=warehouse_tx.id, sku="SKU-001", available_qty=6, reserved_qty=0),
                Inventory(warehouse_id=warehouse_tx.id, sku="SKU-777", available_qty=2, reserved_qty=0),
            ]
        )
        db.commit()
        return str(warehouse_nj.id), str(warehouse_tx.id)


def test_list_inventory_filters_and_reads_database_rows(tmp_path, monkeypatch) -> None:
    client, session_local = create_client(tmp_path, monkeypatch)
    seed_inventory(session_local)

    with client:
        response = client.get("/inventory", params={"warehouse_code": "tx"})

    assert response.status_code == 200
    payload = response.json()
    assert {row["warehouse_code"] for row in payload} == {"TX"}
    assert len(payload) == 2


def test_reservation_and_release_write_rows_and_invalidate_cache(tmp_path, monkeypatch) -> None:
    client, session_local = create_client(tmp_path, monkeypatch)
    warehouse_id, _ = seed_inventory(session_local)
    order_id = str(uuid.uuid4())

    with client:
        first_read = client.get("/inventory/SKU-001")
        assert first_read.status_code == 200
        assert first_read.json()[0]["available_qty"] == 10

        reserve_response = client.post(
            "/reservations",
            json={
                "order_id": order_id,
                "warehouse_id": warehouse_id,
                "items": [{"sku": "SKU-001", "quantity": 3}],
            },
        )
        assert reserve_response.status_code == 201

        second_read = client.get("/inventory/SKU-001")
        assert second_read.status_code == 200
        assert second_read.json()[0]["available_qty"] == 7

        release_response = client.post("/reservations/release", json={"order_id": order_id})
        assert release_response.status_code == 200

        third_read = client.get("/inventory/SKU-001")
        assert third_read.status_code == 200
        assert third_read.json()[0]["available_qty"] == 10

    with session_local() as db:
        reservation = db.query(Reservation).filter(Reservation.order_id == uuid.UUID(order_id)).one()
        assert reservation.status == ReservationStatus.released

        inventory_row = (
            db.query(Inventory)
            .filter(Inventory.warehouse_id == uuid.UUID(warehouse_id), Inventory.sku == "SKU-001")
            .one()
        )
        assert inventory_row.available_qty == 10
        assert inventory_row.reserved_qty == 0


def test_reservation_returns_conflict_on_insufficient_stock(tmp_path, monkeypatch) -> None:
    client, session_local = create_client(tmp_path, monkeypatch)
    warehouse_id, _ = seed_inventory(session_local)

    with client:
        response = client.post(
            "/reservations",
            json={
                "order_id": str(uuid.uuid4()),
                "warehouse_id": warehouse_id,
                "items": [{"sku": "SKU-001", "quantity": 99}],
            },
        )

    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]
