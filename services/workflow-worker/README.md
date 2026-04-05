# Workflow Worker

Temporal worker for the order fulfillment workflow.

Implemented responsibilities:

- load orders and line items from PostgreSQL
- fetch inventory and warehouse snapshot from the Inventory service
- call the Routing Engine
- reserve stock and release it on failure
- simulate payment authorization
- simulate shipment creation with retries
- write workflow events and shipment records
- mark orders `confirmed` or `failed`
