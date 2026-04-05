import type {
  InventoryRecord,
  Order,
  ServiceMetrics,
  Shipment,
  Warehouse,
  WorkflowEvent,
} from "./types";

async function request<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function fetchOrders(limit = 25) {
  return request<Order[]>(`/api/order/orders?limit=${limit}`);
}

export function fetchOrder(orderId: string) {
  return request<Order>(`/api/order/orders/${orderId}`);
}

export function fetchOrderEvents(orderId: string) {
  return request<WorkflowEvent[]>(`/api/order/orders/${orderId}/events`);
}

export function fetchOrderShipments(orderId: string) {
  return request<Shipment[]>(`/api/order/orders/${orderId}/shipments`);
}

export function fetchOrderMetrics() {
  return request<ServiceMetrics>("/api/order/metrics");
}

export function fetchOrderHealth() {
  return request<ServiceMetrics>("/api/order/health");
}

export function fetchWarehouses() {
  return request<Warehouse[]>("/api/inventory/warehouses");
}

export function fetchInventory(limit = 120, warehouseCode?: string) {
  const search = new URLSearchParams({ limit: String(limit) });
  if (warehouseCode && warehouseCode !== "ALL") {
    search.set("warehouse_code", warehouseCode);
  }
  return request<InventoryRecord[]>(`/api/inventory/inventory?${search.toString()}`);
}

export function fetchInventoryMetrics() {
  return request<ServiceMetrics>("/api/inventory/metrics");
}

export function fetchInventoryHealth() {
  return request<ServiceMetrics>("/api/inventory/health");
}

export function fetchRoutingMetrics() {
  return request<ServiceMetrics>("/api/routing/metrics");
}

export function fetchRoutingHealth() {
  return request<ServiceMetrics>("/api/routing/health");
}

