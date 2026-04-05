# Terraform

This directory contains the Terraform configuration for the AWS deployment.

## What is included

- `modules/network`
  - VPC
  - internet gateway
  - NAT gateway
  - public, private application, and private data subnets

- `modules/ecr`
  - ECR repositories for each service image
  - lifecycle policy to trim old images

- `modules/rds`
  - PostgreSQL instance
  - subnet group
  - security group
  - parameter group

- `modules/eks`
  - EKS cluster
  - managed node group
  - IAM roles
  - CloudWatch log group

- `environments/dev`
  - provider configuration
  - module wiring
  - example `tfvars`
  - example remote-state backend file

## Intended apply order

1. bootstrap AWS account access and Terraform remote state
2. `terraform init`
3. `terraform plan`
4. `terraform apply`
5. push images to ECR
6. deploy workloads to EKS

## Notes

- This configuration is designed for a dedicated dev or sandbox AWS account.
- It is designed for a dedicated dev/sandbox AWS account first.
- Before apply, confirm your chosen Kubernetes version is supported in your target AWS region.
