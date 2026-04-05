from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "routing_engine_http_requests_total",
    "Total HTTP requests handled by the Routing Engine.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "routing_engine_http_request_duration_seconds",
    "Latency of HTTP requests handled by the Routing Engine.",
    ["method", "path"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
ROUTING_REQUESTS_TOTAL = Counter(
    "routing_engine_route_requests_total",
    "Route computation requests grouped by outcome.",
    ["outcome"],
)
ROUTING_COMPUTATION_SECONDS = Histogram(
    "routing_engine_route_computation_seconds",
    "Time spent evaluating candidate fulfillment plans.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
ROUTING_CANDIDATE_PLAN_COUNT = Histogram(
    "routing_engine_candidate_plan_count",
    "Number of candidate plans produced for each routing request.",
    buckets=(1, 2, 3, 4, 5, 8, 12),
)
ROUTING_SPLIT_SELECTIONS_TOTAL = Counter(
    "routing_engine_split_selections_total",
    "Orders whose selected route uses more than one warehouse.",
)
ROUTING_FALLBACK_SELECTIONS_TOTAL = Counter(
    "routing_engine_fallback_selections_total",
    "Orders whose selected route violates the preferred SLA and uses fallback logic.",
)


def _request_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    return request.url.path


async def instrument_http(request: Request, call_next) -> Response:
    path = _request_path(request)
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=path,
        ).observe(perf_counter() - started_at)


def render_prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
