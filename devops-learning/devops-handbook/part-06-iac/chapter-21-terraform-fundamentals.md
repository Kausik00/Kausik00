# Chapter 21: Terraform — HCL, Providers, and Modules

*DevOps Handbook — Pages 92–95 of this PDF edition*
---

## 21.1 Terraform overview

**Terraform** (HashiCorp / OpenTofu fork) is the most widely used multi-cloud IaC tool. You write **HCL** (HashiCorp Configuration Language); Terraform calls cloud APIs via **providers**.

```bash
terraform init      # Download providers, init backend
terraform fmt       # Format code
terraform validate  # Syntax check
terraform plan      # Preview changes
terraform apply     # Create/update/destroy resources
terraform destroy   # Tear down (use carefully)
```

---

## 21.2 Basic configuration

`main.tf`:

```hcl
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "prod/vpc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "logs" {
  bucket = "${var.project_name}-logs-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

`variables.tf`:

```hcl
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}
```

`outputs.tf`:

```hcl
output "logs_bucket_name" {
  value       = aws_s3_bucket.logs.id
  description = "Name of the logs S3 bucket"
}
```

Apply with: `terraform apply -var="project_name=myapp" -var="environment=dev"`

---

## 21.3 Resources, data sources, and dependencies

### Data sources — read existing infrastructure

```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"
}
```

### Implicit vs explicit dependencies

Terraform infers dependencies from references. Use `depends_on` when ordering matters but no attribute reference exists.

---

## 21.4 Modules — reusable infrastructure

`modules/vpc/main.tf`:

```hcl
resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  tags = { Name = var.name }
}

resource "aws_subnet" "public" {
  count             = length(var.public_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  map_public_ip_on_launch = true
}
```

Using the module:

```hcl
module "vpc" {
  source = "./modules/vpc"

  name                = "prod-vpc"
  cidr_block          = "10.0.0.0/16"
  public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  availability_zones  = ["us-east-1a", "us-east-1b"]
}
```

Publish modules to **Terraform Registry** or private registries for org-wide reuse.

---

## 21.5 Lifecycle meta-arguments

```hcl
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t3.micro"

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = false   # Set true for prod databases
    ignore_changes        = [tags["LastReboot"]]  # Ignore specific drift
  }
}
```

---

## 21.6 Workspaces and environments

```bash
terraform workspace list
terraform workspace new staging
terraform workspace select prod
```

Workspaces share the same backend key by default—often **separate directories per environment** (with separate state keys) is clearer for production.

---

## 21.7 CI/CD integration

GitHub Actions example (plan on PR):

```yaml
- name: Terraform Plan
  run: |
    terraform init -input=false
    terraform plan -input=false -no-color -out=tfplan
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Apply only from protected `main` branch after approval.

---

## 21.8 Chapter summary

- Terraform workflow: **init → plan → apply** with remote state.
- Use **variables**, **outputs**, and **modules** for reuse.
- Run `terraform plan` in CI on every PR; apply from trusted pipelines only.

---

## 🧪 Lab 21.1

1. Write Terraform to create an S3 bucket with versioning and encryption.
2. Extract a VPC module with 2 public subnets.
3. Configure S3 backend for remote state.
4. Run plan/apply in a free-tier AWS account.

---

*Next: [Chapter 26 — Docker](../part-07-containers/chapter-26-docker-fundamentals.md)*
