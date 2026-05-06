from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import strawberry
from fastapi import Depends
from strawberry.fastapi import BaseContext, GraphQLRouter

from app.cache import inventory_read_cache
from app.db import get_db
from app.models import Inventory, Reservation, Warehouse
from app.observability import INVENTORY_CACHE_REQUESTS_TOTAL
from sqlalchemy.orm import Session, selectinload


@strawberry.type
class GraphQLWarehouse:
    id: str
    code: str
    name: str
    supported_zones: list[str]
    shipping_cost_multiplier: str
    daily_capacity: int
    current_load: int
    active: bool
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def from_model(cls, warehouse: Warehouse) -> "GraphQLWarehouse":
        return cls(
            id=str(warehouse.id),
            code=warehouse.code,
            name=warehouse.name,
            supported_zones=warehouse.supported_zones,
            shipping_cost_multiplier=str(warehouse.shipping_cost_multiplier),
            daily_capacity=warehouse.daily_capacity,
            current_load=warehouse.current_load,
            active=warehouse.active,
            created_at=warehouse.created_at,
            updated_at=warehouse.updated_at,
        )


@strawberry.type
class GraphQLInventoryRecord:
    id: str
    warehouse_id: str
    warehouse_code: str | None
    sku: str
    available_qty: int
    reserved_qty: int
    updated_at: datetime

    @classmethod
    def from_model(cls, record: Inventory) -> "GraphQLInventoryRecord":
        return cls(
            id=str(record.id),
            warehouse_id=str(record.warehouse_id),
            warehouse_code=record.warehouse_code,
            sku=record.sku,
            available_qty=record.available_qty,
            reserved_qty=record.reserved_qty,
            updated_at=record.updated_at,
        )


@strawberry.type
class GraphQLReservation:
    id: str
    order_id: str
    warehouse_id: str
    sku: str
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def from_model(cls, reservation: Reservation) -> "GraphQLReservation":
        return cls(
            id=str(reservation.id),
            order_id=str(reservation.order_id),
            warehouse_id=str(reservation.warehouse_id),
            sku=reservation.sku,
            quantity=reservation.quantity,
            status=reservation.status.value,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
        )


@strawberry.type
class GraphQLHealth:
    status: str
    service: str


@dataclass
class GraphQLContext(BaseContext):
    db: Session


def get_graphql_context(db: Session = Depends(get_db)) -> GraphQLContext:
    return GraphQLContext(db=db)


def _inventory_by_sku(db: Session, sku: str) -> list[Inventory]:
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


def _inventory_list(db: Session, warehouse_code: str | None, limit: int) -> list[Inventory]:
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


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> GraphQLHealth:
        return GraphQLHealth(status="ok", service="inventory-service")

    @strawberry.field
    def warehouses(self, info: strawberry.Info[GraphQLContext]) -> list[GraphQLWarehouse]:
        warehouses = info.context.db.query(Warehouse).order_by(Warehouse.code.asc()).all()
        return [GraphQLWarehouse.from_model(warehouse) for warehouse in warehouses]

    @strawberry.field
    def inventory_by_sku(self, info: strawberry.Info[GraphQLContext], sku: str) -> list[GraphQLInventoryRecord]:
        return [GraphQLInventoryRecord.from_model(record) for record in _inventory_by_sku(info.context.db, sku)]

    @strawberry.field
    def inventory(
        self,
        info: strawberry.Info[GraphQLContext],
        warehouse_code: str | None = None,
        limit: int = 100,
    ) -> list[GraphQLInventoryRecord]:
        return [
            GraphQLInventoryRecord.from_model(record)
            for record in _inventory_list(info.context.db, warehouse_code, limit)
        ]

    @strawberry.field
    def reservations(self, info: strawberry.Info[GraphQLContext], order_id: str) -> list[GraphQLReservation]:
        reservations = (
            info.context.db.query(Reservation)
            .filter(Reservation.order_id == UUID(order_id))
            .order_by(Reservation.created_at.asc())
            .all()
        )
        return [GraphQLReservation.from_model(reservation) for reservation in reservations]


schema = strawberry.Schema(query=Query)
graphql_router = GraphQLRouter(schema, context_getter=get_graphql_context)
