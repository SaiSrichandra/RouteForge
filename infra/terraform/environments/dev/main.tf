locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

module "network" {
  source = "../../modules/network"

  name_prefix              = local.name_prefix
  kubernetes_cluster_name  = var.eks_cluster_name
  vpc_cidr                 = var.vpc_cidr
  availability_zones       = var.availability_zones
  public_subnet_cidrs      = var.public_subnet_cidrs
  private_app_subnet_cidrs = var.private_app_subnet_cidrs
  private_data_subnet_cidrs = var.private_data_subnet_cidrs
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix       = local.name_prefix
  repository_names  = var.ecr_repository_names
}

module "rds" {
  source = "../../modules/rds"

  name_prefix             = local.name_prefix
  vpc_id                  = module.network.vpc_id
  db_subnet_ids           = module.network.private_data_subnet_ids
  allowed_cidr_blocks     = var.private_app_subnet_cidrs
  db_name                 = var.db_name
  db_username             = var.db_username
  db_password             = var.db_password
  db_instance_class       = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  backup_retention_period = var.db_backup_retention_period
}

module "eks" {
  source = "../../modules/eks"

  name_prefix        = local.name_prefix
  cluster_name       = var.eks_cluster_name
  kubernetes_version = var.eks_kubernetes_version
  vpc_id             = module.network.vpc_id
  subnet_ids         = module.network.private_app_subnet_ids
  instance_types     = var.eks_node_instance_types
  desired_size       = var.eks_node_desired_size
  min_size           = var.eks_node_min_size
  max_size           = var.eks_node_max_size
}
