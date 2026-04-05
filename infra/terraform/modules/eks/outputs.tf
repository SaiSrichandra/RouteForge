output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "EKS control plane endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 cluster CA data."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Cluster security group ID."
  value       = aws_security_group.cluster.id
}

output "node_security_group_id" {
  description = "Node security group ID."
  value       = aws_security_group.node.id
}
