# Tradeoffs

## What we intentionally simplify first

- only three warehouses
- heuristic routing instead of linear programming
- simulated payment and shipment providers
- one PostgreSQL database for fast local development
- local Docker Compose before full Kubernetes rollout

## Why those tradeoffs are reasonable

They keep the initial system focused on the hardest engineering concerns:

- system decomposition
- workflow reliability
- optimization logic
- cloud-readiness
- observability and testing discipline

without getting buried in enterprise-scale overhead too early.

## What we would improve next

- replace heuristic search with linear or mixed-integer optimization
- add warehouse-specific packing and carrier constraints
- introduce true asynchronous event publishing with SQS
- add Redis caching and benchmark its effect
- deploy to EKS with Terraform modules and GitHub Actions
- add canary or blue-green deployment strategy
