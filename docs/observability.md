# Observability Guide

This project includes a lightweight observability stack built around Prometheus and Grafana.
It works in the local Docker environment and can also be deployed into EKS.

## What is being measured

### Order API

- HTTP request volume and latency
- orders created
- workflow start failures
- current orders by status
- workflow event count

### Inventory Service

- HTTP request volume and latency
- reservation success and failure counts
- failure reason breakdown
- low-stock record count
- active reservation count

### Routing Engine

- HTTP request volume and latency
- route computation time
- candidate plan counts
- split-route selections
- fallback-route selections

### Workflow Worker

- workflow completion outcomes
- workflow duration
- activity duration by step
- shipment retry count
- compensation count
- payment failure count
- reservation failure count

## Local URLs

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Grafana login: `admin` / `admin`

## EKS URLs

After deploying the EKS observability manifests:

- Prometheus: run `kubectl get svc prometheus -n dor`
- Grafana: run `kubectl get svc grafana -n dor`
- Grafana login: `admin` / `admin`

## Scrape model

Prometheus scrapes the three FastAPI services from their `/prometheus` endpoints.
The workflow worker exposes a Prometheus endpoint on port `9100` using the Python Prometheus client's embedded HTTP server.
In EKS, the same scrape model is used against Kubernetes service DNS names inside the `dor` namespace.

## Demo flow

1. Start the stack and seed inventory data.
2. Open Grafana and load `Distributed Order Routing Overview`.
3. Submit one normal order, one `fail-payment` order, and one `delay-shipment` order.
4. Watch these dashboard effects:
   - `Orders Accepted Per Minute` moves up
   - `Failed Orders` increments for the payment-failure scenario
   - `Shipment Retries` increments for the delayed-shipment scenario
   - `Compensations Triggered` increments for rollback after payment failure
   - `Workflow Duration` and `Activity Latency by Step` change as workflows run

## Why this matters

This observability layer shows the system is operable as well as functional:

- instrument business-critical flows, not just infrastructure
- trace retries and rollback behavior
- turn backend activity into demoable operational signals
- design a system that is operable, not merely functional
