import type { OrderInput, OrderRecord, Shipment, WorkflowEvent } from "./types";

const apiBaseUrl = "http://a9e83f51b01c94702826fd8e8bb7e5cb-660024319.us-east-1.elb.amazonaws.com/api/order";
const graphqlUrl = `${apiBaseUrl}/graphql`;

type GraphQLResponse<T> = {
  data?: T;
  errors?: Array<{ message: string }>;
};

type GraphQLOrderItem = {
  id: string;
  sku: string;
  quantity: number;
  unitPrice: string;
};

type GraphQLCandidatePlan = {
  warehousesUsed: string[];
  shippingCost: string;
  totalScore: string;
};

type GraphQLFulfillmentPlan = {
  selectedPlan?: GraphQLCandidatePlan | null;
};

type GraphQLOrder = {
  id: string;
  customerId: string;
  destinationZone: string;
  status: string;
  totalCost: string | null;
  etaDays: number | null;
  fallbackTriggered: boolean;
  workflowId: string | null;
  fulfillmentPlan: GraphQLFulfillmentPlan | null;
  createdAt: string;
  updatedAt: string | null;
  items: GraphQLOrderItem[];
};

type GraphQLWorkflowEvent = {
  id: string;
  orderId: string;
  workflowId: string;
  eventType: string;
  payload: Record<string, unknown> | null;
  createdAt: string;
};

type GraphQLShipment = {
  id: string;
  orderId: string;
  warehouseCode: string;
  trackingId: string;
  status: string;
};

function normalizeRequestError(error: unknown): Error {
  if (error instanceof Error) {
    if (error.message.includes("Failed to fetch")) {
      return new Error("Request could not be completed.");
    }
    return error;
  }

  return new Error("Request could not be completed.");
}

function mapOrder(order: GraphQLOrder): OrderRecord {
  return {
    id: order.id,
    customer_id: order.customerId,
    destination_zone: order.destinationZone,
    status: order.status,
    total_cost: order.totalCost,
    eta_days: order.etaDays,
    fallback_triggered: order.fallbackTriggered,
    workflow_id: order.workflowId,
    fulfillment_plan: order.fulfillmentPlan
      ? {
          selected_plan: order.fulfillmentPlan.selectedPlan
            ? {
                warehouses_used: order.fulfillmentPlan.selectedPlan.warehousesUsed,
                shipping_cost: order.fulfillmentPlan.selectedPlan.shippingCost,
                total_score: Number(order.fulfillmentPlan.selectedPlan.totalScore),
              }
            : undefined,
        }
      : null,
    created_at: order.createdAt,
    updated_at: order.updatedAt,
  };
}

function mapEvent(event: GraphQLWorkflowEvent): WorkflowEvent {
  return {
    id: event.id,
    order_id: event.orderId,
    workflow_id: event.workflowId,
    event_type: event.eventType,
    payload: event.payload,
    created_at: event.createdAt,
  };
}

function mapShipment(shipment: GraphQLShipment): Shipment {
  return {
    id: shipment.id,
    order_id: shipment.orderId,
    warehouse_code: shipment.warehouseCode,
    tracking_id: shipment.trackingId,
    status: shipment.status,
  };
}

async function graphqlRequest<TData>(
  query: string,
  variables?: Record<string, unknown>,
): Promise<TData> {
  try {
    const response = await fetch(graphqlUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query, variables }),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed with ${response.status}`);
    }

    const payload = (await response.json()) as GraphQLResponse<TData>;
    if (payload.errors && payload.errors.length > 0) {
      throw new Error(payload.errors.map((error) => error.message).join("; "));
    }
    if (!payload.data) {
      throw new Error("Request returned no data.");
    }

    return payload.data;
  } catch (error) {
    throw normalizeRequestError(error);
  }
}

export async function createOrder(payload: OrderInput): Promise<OrderRecord> {
  const data = await graphqlRequest<{ createOrder: GraphQLOrder }>(
    `
      mutation CreateOrder($payload: GraphQLOrderCreateInput!) {
        createOrder(payload: $payload) {
          id
          customerId
          destinationZone
          status
          totalCost
          etaDays
          fallbackTriggered
          workflowId
          createdAt
          updatedAt
          fulfillmentPlan {
            selectedPlan {
              warehousesUsed
              shippingCost
              totalScore
            }
          }
        }
      }
    `,
    {
      payload: {
        customerId: payload.customer_id,
        destinationZone: payload.destination_zone,
        lineItems: payload.line_items.map((item) => ({
          sku: item.sku,
          quantity: item.quantity,
          unitPrice: item.unit_price,
        })),
      },
    },
  );

  return mapOrder(data.createOrder);
}

export async function getOrder(orderId: string): Promise<OrderRecord> {
  const data = await graphqlRequest<{ order: GraphQLOrder | null }>(
    `
      query Order($orderId: String!) {
        order(orderId: $orderId) {
          id
          customerId
          destinationZone
          status
          totalCost
          etaDays
          fallbackTriggered
          workflowId
          createdAt
          updatedAt
          fulfillmentPlan {
            selectedPlan {
              warehousesUsed
              shippingCost
              totalScore
            }
          }
        }
      }
    `,
    { orderId },
  );

  if (!data.order) {
    throw new Error("Order not found.");
  }

  return mapOrder(data.order);
}

export async function getOrderEvents(orderId: string): Promise<WorkflowEvent[]> {
  const data = await graphqlRequest<{ orderEvents: GraphQLWorkflowEvent[] }>(
    `
      query OrderEvents($orderId: String!) {
        orderEvents(orderId: $orderId) {
          id
          orderId
          workflowId
          eventType
          payload
          createdAt
        }
      }
    `,
    { orderId },
  );

  return data.orderEvents.map(mapEvent);
}

export async function getOrderShipments(orderId: string): Promise<Shipment[]> {
  const data = await graphqlRequest<{ orderShipments: GraphQLShipment[] }>(
    `
      query OrderShipments($orderId: String!) {
        orderShipments(orderId: $orderId) {
          id
          orderId
          warehouseCode
          trackingId
          status
        }
      }
    `,
    { orderId },
  );

  return data.orderShipments.map(mapShipment);
}
