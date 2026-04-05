from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import select

from app.cache import inventory_read_cache
from app.db import Base, engine, get_db
from app.models import Inventory, Reservation, ReservationStatus, Warehouse
from app.observability import (
    INVENTORY_CACHE_REQUESTS_TOTAL,
    RESERVATION_FAILURES_TOTAL,
    RESERVATION_REQUESTS_TOTAL,
    instrument_http,
    render_prometheus_metrics,
)
from app.schemas import (
    InventoryRead,
    ReservationCreate,
    ReservationRead,
    ReservationRelease,
    WarehouseRead,
)

app = FastAPI(
    title="Inventory Service",
    version="0.1.0",
    description="Warehouse metadata and inventory lookup service.",
)
app.middleware("http")(instrument_http)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "inventory-service"}


@app.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses(db: Session = Depends(get_db)) -> list[Warehouse]:
    return db.query(Warehouse).order_by(Warehouse.code.asc()).all()


@app.get("/inventory/{sku}", response_model=list[InventoryRead])
def inventory_by_sku(sku: str, db: Session = Depends(get_db)) -> list[Inventory]:
    cache_key = sku.upper()
    cached = inventory_read_cache.get("inventory_by_sku", cache_key)
    if cached is not None:
        INVENTORY_CACHE_REQUESTS_TOTAL.labels(endpoint="inventory_by_sku", outcome="hit").inc()
        return cached

    INVENTORY_CACHE_REQUESTS_TOTAL.labels(endpoint="inventory_by_sku", outcome="miss").inc()
    records = (
        db.query(Inventory)
        .options(selectinload(Inventory.warehouse))
        .filter(Inventory.sku == sku)
        .order_by(Inventory.available_qty.desc())
        .all()
    )
    return inventory_read_cache.set("inventory_by_sku", cache_key, records)


@app.get("/inventory", response_model=list[InventoryRead])
def list_inventory(
    warehouse_code: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Inventory]:
    normalized_code = warehouse_code.upper() if warehouse_code else ""
    effective_limit = min(max(limit, 1), 500)
    cache_key = f"{normalized_code}:{effective_limit}"
    cached = inventory_read_cache.get("list_inventory", cache_key)
    if cached is not None:
        INVENTORY_CACHE_REQUESTS_TOTAL.labels(endpoint="list_inventory", outcome="hit").inc()
        return cached

    INVENTORY_CACHE_REQUESTS_TOTAL.labels(endpoint="list_inventory", outcome="miss").inc()
    query = db.query(Inventory).options(selectinload(Inventory.warehouse)).join(Warehouse)
    if warehouse_code:
        query = query.filter(Warehouse.code == normalized_code)
    records = query.order_by(Inventory.available_qty.desc()).limit(effective_limit).all()
    return inventory_read_cache.set("list_inventory", cache_key, records)


@app.post("/reservations", response_model=list[ReservationRead], status_code=201)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)) -> list[Reservation]:
    created_reservations: list[Reservation] = []

    try:
        for item in payload.items:
            inventory = (
                db.execute(
                    select(Inventory)
                    .where(
                        Inventory.warehouse_id == payload.warehouse_id,
                        Inventory.sku == item.sku,
                    )
                    .with_for_update()
                )
                .scalar_one_or_none()
            )

            if inventory is None:
                RESERVATION_REQUESTS_TOTAL.labels(operation="reserve", outcome="error").inc()
                RESERVATION_FAILURES_TOTAL.labels(operation="reserve", reason="inventory_missing").inc()
                raise HTTPException(status_code=404, detail=f"Inventory record not found for SKU {item.sku}")

            if inventory.available_qty < item.quantity:
                RESERVATION_REQUESTS_TOTAL.labels(operation="reserve", outcome="error").inc()
                RESERVATION_FAILURES_TOTAL.labels(operation="reserve", reason="insufficient_stock").inc()
                raise HTTPException(status_code=409, detail=f"Insufficient stock for SKU {item.sku}")

            inventory.available_qty -= item.quantity
            inventory.reserved_qty += item.quantity

            reservation = Reservation(
                order_id=payload.order_id,
                warehouse_id=payload.warehouse_id,
                sku=item.sku,
                quantity=item.quantity,
                status=ReservationStatus.reserved,
            )
            db.add(reservation)
            created_reservations.append(reservation)

        db.commit()
        RESERVATION_REQUESTS_TOTAL.labels(operation="reserve", outcome="success").inc()
        inventory_read_cache.clear()
    except HTTPException:
        db.rollback()
        raise

    for reservation in created_reservations:
        db.refresh(reservation)

    return created_reservations


@app.post("/reservations/release", response_model=list[ReservationRead])
def release_reservation(payload: ReservationRelease, db: Session = Depends(get_db)) -> list[Reservation]:
    query = db.query(Reservation).filter(
        Reservation.order_id == payload.order_id,
        Reservation.status == ReservationStatus.reserved,
    )
    if payload.warehouse_id is not None:
        query = query.filter(Reservation.warehouse_id == payload.warehouse_id)

    reservations = query.all()
    if not reservations:
        RESERVATION_REQUESTS_TOTAL.labels(operation="release", outcome="error").inc()
        RESERVATION_FAILURES_TOTAL.labels(operation="release", reason="not_found").inc()
        raise HTTPException(status_code=404, detail="No active reservations found")

    for reservation in reservations:
        inventory = (
            db.execute(
                select(Inventory)
                .where(
                    Inventory.warehouse_id == reservation.warehouse_id,
                    Inventory.sku == reservation.sku,
                )
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if inventory is None:
            db.rollback()
            RESERVATION_REQUESTS_TOTAL.labels(operation="release", outcome="error").inc()
            RESERVATION_FAILURES_TOTAL.labels(operation="release", reason="inventory_missing").inc()
            raise HTTPException(status_code=404, detail=f"Inventory record not found for SKU {reservation.sku}")

        inventory.available_qty += reservation.quantity
        inventory.reserved_qty = max(inventory.reserved_qty - reservation.quantity, 0)
        reservation.status = ReservationStatus.released

    db.commit()
    RESERVATION_REQUESTS_TOTAL.labels(operation="release", outcome="success").inc()
    inventory_read_cache.clear()

    for reservation in reservations:
        db.refresh(reservation)

    return reservations


@app.get("/reservations/{order_id}", response_model=list[ReservationRead])
def list_reservations(order_id: UUID, db: Session = Depends(get_db)) -> list[Reservation]:
    return db.query(Reservation).filter(Reservation.order_id == order_id).all()


@app.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, object]:
    return {
        "service": "inventory-service",
        "warehouse_count": db.query(func.count(Warehouse.id)).scalar() or 0,
        "inventory_records": db.query(func.count(Inventory.id)).scalar() or 0,
        "low_stock_records": db.query(func.count(Inventory.id)).filter(Inventory.available_qty < 10).scalar() or 0,
        "active_reservations": db.query(func.count(Reservation.id)).filter(Reservation.status == ReservationStatus.reserved).scalar() or 0,
    }


@app.get("/prometheus")
def prometheus_metrics(db: Session = Depends(get_db)):
    return render_prometheus_metrics(db)
