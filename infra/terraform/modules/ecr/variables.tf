variable "name_prefix" {
  description = "Prefix used for resource names."
  type        = string
}

variable "repository_names" {
  description = "ECR repositories to create."
  type        = list(string)
}
