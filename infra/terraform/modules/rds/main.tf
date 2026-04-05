resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.db_subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnets"
  }
}

resource "aws_security_group" "this" {
  name        = "${var.name_prefix}-rds-sg"
  description = "PostgreSQL access for the order routing platform"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from application subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-rds-sg"
  }
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-postgres16"
  family = "postgres16"

  parameter {
    name  = "log_min_duration_statement"
    value = "250"
  }

  tags = {
    Name = "${var.name_prefix}-postgres16"
  }
}

resource "aws_db_instance" "this" {
  identifier                   = "${var.name_prefix}-postgres"
  engine                       = "postgres"
  engine_version               = "16"
  instance_class               = var.db_instance_class
  allocated_storage            = var.allocated_storage
  max_allocated_storage        = var.allocated_storage * 2
  db_name                      = var.db_name
  username                     = var.db_username
  password                     = var.db_password
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [aws_security_group.this.id]
  parameter_group_name         = aws_db_parameter_group.this.name
  skip_final_snapshot          = true
  deletion_protection          = false
  backup_retention_period      = var.backup_retention_period
  storage_encrypted            = true
  publicly_accessible          = false
  multi_az                     = false
  auto_minor_version_upgrade   = true
  performance_insights_enabled = true

  tags = {
    Name = "${var.name_prefix}-postgres"
  }
}
