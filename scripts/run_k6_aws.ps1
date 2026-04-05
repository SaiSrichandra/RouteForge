param(
    [string]$DashboardBaseUrl = $env:DASHBOARD_BASE_URL
)

if (-not $DashboardBaseUrl) {
    throw "DashboardBaseUrl is required. Pass -DashboardBaseUrl or set DASHBOARD_BASE_URL."
}

$env:BASE_URL = "$DashboardBaseUrl/api/order"
Write-Host "Running k6 against $env:BASE_URL"
k6 run load-tests/order-submissions.js
