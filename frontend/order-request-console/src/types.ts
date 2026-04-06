export type OrderItemInput = {
  sku: string;
  quantity: number;
  unit_price: number;
};

export type OrderInput = {
  customer_id: string;
  destination_zone: string;
  line_items: OrderItemInput[];
};

export type OrderRecord = {
  id: string;
  customer_id: string;
  destination_zone: string;
  status: string;
  total_cost: string | null;
  eta_days: number | null;
  fallback_triggered: boolean;
  workflow_id: string | null;
  fulfillment_plan: {
    selected_plan?: {
      warehouses_used: string[];
      shipping_cost: string;
      total_score: number;
    };
  } | null;
  created_at: string;
  updated_at: string | null;
};

export type WorkflowEvent = {
  id: string;
  order_id: string;
  workflow_id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type Shipment = {
  id: string;
  order_id: string;
  warehouse_code: string;
  tracking_id: string;
  status: string;
};

export type Scenario = {
  id: string;
  name: string;
  description: string;
  payload: OrderInput;
};

export type SubmissionRecord = {
  requestName: string;
  submittedAt: string;
  order: OrderRecord;
};
