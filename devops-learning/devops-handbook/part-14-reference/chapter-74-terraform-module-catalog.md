# Chapter 74: Terraform Module Catalog

*DevOps Handbook — Pages 416–426 of this PDF edition*

This chapter is a catalog of **complete, callable Terraform modules** in the style you would use for a production AWS landing: VPC, EKS, RDS, and the root module that wires them. The code is teaching-grade—trimmed of every brand-specific quirk, but complete enough to show interfaces, versioning, and calling patterns.

Principles for every module here:

| Rule | Practice |
|------|----------|
| Interface | `variables.tf` is the product; keep it small |
| Defaults | Safe defaults (private, encrypted, no public DB) |
| Outputs | Stable names; no leaking random IDs as contracts |
| Version | Semver tags; consumers pin `source` + `version` |
| State | One workspace/state per environment, not per module file |
| Provider | Root configures providers; modules inherit |

Directory layout:

```
infra/
  modules/
    vpc/
    eks/
    rds-postgres/
    kms/
  live/
    prod/
      us-east-1/
        main.tf
        variables.tf
        terraform.tfvars
        backend.tf
```

---

## 74.1 Root calling pattern (live/prod)

```hcl
# live/prod/us-east-1/versions.tf
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  backend "s3" {
    bucket         = "acme-tfstate-prod"
    key            = "us-east-1/platform/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "acme-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = "prod"
      ManagedBy   = "terraform"
      System      = "shopstream-platform"
    }
  }
}
```

```hcl
# live/prod/us-east-1/main.tf
module "kms" {
  source = "../../../modules/kms"
  name   = "shopstream-prod"
}

module "vpc" {
  source = "../../../modules/vpc"

  name               = "shopstream-prod"
  cidr               = "10.40.0.0/16"
  azs                = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets    = ["10.40.0.0/20", "10.40.16.0/20", "10.40.32.0/20"]
  public_subnets     = ["10.40.48.0/20", "10.40.64.0/20", "10.40.80.0/20"]
  enable_nat_gateway = true
  single_nat_gateway = false
}

module "eks" {
  source = "../../../modules/eks"

  cluster_name       = "shopstream-prod"
  kubernetes_version = "1.30"
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  kms_key_arn        = module.kms.key_arn
}

module "rds" {
  source = "../../../modules/rds-postgres"

  identifier          = "shopstream-prod"
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_subnet_ids
  allowed_cidr_blocks = module.vpc.private_subnets_cidr_blocks
  kms_key_arn         = module.kms.key_arn
  instance_class      = "db.r6g.xlarge"
  engine_version      = "16.3"
}
```

Pin published modules instead of relative paths when the module is stable:

```hcl
module "vpc" {
  source  = "app.terraform.io/acme/vpc/aws"
  version = "2.4.1"
  # ...
}
```

---

## 74.2 Module: KMS (dependency of the others)

`modules/kms/variables.tf`

```hcl
variable "name" {
  type        = string
  description = "Human name used in aliases and tags."
}
```

`modules/kms/main.tf`

```hcl
resource "aws_kms_key" "this" {
  description             = "Platform key for ${var.name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}
```

`modules/kms/outputs.tf`

```hcl
output "key_arn" {
  value = aws_kms_key.this.arn
}

output "key_id" {
  value = aws_kms_key.this.key_id
}
```

---

## 74.3 Module: VPC

This module creates a three-AZ VPC, public and private subnets, NAT gateways per AZ (HA), route tables, and VPC flow logs.

`modules/vpc/variables.tf`

```hcl
variable "name" { type = string }
variable "cidr" { type = string }

variable "azs" {
  type = list(string)
}

variable "private_subnets" {
  type = list(string)
}

variable "public_subnets" {
  type = list(string)
}

variable "enable_nat_gateway" {
  type    = bool
  default = true
}

variable "single_nat_gateway" {
  type    = bool
  default = false
  description = "Set true only in nonprod to save cost."
}

variable "enable_flow_logs" {
  type    = bool
  default = true
}
```

Validation example:

```hcl
variable "cidr" {
  type = string
  validation {
    condition     = can(cidrhost(var.cidr, 0))
    error_message = "cidr must be a valid IPv4 CIDR."
  }
}
```

`modules/vpc/main.tf` (core resources)

```hcl
resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = var.name }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "private" {
  count                   = length(var.private_subnets)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.private_subnets[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = false
  tags = {
    Name                              = "${var.name}-private-${var.azs[count.index]}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_subnet" "public" {
  count                   = length(var.public_subnets)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnets[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true
  tags = {
    Name                     = "${var.name}-public-${var.azs[count.index]}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.azs)) : 0
  domain = "vpc"
}

resource "aws_nat_gateway" "this" {
  count         = length(aws_eip.nat)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[var.single_nat_gateway ? 0 : count.index].id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
}

resource "aws_route" "public_inet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = length(aws_subnet.private)
  vpc_id = aws_vpc.this.id
}

resource "aws_route" "private_nat" {
  count                  = var.enable_nat_gateway ? length(aws_route_table.private) : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[var.single_nat_gateway ? 0 : count.index].id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
```

Flow logs (abbreviated):

```hcl
resource "aws_flow_log" "this" {
  count                = var.enable_flow_logs ? 1 : 0
  vpc_id               = aws_vpc.this.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow[0].arn
  iam_role_arn         = aws_iam_role.flow[0].arn
}
```

Outputs:

```hcl
output "vpc_id" { value = aws_vpc.this.id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "private_subnets_cidr_blocks" { value = aws_subnet.private[*].cidr_block }
output "nat_gateway_ids" { value = aws_nat_gateway.this[*].id }
```

Calling notes: tag subnets for the AWS load balancer controller. Never reuse a CIDR that overlaps VPN or another VPC you will peer.

---

## 74.4 Module: EKS

This is a *shape*, not a replacement for the official `terraform-aws-modules/eks` module. In production, prefer the community module *or* wrap it. The catalog shows the control-plane contract you must expose.

`modules/eks/variables.tf`

```hcl
variable "cluster_name" { type = string }
variable "kubernetes_version" { type = string }
variable "vpc_id" { type = string }

variable "private_subnet_ids" {
  type = list(string)
}

variable "kms_key_arn" { type = string }

variable "endpoint_public_access" {
  type    = bool
  default = false
}

variable "system_node_instance_types" {
  type    = list(string)
  default = ["m6i.large"]
}
```

`modules/eks/main.tf` excerpts:

```hcl
resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
  ])
  role       = aws_iam_role.cluster.name
  policy_arn = each.value
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
  }

  encryption_config {
    provider { key_arn = var.kms_key_arn }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.system_node_instance_types
  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 6
  }
  update_config {
    max_unavailable = 1
  }
  labels = { role = "system" }
  taint {
    key    = "CriticalAddonsOnly"
    value  = "true"
    effect = "NO_SCHEDULE"
  }
}
```

IRSA OIDC provider:

```hcl
data "tls_certificate" "oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "this" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.oidc.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
}
```

Outputs the app teams need:

```hcl
output "cluster_name" { value = aws_eks_cluster.this.name }
output "cluster_endpoint" { value = aws_eks_cluster.this.endpoint }
output "cluster_ca" { value = aws_eks_cluster.this.certificate_authority[0].data }
output "oidc_provider_arn" { value = aws_iam_openid_connect_provider.this.arn }
output "oidc_issuer" { value = aws_eks_cluster.this.identity[0].oidc[0].issuer }
```

Do not put kubeconfig in state as a sensitive output if you can avoid it; generate it in CI from `aws eks update-kubeconfig`.

---

## 74.5 Module: RDS PostgreSQL

```hcl
variable "identifier" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_cidr_blocks" { type = list(string) }
variable "kms_key_arn" { type = string }
variable "instance_class" { type = string }
variable "engine_version" { type = string }

variable "multi_az" {
  type    = bool
  default = true
}

variable "backup_retention" {
  type    = number
  default = 14
}
```

```hcl
resource "aws_db_subnet_group" "this" {
  name       = var.identifier
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "this" {
  name   = "${var.identifier}-rds"
  vpc_id = var.vpc_id

  ingress {
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
}

resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "master" {
  name       = "${var.identifier}/master"
  kms_key_id = var.kms_key_arn
}

resource "aws_secretsmanager_secret_version" "master" {
  secret_id = aws_secretsmanager_secret.master.id
  secret_string = jsonencode({
    username = "app_master"
    password = random_password.master.result
  })
}

resource "aws_db_instance" "this" {
  identifier                            = var.identifier
  engine                                = "postgres"
  engine_version                        = var.engine_version
  instance_class                        = var.instance_class
  allocated_storage                     = 100
  max_allocated_storage                 = 500
  storage_encrypted                     = true
  kms_key_id                            = var.kms_key_arn
  username                              = "app_master"
  password                              = random_password.master.result
  db_subnet_group_name                  = aws_db_subnet_group.this.name
  vpc_security_group_ids                = [aws_security_group.this.id]
  multi_az                              = var.multi_az
  publicly_accessible                   = false
  backup_retention_period               = var.backup_retention
  deletion_protection                   = true
  skip_final_snapshot                   = false
  final_snapshot_identifier             = "${var.identifier}-final"
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]
  auto_minor_version_upgrade            = true
  copy_tags_to_snapshot                 = true
}
```

Outputs:

```hcl
output "endpoint" { value = aws_db_instance.this.address }
output "port" { value = aws_db_instance.this.port }
output "secret_arn" { value = aws_secretsmanager_secret.master.arn }
output "security_group_id" { value = aws_security_group.this.id }
```

Prefer IRSA + Secrets Store CSI over stuffing the password into Kubernetes Secrets via Terraform when possible. If Terraform must create the Secret, mark it sensitive and never print it in CI logs.

Tighten the SG: in a real catalog, ingress should come from the EKS node or pod SG, not the entire private CIDR.

---

## 74.6 IRSA helper module (calling pattern)

```hcl
module "checkout_irsa" {
  source = "../../../modules/irsa"

  name                = "checkout"
  oidc_provider_arn   = module.eks.oidc_provider_arn
  oidc_issuer         = module.eks.oidc_issuer
  namespace           = "shop"
  service_account     = "checkout"
  policy_json         = data.aws_iam_policy_document.checkout.json
}
```

Trust policy fragment:

```hcl
data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account}"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}
```

---

## 74.7 Workspaces vs directories

| Approach | When |
|----------|------|
| Directories `live/prod`, `live/staging` | Clear blast radius; recommended |
| Terraform workspaces | Small teams, identical topology |
| One state for all accounts | Never |

```bash
terraform -chdir=live/prod/us-east-1 init
terraform -chdir=live/prod/us-east-1 plan -out=tfplan
terraform -chdir=live/prod/us-east-1 apply tfplan
```

CI concurrency: one apply per state key. Use GitHub `concurrency: terraform-prod-use1`.

---

## 74.8 Testing and policy

```bash
terraform fmt -recursive
terraform validate
tflint --recursive
checkov -d modules/vpc
terraform test
```

`terraform test` example:

```hcl
# tests/vpc.tftest.hcl
run "cidr_valid" {
  command = plan
  variables {
    name            = "test"
    cidr            = "10.90.0.0/16"
    azs             = ["us-east-1a", "us-east-1b"]
    private_subnets = ["10.90.0.0/20", "10.90.16.0/20"]
    public_subnets  = ["10.90.32.0/20", "10.90.48.0/20"]
  }
}
```

OPA/Conftest: deny `publicly_accessible = true` on RDS, deny `endpoint_public_access` in prod tfvars.

---

## 74.9 Module versioning and promotion

1. Change module in a PR with a changelog.
2. Tag `v2.5.0`.
3. Bump `version` in staging live root; apply; soak.
4. Bump prod.

Breaking changes: removing an output, renaming a resource without `moved` blocks, shrinking CIDRs.

```hcl
moved {
  from = aws_nat_gateway.this
  to   = aws_nat_gateway.this[0]
}
```

---

## 74.10 Anti-patterns

| Anti-pattern | Result |
|--------------|--------|
| Count of unrelated resources in one module | Un-reviewable plans |
| `file()` of kubeconfig into Git | Secret leak |
| `terraform destroy` in prod CI | Career-limiting |
| Inline provider in child module | Alias hell |
| Random names without `prevent_destroy` | Recreate of RDS |
| Spreading one VPC across two states | Race and orphan ENIs |

Lifecycle guards:

```hcl
lifecycle {
  prevent_destroy = true
}
```

Use on RDS, KMS, and the VPC itself in prod.

---

## 74.11 Remote state sharing to app repos

Platform state exposes a read-only policy for app Terraform:

```hcl
data "terraform_remote_state" "platform" {
  backend = "s3"
  config = {
    bucket = "acme-tfstate-prod"
    key    = "us-east-1/platform/terraform.tfstate"
    region = "us-east-1"
  }
}

resource "aws_security_group_rule" "from_nodes" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = data.terraform_remote_state.platform.outputs.rds_sg_id
  source_security_group_id = data.terraform_remote_state.platform.outputs.node_sg_id
}
```

Alternatively, publish outputs to SSM Parameter Store so app repos do not need S3 state access.

---

## 74.12 Checklist for a new environment

1. New AWS account or OU, SCPs in place.
2. Bootstrap bucket + DynamoDB lock table (can be a tiny bootstrap module in the management account).
3. `terraform apply` KMS → VPC → EKS → RDS in that order (or one root that does all with `depends_on` implicit via references).
4. Register OIDC; install cluster addons (CNI, CSI, CoreDNS) via a follow-up module.
5. Hand app teams: subnet IDs, OIDC ARN, RDS endpoint SSM path.
6. Drift: weekly `plan` in CI; no-op expected.

This catalog is the skeleton of a platform. Grow it with WAF, CloudFront, and MSK modules using the same interface style: **few variables, encrypted by default, outputs as contracts**.

---

## 74.13 Addon module (cluster after EKS exists)

Do not stuff aws-load-balancer-controller, EBS CSI, and CoreDNS patches into the EKS module. A second root or module `eks-addons` takes `cluster_name` and `oidc_provider_arn` as inputs. That split lets you upgrade addons without a plan that also offers to replace the control plane.

```hcl
module "addons" {
  source             = "../../../modules/eks-addons"
  cluster_name       = module.eks.cluster_name
  oidc_provider_arn  = module.eks.oidc_provider_arn
  vpc_id             = module.vpc.vpc_id
}
```

Helm releases in Terraform (`helm_release`) are convenient and also a lock-in: GitOps for addons is often cleaner. Pick one control plane for addons, not both.

---

## 74.14 Variable design rules (enforced in code review)

1. No `variable "everything" { type = any }`.
2. Booleans default to the **secure** side (`publicly_accessible = false`).
3. Lists of AZs and subnets must be the same length — `validation` block.
4. Do not pass the entire `aws_eks_cluster` object into children; pass IDs/ARNs.
5. Names include environment: collision across accounts is still painful in logs.

```hcl
variable "azs" { type = list(string) }

variable "private_subnets" {
  type = list(string)
  validation {
    condition     = length(var.private_subnets) == length(var.azs)
    error_message = "private_subnets and azs length must match."
  }
}
```

---

## 74.15 Plan-reading checklist for reviewers

| Plan line | Question |
|-----------|----------|
| `must be replaced` | Is this RDS/KMS/VPC? Stop. |
| `forces replacement` on subnet | Will ENIs/pods survive? |
| `0 to 1` IAM policy | Least privilege? |
| `1 to 0` security group rule | Who depends on it? |
| tags only | Still can restart some AWS APIs; usually OK |

Require the plan artifact as a build attachment. “I applied from my laptop because CI was red” is how Atlas Freight (Chapter 76) happens.
