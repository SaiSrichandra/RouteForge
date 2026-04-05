# Testing and Performance Guide

This guide covers four validation layers in the project:

- routing heuristic unit tests
- API and database integration tests
- workflow tests for Temporal orchestration logic
- a lightweight performance story with one read-cache optimization and a load-test script

## Automated test layers

### 1. Routing heuristic unit tests

These tests already exist in [test_engine.py](../services/routing-engine/tests/test_engine.py).

They prove:

- a valid single-warehouse plan beats a more expensive option
- the engine splits an order when inventory forces it
- fallback still returns the lowest-score route when SLA cannot be met
- infeasible orders raise a clear error

### 2. API and database integration tests

New integration coverage lives in:

- [order-api tests](../services/order-api/tests/test_api.py)
- [inventory-service tests](../services/inventory-service/tests/test_api.py)

These tests use FastAPI `TestClient` plus a temporary SQLite database to validate:

- order creation writes orders, items, and workflow events
- workflow start failure marks the order as failed
- inventory reads return persisted rows
- reservation creation and release update inventory and reservation tables correctly
- inventory cache invalidation keeps reads correct after writes

### 3. Workflow tests

Workflow coverage lives in:

- [workflow tests](../services/workflow-worker/tests/test_workflows.py)
- [activity retry test](../services/workflow-worker/tests/test_activities.py)
- [real Temporal environment test](../services/workflow-worker/tests/test_temporal_environment.py)

These tests validate:

- the happy-path activity sequence
- compensation flow when a downstream step fails after reservations are created
- retry policy configuration for shipment creation
- the simulated shipment-delay behavior that triggers retries
- real retry behavior inside Temporal's time-skipping test environment

## CI coverage

GitHub Actions runs all test layers in [ci.yml](../.github/workflows/ci.yml):

- routing-engine unit tests
- order-api integration tests
- inventory-service integration tests
- workflow-worker tests
- inventory cache benchmark with uploaded artifact and job summary output

## Load test

A lightweight k6 script lives in [order-submissions.js](../load-tests/order-submissions.js).

It ramps to 50 virtual users and then 100 virtual users while posting orders to the Order API.

Run it against local Order API:

```powershell
k6 run load-tests/order-submissions.js
```

Run it against the AWS dashboard proxy:

```powershell
$env:BASE_URL = "http://<dashboard-hostname>/api/order"
k6 run load-tests/order-submissions.js
```

Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_k6_aws.ps1
```

## Small optimization: inventory read cache

To create a measurable performance story, the Inventory service now includes a tiny in-process TTL cache for:

- `GET /inventory/{sku}`
- `GET /inventory`

The cache is invalidated after reservation writes and releases, so correctness is preserved while hot inventory reads get faster.

Relevant files:

- [cache.py](../services/inventory-service/app/cache.py)
- [main.py](../services/inventory-service/app/main.py)
- [observability.py](../services/inventory-service/app/observability.py)

## Benchmark

The benchmark script lives in [benchmark_inventory_cache.py](../scripts/benchmark_inventory_cache.py).

Run it with:

```powershell
python scripts/benchmark_inventory_cache.py
```

It benchmarks repeated `GET /inventory/SKU-HOT` requests before and after the cache is enabled using the same seeded dataset.

The current benchmark result from a clean Docker Python environment was:

- without cache: mean `15.68ms`, p50 `14.43ms`, p95 `18.73ms`
- with cache: mean `7.20ms`, p50 `6.84ms`, p95 `9.10ms`
- improvement: mean `54.1%`, p95 `51.4%`
