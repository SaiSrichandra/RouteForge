from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, WorkflowEvent

HTTP_REQUESTS_TOTAL = Counter(
    "order_api_http_requests_total",
    "Total HTTP requests handled by the Order API.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "order_api_http_request_duration_seconds",
    "Latency of HTTP requests handled by the Order API.",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
ORDERS_CREATED_TOTAL = Counter(
    "order_api_orders_created_total",
    "Orders accepted by the Order API.",
)
WORKFLOW_START_FAILURES_TOTAL = Counter(
    "order_api_workflow_start_failures_total",
    "Orders persisted successfully but failed to start a Temporal workflow.",
)
ORDERS_BY_STATUS = Gauge(
    "order_api_orders_by_status",
    "Current number of orders by status.",
    ["status"],
)
WORKFLOW_EVENTS_STORED = Gauge(
    "order_api_workflow_events_stored",
    "Current number of workflow events stored in PostgreSQL.",
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


def update_db_metrics(db: Session) -> None:
    for status in OrderStatus:
        ORDERS_BY_STATUS.labels(status=status.value).set(
            db.query(func.count(Order.id)).filter(Order.status == status).scalar() or 0
        )
    WORKFLOW_EVENTS_STORED.set(db.query(func.count(WorkflowEvent.id)).scalar() or 0)


def render_prometheus_metrics(db: Session) -> Response:
    update_db_metrics(db)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
