from time import perf_counter

from fastapi import FastAPI, HTTPException

from app.engine import (
    DELAY_PENALTY_MULTIPLIER,
    HIGH_LOAD_PENALTY_MULTIPLIER,
    SPLIT_SHIPMENT_PENALTY,
    route_order,
)
from app.observability import (
    ROUTING_CANDIDATE_PLAN_COUNT,
    ROUTING_COMPUTATION_SECONDS,
    ROUTING_FALLBACK_SELECTIONS_TOTAL,
    ROUTING_REQUESTS_TOTAL,
    ROUTING_SPLIT_SELECTIONS_TOTAL,
    instrument_http,
    render_prometheus_metrics,
)
from app.schemas import RouteOrderRequest, RouteOrderResponse

app = FastAPI(
    title="Routing Engine",
    version="0.1.0",
    description="Warehouse routing heuristic for distributed fulfillment.",
)
app.middleware("http")(instrument_http)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "routing-engine"}


@app.post("/route-order", response_model=RouteOrderResponse)
def route_order_endpoint(payload: RouteOrderRequest) -> RouteOrderResponse:
    started_at = perf_counter()
    try:
        selected, candidates = route_order(payload)
    except ValueError as exc:
        ROUTING_REQUESTS_TOTAL.labels(outcome="error").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ROUTING_REQUESTS_TOTAL.labels(outcome="success").inc()
    ROUTING_COMPUTATION_SECONDS.observe(perf_counter() - started_at)
    ROUTING_CANDIDATE_PLAN_COUNT.observe(len(candidates))
    if len(selected.warehouses_used) > 1:
        ROUTING_SPLIT_SELECTIONS_TOTAL.inc()
    if not selected.sla_met:
        ROUTING_FALLBACK_SELECTIONS_TOTAL.inc()
    return RouteOrderResponse(selected_plan=selected, candidate_plans=candidates)


@app.get("/metrics")
def metrics() -> dict[str, object]:
    return {
        "service": "routing-engine",
        "split_penalty": str(SPLIT_SHIPMENT_PENALTY),
        "high_load_penalty_multiplier": str(HIGH_LOAD_PENALTY_MULTIPLIER),
        "delay_penalty_multiplier": str(DELAY_PENALTY_MULTIPLIER),
    }


@app.get("/prometheus")
def prometheus_metrics():
    return render_prometheus_metrics()
