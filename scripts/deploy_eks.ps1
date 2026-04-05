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
    [string]$TemporalUiPublicUrl = $env:TEMPORAL_UI_PUBLIC_URL,
    [string]$GrafanaPublicUrl = $env:GRAFANA_PUBLIC_URL,
    [string]$PrometheusPublicUrl = $env:PROMETHEUS_PUBLIC_URL,
    [switch]$ApplySeedJob
)

if (-not $AwsAccountId) {
    throw "AwsAccountId is required. Pass -AwsAccountId or set AWS_ACCOUNT_ID."
}

if (-not $RdsEndpoint) {
    throw "RdsEndpoint is required. Pass -RdsEndpoint or set RDS_ENDPOINT."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$templatesDir = Join-Path $repoRoot "infra\kubernetes\templates"
$prometheusConfigPath = Join-Path $repoRoot "infra\observability\prometheus\prometheus.yml"
$grafanaDatasourcePath = Join-Path $repoRoot "infra\observability\grafana\provisioning\datasources\prometheus.yml"
$grafanaDashboardProviderPath = Join-Path $repoRoot "infra\observability\grafana\provisioning\dashboards\dashboard.yml"
$grafanaDashboardJsonPath = Join-Path $repoRoot "infra\observability\grafana\dashboards\order-routing-overview.json"
$registry = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$encodedDbUser = [System.Uri]::EscapeDataString($DbUser)
$encodedDbPassword = [System.Uri]::EscapeDataString($DbPassword)
$databaseUrl = "postgresql+psycopg://${encodedDbUser}:${encodedDbPassword}@${RdsEndpoint}:5432/${DbName}?sslmode=require"

function Get-ServicePublicUrl {
    param(
        [string]$ServiceName,
        [int]$Port,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        $hostName = kubectl get svc $ServiceName -n $Namespace -o jsonpath="{.status.loadBalancer.ingress[0].hostname}" 2>$null
        if (-not $hostName) {
            $hostName = kubectl get svc $ServiceName -n $Namespace -o jsonpath="{.status.loadBalancer.ingress[0].ip}" 2>$null
        }

        if ($hostName) {
            return "http://${hostName}:${Port}"
        }

        Start-Sleep -Seconds 5
    }

    return ""
}

$replacements = @{
    "__NAMESPACE__" = $Namespace
    "__DATABASE_URL__" = $databaseUrl
    "__DB_PASSWORD__" = $DbPassword
    "__RDS_ENDPOINT__" = $RdsEndpoint
    "__ORDER_API_IMAGE__" = "$registry/dor-dev/order-api:$ImageTag"
    "__INVENTORY_SERVICE_IMAGE__" = "$registry/dor-dev/inventory-service:$ImageTag"
    "__ROUTING_ENGINE_IMAGE__" = "$registry/dor-dev/routing-engine:$ImageTag"
    "__WORKFLOW_WORKER_IMAGE__" = "$registry/dor-dev/workflow-worker:$ImageTag"
    "__DASHBOARD_IMAGE__" = "$registry/dor-dev/dashboard:$ImageTag"
    "__TEMPORAL_UI_PUBLIC_URL__" = ""
    "__GRAFANA_PUBLIC_URL__" = ""
    "__PROMETHEUS_PUBLIC_URL__" = ""
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

function Apply-ConfigMapFromFile {
    param(
        [string]$Name,
        [string]$FilePath
    )

    $fileName = Split-Path -Leaf $FilePath
    $fromFileArg = "--from-file=$fileName=$FilePath"

    kubectl create configmap $Name `
        --namespace $Namespace `
        $fromFileArg `
        --dry-run=client `
        -o yaml | kubectl apply -f -

    if ($LASTEXITCODE -ne 0) {
        throw "kubectl create/apply configmap failed for $Name"
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
    "temporal-dynamic-config.yaml",
    "temporal-postgresql.yaml"
)

foreach ($template in $orderedTemplates) {
    Apply-Template -FileName $template
}

Apply-ConfigMapFromFile -Name "prometheus-config" -FilePath $prometheusConfigPath
Apply-ConfigMapFromFile -Name "grafana-datasources" -FilePath $grafanaDatasourcePath
Apply-ConfigMapFromFile -Name "grafana-dashboard-provider" -FilePath $grafanaDashboardProviderPath
Apply-ConfigMapFromFile -Name "grafana-dashboards" -FilePath $grafanaDashboardJsonPath

$deploymentTemplates = @(
    "temporal.yaml",
    "temporal-ui.yaml",
    "prometheus.yaml",
    "grafana.yaml",
    "inventory-service.yaml",
    "routing-engine.yaml",
    "order-api.yaml",
    "workflow-worker.yaml"
)

foreach ($template in $deploymentTemplates) {
    Apply-Template -FileName $template
}

if (-not $TemporalUiPublicUrl) {
    $TemporalUiPublicUrl = Get-ServicePublicUrl -ServiceName "temporal-ui" -Port 8080
}

if (-not $GrafanaPublicUrl) {
    $GrafanaPublicUrl = Get-ServicePublicUrl -ServiceName "grafana" -Port 3000
}

if (-not $PrometheusPublicUrl) {
    $PrometheusPublicUrl = Get-ServicePublicUrl -ServiceName "prometheus" -Port 9090
}

$replacements["__TEMPORAL_UI_PUBLIC_URL__"] = $TemporalUiPublicUrl
$replacements["__GRAFANA_PUBLIC_URL__"] = $GrafanaPublicUrl
$replacements["__PROMETHEUS_PUBLIC_URL__"] = $PrometheusPublicUrl

Apply-Template -FileName "dashboard.yaml"

if ($ApplySeedJob) {
    kubectl delete job dor-seed-data -n $Namespace --ignore-not-found
    Apply-Template -FileName "seed-job.yaml"
}

kubectl rollout restart deployment temporal -n $Namespace
kubectl rollout restart deployment temporal-ui -n $Namespace
kubectl rollout restart deployment prometheus -n $Namespace
kubectl rollout restart deployment grafana -n $Namespace
kubectl rollout restart deployment inventory-service -n $Namespace
kubectl rollout restart deployment routing-engine -n $Namespace
kubectl rollout restart deployment order-api -n $Namespace
kubectl rollout restart deployment workflow-worker -n $Namespace
kubectl rollout restart deployment dashboard -n $Namespace

Write-Host "Deployment submitted to namespace '$Namespace'."
if ($TemporalUiPublicUrl) {
    Write-Host "Temporal UI: $TemporalUiPublicUrl"
}
if ($GrafanaPublicUrl) {
    Write-Host "Grafana: $GrafanaPublicUrl"
}
if ($PrometheusPublicUrl) {
    Write-Host "Prometheus: $PrometheusPublicUrl"
}
Write-Host "Check rollout progress with:"
Write-Host "kubectl get pods -n $Namespace"
Write-Host "kubectl get svc -n $Namespace"
