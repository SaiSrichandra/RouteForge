variable "aws_region" {
  description = "AWS region for the development environment."
  type        = string
}

variable "project_name" {
  description = "Project slug used for naming AWS resources."
  type        = string
  default     = "dor"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones used by the environment."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks, one per availability zone."
  type        = list(string)
}

variable "private_app_subnet_cidrs" {
  description = "Private application subnet CIDR blocks, one per availability zone."
  type        = list(string)
}

variable "private_data_subnet_cidrs" {
  description = "Private data subnet CIDR blocks, one per availability zone."
  type        = list(string)
}

variable "ecr_repository_names" {
  description = "Container repositories for application services."
  type        = list(string)
  default = [
    "order-api",
    "inventory-service",
    "routing-engine",
    "workflow-worker",
    "dashboard",
  ]
}

variable "db_name" {
  description = "Application database name."
  type        = string
  default     = "order_routing"
}

variable "db_username" {
  description = "Master username for PostgreSQL."
  type        = string
  default     = "dor_admin"
}

variable "db_password" {
  description = "Master password for PostgreSQL."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class for the PostgreSQL instance."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Initial RDS storage allocation in GiB."
  type        = number
  default     = 20
}

variable "db_backup_retention_period" {
  description = "Automated backup retention in days. Free-tier-friendly default is 1."
  type        = number
  default     = 1
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "dor-dev"
}

variable "eks_kubernetes_version" {
  description = "Kubernetes version for the EKS cluster. Confirm support in your chosen region before apply."
  type        = string
  default     = "1.34"
}

variable "eks_node_instance_types" {
  description = "Instance types used by the EKS managed node group."
  type        = list(string)
  default     = ["t3.micro"]
}

variable "eks_node_desired_size" {
  description = "Desired node count for the primary node group."
  type        = number
  default     = 1
}

variable "eks_node_min_size" {
  description = "Minimum node count for the primary node group."
  type        = number
  default     = 1
}

variable "eks_node_max_size" {
  description = "Maximum node count for the primary node group."
  type        = number
  default     = 1
}
