# CI/CD Guide

This repository uses GitHub Actions for both CI and AWS deployment automation.

## CI workflow

The CI workflow lives in [ci.yml](../.github/workflows/ci.yml).

It runs on pull requests and pushes to `main` or `master`, and it validates:

- backend code quality with Ruff
- Python import and syntax health through module compilation
- routing-engine tests
- dashboard production build
- Docker image builds for `order-api`, `inventory-service`, `routing-engine`, `workflow-worker`, and `dashboard`

This is the merge gate for the repository.

## CD workflow

The deploy workflow lives in [cd.yml](../.github/workflows/cd.yml).

It supports two entry points:

- automatic deployment after `CI` succeeds on `main` or `master`
- manual deployment through `workflow_dispatch`

The workflow:

- assumes an AWS IAM role through GitHub OIDC
- builds and pushes versioned images to ECR
- updates kubeconfig for the EKS cluster
- runs the same [push_images.ps1](../scripts/push_images.ps1) and [deploy_eks.ps1](../scripts/deploy_eks.ps1) scripts used for manual AWS deployment
- waits for rollout of Temporal, the app services, Prometheus, Grafana, and the dashboard

This gives the project a full CI/CD story:

- CI proves the repository is safe to merge
- CD publishes the images and rolls the stack out to AWS

## Required GitHub setup

Before CD can run, configure these repository settings.

### Repository variables

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `EKS_CLUSTER_NAME`
- `EKS_NAMESPACE`
- `RDS_ENDPOINT`

Example values:

- `AWS_REGION=us-east-1`
- `AWS_ACCOUNT_ID=<aws-account-id>`
- `EKS_CLUSTER_NAME=dor-dev`
- `EKS_NAMESPACE=dor`
- `RDS_ENDPOINT=<rds-endpoint>`

### Repository secrets

- `AWS_GITHUB_ACTIONS_ROLE_ARN`
- `DOR_DB_PASSWORD`

`DOR_DB_PASSWORD` must match the live RDS password for the `dor_admin` user.

## AWS OIDC role

Create a dedicated IAM role for GitHub Actions and trust the GitHub OIDC provider.

The trust relationship should be scoped to your repo and deploy branch. Replace `<account-id>`, `<owner>`, and `<repo>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": [
            "repo:<owner>/<repo>:ref:refs/heads/main",
            "repo:<owner>/<repo>:ref:refs/heads/master"
          ]
        }
      }
    }
  ]
}
```

For an initial dev environment, the quickest setup is to grant the role deploy access in that account and tighten permissions later.

## Recommended branch policy

1. all feature work lands through pull requests
2. `CI` must pass before merge
3. only `main` or `master` should trigger automatic deployment

## Local equivalents

You can still run the same path locally:

```powershell
python -m compileall services scripts
$env:PYTHONPATH = "services/routing-engine"
python -m pytest services/routing-engine/tests -q
npm.cmd run build --prefix frontend\dashboard
docker compose build order-api inventory-service routing-engine workflow-worker
.\scripts\push_images.ps1 -Tag "manual"
.\scripts\deploy_eks.ps1 -DbPassword "<your-rds-password>" -ImageTag "manual"
```
