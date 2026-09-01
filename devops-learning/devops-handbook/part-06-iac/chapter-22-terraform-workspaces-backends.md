# Chapter 22: Terraform — Workspaces, Backends, and CI Integration

*DevOps Handbook — Part VI, Pages 411–430*

---

## 22.1 Why remote state and backends matter

Terraform's **state file** is the source of truth mapping HCL resource addresses to real cloud IDs. Local state on a laptop does not scale for teams: it cannot be shared, locked, or audited. A **backend** configures where Terraform stores state and how it acquires **locks** during `plan` and `apply`.

| Backend type | Locking | Best for |
|--------------|---------|----------|
| `local` | None | Solo learning only |
| `s3` + DynamoDB | Yes | AWS teams |
| `azurerm` | Yes | Azure |
| `gcs` | Yes | GCP |
| `remote` (Terraform Cloud/Enterprise) | Yes | Org policy, run UI, Sentinel |
| `kubernetes` | Via API | GitOps-native shops |

Remote state enables collaboration, CI pipelines, and disaster recovery. Treat state as sensitive: it often contains secrets even when outputs are marked `sensitive`.

---

## 22.2 Configuring S3 backend with locking

`backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "acme-terraform-state"
    key            = "networking/vpc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:123456789012:key/abcd-1234"
  }
}
```

Bootstrap the backend itself with a one-time local state apply, or use a separate `bootstrap/` directory:

```hcl
# bootstrap/main.tf — run once with local backend
resource "aws_s3_bucket" "state" {
  bucket = "acme-terraform-state"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_dynamodb_table" "locks" {
  name         = "terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

### Partial backend configuration

Pass backend settings at `init` time for multi-environment reuse:

```bash
terraform init \
  -backend-config="bucket=acme-terraform-state" \
  -backend-config="key=prod/app/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=terraform-locks"
```

Use `backend.hcl` files per environment and `-backend-config=backend-prod.hcl`.

---

## 22.3 Terraform workspaces

**Workspaces** partition a single configuration into multiple isolated state instances within the same backend. Each workspace gets its own state object (for S3 backends, the key becomes `env:/<workspace>/...`).

```bash
terraform workspace list
terraform workspace new staging
terraform workspace select prod
terraform workspace show
```

Reference workspace in HCL:

```hcl
locals {
  environment = terraform.workspace

  instance_type = {
    dev     = "t3.micro"
    staging = "t3.small"
    prod    = "m6i.large"
  }[terraform.workspace]
}

resource "aws_instance" "app" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = local.instance_type
  tags = {
    Environment = local.environment
  }
}
```

### Workspaces vs directory-per-environment

| Approach | Pros | Cons |
|----------|------|------|
| **Workspaces** | One codebase, quick switching | Easy to apply to wrong workspace |
| **Separate directories** (`env/prod`, `env/staging`) | Explicit, clearer in CI | Duplication unless using modules |
| **Separate repos** | Strong blast-radius isolation | Harder to keep modules in sync |

Production teams often prefer **separate state keys per environment** (directory or `-backend-config`) over workspaces alone, because `terraform workspace select` mistakes have caused real outages.

---

## 22.4 State operations and safety

```bash
terraform state list
terraform state show aws_instance.app
terraform state mv aws_instance.old aws_instance.new
terraform state rm aws_instance.orphan   # Remove from state, not from cloud
terraform import aws_instance.app i-0abc123def456
```

**`terraform state rm`** does not destroy the resource—it only forgets it. **`terraform import`** adopts existing infrastructure into state.

For large refactors, use **`moved` blocks** (Terraform 1.1+):

```hcl
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}
```

Enable **state encryption**, **versioning** on the S3 bucket, and restrict IAM to CI roles and break-glass admin roles only.

---

## 22.5 CI/CD integration patterns

### Pull request: plan only

```yaml
# .github/workflows/terraform.yml
name: Terraform
on:
  pull_request:
    paths: ['infra/**']
  push:
    branches: [main]
    paths: ['infra/**']

permissions:
  id-token: write   # OIDC
  contents: read
  pull-requests: write

jobs:
  plan:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: infra
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.0

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-terraform-plan
          aws-region: us-east-1

      - run: terraform init -input=false
      - run: terraform fmt -check -recursive
      - run: terraform validate
      - run: terraform plan -input=false -no-color -out=tfplan

      - uses: actions/upload-artifact@v4
        with:
          name: tfplan
          path: infra/tfplan
```

Post plan output as a PR comment with `terraform show -no-color tfplan` or tools like **atlantis** or **terraform-cloud** run tasks.

### Main branch: apply with approval

```yaml
  apply:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: plan
    environment: production   # Requires GitHub Environment approval
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-terraform-apply
          aws-region: us-east-1
      - run: terraform init -input=false
      - run: terraform apply -input=false -auto-approve
```

### OIDC over long-lived keys

Prefer **OIDC federation** (`aws-actions/configure-aws-credentials` with `role-to-assume`) instead of storing `AWS_ACCESS_KEY_ID` in GitHub Secrets. Scope IAM roles: plan role read-only, apply role write with conditions on branch and environment.

---

## 22.6 Atlantis and Terraform Cloud

**Atlantis** runs `terraform plan` on PRs inside your VPC:

```yaml
# atlantis.yaml
version: 3
projects:
  - name: prod-vpc
    dir: infra/networking
    workspace: default
    autoplan:
      when_modified: ["**/*.tf", "**/*.tfvars"]
    apply_requirements: [approved, mergeable]
```

**Terraform Cloud (TFC)** / **HCP Terraform** centralizes runs, variables, and policy (Sentinel/OPA). The `cloud` block replaces manual backend config:

```hcl
terraform {
  cloud {
    organization = "acme-corp"
    workspaces {
      name = "prod-networking"
    }
  }
}
```

---

## 22.7 Testing and policy in the pipeline

| Tool | Purpose |
|------|---------|
| **tflint** | Lint provider-specific mistakes |
| **checkov** / **tfsec** | Security misconfiguration scan |
| **terratest** | Go integration tests against real APIs |
| **terraform test** (1.6+) | Native `.tftest.hcl` unit tests |

```hcl
# tests/vpc.tftest.hcl
run "valid_cidr" {
  command = plan
  variables {
    cidr_block = "10.0.0.0/16"
  }
  assert {
    condition     = aws_vpc.this.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR mismatch"
  }
}
```

Run `terraform test` in CI before `plan`.

---

## 22.8 Chapter summary

- Use **remote backends** with **locking**; never rely on local state in teams.
- **Workspaces** isolate state within one config; **separate state keys** per environment are often safer for production.
- CI should run **fmt**, **validate**, **test**, **scan**, and **plan** on every PR; **apply** only from protected branches with human approval.
- Prefer **OIDC** credentials and least-privilege IAM roles for pipeline identities.

---

## 🧪 Lab 22.1

1. Bootstrap an S3 bucket and DynamoDB table for Terraform state.
2. Migrate a Chapter 21 project from local to remote backend.
3. Create `dev` and `prod` workspaces (or separate backend keys) with different instance types.
4. Add a GitHub Actions workflow that runs `terraform plan` on PRs.
5. Import an existing S3 bucket into Terraform state.

---

## 🧪 Lab 22.2

1. Configure Atlantis (or TFC free tier) for automated PR plans.
2. Add `tflint` and `checkov` steps that fail the pipeline on high-severity findings.
3. Write a `terraform test` file validating a module output.

---

## Review questions

1. What happens if two engineers run `terraform apply` simultaneously without state locking?
2. When would you choose separate directories over Terraform workspaces?
3. Why should the plan role in CI have fewer permissions than the apply role?
4. What is the difference between `terraform state rm` and `terraform destroy`?
5. How does OIDC improve on static AWS access keys in GitHub Actions?

---

*Next: [Chapter 23 — Ansible Playbooks, Roles, Inventories](./chapter-23-ansible-playbooks.md)*
