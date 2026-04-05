resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  for_each = {
    for index, cidr in var.public_subnet_cidrs :
    index => {
      cidr = cidr
      az   = var.availability_zones[index]
    }
  }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = {
    Name                                             = "${var.name_prefix}-public-${each.value.az}"
    "kubernetes.io/role/elb"                         = "1"
    "kubernetes.io/cluster/${var.kubernetes_cluster_name}" = "shared"
  }
}

resource "aws_subnet" "private_app" {
  for_each = {
    for index, cidr in var.private_app_subnet_cidrs :
    index => {
      cidr = cidr
      az   = var.availability_zones[index]
    }
  }

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = {
    Name                                                  = "${var.name_prefix}-private-app-${each.value.az}"
    "kubernetes.io/role/internal-elb"                     = "1"
    "kubernetes.io/cluster/${var.kubernetes_cluster_name}" = "shared"
  }
}

resource "aws_subnet" "private_data" {
  for_each = {
    for index, cidr in var.private_data_subnet_cidrs :
    index => {
      cidr = cidr
      az   = var.availability_zones[index]
    }
  }

  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = {
    Name = "${var.name_prefix}-private-data-${each.value.az}"
  }
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.name_prefix}-nat-eip"
  }
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = values(aws_subnet.public)[0].id

  tags = {
    Name = "${var.name_prefix}-nat"
  }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.name_prefix}-public-rt"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = {
    Name = "${var.name_prefix}-private-rt"
  }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_app" {
  for_each       = aws_subnet.private_app
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_data" {
  for_each       = aws_subnet.private_data
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}
