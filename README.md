# Distributed Order Routing Platform

Cloud-native fulfillment platform that accepts customer orders, chooses the best warehouse fulfillment strategy, orchestrates downstream steps with Temporal, exposes a React dashboard, and runs on AWS EKS with observability, CI/CD, and performance testing.

## What this project does

Given an order with multiple SKUs and a destination zone, the system:

- evaluates warehouse inventory and coverage
- computes candidate fulfillment plans
- chooses the best route using an explainable heuristic
- reserves inventory
- runs a Temporal workflow for payment and shipment creation
- records workflow events and shipments
- exposes the full lifecycle through APIs, a dashboard, and monitoring

This project demonstrates distributed systems design, workflow orchestration, compensation, infrastructure-as-code, observability, CI/CD, testing, and performance tuning.

## Architecture

```mermaid
flowchart LR
    UI["React Dashboard"] --> API["Order API"]
    API --> DB["PostgreSQL / RDS"]
    API --> TEMP["Temporal Server"]
    TEMP --> WORKER["Workflow Worker"]
    WORKER --> INV["Inventory Service"]
    WORKER --> ROUTE["Routing Engine"]
    WORKER --> DB
    INV --> DB
    API --> OBS["Prometheus / Grafana"]
    INV --> OBS
    ROUTE --> OBS
    WORKER --> OBS
```

## Services

- `order-api`: accepts orders and exposes order, event, and shipment APIs
- `inventory-service`: serves warehouse inventory and manages reservations/releases
- `routing-engine`: computes and scores fulfillment plans
- `workflow-worker`: runs Temporal workflows, retries, and compensation logic
- `dashboard`: web UI for orders, events, shipments, and system links
- `prometheus` / `grafana`: metrics collection and visualization

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL, Temporal Python SDK
- Frontend: React, TypeScript, Vite
- Infra: Docker Compose, Kubernetes, Terraform, AWS EKS, RDS, ECR
- Observability: Prometheus, Grafana
- Delivery: GitHub Actions CI/CD
- Testing: pytest, Temporal test environment, k6

## Key Features

- Warehouse routing with single-warehouse, split-shipment, fallback, and infeasible-plan handling
- Inventory reservation plus compensation on downstream failure
- Temporal-based fulfillment orchestration with retries
- Workflow event history for debugging and UI visibility
- Live cloud deployment on AWS EKS
- Prometheus/Grafana observability
- CI/CD with GitHub Actions, ECR, and EKS deployment

## Current Status

The platform is fully deployed on AWS and also runnable locally.

Current project capabilities include:

- multi-service order routing and orchestration
- Terraform-provisioned AWS infrastructure
- EKS deployment with public dashboard and tooling endpoints
- Prometheus and Grafana in-cluster monitoring
- routing unit tests
- API and database integration tests
- workflow tests, including Temporal time-skipping tests
- k6 load testing and benchmark-backed optimization

## Performance Story

Two measurable improvements were built into the project:

1. Inventory caching

- added a lightweight cache for hot inventory reads
- benchmark result: about `54.1%` mean latency improvement and `51.4%` p95 improvement

2. Async order submission

- moved Temporal workflow start off the synchronous `POST /orders` request path
- direct k6 result before change: `12.50%` failed, `p95 59.76s`
- direct k6 result after change: `0.46%` failed, `p95 781ms`

The second result comes from a real AWS load test and a deliberate architecture change, not just additional infrastructure.

## Repository Layout

```text
services/
  order-api/
  inventory-service/
  routing-engine/
  workflow-worker/
frontend/
  dashboard/
infra/
  kubernetes/
  observability/
  terraform/
load-tests/
scripts/
docs/
```

## Local Development

Start the local stack:

```powershell
docker compose up -d --build postgres temporal temporal-ui order-api inventory-service routing-engine workflow-worker prometheus grafana
```

Seed demo data:

```powershell
docker run --rm --network minidevsecops_default -v "${PWD}:/workspace" -w /workspace python:3.11-slim sh -lc "pip install --no-cache-dir 'psycopg[binary]==3.2.9' >/tmp/pip.log && DATABASE_URL=postgresql://postgres:postgres@postgres:5432/order_routing python scripts/seed_demo_data.py"
```

Run the dashboard locally:

```powershell
npm.cmd install --prefix frontend\dashboard
npm.cmd run dev --prefix frontend\dashboard
```

Useful local URLs:

- Dashboard: `http://localhost:5173`
- Temporal UI: `http://localhost:8088`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

## Demo Scenarios

Use `customer_id` to trigger deterministic demo behavior:

- success flow: `cust-orchestrated-001`
- payment failure with compensation: any value containing `fail-payment`
- delayed shipment with retry: any value containing `delay-shipment`

Useful APIs:

- `POST /orders`
- `GET /orders/{id}`
- `GET /orders/{id}/events`
- `GET /orders/{id}/shipments`

## Testing

This repo includes four proof layers:

- routing-engine unit tests
- order-api integration tests
- inventory-service integration tests
- workflow-worker tests, including Temporal time-skipping environment tests

Load testing is included with k6:

- `load-tests/order-submissions.js`
- `scripts/run_k6_aws.ps1`

## CI/CD

GitHub Actions now covers both validation and delivery:

- `.github/workflows/ci.yml`: linting, tests, frontend build, Docker validation
- `.github/workflows/cd.yml`: AWS auth via GitHub OIDC, ECR push, EKS deploy

This gives the project a full source-control-to-cloud deployment path when connected to GitHub.

## AWS Deployment

AWS infrastructure is provisioned with Terraform modules for:

- networking
- ECR
- RDS
- EKS

The Kubernetes deployment layer includes:

- app services
- Temporal
- dashboard
- Prometheus
- Grafana

Deployment helpers:

- `scripts/push_images.ps1`
- `scripts/deploy_eks.ps1`

## Documentation

Read these next if you want the full system story:

- `docs/system-design.md`
- `docs/workflow-sequence.md`
- `docs/er-diagram.md`
- `docs/tradeoffs.md`
- `docs/observability.md`
- `docs/testing-performance.md`
- `docs/ci-cd.md`
- `docs/aws-bootstrap.md`
- `docs/eks-deployment.md`

## Project Highlights

This project demonstrates:

- service decomposition and distributed systems design
- workflow durability, retries, and compensation
- observability with real metrics and dashboards
- cloud deployment on AWS EKS with Terraform
- CI/CD and release automation
- testing across unit, integration, workflow, and load levels
- performance improvement driven by measurement
