# Dev Environment

This environment provisions the AWS foundation for the Distributed Order Routing platform:

- VPC with public, private application, and private data subnets
- ECR repositories for the service images
- PostgreSQL on RDS
- EKS cluster with a managed node group

## Expected workflow

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Replace the placeholder database password.
3. Create an S3 bucket and DynamoDB table for remote Terraform state.
4. Copy `backend.hcl.example` to `backend.hcl` and update it for your account.
5. Run:

```bash
terraform init -backend-config backend.hcl
terraform plan
terraform apply
```
