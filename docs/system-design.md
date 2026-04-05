# System Design

## Problem statement

Build a cloud-native order fulfillment platform that decides where and how to fulfill a customer order across multiple warehouses while balancing cost, speed, and operational constraints.

## Core business rules

The platform evaluates each order against these rules:

1. Prefer a single warehouse if it can fulfill the entire order within SLA.
2. If a split is required, minimize the number of warehouses.
3. Among valid plans, choose the lowest total score.
4. Penalize plans that use highly loaded warehouses.
5. Reject or flag plans that violate delivery SLA.
6. Trigger fallback and compensation logic when downstream steps fail.

## Warehouses

We model three warehouses because that is enough to create non-trivial routing behavior without turning the search space into a research project.

| Warehouse | Strength | Weakness | Typical zones |
| --- | --- | --- | --- |
| New Jersey | fast East Coast delivery | costlier to West Coast | east, northeast |
| Dallas | balanced central location | average for all zones | central, south, east |
| Reno | fast West Coast delivery | lower capacity | west, southwest |

## Service responsibilities

### Order API

- validates external order requests
- persists orders and line items
- creates correlation IDs and workflow IDs
- starts Temporal workflows
- exposes order status for the UI

### Inventory Service

- owns warehouse and inventory data
- supports snapshot reads
- performs stock reservations and releases
- tracks reservation state for workflow compensation

### Routing Engine

- accepts an order plus inventory/warehouse snapshot
- builds candidate fulfillment plans
- scores candidates
- returns the best plan with alternatives for observability

### Workflow Worker

- runs the fulfillment workflow in Temporal
- coordinates activity retries and compensation
- writes workflow events for auditability

### Dashboard

- shows order lifecycle and routing decisions
- makes the system demoable and debuggable

## Routing strategy

The routing engine is intentionally explainable instead of mathematically perfect.

### Rule-based heuristic

1. Filter warehouses that serve the destination zone.
2. Check whether any one warehouse can fulfill the whole order within SLA.
3. If not, try the minimum number of warehouses needed.
4. Build a plan that minimizes splits per SKU.
5. Choose the valid plan with the lowest base cost.

### Weighted scoring

Each candidate gets a score:

```text
score = shipping_cost
      + penalty_for_split
      + penalty_for_delay
      + penalty_for_high_load
```

This keeps the routing behavior explainable while still improving decision quality. Each term can be tuned and validated independently.

## Data model

Main tables:

- `orders`
- `order_items`
- `warehouses`
- `inventory`
- `reservations`
- `shipments`
- `workflow_events`

Important decisions:

- `inventory` gets a composite index on `(warehouse_id, sku)`
- order and reservation statuses use enums
- timestamps are stored on all major records
- warehouse load is explicit so the routing engine can penalize overload risk

## Workflow design

The fulfillment workflow follows this high-level sequence:

1. Validate order
2. Fetch inventory snapshot
3. Compute routing plan
4. Reserve inventory
5. Simulate payment authorization
6. Simulate shipment creation
7. Confirm order

Failure behavior:

- if reservation fails midway, release previously reserved stock
- if payment fails, release all reservations
- if shipment creation is transiently delayed, retry with backoff

## Why Temporal instead of custom retry logic

Temporal is a strong fit because this process is:

- long running
- stateful
- failure-prone
- distributed across services

Temporal gives us:

- durable workflow state
- activity retries with policy control
- compensation patterns
- event history for debugging
- easier recovery after worker crashes or restarts

## Performance focus

Critical path operations:

- inventory reads
- reservation writes
- routing computation

Optimization priorities:

1. add the right database indexes
2. keep inventory queries narrow
3. make routing logic deterministic and testable
4. consider Redis caching for hot inventory reads

