import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OrderStatus(str, enum.Enum):
    pending = "pending"
    routing = "routing"
    confirmed = "confirmed"
    failed = "failed"


class ShipmentStatus(str, enum.Enum):
    created = "created"
    failed = "failed"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    destination_zone: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.pending,
        nullable=False,
    )
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    eta_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_triggered: Mapped[bool] = mapped_column(default=False, nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fulfillment_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    workflow_events: Mapped[list["WorkflowEvent"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    warehouse_code: Mapped[str] = mapped_column(String(32), index=True)
    tracking_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, name="shipment_status"),
        default=ShipmentStatus.created,
        nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    order: Mapped[Order] = relationship(back_populates="shipments")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="workflow_events")
