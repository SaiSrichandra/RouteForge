variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "kubernetes_cluster_name" {
  description = "Cluster name used for subnet discovery tags."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "Availability zones used by the environment."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs."
  type        = list(string)
}

variable "private_app_subnet_cidrs" {
  description = "Private application subnet CIDRs."
  type        = list(string)
}

variable "private_data_subnet_cidrs" {
  description = "Private data subnet CIDRs."
  type        = list(string)
}
