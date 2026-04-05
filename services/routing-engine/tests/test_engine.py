from decimal import Decimal

from app.engine import route_order
from app.schemas import LineItem, RouteOrderRequest, WarehouseInventory, WarehouseSnapshot


def build_request() -> RouteOrderRequest:
    return RouteOrderRequest(
        destination_zone="east",
        max_eta_days=3,
        line_items=[
            LineItem(sku="SKU-001", quantity=2, unit_price=Decimal("12.50")),
            LineItem(sku="SKU-002", quantity=1, unit_price=Decimal("20.00")),
        ],
        warehouses=[
            WarehouseSnapshot(
                warehouse_id="w-east",
                code="NJ",
                supported_zones=["east", "central"],
                shipping_cost_multiplier=Decimal("1.10"),
                daily_capacity=100,
                current_load=40,
                base_shipping_cost=Decimal("6.00"),
                eta_days=2,
                inventory=[
                    WarehouseInventory(sku="SKU-001", available_qty=5),
                    WarehouseInventory(sku="SKU-002", available_qty=3),
                ],
            ),
            WarehouseSnapshot(
                warehouse_id="w-central",
                code="TX",
                supported_zones=["east", "central", "south"],
                shipping_cost_multiplier=Decimal("0.95"),
                daily_capacity=100,
                current_load=95,
                base_shipping_cost=Decimal("5.00"),
                eta_days=3,
                inventory=[
                    WarehouseInventory(sku="SKU-001", available_qty=5),
                    WarehouseInventory(sku="SKU-002", available_qty=3),
                ],
            ),
        ],
    )


def test_prefers_single_warehouse_with_lower_total_score() -> None:
    selected, candidates = route_order(build_request())

    assert selected.warehouses_used == ["NJ"]
    assert len(candidates) == 2
    assert selected.sla_met is True


def test_splits_order_when_single_warehouse_cannot_cover_inventory() -> None:
    request = build_request()
    request.warehouses[0].inventory[0].available_qty = 1
    request.warehouses[1].inventory[1].available_qty = 0

    selected, _ = route_order(request)

    assert selected.warehouses_used == ["NJ", "TX"]
    assert selected.split_count == 1
    assert selected.sla_met is True


def test_prefers_lowest_score_fallback_when_no_sla_valid_plan_exists() -> None:
    request = build_request()
    request.warehouses[0].eta_days = 5
    request.warehouses[1].eta_days = 4
    request.warehouses[1].inventory[0].available_qty = 1

    selected, _ = route_order(request)

    assert selected.warehouses_used == ["NJ"]
    assert selected.sla_met is False


def test_raises_when_no_zone_support_exists() -> None:
    request = build_request()
    request.destination_zone = "west"

    try:
        route_order(request)
    except ValueError as exc:
        assert "No feasible route found" in str(exc)
    else:
        raise AssertionError("Expected route_order to raise ValueError")
