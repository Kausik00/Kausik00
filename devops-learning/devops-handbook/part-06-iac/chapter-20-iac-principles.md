# Chapter 20: IaC Principles — State, Idempotency, and Drift

*DevOps Handbook — Part VI, Pages 361–380*

---

## 20.1 What is Infrastructure as Code?

**Infrastructure as Code (IaC)** means defining servers, networks, databases, and cloud resources in **machine-readable files** stored in version control—treated like application code.

Benefits:

- **Reproducibility** — Identical dev/staging/prod environments
- **Auditability** — Git history shows who changed what
- **Speed** — Provision in minutes, not days
- **Documentation** — Code is the source of truth
- **Disaster recovery** — Rebuild from code

---

## 20.2 Declarative vs imperative

| Style | You specify | Example tools |
|-------|-------------|---------------|
| **Declarative** | Desired end state | Terraform, CloudFormation, Kubernetes YAML |
| **Imperative** | Steps to execute | Ansible (mostly), shell scripts, AWS CLI scripts |

**Declarative** tools compare desired state to actual state and compute a plan. **Imperative** tools run commands in sequence.

Most modern IaC is declarative with imperative escape hatches.

---

## 20.3 Idempotency

An operation is **idempotent** if running it multiple times produces the same result.

```yaml
# Ansible — idempotent: "ensure nginx is installed and running"
- name: Install nginx
  apt:
    name: nginx
    state: present

- name: Start nginx
  service:
    name: nginx
    state: started
```

Running the playbook twice does not install nginx twice or restart unnecessarily.

**Why it matters:** CI/CD pipelines re-run constantly; non-idempotent scripts cause drift and outages.

---

## 20.4 State management

Tools like **Terraform** track what they created in a **state file** (`terraform.tfstate`).

State maps resource addresses to real cloud IDs:

```json
{
  "resources": [{
    "type": "aws_s3_bucket",
    "name": "logs",
    "instances": [{
      "attributes": { "id": "my-app-logs-bucket", "arn": "arn:aws:s3:::..." }
    }]
  }]
}
```

### State best practices

1. **Remote state** — Store in S3 + DynamoDB lock (AWS), GCS, Terraform Cloud
2. **Never commit secrets** in state (may contain sensitive values)
3. **Locking** — Prevent concurrent `terraform apply` from corrupting state
4. **State encryption** at rest

---

## 20.5 Configuration drift

**Drift** occurs when live infrastructure diverges from IaC definitions (manual console changes, emergency fixes).

Detection:

- `terraform plan` shows drift before apply
- AWS Config rules
- Scheduled drift detection jobs

Remediation:

- **Reconcile** — Apply IaC to restore desired state
- **Import** — Bring manual resources under IaC management
- **Prevent** — Restrict console access; require IaC PRs

---

## 20.6 IaC workflow in teams

```
Developer → PR with .tf changes → CI runs terraform plan → Review → Merge
    → CD runs terraform apply → Slack notification
```

### Directory structure (example)

```
infrastructure/
├── modules/
│   ├── vpc/
│   ├── eks/
│   └── rds/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── README.md
```

Each environment calls shared modules with different variables.

---

## 20.7 Testing IaC

| Level | Tool | What it checks |
|-------|------|----------------|
| Lint | `terraform fmt`, `tflint`, `cfn-lint` | Syntax and style |
| Static security | `checkov`, `tfsec`, `kics` | Misconfigurations |
| Plan | `terraform plan` in CI | Expected changes |
| Integration | Terratest, kitchen-terraform | Real deploy in test account |

---

## 20.8 Chapter summary

- IaC makes infrastructure versioned, repeatable, and reviewable.
- Prefer **declarative**, **idempotent** tools.
- Manage **state** remotely with locking; detect and fix **drift**.

---

## 🧪 Lab 20.1

1. Manually change a tag on a Terraform-managed resource in the AWS console.
2. Run `terraform plan` and observe drift output.
3. Run `terraform apply` to reconcile.

---

*Next: [Chapter 21 — Terraform](../part-06-iac/chapter-21-terraform-fundamentals.md)*
