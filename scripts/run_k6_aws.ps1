param(
    [string]$DashboardBaseUrl = "http://a9e83f51b01c94702826fd8e8bb7e5cb-660024319.us-east-1.elb.amazonaws.com"
)

$env:BASE_URL = "$DashboardBaseUrl/api/order"
Write-Host "Running k6 against $env:BASE_URL"
k6 run load-tests/order-submissions.js
