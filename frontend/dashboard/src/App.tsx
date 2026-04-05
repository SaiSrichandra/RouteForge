import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";

import {
  fetchInventory,
  fetchInventoryHealth,
  fetchInventoryMetrics,
  fetchOrder,
  fetchOrderEvents,
  fetchOrderHealth,
  fetchOrderMetrics,
  fetchOrders,
  fetchOrderShipments,
  fetchRoutingHealth,
  fetchRoutingMetrics,
  fetchWarehouses,
} from "./api";
import type {
  CandidatePlan,
  Order,
  ServiceMetrics
} from "./types";

const temporalUiUrl =
  import.meta.env.VITE_TEMPORAL_UI_URL ??
  (window.location.port === "5173" ? "http://localhost:8088" : `${window.location.origin}/temporal/`);

const grafanaUrl =
  import.meta.env.VITE_GRAFANA_URL ??
  (window.location.port === "5173" ? "http://localhost:3001" : "#");

const prometheusUrl =
  import.meta.env.VITE_PROMETHEUS_URL ??
  (window.location.port === "5173" ? "http://localhost:9090" : "#");

function usePolling<T>(loader: () => Promise<T>, deps: unknown[] = [], intervalMs = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function run() {
      try {
        const next = await loader();
        if (!active) {
          return;
        }
        setData(next);
        setError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void run();
    const timer = window.setInterval(() => {
      void run();
    }, intervalMs);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error };
}

function formatCurrency(value: string | null) {
  if (!value) {
    return "Pending";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(value));
}

function formatTime(value: string | null) {
  if (!value) {
    return "N/A";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(status: string) {
  switch (status) {
    case "confirmed":
      return "status status-green";
    case "failed":
      return "status status-red";
    case "routing":
      return "status status-amber";
    default:
      return "status status-slate";
  }
}

function eventLabel(eventType: string) {
  return eventType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <p className="eyebrow">Distributed Fulfillment</p>
          <h1>Order Routing Console</h1>
          <p className="muted">
            Watch routing choices, workflow retries, and inventory changes in one place.
          </p>
        </div>

        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Orders
          </NavLink>
          <NavLink to="/inventory" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Inventory
          </NavLink>
          <NavLink to="/health" className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
            Health
          </NavLink>
        </nav>

        <div className="sidebar-card">
          <p className="sidebar-label">Live demo routes</p>
          <p className="sidebar-copy">Normal, rollback, and retry scenarios are all available from the API.</p>
          <a className="sidebar-link" href={temporalUiUrl} target="_blank" rel="noreferrer">
            Open Temporal UI
          </a>
          {grafanaUrl !== "#" ? (
            <a className="sidebar-link" href={grafanaUrl} target="_blank" rel="noreferrer">
              Open Grafana
            </a>
          ) : null}
        </div>

        <div className="sidebar-foot">
          <span>View</span>
          <strong>{location.pathname === "/" ? "orders" : location.pathname.replace("/", "")}</strong>
        </div>
      </aside>

      <main className="content">{children}</main>
    </div>
  );
}

function SummaryStrip({ orders }: { orders: Order[] }) {
  const stats = useMemo(() => {
    const confirmed = orders.filter((order) => order.status === "confirmed").length;
    const failed = orders.filter((order) => order.status === "failed").length;
    const split = orders.filter(
      (order) => (order.fulfillment_plan?.selected_plan.warehouses_used.length ?? 0) > 1,
    ).length;
    return { total: orders.length, confirmed, failed, split };
  }, [orders]);

  return (
    <section className="summary-strip">
      <MetricCard label="Recent Orders" value={String(stats.total)} note="Latest workflow-backed submissions" />
      <MetricCard label="Confirmed" value={String(stats.confirmed)} note="Successfully orchestrated" />
      <MetricCard label="Failed" value={String(stats.failed)} note="Useful for rollback demos" />
      <MetricCard label="Split Shipments" value={String(stats.split)} note="Orders using multiple warehouses" />
    </section>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="metric-card">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </div>
  );
}

function OrdersPage() {
  const { data: orders, loading, error } = usePolling(() => fetchOrders(30), [], 4000);

  if (loading) {
    return <PageState title="Loading orders" message="Pulling recent workflow-backed orders from the API." />;
  }

  if (error || !orders) {
    return <PageState title="Orders unavailable" message={error ?? "Order data could not be loaded."} />;
  }

  return (
    <>
      <HeaderBlock
        title="Orders"
        subtitle="Recent orders with routing cost, ETA, workflow status, and fulfillment plan selection."
      />
      <SummaryStrip orders={orders} />
      <section className="orders-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>Recent Orders</h2>
            <span>{orders.length} loaded</span>
          </div>

          <div className="order-list">
            {orders.map((order) => {
              const warehouseCount = order.fulfillment_plan?.selected_plan.warehouses_used.length ?? 0;
              return (
                <Link key={order.id} className="order-row" to={`/orders/${order.id}`}>
                  <div>
                    <div className="order-row-top">
                      <strong>{order.id.slice(0, 8)}</strong>
                      <span className={statusTone(order.status)}>{order.status}</span>
                    </div>
                    <p>{order.customer_id}</p>
                  </div>
                  <div className="order-row-metrics">
                    <span>{formatCurrency(order.total_cost)}</span>
                    <span>{warehouseCount || "?"} wh</span>
                    <span>{order.eta_days ? `${order.eta_days}d ETA` : "Calculating"}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        <div className="panel panel-hint">
          <h2>What recruiters should notice</h2>
          <p>
            Each order is more than a database row. The selected plan, workflow timeline, and shipment records all
            come from the orchestrated backend flow.
          </p>
          <ul className="flat-list">
            <li>Routing decisions remain explainable through stored candidate plans.</li>
            <li>Failures leave a visible audit trail instead of disappearing into logs.</li>
            <li>Retry and compensation behavior is demoable with deterministic scenarios.</li>
          </ul>
        </div>
      </section>
    </>
  );
}

function OrderDetailPage() {
  const { orderId } = useParams();
  const { data: order, loading: orderLoading, error: orderError } = usePolling(
    () => fetchOrder(orderId!),
    [orderId],
    3500,
  );
  const { data: events, loading: eventsLoading } = usePolling(() => fetchOrderEvents(orderId!), [orderId], 3500);
  const { data: shipments, loading: shipmentsLoading } = usePolling(
    () => fetchOrderShipments(orderId!),
    [orderId],
    3500,
  );

  if (!orderId) {
    return <PageState title="No order selected" message="Choose an order from the list to inspect its workflow." />;
  }

  if (orderLoading || !order) {
    return <PageState title="Loading order detail" message={orderError ?? "Fetching fulfillment details."} />;
  }

  const selectedPlan = order.fulfillment_plan?.selected_plan;
  const groupedAllocations = selectedPlan?.allocations.reduce<Record<string, CandidatePlan["allocations"]>>(
    (acc, allocation) => {
      const list = acc[allocation.code] ?? [];
      list.push(allocation);
      acc[allocation.code] = list;
      return acc;
    },
    {},
  );

  return (
    <>
      <HeaderBlock
        title={`Order ${order.id.slice(0, 8)}`}
        subtitle="Selected plan, candidate alternatives, workflow events, and shipment artifacts."
        action={
          <Link className="ghost-link" to="/">
            Back to Orders
          </Link>
        }
      />

      <section className="detail-hero">
        <div className="hero-card">
          <p className="eyebrow">Current Status</p>
          <div className="hero-inline">
            <span className={statusTone(order.status)}>{order.status}</span>
            <span>{formatCurrency(order.total_cost)}</span>
            <span>{order.eta_days ? `${order.eta_days} day ETA` : "Pending ETA"}</span>
          </div>
          <p className="muted">
            Destination zone: <strong>{order.destination_zone}</strong> · Workflow:{" "}
            <strong>{order.workflow_id ?? "pending"}</strong>
          </p>
        </div>

        <div className="hero-card">
          <p className="eyebrow">Order Payload</p>
          <div className="item-stack">
            {order.items.map((item) => (
              <div className="item-pill" key={item.id}>
                <strong>{item.sku}</strong>
                <span>{item.quantity} units</span>
                <span>{formatCurrency(item.unit_price)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="hero-card">
          <p className="eyebrow">Fulfillment Posture</p>
          <div className="hero-inline">
            <span>{selectedPlan?.warehouses_used.length ?? 0} warehouses</span>
            <span>{selectedPlan?.split_count ?? 0} splits</span>
            <span>{selectedPlan?.sla_met ? "SLA met" : "Fallback used"}</span>
          </div>
          <p className="muted">
            Alternative candidate plans are kept in the order payload to make tradeoffs explainable.
          </p>
        </div>
      </section>

      <section className="detail-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>Selected Fulfillment Plan</h2>
            <span>{selectedPlan ? `${selectedPlan.warehouses_used.join(", ")} chosen` : "Not ready"}</span>
          </div>
          {selectedPlan ? (
            <>
              <div className="plan-metrics">
                <MetricCard label="Shipping Cost" value={formatCurrency(selectedPlan.shipping_cost)} note="Base + multiplier" />
                <MetricCard label="Total Score" value={selectedPlan.total_score} note="Cost + split + load + delay" />
                <MetricCard label="Load Penalty" value={selectedPlan.load_penalty} note="Bias away from hot warehouses" />
              </div>
              <div className="allocation-grid">
                {Object.entries(groupedAllocations ?? {}).map(([code, allocations]) => (
                  <div className="allocation-card" key={code}>
                    <h3>{code}</h3>
                    {allocations.map((allocation) => (
                      <div className="allocation-row" key={`${allocation.code}-${allocation.sku}`}>
                        <span>{allocation.sku}</span>
                        <strong>{allocation.quantity}</strong>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="muted">The workflow has not produced a fulfillment plan yet.</p>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Workflow Timeline</h2>
            <span>{eventsLoading ? "Refreshing" : `${events?.length ?? 0} events`}</span>
          </div>
          <div className="timeline">
            {(events ?? []).map((event) => (
              <div className="timeline-row" key={event.id}>
                <div className="timeline-dot" />
                <div>
                  <div className="timeline-head">
                    <strong>{eventLabel(event.event_type)}</strong>
                    <span>{formatTime(event.created_at)}</span>
                  </div>
                  {event.payload && Object.keys(event.payload).length > 0 ? (
                    <pre className="payload-block">{JSON.stringify(event.payload, null, 2)}</pre>
                  ) : (
                    <p className="muted">No extra payload</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Shipments</h2>
            <span>{shipmentsLoading ? "Refreshing" : `${shipments?.length ?? 0} created`}</span>
          </div>
          {shipments && shipments.length > 0 ? (
            <div className="shipment-list">
              {shipments.map((shipment) => (
                <div className="shipment-card" key={shipment.id}>
                  <strong>{shipment.tracking_id}</strong>
                  <span>{shipment.warehouse_code}</span>
                  <span className={statusTone(shipment.status)}>{shipment.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No shipment record yet.</p>
          )}
        </div>
      </section>
    </>
  );
}

function InventoryPage() {
  const [warehouseFilter, setWarehouseFilter] = useState("ALL");
  const { data: warehouses, loading: warehousesLoading } = usePolling(() => fetchWarehouses(), [], 10000);
  const { data: inventory, loading: inventoryLoading, error } = usePolling(
    () => fetchInventory(180, warehouseFilter),
    [warehouseFilter],
    6000,
  );

  return (
    <>
      <HeaderBlock
        title="Inventory"
        subtitle="Per-warehouse stock levels and reservation pressure across the seeded catalog."
      />
      <section className="toolbar">
        <label>
          Warehouse
          <select value={warehouseFilter} onChange={(event) => setWarehouseFilter(event.target.value)}>
            <option value="ALL">All warehouses</option>
            {(warehouses ?? []).map((warehouse) => (
              <option key={warehouse.id} value={warehouse.code}>
                {warehouse.code} · {warehouse.name}
              </option>
            ))}
          </select>
        </label>
        <div className="toolbar-note">
          {warehousesLoading ? "Loading warehouses..." : `${warehouses?.length ?? 0} warehouse profiles loaded`}
        </div>
      </section>

      {inventoryLoading && !inventory ? (
        <PageState title="Loading inventory" message="Gathering stock positions from the inventory service." />
      ) : error || !inventory ? (
        <PageState title="Inventory unavailable" message={error ?? "Inventory data could not be loaded."} />
      ) : (
        <section className="panel">
          <div className="panel-head">
            <h2>Inventory Snapshot</h2>
            <span>{inventory.length} records</span>
          </div>
          <div className="inventory-table">
            <div className="table-head">
              <span>Warehouse</span>
              <span>SKU</span>
              <span>Available</span>
              <span>Reserved</span>
              <span>Updated</span>
            </div>
            {inventory.map((record) => (
              <div className="table-row" key={record.id}>
                <span>{record.warehouse_code ?? record.warehouse_id.slice(0, 8)}</span>
                <strong>{record.sku}</strong>
                <span>{record.available_qty}</span>
                <span>{record.reserved_qty}</span>
                <span>{formatTime(record.updated_at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function HealthPage() {
  const { data: orderMetrics } = usePolling(fetchOrderMetrics, [], 5000);
  const { data: inventoryMetrics } = usePolling(fetchInventoryMetrics, [], 5000);
  const { data: routingMetrics } = usePolling(fetchRoutingMetrics, [], 5000);
  const { data: orderHealth } = usePolling(fetchOrderHealth, [], 7000);
  const { data: inventoryHealth } = usePolling(fetchInventoryHealth, [], 7000);
  const { data: routingHealth } = usePolling(fetchRoutingHealth, [], 7000);

  return (
    <>
      <HeaderBlock
        title="System Health"
        subtitle="Service reachability, metrics snapshots, and observability links for the operational story."
      />
      <section className="health-grid">
        <HealthCard title="Order API" health={orderHealth} metrics={orderMetrics} />
        <HealthCard title="Inventory Service" health={inventoryHealth} metrics={inventoryMetrics} />
        <HealthCard title="Routing Engine" health={routingHealth} metrics={routingMetrics} />
        <div className="panel temporal-card">
          <div className="panel-head">
            <h2>Temporal</h2>
            <span className="status status-green">reachable</span>
          </div>
          <p className="muted">
            Use the Temporal UI to inspect durable workflow histories, retries, and task queues.
          </p>
          <a className="cta-link" href={temporalUiUrl} target="_blank" rel="noreferrer">
            Open Temporal UI
          </a>
        </div>
        <div className="panel temporal-card">
          <div className="panel-head">
            <h2>Prometheus & Grafana</h2>
            <span className="status status-green">ready</span>
          </div>
          <p className="muted">
            Prometheus scrapes every service and Grafana ships with a dashboard for order intake, retries, latency, and compensation.
          </p>
          {window.location.port === "5173" ? (
            <>
              <a className="cta-link" href={prometheusUrl} target="_blank" rel="noreferrer">
                Open Prometheus
              </a>
              <a className="cta-link" href={grafanaUrl} target="_blank" rel="noreferrer">
                Open Grafana
              </a>
            </>
          ) : (
            <p className="muted">Local observability links are available in the Docker development stack.</p>
          )}
        </div>
      </section>
    </>
  );
}

function HealthCard({
  title,
  health,
  metrics,
}: {
  title: string;
  health: ServiceMetrics | null;
  metrics: ServiceMetrics | null;
}) {
  const rows = Object.entries(metrics ?? {});
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        <span className={health?.status === "ok" ? "status status-green" : "status status-red"}>
          {String(health?.status ?? "unknown")}
        </span>
      </div>
      <div className="metric-list">
        {rows.map(([key, value]) => (
          <div className="metric-line" key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <strong>{String(value)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeaderBlock({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <section className="header-block">
      <div>
        <p className="eyebrow">Live Platform View</p>
        <h2>{title}</h2>
        <p className="muted">{subtitle}</p>
      </div>
      {action}
    </section>
  );
}

function PageState({ title, message }: { title: string; message: string }) {
  return (
    <div className="page-state">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
  );
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OrdersPage />} />
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </AppShell>
  );
}
