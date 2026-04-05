variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID hosting the database."
  type        = string
}

variable "db_subnet_ids" {
  description = "Private data subnet IDs."
  type        = list(string)
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach PostgreSQL."
  type        = list(string)
}

variable "db_name" {
  description = "Database name."
  type        = string
}

variable "db_username" {
  description = "Master username."
  type        = string
}

variable "db_password" {
  description = "Master password."
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "Instance class for RDS."
  type        = string
}

variable "allocated_storage" {
  description = "Storage allocation in GiB."
  type        = number
}

variable "backup_retention_period" {
  description = "Automated backup retention in days."
  type        = number
}
