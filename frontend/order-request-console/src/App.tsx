import { useEffect, useMemo, useState } from "react";

import { createOrder, getOrder, getOrderEvents, getOrderShipments } from "./api";
import { scenarios } from "./scenarios";
import type { OrderInput, OrderRecord, Scenario, Shipment, SubmissionRecord, WorkflowEvent } from "./types";

function clonePayload(payload: OrderInput): OrderInput {
  return {
    customer_id: payload.customer_id,
    destination_zone: payload.destination_zone,
    line_items: payload.line_items.map((item) => ({ ...item })),
  };
}

function withRunSpecificCustomer(payload: OrderInput, runLabel: string): OrderInput {
  return {
    ...clonePayload(payload),
    customer_id: `${payload.customer_id}-${runLabel}`,
  };
}

function normalizePayload(payload: OrderInput): OrderInput {
  const normalizedItems = payload.line_items.flatMap((item) => {
    if (item.quantity <= 100) {
      return [item];
    }

    const chunks: OrderInput["line_items"] = [];
    let remaining = item.quantity;

    while (remaining > 0) {
      const chunkQuantity = Math.min(remaining, 100);
      chunks.push({
        sku: item.sku,
        quantity: chunkQuantity,
        unit_price: item.unit_price,
      });
      remaining -= chunkQuantity;
    }

    return chunks;
  });

  return {
    ...clonePayload(payload),
    line_items: normalizedItems,
  };
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

function formatMoney(value: string | null) {
  if (!value) {
    return "Pending";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function statusTone(status: string) {
  switch (status) {
    case "confirmed":
      return "badge badge-success";
    case "failed":
      return "badge badge-danger";
    case "routing":
      return "badge badge-warning";
    default:
      return "badge badge-neutral";
  }
}

function compactId(value: string | null) {
  if (!value) {
    return "Pending";
  }

  return value.length <= 16 ? value : `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function eventLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function App() {
  const [burstCount, setBurstCount] = useState(3);
  const [form, setForm] = useState<OrderInput>(() => clonePayload(scenarios[0].payload));
  const [selectedScenarioId, setSelectedScenarioId] = useState(scenarios[0].id);
  const [submissions, setSubmissions] = useState<SubmissionRecord[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<OrderRecord | null>(null);
  const [selectedEvents, setSelectedEvents] = useState<WorkflowEvent[]>([]);
  const [selectedShipments, setSelectedShipments] = useState<Shipment[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [loadingOrder, setLoadingOrder] = useState(false);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? scenarios[0],
    [selectedScenarioId],
  );

  useEffect(() => {
    if (!selectedOrderId) {
      return;
    }

    let active = true;

    const load = async () => {
      try {
        setLoadingOrder(true);
        const [order, events, shipments] = await Promise.all([
          getOrder(selectedOrderId),
          getOrderEvents(selectedOrderId),
          getOrderShipments(selectedOrderId),
        ]);

        if (!active) {
          return;
        }

        setSelectedOrder(order);
        setSelectedEvents(events);
        setSelectedShipments(shipments);
      } catch (nextError) {
        if (!active) {
          return;
        }
        console.error(nextError);
      } finally {
        if (active) {
          setLoadingOrder(false);
        }
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 4000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selectedOrderId]);

  function loadScenario(scenario: Scenario) {
    setSelectedScenarioId(scenario.id);
    setForm(clonePayload(scenario.payload));
  }

  function updateItem(index: number, key: keyof OrderInput["line_items"][number], value: string) {
    setForm((current) => ({
      ...current,
      line_items: current.line_items.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [key]: key === "sku" ? value : Number(value),
            }
          : item,
      ),
    }));
  }

  function addLineItem() {
    setForm((current) => ({
      ...current,
      line_items: [...current.line_items, { sku: "SKU-001", quantity: 1, unit_price: 10 }],
    }));
  }

  function removeLineItem(index: number) {
    setForm((current) => ({
      ...current,
      line_items: current.line_items.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  async function submitPayload(payload: OrderInput, requestName: string) {
    const order = await createOrder(normalizePayload(payload));
    setSubmissions((current) => [{ requestName, submittedAt: new Date().toISOString(), order }, ...current].slice(0, 18));
    setSelectedOrderId(order.id);
    return order;
  }

  async function handleSingleSubmit() {
    try {
      setSubmitting(true);
      const runLabel = Date.now().toString().slice(-6);
      await submitPayload(withRunSpecificCustomer(form, runLabel), selectedScenario.name);
    } catch (nextError) {
      console.error(nextError);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBurstSubmit() {
    try {
      setSubmitting(true);

      for (let index = 0; index < burstCount; index += 1) {
        const runLabel = `${Date.now().toString().slice(-5)}-${index + 1}`;
        try {
          await submitPayload(withRunSpecificCustomer(form, runLabel), `${selectedScenario.name} Burst`);
        } catch (nextError) {
          console.error(nextError);
        }
      }
    } catch (nextError) {
      console.error(nextError);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <h1>Order Request Console</h1>
          <p className="hero-copy">Submit orders and inspect workflow results.</p>
        </div>
      </header>

      <main className="workspace">
        <section className="content-grid">
          <div className="stack">
            <section className="panel">
              <div className="panel-head">
                <h2>Scenarios</h2>
              </div>

              <div className="scenario-grid">
                {scenarios.map((scenario) => (
                  <button
                    key={scenario.id}
                    type="button"
                    className={scenario.id === selectedScenarioId ? "scenario-card active" : "scenario-card"}
                    onClick={() => loadScenario(scenario)}
                  >
                    <strong>{scenario.name}</strong>
                    <p>{scenario.description}</p>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Request Builder</h2>
              </div>

              <div className="form-grid">
                <label>
                  <span>Customer ID Prefix</span>
                  <input
                    value={form.customer_id}
                    onChange={(event) => setForm((current) => ({ ...current, customer_id: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Destination Zone</span>
                  <select
                    value={form.destination_zone}
                    onChange={(event) => setForm((current) => ({ ...current, destination_zone: event.target.value }))}
                  >
                    <option value="east">east</option>
                    <option value="central">central</option>
                    <option value="west">west</option>
                    <option value="south">south</option>
                  </select>
                </label>
                <label>
                  <span>Burst Count</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={burstCount}
                    onChange={(event) => setBurstCount(Number(event.target.value))}
                  />
                </label>
              </div>

              <div className="line-items">
                <div className="line-items-header">
                  <span>Item Name</span>
                  <span>Quantity</span>
                  <span>Unit Price</span>
                  <span />
                </div>
                {form.line_items.map((item, index) => (
                  <div className="line-item" key={`${item.sku}-${index}`}>
                    <input value={item.sku} onChange={(event) => updateItem(index, "sku", event.target.value)} />
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={item.quantity}
                      onChange={(event) => updateItem(index, "quantity", event.target.value)}
                    />
                    <input
                      type="number"
                      min={0.01}
                      step="0.01"
                      value={item.unit_price}
                      onChange={(event) => updateItem(index, "unit_price", event.target.value)}
                    />
                    <button type="button" className="secondary small" onClick={() => removeLineItem(index)} disabled={form.line_items.length === 1}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>

              <div className="actions">
                <button type="button" className="secondary" onClick={addLineItem}>
                  Add line item
                </button>
                <button type="button" onClick={handleSingleSubmit} disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit single order"}
                </button>
                <button type="button" className="accent" onClick={handleBurstSubmit} disabled={submitting}>
                  {submitting ? "Submitting..." : `Submit burst x${burstCount}`}
                </button>
              </div>
            </section>
          </div>

          <div className="stack">
            <section className="panel">
              <div className="panel-head">
                <h2>Recent Submissions</h2>
              </div>

              <div className="submission-list">
                {submissions.length > 0 ? (
                  submissions.map((submission) => (
                    <button
                      key={`${submission.order.id}-${submission.submittedAt}`}
                      type="button"
                      className={selectedOrderId === submission.order.id ? "submission-card active" : "submission-card"}
                      onClick={() => setSelectedOrderId(submission.order.id)}
                    >
                      <div className="submission-top">
                        <strong>{submission.requestName}</strong>
                        <span className={statusTone(submission.order.status)}>{submission.order.status}</span>
                      </div>
                      <p>{submission.order.customer_id}</p>
                      <div className="submission-meta">
                        <span>{compactId(submission.order.id)}</span>
                        <span>{formatTime(submission.submittedAt)}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <p className="empty-copy">No requests submitted yet.</p>
                )}
              </div>
            </section>

            <section className="panel inspector">
              <div className="panel-head">
                <h2>Order Inspector</h2>
              </div>

              {!selectedOrderId ? (
                <p className="empty-copy">Submit or pick an order to inspect it.</p>
              ) : loadingOrder && !selectedOrder ? (
                <p className="empty-copy">Loading order detail...</p>
              ) : selectedOrder ? (
                <>
                  <div className="stats">
                    <div className="stat">
                      <span>Status</span>
                      <strong>{selectedOrder.status}</strong>
                    </div>
                    <div className="stat">
                      <span>Total</span>
                      <strong>{formatMoney(selectedOrder.total_cost)}</strong>
                    </div>
                    <div className="stat">
                      <span>ETA</span>
                      <strong>{selectedOrder.eta_days ? `${selectedOrder.eta_days}d` : "Pending"}</strong>
                    </div>
                    <div className="stat">
                      <span>Workflow</span>
                      <strong>{compactId(selectedOrder.workflow_id)}</strong>
                    </div>
                  </div>

                  <div className="detail-block">
                    <h3>Selected Plan</h3>
                    <p>
                      {selectedOrder.fulfillment_plan?.selected_plan
                        ? selectedOrder.fulfillment_plan.selected_plan.warehouses_used.join(", ")
                        : "No selected plan yet"}
                    </p>
                  </div>

                  <div className="detail-block">
                    <h3>Workflow Events</h3>
                    <div className="event-list">
                      {selectedEvents.map((event) => (
                        <article className="event-card" key={event.id}>
                          <div className="event-top">
                            <strong>{eventLabel(event.event_type)}</strong>
                            <span>{formatTime(event.created_at)}</span>
                          </div>
                          {event.payload ? <pre>{JSON.stringify(event.payload, null, 2)}</pre> : <p>No payload</p>}
                        </article>
                      ))}
                    </div>
                  </div>

                  <div className="detail-block">
                    <h3>Shipments</h3>
                    {selectedShipments.length > 0 ? (
                      <div className="shipment-list">
                        {selectedShipments.map((shipment) => (
                          <div className="shipment-card" key={shipment.id}>
                            <strong>{shipment.tracking_id}</strong>
                            <span>{shipment.warehouse_code}</span>
                            <span className={statusTone(shipment.status)}>{shipment.status}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p>No shipments yet.</p>
                    )}
                  </div>
                </>
              ) : null}
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}
