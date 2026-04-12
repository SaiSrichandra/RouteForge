import { useEffect, useRef, useState } from "react";
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
import type { CandidatePlan, Order, ServiceMetrics, Warehouse } from "./types";

function usePolling<T>(loader: () => Promise<T>, deps: readonly unknown[] = [], intervalMs = 5000) {
  const loaderRef = useRef(loader);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  loaderRef.current = loader;

  useEffect(() => {
    let active = true;

    async function run() {
      try {
        const next = await loaderRef.current();
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
  }, [intervalMs, ...deps]);

  return { data, loading, error };
}

function formatCurrency(value: string | null) {
  if (!value) {
    return "Pending";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
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

function eventLabel(eventType: string) {
  return eventType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function titleCase(value: string) {
  return value
    .replaceAll("_", " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusTone(status: string) {
  switch (status) {
    case "confirmed":
      return "status status-success";
    case "failed":
      return "status status-danger";
    case "routing":
      return "status status-warning";
    default:
      return "status status-neutral";
  }
}

function compactId(value: string | null) {
  if (!value) {
    return "Pending";
  }
  return value.length <= 14 ? value : `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function candidateWarehouseLabel(plan: CandidatePlan | undefined) {
  if (!plan) {
    return "Awaiting plan";
  }

  return plan.warehouses_used.length === 1 ? plan.warehouses_used[0] : `${plan.warehouses_used.length} warehouses`;
}

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const currentView = location.pathname === "/" ? "Orders" : titleCase(location.pathname.slice(1));

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">RF</div>
          <div>
            <p className="kicker">RouteForge</p>
            <h1>Operations Console</h1>
          </div>
        </div>

        <nav className="topnav" aria-label="Primary">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "topnav-link active" : "topnav-link")}>
            Orders
          </NavLink>
          <NavLink to="/inventory" className={({ isActive }) => (isActive ? "topnav-link active" : "topnav-link")}>
            Inventory
          </NavLink>
          <NavLink to="/health" className={({ isActive }) => (isActive ? "topnav-link active" : "topnav-link")}>
            Services
          </NavLink>
        </nav>
      </header>

      <main className="workspace">
        <section className="hero-banner">
          <div>
            <p className="hero-label">Live View</p>
            <h2>{currentView}</h2>
            <p className="hero-copy">Live visibility into submitted orders, inventory position, and core service health.</p>
          </div>
          <div className="hero-pill">
            <span className="hero-pill-dot" />
            Auto-refreshing order operations
          </div>
        </section>

        {children}
      </main>
    </div>
  );
}

function PageIntro({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <section className="page-intro">
      <div>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
      {action}
    </section>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <section className="empty-state">
      <h3>{title}</h3>
      <p>{message}</p>
    </section>
  );
}

function StatCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  );
}

function SectionCard({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="section-card">
      <div className="section-head">
        <div>
          <h4>{title}</h4>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function OrdersOverview({ orders }: { orders: Order[] }) {
  const confirmed = orders.filter((order) => order.status === "confirmed").length;
  const failed = orders.filter((order) => order.status === "failed").length;
  const inFlight = orders.filter((order) => order.status === "pending" || order.status === "routing").length;
  const splitPlans = orders.filter(
    (order) => (order.fulfillment_plan?.selected_plan.warehouses_used.length ?? 0) > 1,
  ).length;

  return (
    <section className="stats-grid">
      <StatCard label="Orders In View" value={String(orders.length)} note="Most recent workflow-backed submissions" />
      <StatCard label="Confirmed" value={String(confirmed)} note="Orders completed without compensation" />
      <StatCard label="Needs Attention" value={String(failed)} note="Failed workflows or payment rollbacks" />
      <StatCard label="Split Plans" value={String(splitPlans)} note="Orders routed across multiple warehouses" />
      <StatCard label="In Flight" value={String(inFlight)} note="Orders still awaiting final workflow outcome" />
    </section>
  );
}

function OrdersPage() {
  const { data: orders, loading, error } = usePolling(() => fetchOrders(30), [], 4000);

  if (loading) {
    return <EmptyState title="Loading orders" message="Fetching the latest workflow-backed order activity." />;
  }

  if (!orders || error) {
    return <EmptyState title="Orders unavailable" message={error ?? "Order data could not be loaded."} />;
  }

  const failedOrders = orders.filter((order) => order.status === "failed").slice(0, 5);
  const newestOrder = orders[0];

  return (
    <>
      <PageIntro
        title="Order Flow"
        subtitle="Track order state, routing choices, and shipment creation from one operational surface."
      />

      <OrdersOverview orders={orders} />

      <section className="layout-grid layout-grid-orders">
        <SectionCard title="Recent Orders" subtitle={`${orders.length} records shown`}>
          <div className="list-grid">
            {orders.map((order) => {
              const selectedPlan = order.fulfillment_plan?.selected_plan;
              return (
                <Link key={order.id} className="order-list-item" to={`/orders/${order.id}`}>
                  <div className="order-list-main">
                    <div className="order-list-top">
                      <strong>{compactId(order.id)}</strong>
                      <span className={statusTone(order.status)}>{order.status}</span>
                    </div>
                    <p>{order.customer_id}</p>
                  </div>

                  <dl className="order-list-meta">
                    <div>
                      <dt>Route</dt>
                      <dd>{candidateWarehouseLabel(selectedPlan)}</dd>
                    </div>
                    <div>
                      <dt>Total</dt>
                      <dd>{formatCurrency(order.total_cost)}</dd>
                    </div>
                    <div>
                      <dt>ETA</dt>
                      <dd>{order.eta_days ? `${order.eta_days}d` : "Pending"}</dd>
                    </div>
                    <div>
                      <dt>Updated</dt>
                      <dd>{formatTime(order.updated_at ?? order.created_at)}</dd>
                    </div>
                  </dl>
                </Link>
              );
            })}
          </div>
        </SectionCard>

        <div className="stack-grid">
          <SectionCard
            title="Latest Activity"
            subtitle="Fast summary of the most recently submitted order"
            action={
              newestOrder ? (
                <Link className="text-action" to={`/orders/${newestOrder.id}`}>
                  Open detail
                </Link>
              ) : null
            }
          >
            {newestOrder ? (
              <div className="snapshot-card">
                <div className="snapshot-row">
                  <span>Customer</span>
                  <strong>{newestOrder.customer_id}</strong>
                </div>
                <div className="snapshot-row">
                  <span>Status</span>
                  <span className={statusTone(newestOrder.status)}>{newestOrder.status}</span>
                </div>
                <div className="snapshot-row">
                  <span>Workflow</span>
                  <strong>{compactId(newestOrder.workflow_id)}</strong>
                </div>
                <div className="snapshot-row">
                  <span>Destination</span>
                  <strong>{newestOrder.destination_zone}</strong>
                </div>
              </div>
            ) : (
              <p className="subtle-copy">No recent orders available.</p>
            )}
          </SectionCard>

          <SectionCard title="Attention Queue" subtitle="Recent failures and rollbacks that need review">
            {failedOrders.length > 0 ? (
              <div className="compact-list">
                {failedOrders.map((order) => (
                  <Link key={order.id} className="compact-item" to={`/orders/${order.id}`}>
                    <div>
                      <strong>{order.customer_id}</strong>
                      <p>{compactId(order.id)}</p>
                    </div>
                    <span className={statusTone(order.status)}>{order.status}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="subtle-copy">No failed orders in the current window.</p>
            )}
          </SectionCard>
        </div>
      </section>
    </>
  );
}

function OrderDetailPage() {
  const { orderId } = useParams();
  const { data: order, loading: orderLoading, error: orderError } = usePolling(() => fetchOrder(orderId!), [orderId], 3500);
  const { data: events } = usePolling(() => fetchOrderEvents(orderId!), [orderId], 3500);
  const { data: shipments } = usePolling(() => fetchOrderShipments(orderId!), [orderId], 3500);

  if (!orderId) {
    return <EmptyState title="No order selected" message="Select an order to inspect its routing and workflow data." />;
  }

  if (orderLoading || !order) {
    return <EmptyState title="Loading order" message={orderError ?? "Fetching order detail and workflow history."} />;
  }

  const selectedPlan = order.fulfillment_plan?.selected_plan;
  const candidatePlans = order.fulfillment_plan?.candidate_plans ?? [];
  const groupedAllocations =
    selectedPlan?.allocations.reduce<Record<string, CandidatePlan["allocations"]>>((acc, allocation) => {
      const current = acc[allocation.code] ?? [];
      current.push(allocation);
      acc[allocation.code] = current;
      return acc;
    }, {}) ?? {};

  return (
    <>
      <PageIntro
        title={`Order ${compactId(order.id)}`}
        subtitle="Routing context, workflow execution trail, and shipment outputs."
        action={
          <Link className="text-action" to="/">
            Back to orders
          </Link>
        }
      />

      <section className="stats-grid detail-stats">
        <StatCard label="Status" value={titleCase(order.status)} note={`Workflow ${compactId(order.workflow_id)}`} />
        <StatCard label="Total Cost" value={formatCurrency(order.total_cost)} note={`Created ${formatTime(order.created_at)}`} />
        <StatCard label="ETA" value={order.eta_days ? `${order.eta_days} days` : "Pending"} note={`Zone ${order.destination_zone}`} />
        <StatCard
          label="Route Shape"
          value={`${selectedPlan?.warehouses_used.length ?? 0} warehouse(s)`}
          note={order.fallback_triggered ? "Fallback triggered" : "Primary routing path"}
        />
      </section>

      <section className="layout-grid layout-grid-detail">
        <SectionCard title="Selected Fulfillment Plan" subtitle={selectedPlan ? "Chosen route and allocation breakdown" : "Plan not available yet"}>
          {selectedPlan ? (
            <>
              <div className="plan-summary">
                <div className="plan-metric">
                  <span>Shipping cost</span>
                  <strong>{formatCurrency(selectedPlan.shipping_cost)}</strong>
                </div>
                <div className="plan-metric">
                  <span>Total score</span>
                  <strong>{selectedPlan.total_score}</strong>
                </div>
                <div className="plan-metric">
                  <span>Load penalty</span>
                  <strong>{selectedPlan.load_penalty}</strong>
                </div>
                <div className="plan-metric">
                  <span>SLA</span>
                  <strong>{selectedPlan.sla_met ? "Met" : "Missed"}</strong>
                </div>
              </div>

              <div className="allocation-grid">
                {Object.entries(groupedAllocations).map(([code, allocations]) => (
                  <article className="allocation-card" key={code}>
                    <h5>{code}</h5>
                    {allocations.map((allocation) => (
                      <div className="allocation-row" key={`${allocation.code}-${allocation.sku}`}>
                        <span>{allocation.sku}</span>
                        <strong>{allocation.quantity}</strong>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
            </>
          ) : (
            <p className="subtle-copy">The workflow has not stored a fulfillment plan yet.</p>
          )}
        </SectionCard>

        <SectionCard title="Order Payload" subtitle={`${order.items.length} line item(s)`}>
          <div className="compact-list">
            {order.items.map((item) => (
              <div className="compact-item static" key={item.id}>
                <div>
                  <strong>{item.sku}</strong>
                  <p>{item.quantity} unit(s)</p>
                </div>
                <strong>{formatCurrency(item.unit_price)}</strong>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Workflow Timeline" subtitle={`${events?.length ?? 0} event(s)`}>
          <div className="timeline-list">
            {(events ?? []).map((event) => (
              <article className="timeline-item" key={event.id}>
                <div className="timeline-track" />
                <div className="timeline-content">
                  <div className="timeline-header">
                    <strong>{eventLabel(event.event_type)}</strong>
                    <span>{formatTime(event.created_at)}</span>
                  </div>
                  {event.payload && Object.keys(event.payload).length > 0 ? (
                    <pre className="payload-block">{JSON.stringify(event.payload, null, 2)}</pre>
                  ) : (
                    <p className="subtle-copy">No additional payload</p>
                  )}
                </div>
              </article>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Shipments" subtitle={`${shipments?.length ?? 0} record(s)`}>
          {shipments && shipments.length > 0 ? (
            <div className="compact-list">
              {shipments.map((shipment) => (
                <div className="compact-item static" key={shipment.id}>
                  <div>
                    <strong>{shipment.tracking_id}</strong>
                    <p>{shipment.warehouse_code}</p>
                  </div>
                  <span className={statusTone(shipment.status)}>{shipment.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="subtle-copy">No shipment records yet.</p>
          )}
        </SectionCard>

        <SectionCard title="Alternative Plans" subtitle={`${candidatePlans.length} candidate option(s)`}>
          {candidatePlans.length > 0 ? (
            <div className="compact-list">
              {candidatePlans.map((plan, index) => (
                <div className="compact-item static" key={`${plan.total_score}-${index}`}>
                  <div>
                    <strong>{plan.warehouses_used.join(", ")}</strong>
                    <p>{plan.split_count} split(s)</p>
                  </div>
                  <strong>{plan.total_score}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="subtle-copy">No alternative candidate plans stored for this order.</p>
          )}
        </SectionCard>
      </section>
    </>
  );
}

function WarehouseSummary({ warehouses }: { warehouses: Warehouse[] }) {
  return (
    <section className="warehouse-grid">
      {warehouses.map((warehouse) => (
        <article className="warehouse-card" key={warehouse.id}>
          <div className="warehouse-head">
            <strong>{warehouse.code}</strong>
            <span className={warehouse.active ? "status status-success" : "status status-danger"}>
              {warehouse.active ? "Active" : "Inactive"}
            </span>
          </div>
          <p>{warehouse.name}</p>
          <dl>
            <div>
              <dt>Zones</dt>
              <dd>{warehouse.supported_zones.join(", ")}</dd>
            </div>
            <div>
              <dt>Load</dt>
              <dd>{warehouse.current_load} / {warehouse.daily_capacity}</dd>
            </div>
          </dl>
        </article>
      ))}
    </section>
  );
}

function InventoryPage() {
  const [warehouseFilter, setWarehouseFilter] = useState("ALL");
  const { data: warehouses } = usePolling(() => fetchWarehouses(), [], 10000);
  const { data: inventory, loading, error } = usePolling(() => fetchInventory(180, warehouseFilter), [warehouseFilter], 6000);

  return (
    <>
      <PageIntro
        title="Inventory Position"
        subtitle="Current stock, reserved units, and warehouse availability across the fulfillment network."
        action={
          <label className="filter-control">
            <span>Warehouse</span>
            <select value={warehouseFilter} onChange={(event) => setWarehouseFilter(event.target.value)}>
              <option value="ALL">All warehouses</option>
              {(warehouses ?? []).map((warehouse) => (
                <option key={warehouse.id} value={warehouse.code}>
                  {warehouse.code} - {warehouse.name}
                </option>
              ))}
            </select>
          </label>
        }
      />

      {warehouses && warehouses.length > 0 ? <WarehouseSummary warehouses={warehouses} /> : null}

      {loading && !inventory ? (
        <EmptyState title="Loading inventory" message="Collecting stock positions from the inventory service." />
      ) : !inventory || error ? (
        <EmptyState title="Inventory unavailable" message={error ?? "Inventory data could not be loaded."} />
      ) : (
        <SectionCard title="Inventory Snapshot" subtitle={`${inventory.length} record(s) in view`}>
          <div className="table-shell">
            <div className="data-table">
              <div className="data-table-head">
                <span>Warehouse</span>
                <span>SKU</span>
                <span>Available</span>
                <span>Reserved</span>
                <span>Updated</span>
              </div>
              {inventory.map((record) => (
                <div className="data-table-row" key={record.id}>
                  <span>{record.warehouse_code ?? compactId(record.warehouse_id)}</span>
                  <strong>{record.sku}</strong>
                  <span>{record.available_qty}</span>
                  <span>{record.reserved_qty}</span>
                  <span>{formatTime(record.updated_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      )}
    </>
  );
}

function HealthCard({ title, health, metrics }: { title: string; health: ServiceMetrics | null; metrics: ServiceMetrics | null }) {
  const rows = Object.entries(metrics ?? {}).slice(0, 8);

  return (
    <article className="service-card">
      <div className="service-card-head">
        <div>
          <h5>{title}</h5>
          <p>{health?.service ? String(health.service) : "Operational metrics"}</p>
        </div>
        <span className={health?.status === "ok" ? "status status-success" : "status status-danger"}>
          {String(health?.status ?? "unknown")}
        </span>
      </div>

      <div className="metric-stack">
        {rows.map(([key, value]) => (
          <div className="metric-row" key={key}>
            <span>{titleCase(key)}</span>
            <strong>{String(value)}</strong>
          </div>
        ))}
      </div>
    </article>
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
      <PageIntro
        title="Service Health"
        subtitle="Endpoint status and operating metrics for the services that power order processing."
      />

      <section className="service-grid">
        <HealthCard title="Order API" health={orderHealth} metrics={orderMetrics} />
        <HealthCard title="Inventory Service" health={inventoryHealth} metrics={inventoryMetrics} />
        <HealthCard title="Routing Engine" health={routingHealth} metrics={routingMetrics} />
      </section>
    </>
  );
}

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<OrdersPage />} />
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </Shell>
  );
}
