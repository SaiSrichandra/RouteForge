param(
    [string]$AwsRegion = "us-east-1",
    [string]$AwsAccountId = "565582985513",
    [string]$Tag = "latest"
)

$registry = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$images = @(
    @{ Name = "order-api"; Repo = "dor-dev/order-api"; Context = "services/order-api" },
    @{ Name = "inventory-service"; Repo = "dor-dev/inventory-service"; Context = "services/inventory-service" },
    @{ Name = "routing-engine"; Repo = "dor-dev/routing-engine"; Context = "services/routing-engine" },
    @{ Name = "workflow-worker"; Repo = "dor-dev/workflow-worker"; Context = "services/workflow-worker" },
    @{ Name = "dashboard"; Repo = "dor-dev/dashboard"; Context = "frontend/dashboard" }
)

aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $registry

foreach ($image in $images) {
    $uri = "$registry/$($image.Repo):$Tag"
    Write-Host "Building $($image.Name) -> $uri"
    docker build -t $uri $image.Context
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed for $($image.Name)"
    }

    Write-Host "Pushing $uri"
    docker push $uri
    if ($LASTEXITCODE -ne 0) {
        throw "Docker push failed for $($image.Name)"
    }
}
