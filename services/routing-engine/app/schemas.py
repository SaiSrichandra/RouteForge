from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    sku: str = Field(min_length=2, max_length=64)
    quantity: int = Field(gt=0, le=100)
    unit_price: Decimal = Field(gt=0)


class WarehouseInventory(BaseModel):
    sku: str
    available_qty: int = Field(ge=0)


class WarehouseSnapshot(BaseModel):
    warehouse_id: str
    code: str
    supported_zones: list[str]
    shipping_cost_multiplier: Decimal = Field(gt=0)
    daily_capacity: int = Field(gt=0)
    current_load: int = Field(ge=0)
    base_shipping_cost: Decimal = Field(gt=0)
    eta_days: int = Field(gt=0)
    inventory: list[WarehouseInventory]


class RouteOrderRequest(BaseModel):
    destination_zone: str
    max_eta_days: int = Field(gt=0, le=14)
    line_items: list[LineItem] = Field(min_length=1, max_length=20)
    warehouses: list[WarehouseSnapshot] = Field(min_length=1)


class PlanAllocation(BaseModel):
    warehouse_id: str
    code: str
    sku: str
    quantity: int


class CandidatePlan(BaseModel):
    warehouses_used: list[str]
    allocations: list[PlanAllocation]
    shipping_cost: Decimal
    eta_days: int
    sla_met: bool
    split_count: int
    load_penalty: Decimal
    delay_penalty: Decimal
    total_score: Decimal


class RouteOrderResponse(BaseModel):
    selected_plan: CandidatePlan
    candidate_plans: list[CandidatePlan]
