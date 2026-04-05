from prometheus_client import Counter, Histogram, start_http_server

WORKFLOW_RESULTS_TOTAL = Counter(
    "workflow_worker_order_workflows_total",
    "Terminal order workflow outcomes handled by the worker.",
    ["outcome"],
)
WORKFLOW_DURATION_SECONDS = Histogram(
    "workflow_worker_order_workflow_duration_seconds",
    "Elapsed time between order creation and workflow completion/failure.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)
ACTIVITY_DURATION_SECONDS = Histogram(
    "workflow_worker_activity_duration_seconds",
    "Duration of workflow activities executed by the worker.",
    ["activity"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
SHIPMENT_RETRY_TOTAL = Counter(
    "workflow_worker_shipment_retry_total",
    "Retries triggered while creating downstream shipments.",
)
COMPENSATIONS_TOTAL = Counter(
    "workflow_worker_compensations_total",
    "Compensation actions triggered by the workflow worker.",
    ["type"],
)
SPLIT_ORDERS_TOTAL = Counter(
    "workflow_worker_split_orders_total",
    "Orders whose selected route was split across multiple warehouses.",
)
WORKFLOW_FALLBACK_TOTAL = Counter(
    "workflow_worker_fallback_total",
    "Orders that required a fallback route outside the preferred SLA posture.",
)
PAYMENT_FAILURE_TOTAL = Counter(
    "workflow_worker_payment_failures_total",
    "Simulated payment authorization failures.",
)
RESERVATION_FAILURE_TOTAL = Counter(
    "workflow_worker_reservation_failures_total",
    "Inventory reservation failures seen by the workflow worker.",
)

_metrics_server_started = False


def ensure_metrics_server(port: int) -> None:
    global _metrics_server_started
    if _metrics_server_started:
        return
    start_http_server(port)
    _metrics_server_started = True
