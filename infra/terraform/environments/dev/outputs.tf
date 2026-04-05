output "vpc_id" {
  description = "VPC ID for the dev environment."
  value       = module.network.vpc_id
}

output "private_app_subnet_ids" {
  description = "Private application subnets used by EKS workloads."
  value       = module.network.private_app_subnet_ids
}

output "ecr_repository_urls" {
  description = "ECR repository URLs keyed by service name."
  value       = module.ecr.repository_urls
}

output "rds_endpoint" {
  description = "PostgreSQL endpoint."
  value       = module.rds.db_endpoint
}

output "rds_security_group_id" {
  description = "Security group attached to the PostgreSQL instance."
  value       = module.rds.security_group_id
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Cluster security group ID."
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "Node security group ID."
  value       = module.eks.node_security_group_id
}
