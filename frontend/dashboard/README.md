# Dashboard

React + TypeScript dashboard for the Distributed Order Routing & Optimization System.

## Views

- orders list with status, cost, ETA, and warehouse count
- order detail with workflow timeline, selected plan, and shipments
- inventory view with warehouse filtering
- health page with service metrics and Temporal UI link

## Local run

```powershell
npm.cmd install
npm.cmd run dev
```

The Vite dev server proxies backend calls to:

- `http://localhost:8000` for Order API
- `http://localhost:8001` for Inventory service
- `http://localhost:8002` for Routing Engine
