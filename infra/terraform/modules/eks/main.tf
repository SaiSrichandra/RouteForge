data "aws_iam_policy_document" "cluster_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "node_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.name_prefix}-eks-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.cluster_assume_role.json
}

resource "aws_iam_role_policy_attachment" "cluster" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSServicePolicy",
  ])

  role       = aws_iam_role.cluster.name
  policy_arn = each.value
}

resource "aws_iam_role" "node" {
  name               = "${var.name_prefix}-eks-node-role"
  assume_role_policy = data.aws_iam_policy_document.node_assume_role.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
  ])

  role       = aws_iam_role.node.name
  policy_arn = each.value
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 14
}

resource "aws_security_group" "cluster" {
  name        = "${var.name_prefix}-eks-cluster-sg"
  description = "Control plane security group"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-eks-cluster-sg"
  }
}

resource "aws_security_group" "node" {
  name        = "${var.name_prefix}-eks-node-sg"
  description = "Managed node security group"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-eks-node-sg"
  }
}

resource "aws_security_group_rule" "cluster_from_nodes" {
  type                     = "ingress"
  description              = "Worker nodes to control plane"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.cluster.id
  source_security_group_id = aws_security_group.node.id
}

resource "aws_security_group_rule" "nodes_self" {
  type              = "ingress"
  description       = "Node to node traffic"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.node.id
  self              = true
}

resource "aws_security_group_rule" "nodes_from_cluster" {
  type                     = "ingress"
  description              = "Control plane to nodes"
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  security_group_id        = aws_security_group.node.id
  source_security_group_id = aws_security_group.cluster.id
}

resource "aws_launch_template" "node" {
  name_prefix = "${var.name_prefix}-eks-node-"

  vpc_security_group_ids = [aws_security_group.node.id]

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.cluster_name}-worker"
    }
  }
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler",
  ]

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    security_group_ids      = [aws_security_group.cluster.id]
  }

  depends_on = [
    aws_cloudwatch_log_group.this,
    aws_iam_role_policy_attachment.cluster,
  ]

  tags = {
    Name = var.cluster_name
  }
}

resource "aws_eks_node_group" "primary" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-primary"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = var.instance_types
  ami_type        = "AL2023_x86_64_STANDARD"

  scaling_config {
    desired_size = var.desired_size
    min_size     = var.min_size
    max_size     = var.max_size
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  depends_on = [
    aws_iam_role_policy_attachment.node,
  ]

  tags = {
    Name = "${var.cluster_name}-primary"
  }
}
