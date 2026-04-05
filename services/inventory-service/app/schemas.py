import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import ReservationStatus


class WarehouseRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    supported_zones: list[str]
    shipping_cost_multiplier: Decimal
    daily_capacity: int
    current_load: int
    active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class InventoryRead(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    warehouse_code: str | None = None
    sku: str
    available_qty: int
    reserved_qty: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReservationItemRequest(BaseModel):
    sku: str = Field(min_length=2, max_length=64)
    quantity: int = Field(gt=0, le=500)


class ReservationCreate(BaseModel):
    order_id: uuid.UUID
    warehouse_id: uuid.UUID
    items: list[ReservationItemRequest] = Field(min_length=1, max_length=20)


class ReservationRelease(BaseModel):
    order_id: uuid.UUID
    warehouse_id: uuid.UUID | None = None


class ReservationRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    warehouse_id: uuid.UUID
    sku: str
    quantity: int
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
