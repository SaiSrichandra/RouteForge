import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    supported_zones: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    shipping_cost_multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="warehouse")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        Index("ix_inventory_warehouse_sku", "warehouse_id", "sku"),
        UniqueConstraint("warehouse_id", "sku", name="uq_inventory_warehouse_sku"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    warehouse: Mapped[Warehouse] = relationship(back_populates="inventory_items")

    @property
    def warehouse_code(self) -> str | None:
        return self.warehouse.code if self.warehouse is not None else None


class ReservationStatus(str, enum.Enum):
    reserved = "reserved"
    released = "released"
    failed = "failed"


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (Index("ix_reservations_order_warehouse", "order_id", "warehouse_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"),
        default=ReservationStatus.reserved,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    warehouse: Mapped[Warehouse] = relationship()
