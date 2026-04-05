import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import OrderStatus, ShipmentStatus


class OrderItemCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=64)
    quantity: int = Field(gt=0, le=100)
    unit_price: Decimal = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=3, max_length=64)
    destination_zone: str = Field(min_length=2, max_length=32)
    line_items: list[OrderItemCreate] = Field(min_length=1, max_length=20)


class OrderItemRead(BaseModel):
    id: uuid.UUID
    sku: str
    quantity: int
    unit_price: Decimal

    model_config = {"from_attributes": True}


class OrderRead(BaseModel):
    id: uuid.UUID
    customer_id: str
    destination_zone: str
    status: OrderStatus
    total_cost: Decimal | None
    eta_days: int | None
    fallback_triggered: bool
    workflow_id: str | None
    fulfillment_plan: dict | None
    created_at: datetime
    updated_at: datetime | None
    items: list[OrderItemRead]

    model_config = {"from_attributes": True}


class ShipmentRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    warehouse_code: str
    tracking_id: str
    status: ShipmentStatus
    payload: dict | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class WorkflowEventRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    workflow_id: str
    event_type: str
    payload: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
