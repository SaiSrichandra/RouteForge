# AWS Bootstrap Guide

This guide covers the first AWS actions to perform before Terraform and GitHub Actions deployment.

## Goal

Prepare a safe dev account so Terraform and CI/CD can create and manage:

- VPC networking
- ECR repositories
- RDS PostgreSQL
- EKS cluster and worker nodes
- CloudWatch log resources

## Step 1. Choose a region

Pick one region and stay consistent. One practical default is:

- `us-east-1`

## Step 2. Create a Terraform IAM user or role

Fastest path for a personal dev account:

1. Open AWS Console
2. Go to `IAM`
3. Create a user such as `terraform-dor-dev`
4. Enable programmatic access if your account flow asks for access keys

## Step 3. Create local access keys

After creating the IAM user:

1. Create an access key
2. Save:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

Then configure them locally:

```powershell
aws configure
```

Use:

- AWS Access Key ID: your key
- AWS Secret Access Key: your secret
- Default region name: your chosen region, for example `us-east-1`
- Default output format: `json`

## Step 4. Create remote Terraform state storage

Create two things:

1. an S3 bucket for Terraform state
2. a DynamoDB table for state locking

Suggested names:

- S3 bucket: `dor-terraform-state-<your-unique-suffix>`
- DynamoDB table: `dor-terraform-locks`

For the DynamoDB table:

- partition key name: `LockID`
- partition key type: `String`

## Step 5. Fill the Terraform environment files

In dev

1. copy `terraform.tfvars.example` to `terraform.tfvars`
2. copy `backend.hcl.example` to `backend.hcl`
3. replace the placeholders

Important:

- set a real `db_password`
- keep `db_backup_retention_period = 1` if your account is under free-tier restrictions
- use your real state bucket name
- use your real DynamoDB table name
- keep the region consistent everywhere

## Step 6. Create a GitHub Actions deploy role

To automate CD, create a separate IAM role for GitHub Actions using OIDC.

High-level setup:

1. Add the GitHub OIDC identity provider if it does not already exist:
   - provider URL: `https://token.actions.githubusercontent.com`
   - audience: `sts.amazonaws.com`
2. Create a role such as `github-actions-dor-deploy`
3. Trust only your repository and deploy branch
4. Grant the role access for:
   - ECR push
   - EKS cluster access
   - read actions used during rollout verification

The GitHub deploy workflow in cd.yml expects the role ARN in the repository secret `AWS_GITHUB_ACTIONS_ROLE_ARN`.

## Step 7. Configure GitHub repository settings

Add these repository variables:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `EKS_CLUSTER_NAME`
- `EKS_NAMESPACE`
- `RDS_ENDPOINT`

Add these repository secrets:

- `AWS_GITHUB_ACTIONS_ROLE_ARN`
- `DOR_DB_PASSWORD`

`DOR_DB_PASSWORD` must match the live RDS password used by the application in EKS.

## Step 8. Validate the core Terraform values

Before provisioning, confirm:

1. the AWS region
2. the Terraform state bucket name
3. the DynamoDB lock table name
4. the selected availability zones

These values should be reflected consistently in `backend.hcl`, `terraform.tfvars`, and the AWS CLI environment used for deployment.
