output "db_endpoint" {
  description = "PostgreSQL endpoint."
  value       = aws_db_instance.this.address
}

output "db_port" {
  description = "PostgreSQL port."
  value       = aws_db_instance.this.port
}

output "security_group_id" {
  description = "Security group attached to the PostgreSQL instance."
  value       = aws_security_group.this.id
}
