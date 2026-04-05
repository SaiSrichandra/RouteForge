# EKS Deployment Guide

This guide covers the post-Terraform phase: building images, pushing them to ECR, and deploying the application stack onto EKS.

## What gets deployed

- Temporal server
- Temporal UI, exposed directly with its own `LoadBalancer`
- Prometheus, exposed directly with its own `LoadBalancer`
- Grafana, exposed directly with its own `LoadBalancer`
- Order API
- Inventory service
- Routing engine
- Workflow worker
- Dashboard served by Nginx, with in-cluster API proxying

## Files involved

- Dashboard container: [Dockerfile](../frontend/dashboard/Dockerfile)
- Dashboard reverse proxy config: [nginx.conf](../frontend/dashboard/nginx.conf)
- Kubernetes templates: [templates](../infra/kubernetes/templates)
- Image push helper: [push_images.ps1](../scripts/push_images.ps1)
- EKS deploy helper: [deploy_eks.ps1](../scripts/deploy_eks.ps1)

## Step 1. Push images to ECR

From the repo root:

```powershell
.\scripts\push_images.ps1
```

This builds and pushes:

- `order-api`
- `inventory-service`
- `routing-engine`
- `workflow-worker`
- `dashboard`

## Step 2. Deploy to EKS

Use your database password from Terraform:

```powershell
.\scripts\deploy_eks.ps1 -DbPassword "<your-rds-password>"
```

To also seed warehouse and inventory data in-cluster:

```powershell
.\scripts\deploy_eks.ps1 -DbPassword "<your-rds-password>" -ApplySeedJob
```

## Step 3. Check rollout

```powershell
kubectl get pods -n dor
kubectl get svc -n dor
kubectl get jobs -n dor
```

## Step 4. Find the dashboard URL

The dashboard service is a `LoadBalancer`, so AWS will provision an external address:

```powershell
kubectl get svc dashboard -n dor
```

Open the external hostname once it appears.

## Step 5. Find the Temporal UI URL

Temporal UI is also exposed with its own `LoadBalancer`:

```powershell
kubectl get svc temporal-ui -n dor
```

Open the external hostname once it appears.

## Step 6. Find observability URLs

Prometheus and Grafana are also exposed with `LoadBalancer` services:

```powershell
kubectl get svc prometheus -n dor
kubectl get svc grafana -n dor
```

Grafana login is `admin` / `admin`.

## Notes and tradeoffs

- This EKS deployment is intentionally compact for a small dev environment.
- Temporal is deployed with `auto-setup` for simplicity. That is acceptable for a demo environment but not the final production posture.
- The dashboard proxies internal APIs with Nginx so the frontend can keep using relative `/api/...` routes.
- Temporal UI is exposed directly because it is more reliable at the domain root than under a subpath proxy.
- Prometheus and Grafana are exposed directly for demo simplicity in EKS.
- On a very small node group, pod scheduling may be tight. If pods remain pending, scale the node group upward.
