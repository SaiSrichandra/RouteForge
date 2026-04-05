from decimal import Decimal
from itertools import combinations

from app.schemas import CandidatePlan, LineItem, PlanAllocation, RouteOrderRequest, WarehouseSnapshot

SPLIT_SHIPMENT_PENALTY = Decimal("8.00")
HIGH_LOAD_PENALTY_MULTIPLIER = Decimal("20.00")
DELAY_PENALTY_MULTIPLIER = Decimal("50.00")


def route_order(request: RouteOrderRequest) -> tuple[CandidatePlan, list[CandidatePlan]]:
    valid_plans: list[CandidatePlan] = []
    fallback_plans: list[CandidatePlan] = []
    eligible = [warehouse for warehouse in request.warehouses if request.destination_zone in warehouse.supported_zones]

    for warehouse_count in range(1, len(eligible) + 1):
        for subset in combinations(eligible, warehouse_count):
            plan = build_candidate(list(subset), request.line_items, request.max_eta_days)
            if plan is not None:
                if plan.sla_met:
                    valid_plans.append(plan)
                else:
                    fallback_plans.append(plan)

        if valid_plans:
            break

    candidate_plans = valid_plans if valid_plans else fallback_plans
    if not candidate_plans:
        raise ValueError("No feasible route found for this order")

    scored = sorted(candidate_plans, key=lambda plan: (plan.total_score, plan.shipping_cost, plan.eta_days))
    return scored[0], scored


def build_candidate(
    warehouses: list[WarehouseSnapshot],
    line_items: list[LineItem],
    max_eta_days: int,
) -> CandidatePlan | None:
    allocations: list[PlanAllocation] = []
    inventory_maps = {
        warehouse.warehouse_id: {inventory.sku: inventory.available_qty for inventory in warehouse.inventory}
        for warehouse in warehouses
    }

    ordered_warehouses = sorted(
        warehouses,
        key=lambda warehouse: (
            warehouse.current_load / warehouse.daily_capacity,
            warehouse.shipping_cost_multiplier,
            warehouse.base_shipping_cost,
        ),
    )

    for item in line_items:
        remaining = item.quantity
        used_codes_for_item: set[str] = set()

        item_candidates = sorted(
            ordered_warehouses,
            key=lambda warehouse: (
                0 if inventory_maps[warehouse.warehouse_id].get(item.sku, 0) >= remaining else 1,
                warehouse.current_load / warehouse.daily_capacity,
                warehouse.shipping_cost_multiplier,
            ),
        )

        for warehouse in item_candidates:
            available = inventory_maps[warehouse.warehouse_id].get(item.sku, 0)
            if available <= 0 or remaining <= 0:
                continue

            assigned = min(available, remaining)
            inventory_maps[warehouse.warehouse_id][item.sku] -= assigned
            remaining -= assigned
            used_codes_for_item.add(warehouse.code)
            allocations.append(
                PlanAllocation(
                    warehouse_id=warehouse.warehouse_id,
                    code=warehouse.code,
                    sku=item.sku,
                    quantity=assigned,
                )
            )

        if remaining > 0:
            return None

        if len(used_codes_for_item) > 2:
            return None

    warehouses_used = sorted({allocation.code for allocation in allocations})
    if not warehouses_used:
        return None

    warehouse_lookup = {warehouse.code: warehouse for warehouse in warehouses}
    shipping_cost = sum(
        (
            warehouse_lookup[code].base_shipping_cost * warehouse_lookup[code].shipping_cost_multiplier
            for code in warehouses_used
        ),
        Decimal("0.00"),
    )
    max_eta = max(warehouse_lookup[code].eta_days for code in warehouses_used)
    sla_met = max_eta <= max_eta_days
    split_count = max(len(warehouses_used) - 1, 0)
    load_penalty = sum(
        (
            Decimal(str(warehouse_lookup[code].current_load / warehouse_lookup[code].daily_capacity))
            * HIGH_LOAD_PENALTY_MULTIPLIER
            for code in warehouses_used
        ),
        Decimal("0.00"),
    )
    delay_penalty = (
        Decimal(max(0, max_eta - max_eta_days)) * DELAY_PENALTY_MULTIPLIER
        if not sla_met
        else Decimal("0.00")
    )
    total_score = shipping_cost + (Decimal(split_count) * SPLIT_SHIPMENT_PENALTY) + load_penalty + delay_penalty

    return CandidatePlan(
        warehouses_used=warehouses_used,
        allocations=allocations,
        shipping_cost=shipping_cost.quantize(Decimal("0.01")),
        eta_days=max_eta,
        sla_met=sla_met,
        split_count=split_count,
        load_penalty=load_penalty.quantize(Decimal("0.01")),
        delay_penalty=delay_penalty.quantize(Decimal("0.01")),
        total_score=total_score.quantize(Decimal("0.01")),
    )
