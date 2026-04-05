export type OrderStatus = "pending" | "routing" | "confirmed" | "failed";

export interface OrderItem {
  id: string;
  sku: string;
  quantity: number;
  unit_price: string;
}

export interface Allocation {
  warehouse_id: string;
  code: string;
  sku: string;
  quantity: number;
}

export interface CandidatePlan {
  warehouses_used: string[];
  allocations: Allocation[];
  shipping_cost: string;
  eta_days: number;
  sla_met: boolean;
  split_count: number;
  load_penalty: string;
  delay_penalty: string;
  total_score: string;
}

export interface FulfillmentPlan {
  selected_plan: CandidatePlan;
  candidate_plans: CandidatePlan[];
}

export interface Order {
  id: string;
  customer_id: string;
  destination_zone: string;
  status: OrderStatus;
  total_cost: string | null;
  eta_days: number | null;
  fallback_triggered: boolean;
  workflow_id: string | null;
  fulfillment_plan: FulfillmentPlan | null;
  created_at: string;
  updated_at: string | null;
  items: OrderItem[];
}

export interface WorkflowEvent {
  id: string;
  order_id: string;
  workflow_id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface Shipment {
  id: string;
  order_id: string;
  warehouse_code: string;
  tracking_id: string;
  status: string;
  payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string | null;
}

export interface Warehouse {
  id: string;
  code: string;
  name: string;
  supported_zones: string[];
  shipping_cost_multiplier: string;
  daily_capacity: number;
  current_load: number;
  active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface InventoryRecord {
  id: string;
  warehouse_id: string;
  warehouse_code: string | null;
  sku: string;
  available_qty: number;
  reserved_qty: number;
  updated_at: string;
}

export interface ServiceMetrics {
  [key: string]: string | number | boolean | null;
}

