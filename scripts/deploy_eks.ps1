param(
    [string]$AwsRegion = "us-east-1",
    [string]$ClusterName = "dor-dev",
    [string]$Namespace = "dor",
    [string]$AwsAccountId = $env:AWS_ACCOUNT_ID,
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,
    [string]$RdsEndpoint = $env:RDS_ENDPOINT,
    [string]$DbName = "order_routing",
    [string]$DbUser = "dor_admin",
    [string]$ImageTag = "latest",
    [string]$OrderApiCorsOrigins = $(if ($env:ORDER_API_CORS_ORIGINS) { $env:ORDER_API_CORS_ORIGINS } else { "*" }),
    [switch]$ApplySeedJob,
    [switch]$DeployWorkflowInfra
)

if (-not $AwsAccountId) {
    throw "AwsAccountId is required. Pass -AwsAccountId or set AWS_ACCOUNT_ID."
}

if (-not $RdsEndpoint) {
    throw "RdsEndpoint is required. Pass -RdsEndpoint or set RDS_ENDPOINT."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$templatesDir = Join-Path $repoRoot "infra\kubernetes\templates"
$registry = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$encodedDbUser = [System.Uri]::EscapeDataString($DbUser)
$encodedDbPassword = [System.Uri]::EscapeDataString($DbPassword)
$databaseUrl = "postgresql+psycopg://${encodedDbUser}:${encodedDbPassword}@${RdsEndpoint}:5432/${DbName}?sslmode=require"

$replacements = @{
    "__NAMESPACE__" = $Namespace
    "__DATABASE_URL__" = $databaseUrl
    "__DB_PASSWORD__" = $DbPassword
    "__RDS_ENDPOINT__" = $RdsEndpoint
    "__ORDER_API_CORS_ORIGINS__" = $OrderApiCorsOrigins
    "__ORDER_API_IMAGE__" = "$registry/dor-dev/order-api:$ImageTag"
    "__INVENTORY_SERVICE_IMAGE__" = "$registry/dor-dev/inventory-service:$ImageTag"
    "__ROUTING_ENGINE_IMAGE__" = "$registry/dor-dev/routing-engine:$ImageTag"
    "__WORKFLOW_WORKER_IMAGE__" = "$registry/dor-dev/workflow-worker:$ImageTag"
    "__DASHBOARD_IMAGE__" = "$registry/dor-dev/dashboard:$ImageTag"
}

function Apply-Template {
    param([string]$FileName)

    $path = Join-Path $templatesDir $FileName
    $content = Get-Content $path -Raw
    foreach ($entry in $replacements.GetEnumerator()) {
        $content = $content.Replace($entry.Key, $entry.Value)
    }
    $content | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl apply failed for $FileName"
    }
}

aws eks update-kubeconfig --region $AwsRegion --name $ClusterName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update kubeconfig for $ClusterName"
}

$orderedTemplates = @(
    "namespace.yaml",
    "app-configmap.yaml",
    "app-secret.yaml",
    "restock-cronjob.yaml"
)

if ($DeployWorkflowInfra) {
    $orderedTemplates += @(
        "temporal-dynamic-config.yaml",
        "temporal-postgresql.yaml"
    )
}

foreach ($template in $orderedTemplates) {
    Apply-Template -FileName $template
}

kubectl delete svc grafana prometheus temporal-ui order-api-public -n $Namespace --ignore-not-found
kubectl delete deployment grafana prometheus temporal-ui -n $Namespace --ignore-not-found
kubectl delete configmap prometheus-config grafana-datasources grafana-dashboard-provider grafana-dashboards -n $Namespace --ignore-not-found

$deploymentTemplates = @(
    "inventory-service.yaml",
    "routing-engine.yaml",
    "order-api.yaml",
    "workflow-worker.yaml",
    "dashboard.yaml"
)

if ($DeployWorkflowInfra) {
    $deploymentTemplates = @("temporal.yaml") + $deploymentTemplates
}

foreach ($template in $deploymentTemplates) {
    Apply-Template -FileName $template
}

if ($ApplySeedJob) {
    kubectl delete job dor-seed-data -n $Namespace --ignore-not-found
    Apply-Template -FileName "seed-job.yaml"
}

Write-Host "Deployment submitted to namespace '$Namespace'."
Write-Host "Check rollout progress with:"
Write-Host "kubectl get pods -n $Namespace"
Write-Host "kubectl get svc -n $Namespace"
