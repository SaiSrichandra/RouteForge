from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Inventory, Reservation, ReservationStatus, Warehouse

HTTP_REQUESTS_TOTAL = Counter(
    "inventory_service_http_requests_total",
    "Total HTTP requests handled by the Inventory service.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "inventory_service_http_request_duration_seconds",
    "Latency of HTTP requests handled by the Inventory service.",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
RESERVATION_REQUESTS_TOTAL = Counter(
    "inventory_service_reservation_requests_total",
    "Reservation operations handled by the Inventory service.",
    ["operation", "outcome"],
)
RESERVATION_FAILURES_TOTAL = Counter(
    "inventory_service_reservation_failures_total",
    "Reservation operation failures grouped by reason.",
    ["operation", "reason"],
)
INVENTORY_CACHE_REQUESTS_TOTAL = Counter(
    "inventory_service_inventory_cache_requests_total",
    "Inventory read cache lookups by endpoint and outcome.",
    ["endpoint", "outcome"],
)
WAREHOUSE_COUNT = Gauge(
    "inventory_service_warehouse_count",
    "Configured warehouse count.",
)
INVENTORY_RECORD_COUNT = Gauge(
    "inventory_service_inventory_records",
    "Inventory rows stored in PostgreSQL.",
)
LOW_STOCK_RECORD_COUNT = Gauge(
    "inventory_service_low_stock_records",
    "Inventory rows with available quantity below 10.",
)
ACTIVE_RESERVATION_COUNT = Gauge(
    "inventory_service_active_reservations",
    "Reservations currently holding stock.",
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
    WAREHOUSE_COUNT.set(db.query(func.count(Warehouse.id)).scalar() or 0)
    INVENTORY_RECORD_COUNT.set(db.query(func.count(Inventory.id)).scalar() or 0)
    LOW_STOCK_RECORD_COUNT.set(
        db.query(func.count(Inventory.id)).filter(Inventory.available_qty < 10).scalar() or 0
    )
    ACTIVE_RESERVATION_COUNT.set(
        db.query(func.count(Reservation.id)).filter(Reservation.status == ReservationStatus.reserved).scalar() or 0
    )


def render_prometheus_metrics(db: Session) -> Response:
    update_db_metrics(db)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
