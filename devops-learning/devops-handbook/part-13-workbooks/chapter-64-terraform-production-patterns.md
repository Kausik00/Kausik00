# Chapter 64: Terraform Production Patterns

*DevOps Handbook — Workbook*
---

## 64.1 Terraform in production is a state machine with opinions

Terraform is not “the AWS GUI in text form.” In production it is a **desired-state engine** whose real database is **remote state**, whose API is **plan/apply**, and whose failure mode is **unencoded human surgery**. This workbook covers module versioning, state surgery, refactoring without downtime, testing, policy as code, and multi-account layouts that survive more than one team.

If you remember one rule: **the cloud is not the source of truth Terraform will use on the next plan—state is.** Drift is a first-class operational event (Chapter 20), not a surprise.

| Layer | Production question |
|-------|---------------------|
| Code | Are modules pinned, reviewed, and compatible? |
| State | Who can read/write? Is there a lock? Backups? |
| Plan | Is CI the only applier for prod? |
| Policy | Can an engineer `aws_iam_policy` `*` by accident? |
| Identity | OIDC roles per account, or long-lived keys? (Chapter 67) |

---

## 64.2 Module versioning that does not strand environments

Unversioned `source = "../modules/vpc"` is fine for a tutorial and a trap for twenty environments. Production modules live in a registry or a git source **with a tag**.

```hcl
module "vpc" {
  source  = "app.terraform.io/acme/vpc/aws"
  version = "~> 3.12.0"

  cidr = "10.12.0.0/16"
  azs  = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

module "eks" {
  source = "git::https://github.com/acme/terraform-aws-eks.git?ref=v2.4.1"
  # ...
}
```

### 64.2.1 SemVer for infrastructure modules

| Bump | Compatible change | Example |
|------|-------------------|---------|
| Patch | Docs, harmless defaults, bugfix with same interface | Fix a tag |
| Minor | New optional variable, new output | Add flow logs toggle default off |
| Major | Required variable, removed output, resource replacement | Rename `cluster_name`, force new subnet |

**Replacement** (`forces replacement` in plan) is a major event even if the HCL “looks like a minor.” Encode that in the changelog. Consumers pin `~> 3.12.0` so they do not auto-eat a 4.0 that recreates a database.

### 64.2.2 The module contract

Every module README in production must list:

- Required providers and **minimum versions**
- Backward-incompatible resource behaviors
- Examples for the 80% case (three-tier VPC, private EKS)
- Upgrade notes (`moved` blocks, state commands)

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40.0, < 6.0.0"
    }
  }
}
```

Provider major bumps are **your** major bumps. Pin them in the root module; do not let a child module float `aws` to 6.x on Friday.

### 64.2.3 Promotion of module versions

Treat module versions like application versions:

1. Publish `v3.13.0-rc.1` from the module repo.
2. Apply in **sandbox** account.
3. Apply in **nonprod**.
4. Tag `v3.13.0` and open PRs that bump consumers.
5. Prod last, with a plan reviewed by the owning team.

Do not “just change source ref on prod” in the CLI.

---

## 64.3 State: backends, locking, isolation, and blast radius

```hcl
terraform {
  backend "s3" {
    bucket         = "acme-tfstate-prod"
    key            = "networking/vpc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "acme-tf-locks"
    encrypt        = true
  }
}
```

**One state file per blast radius.** A single state that contains VPC + EKS + RDS + 40 apps means one `terraform apply` can propose destroying the company. Split by:

- Account × environment × domain (network, platform, app)
- Team ownership
- Change frequency (stable VPC vs weekly app IAM)

Workspaces (`terraform workspace`) are a **naming trick**, not isolation. They share the same backend configuration and often the same credentials. Prefer **directory + backend key** or separate backends per account.

### 64.3.1 State access control

State contains secrets (RDS passwords if you did the wrong thing), resource IDs, and architecture. Restrict `s3:GetObject` on state buckets. Enable bucket versioning **and** test restore. DynamoDB lock table failures look like “Terraform hung”; they are often IAM or a crashed apply that left a lock.

```bash
terraform force-unlock <LOCK_ID>   # only after proving no other apply is running
```

Never force-unlock because you are impatient. Two applies on one state is split-brain.

---

## 64.4 State surgery: import, rm, mv, and the `moved` block

State surgery is valid when reality and state diverged **and** you understand both. It is invalid as a substitute for reading the plan.

### 64.4.1 Import

```bash
terraform import aws_s3_bucket.logs acme-app-logs-prod
```

Terraform 1.5+ `import` blocks:

```hcl
import {
  to = aws_s3_bucket.logs
  id = "acme-app-logs-prod"
}
```

After import, **immediately** `terraform plan` and reconcile attributes Terraform wants to change (often ACLs, encryption, tags). An import that is not followed by a clean plan is an incomplete import.

### 64.4.2 Remove from state without destroying cloud objects

```bash
terraform state rm aws_iam_role.legacy
```

Use when another system now owns the object, or you will re-import elsewhere. Pair with `lifecycle { prevent_destroy = true }` on irreplaceable resources **before** you need it.

### 64.4.3 Move addresses

```bash
terraform state mv aws_security_group.app module.network.aws_security_group.app
```

HCL `moved` blocks survive for the team and for CI:

```hcl
moved {
  from = aws_security_group.app
  to   = module.network.aws_security_group.app
}
```

`moved` is refactoring; `state mv` is the emergency equivalent. Prefer `moved` in code review.

### 64.4.4 Editing JSON state by hand

**Do not.** If you must (corrupt serial, HashiCorp support), copy the versioned object from S3 to an air-gapped editor, validate JSON, increment serial carefully, and know you can brick the lock. This is a last resort after `terraform state pull` analysis.

```bash
terraform state pull > /tmp/state.json
# inspect; never push a guess
```

### 64.4.5 Refresh and ignore

`terraform apply -refresh-only` records drift into state without changing cloud objects. Useful after out-of-band console changes you intend to keep. Then encode the change in HCL so the next full plan is empty.

`ignore_changes` is a **debt marker**. Every instance needs a comment: *who* changes this field and *why* Terraform must not fight them (ASG desired capacity, EKS-managed add-on versions, etc.).

---

## 64.5 Refactoring live infrastructure

Refactoring goals: **empty plan** after the move, **zero destroy/create** of stateful resources.

Checklist:

1. Branch from the last applied commit (never from local dirty state).
2. Add `moved` blocks **in the same PR** as module extraction.
3. Run plan against prod **read-only** in CI.
4. If the plan shows replacement of RDS/KMS/S3, **stop**.
5. Apply during a window only if replacements are actually required and have a restore plan.

**Renaming a resource in HCL without `moved`** is a destroy+create. That is how “we just cleaned up names” becomes a data-loss incident.

**Count to for_each:**

```hcl
# before
resource "aws_subnet" "private" {
  count = 3
  # ...
}

# after — needs moved from count index to each.key
resource "aws_subnet" "private" {
  for_each = local.az_map
  # ...
}
```

Write explicit `moved` from `aws_subnet.private[0]` to `aws_subnet.private["use1-az1"]`. Do not hope Terraform guesses.

---

## 64.6 Testing Terraform

| Layer | Tool | What it proves |
|-------|------|----------------|
| Format/lint | `terraform fmt`, `tflint` | Hygiene |
| Static policy | Checkov, tfsec, OPA/Conftest, Sentinel | Security/cost baselines |
| Unit (plan) | `terraform test`, Terratest plan JSON | Module logic |
| Integration | Terratest apply in ephemeral account | Real APIs |
| Contract | `terraform-docs`, examples | Humans |

```hcl
# tests/vpc.tftest.hcl (Terraform native tests)
run "plan_vpc" {
  command = plan
  assert {
    condition     = length(module.vpc.private_subnets) == 3
    error_message = "expected 3 private subnets"
  }
}
```

Terratest pattern (Go): apply, HTTP check, destroy in `defer`. Always tag ephemeral resources with `ttl` and a janitor (cloud-nuke / AWS Resource Explorer + Lambda) because destroy fails.

**CI for modules:** on every PR, `terraform test` plus Checkov. Nightly: apply example in sandbox.

Do not “test in prod” by applying a module version nobody else has run.

---

## 64.7 Policy as code in the apply path

Policy that is not in the pipeline is a wiki. Production patterns:

1. **Prevent** — Sentinel/OPA on the plan JSON (`terraform show -json`).
2. **Detect** — Config scanners on repo (Checkov) *and* cloud (AWS Config).
3. **Break-glass** — annotated exceptions with expiry, not comments forever.

Example Conftest-style idea (conceptual): deny `aws_security_group_rule` CIDR `0.0.0.0/0` on port 22 unless `exception` tag present.

OPA/Gatekeeper is for Kubernetes (Chapter 69); Terraform plan policy is **pre-apply**. Both belong in a mature org.

Cost policy: Infracost diff on PRs so “we added NAT gateways in every AZ” is visible before apply.

---

## 64.8 Multi-account and multi-region patterns

A single AWS account for prod+dev is an incident waiting for IAM. Typical layout:

| Account | Purpose | Terraform roots |
|---------|---------|-----------------|
| org-management | SCPs, org trail | Rare, highly locked |
| identity | SSO, IAM Identity Center | Separate state |
| network | Shared VPC/TGW | Network team |
| prod-app-N | Workloads | App teams via modules |
| nonprod | Sandbox | Looser policy |
| audit/log | Immutable logs | No app engineers write |

**Provider configuration:**

```hcl
provider "aws" {
  region = "us-east-1"
  assume_role {
    role_arn = "arn:aws:iam::222233334444:role/terraform-prod"
  }
}

provider "aws" {
  alias  = "dns"
  region = "us-east-1"
  assume_role {
    role_arn = "arn:aws:iam::111122223333:role/terraform-dns"
  }
}
```

**Stacks that must compose:** network outputs (subnet IDs) consumed by app stacks via `terraform_remote_state` **or** (better) a **parameter store / SSM / VPC lattice** contract, or a published module that *looks up* data sources.

`terraform_remote_state` creates a **read coupling** and often exposes too much. Prefer:

```hcl
data "aws_subnets" "private" {
  filter {
    name   = "tag:Tier"
    values = ["private"]
  }
}
```

Lookups by **tag contract** are more resilient than digging into another team’s state file.

**Terraform Cloud / Spacelift / Atlantis / env0:** pick one apply orchestrator. The pattern is PR → plan comment → owner approve → apply with OIDC. Local apply to prod with admin keys is the anti-pattern this chapter exists to kill.

---

## 64.9 CI apply, OIDC, and secrets

```yaml
# sketch: GitHub Actions OIDC to AWS
permissions:
  id-token: write
  contents: read
```

Map `repo:org/infra:ref:refs/heads/main` to `terraform-prod` role. Feature branches assume `terraform-nonprod`. This is the same OIDC story as Chapter 67, applied to IaC.

Never store `AWS_SECRET_ACCESS_KEY` in Terraform Cloud *and* in GitHub *and* in a 1Password vault shared with the company. One identity path.

Sensitive outputs: `sensitive = true`, and do not print plans to public PRs if they contain secret values (random passwords). Generate secrets in Vault/AWS Secrets Manager; Terraform should store **references**.

---

## 64.10 Worked incident: accidental database replacement

**Plan snippet:** `-/+ aws_db_instance.main` because `identifier` changed when a module author “cleaned up names.”

**Response:**

1. Do not apply.
2. Revert the variable change **or** add `lifecycle { ignore_changes = [identifier] }` only if the name is immutable in AWS and you accept the drift.
3. If a junior already applied: restore from snapshot, **do not** “terraform undo.” State now points at a new empty DB. `state rm` the new instance after snapshot restore only with a senior + runbook.
4. Add a Sentinel/OPA rule: deny plans that replace resources typed in a `stateful_types` list (`aws_db_instance`, `aws_efs_file_system`, `aws_elasticsearch_domain`, …) without a `destroy_ok` tag.

**Prevention:** `prevent_destroy`, CODEOWNERS on modules that touch data stores, and plan review that searches for `must be replaced`.

---

## 64.11 Operational runbook snippets

```bash
terraform fmt -recursive
terraform init -upgrade=false
terraform validate
terraform plan -out=tfplan
terraform show -json tfplan | jq '.resource_changes[] | select(.change.actions[]=="delete")'

# targeted apply is a smell; use only to unblock with a ticket
terraform apply -target=module.vpc -out=tfplan
```

Targeted apply **lies by omission**: it can leave dangling references. Follow with a full plan.

---

## 🧪 Lab 64.1 — Module version bump with moved

1. Create a root module with an `aws_s3_bucket` (or `random_id` locally if no cloud).
2. Extract the bucket into `./modules/bucket` without `moved`; observe destroy/create in plan (use `terraform plan` against a real sandbox or `null_resource` analog).
3. Add a `moved` block; confirm plan is empty (or in-place only).
4. Tag the module `v1.0.0` and consume with `?ref=v1.0.0`.

---

## 🧪 Lab 64.2 — Import and reconcile

1. Create a bucket in console (sandbox).
2. Write HCL that does not quite match (missing tags).
3. `terraform import` then plan; add tags until plan is empty.
4. Document every attribute Terraform wanted to change.

---

## 🧪 Lab 64.3 — Policy gate on a dangerous plan

1. Write a small script or Checkov custom check that fails if a plan JSON contains `delete` on `aws_db_instance`.
2. Generate a synthetic plan JSON fixture with a delete.
3. Wire it as a CI job that exits non-zero.

---

## 🧪 Lab 64.4 — Multi-account data lookup

1. In account A, tag subnets `Tier=private`.
2. In account B HCL, use `data.aws_subnets` (or mocked fixture) filtered by that tag.
3. Contrast with `terraform_remote_state` outputs. List two coupling risks of remote state.

---

## 64.12 Anti-patterns checklist

| Anti-pattern | Replace with |
|--------------|--------------|
| One state to rule them all | Split states |
| Workspaces as multi-account | Separate backends/roles |
| Unpinned modules | Registry version / git tag |
| Apply from laptops to prod | CI OIDC + approvals |
| `ignore_changes` without comment | Documented exception |
| Hand-edited state JSON | import/mv/moved |
| Secrets in state | Secret manager + IAM |
| `-target` as lifestyle | Smaller states, better modules |

---

## Review questions

1. Why is a Terraform workspace a poor substitute for an AWS account boundary?
2. When is a module change a **major** version even if all variables remain optional?
3. Describe a safe procedure to extract a resource into a module with zero replacement.
4. What is the difference between `terraform state rm` and `terraform destroy` for that address?
5. Why is `terraform_remote_state` coupling risky between teams? What is an alternative contract?
6. A lock is stuck. What must you prove before `force-unlock`?
7. How do you prevent accidental RDS replacement in both HCL and CI policy?
8. Where should provider version constraints live, and why not only in child modules?
9. What belongs in a module changelog besides HCL variable diffs?
10. Explain why `-target` can produce a green apply that the next full plan wants to undo.

---

## Further practice

Revisit Chapters 21–22 and 25. Production Terraform is those chapters plus **versioning, state discipline, and multi-account identity**.
