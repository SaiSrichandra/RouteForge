param(
    [string]$AwsRegion = "us-east-1",
    [string]$ClusterName = "dor-dev",
    [string]$Namespace = "dor",
    [string]$NodegroupName = "dor-dev-primary",
    [string]$RdsInstanceIdentifier = "dor-dev-postgres",
    [string]$AwsAccountId = $env:AWS_ACCOUNT_ID,
    [Parameter(Mandatory = $true)]
    [string]$DbPassword,
    [string]$RdsEndpoint = $env:RDS_ENDPOINT,
    [int]$DesiredNodes = 6,
    [int]$MaxNodes = 6,
    [switch]$ApplySeedJob
)

if (-not $AwsAccountId) {
    throw "AwsAccountId is required. Pass -AwsAccountId or set AWS_ACCOUNT_ID."
}

if (-not $RdsEndpoint) {
    throw "RdsEndpoint is required. Pass -RdsEndpoint or set RDS_ENDPOINT."
}

Write-Host "Starting clean reset for namespace '$Namespace'..."

aws rds start-db-instance `
    --region $AwsRegion `
    --db-instance-identifier $RdsInstanceIdentifier 2>$null

$dbReady = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $status = aws rds describe-db-instances `
        --region $AwsRegion `
        --db-instance-identifier $RdsInstanceIdentifier `
        --query "DBInstances[0].DBInstanceStatus" `
        --output text

    if ($status -eq "available") {
        $dbReady = $true
        break
    }

    Write-Host "Waiting for RDS to become available..."
    Start-Sleep -Seconds 20
}

if (-not $dbReady) {
    throw "RDS instance $RdsInstanceIdentifier did not become available in time"
}

Write-Host "Scaling node group '$NodegroupName' to $DesiredNodes node(s)..."
aws eks update-nodegroup-config `
    --region $AwsRegion `
    --cluster-name $ClusterName `
    --nodegroup-name $NodegroupName `
    --scaling-config minSize=$DesiredNodes,maxSize=$MaxNodes,desiredSize=$DesiredNodes

if ($LASTEXITCODE -ne 0) {
    throw "Failed to scale nodegroup $NodegroupName"
}

aws eks update-kubeconfig --region $AwsRegion --name $ClusterName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update kubeconfig for $ClusterName"
}

$namespaceExists = kubectl get namespace $Namespace --ignore-not-found -o name
if ($namespaceExists) {
    Write-Host "Deleting namespace '$Namespace'..."
    kubectl delete namespace $Namespace --wait=false
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to delete namespace $Namespace"
    }

    $namespaceDeleted = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        kubectl get namespace $Namespace --ignore-not-found -o name *> $null
        if ($LASTEXITCODE -ne 0 -or -not (kubectl get namespace $Namespace --ignore-not-found -o name 2>$null)) {
            $namespaceDeleted = $true
            break
        }

        Write-Host "Waiting for namespace '$Namespace' to finish deleting..."
        Start-Sleep -Seconds 10
    }

    if (-not $namespaceDeleted) {
        throw "Namespace $Namespace did not delete in time"
    }
}

$deployArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "deploy_eks.ps1"),
    "-AwsRegion", $AwsRegion,
    "-ClusterName", $ClusterName,
    "-Namespace", $Namespace,
    "-AwsAccountId", $AwsAccountId,
    "-DbPassword", $DbPassword,
    "-RdsEndpoint", $RdsEndpoint
)

if ($ApplySeedJob) {
    $deployArgs += "-ApplySeedJob"
}

Write-Host "Re-deploying clean stack..."
& powershell @deployArgs
if ($LASTEXITCODE -ne 0) {
    throw "deploy_eks.ps1 failed during clean reset"
}

Write-Host "Clean reset submitted."
Write-Host "Check status with:"
Write-Host "kubectl get pods -n $Namespace"
Write-Host "kubectl get svc -n $Namespace"
