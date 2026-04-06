import type { OrderInput, OrderRecord, Shipment, WorkflowEvent } from "./types";

const apiBaseUrl = "http://a9e83f51b01c94702826fd8e8bb7e5cb-660024319.us-east-1.elb.amazonaws.com/api/order";

function normalizeRequestError(error: unknown): Error {
  if (error instanceof Error) {
    if (error.message.includes("Failed to fetch")) {
      return new Error("Request was sent, but the browser could not read the response.");
    }
    return error;
  }

  return new Error("Request could not be completed.");
}

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(input, init);
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed with ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    throw normalizeRequestError(error);
  }
}

export function createOrder(payload: OrderInput) {
  return request<OrderRecord>(`${apiBaseUrl}/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function getOrder(orderId: string) {
  return request<OrderRecord>(`${apiBaseUrl}/orders/${orderId}`);
}

export function getOrderEvents(orderId: string) {
  return request<WorkflowEvent[]>(`${apiBaseUrl}/orders/${orderId}/events`);
}

export function getOrderShipments(orderId: string) {
  return request<Shipment[]>(`${apiBaseUrl}/orders/${orderId}/shipments`);
}
