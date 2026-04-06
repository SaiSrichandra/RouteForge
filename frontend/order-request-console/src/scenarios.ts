import type { Scenario } from "./types";

export const scenarios: Scenario[] = [
  {
    id: "success-east",
    name: "Standard Success",
    description: "Straight-through happy path.",
    payload: {
      customer_id: "client-success-east",
      destination_zone: "east",
      line_items: [
        { sku: "SKU-001", quantity: 2, unit_price: 12.5 },
        { sku: "SKU-002", quantity: 1, unit_price: 20 },
      ],
    },
  },
  {
    id: "payment-failure",
    name: "Payment Rollback",
    description: "Deterministic payment failure path.",
    payload: {
      customer_id: "demo-fail-payment",
      destination_zone: "east",
      line_items: [{ sku: "SKU-003", quantity: 1, unit_price: 15 }],
    },
  },
  {
    id: "shipment-retry",
    name: "Shipment Retry",
    description: "Delayed shipment with retry.",
    payload: {
      customer_id: "demo-delay-shipment",
      destination_zone: "east",
      line_items: [{ sku: "SKU-004", quantity: 1, unit_price: 18 }],
    },
  },
  {
    id: "split-fulfillment",
    name: "Split Fulfillment",
    description: "Larger basket for multi-warehouse routing.",
    payload: {
      customer_id: "client-split-central",
      destination_zone: "central",
      line_items: [
        { sku: "SKU-010", quantity: 80, unit_price: 11 },
        { sku: "SKU-011", quantity: 55, unit_price: 14 },
      ],
    },
  },
  {
    id: "mixed-west",
    name: "Mixed Basket",
    description: "Balanced multi-line request.",
    payload: {
      customer_id: "client-mixed-west",
      destination_zone: "west",
      line_items: [
        { sku: "SKU-001", quantity: 1, unit_price: 12.5 },
        { sku: "SKU-005", quantity: 2, unit_price: 22 },
        { sku: "SKU-006", quantity: 1, unit_price: 9.5 },
      ],
    },
  },
];
