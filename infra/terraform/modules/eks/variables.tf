variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for EKS."
  type        = string
}

variable "subnet_ids" {
  description = "Private application subnet IDs used by the cluster and node group."
  type        = list(string)
}

variable "instance_types" {
  description = "Managed node group instance types."
  type        = list(string)
}

variable "desired_size" {
  description = "Desired node count."
  type        = number
}

variable "min_size" {
  description = "Minimum node count."
  type        = number
}

variable "max_size" {
  description = "Maximum node count."
  type        = number
}
