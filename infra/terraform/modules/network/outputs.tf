output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = [for subnet in values(aws_subnet.public) : subnet.id]
}

output "private_app_subnet_ids" {
  description = "Private app subnet IDs."
  value       = [for subnet in values(aws_subnet.private_app) : subnet.id]
}

output "private_data_subnet_ids" {
  description = "Private data subnet IDs."
  value       = [for subnet in values(aws_subnet.private_data) : subnet.id]
}
