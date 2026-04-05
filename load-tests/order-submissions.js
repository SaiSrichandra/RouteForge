import http from "k6/http";
import { check, sleep } from "k6";

const baseUrl = __ENV.BASE_URL || "http://localhost:8000";
const orderUrl = `${baseUrl}/orders`;

export const options = {
  stages: [
    { duration: "30s", target: 50 },
    { duration: "45s", target: 100 },
    { duration: "30s", target: 100 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1500"],
  },
};

function buildPayload() {
  return JSON.stringify({
    customer_id: `k6-user-${__VU}-${__ITER}`,
    destination_zone: "east",
    line_items: [
      { sku: "SKU-001", quantity: 1, unit_price: "12.50" },
      { sku: "SKU-002", quantity: 1, unit_price: "20.00" },
    ],
  });
}

export default function () {
  const response = http.post(orderUrl, buildPayload(), {
    headers: { "Content-Type": "application/json" },
  });

  check(response, {
    "order accepted": (res) => res.status === 201,
  });

  sleep(1);
}
