param(
    [string]$AwsRegion = "us-east-1",
    [string]$ClusterName = "dor-dev",
    [string]$Namespace = "dor",
    [string]$NodegroupName = "dor-dev-primary",
    [string]$RdsInstanceIdentifier = "dor-dev-postgres",
    [int]$NodegroupMaxSize = 3,
    [switch]$KeepRdsRunning
)

$deployments = @(
    "dashboard",
    "inventory-service",
    "order-api",
    "routing-engine",
    "workflow-worker",
    "temporal",
    "temporal-postgresql",
    "temporal-ui",
    "prometheus",
    "grafana"
)

aws eks update-kubeconfig --region $AwsRegion --name $ClusterName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update kubeconfig for $ClusterName"
}

kubectl patch cronjob dor-restock-inventory -n $Namespace --type merge --patch '{\"spec\":{\"suspend\":true}}'
kubectl delete jobs --all -n $Namespace --ignore-not-found

foreach ($deployment in $deployments) {
    kubectl get deployment $deployment -n $Namespace *> $null
    if ($LASTEXITCODE -eq 0) {
        kubectl scale deployment $deployment -n $Namespace --replicas=0
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to scale deployment/$deployment to 0"
        }
    }
}

aws eks update-nodegroup-config `
    --region $AwsRegion `
    --cluster-name $ClusterName `
    --nodegroup-name $NodegroupName `
    --scaling-config minSize=0,maxSize=$NodegroupMaxSize,desiredSize=0

if ($LASTEXITCODE -ne 0) {
    throw "Failed to scale nodegroup $NodegroupName down to zero"
}

if (-not $KeepRdsRunning) {
    aws rds stop-db-instance `
        --region $AwsRegion `
        --db-instance-identifier $RdsInstanceIdentifier

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop RDS instance $RdsInstanceIdentifier"
    }
}

Write-Host "Sleep mode submitted."
Write-Host "Check status with:"
Write-Host "kubectl get pods -n $Namespace"
Write-Host "aws eks describe-nodegroup --region $AwsRegion --cluster-name $ClusterName --nodegroup-name $NodegroupName --query 'nodegroup.scalingConfig'"
if (-not $KeepRdsRunning) {
    Write-Host "aws rds describe-db-instances --region $AwsRegion --db-instance-identifier $RdsInstanceIdentifier --query 'DBInstances[0].DBInstanceStatus'"
}
