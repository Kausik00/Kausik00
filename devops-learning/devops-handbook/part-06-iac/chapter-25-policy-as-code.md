# Chapter 25: Policy as Code — OPA, Checkov, and Sentinel

*DevOps Handbook — Part VI, Pages 466–480*

---

## 25.1 Why policy as code?

Infrastructure and deployment mistakes scale with automation. **Policy as Code (PaC)** encodes guardrails—encryption required, no public S3 buckets, approved regions—as executable rules evaluated in CI, admission controllers, or Terraform runs **before** changes reach production.

| Without PaC | With PaC |
|-------------|----------|
| Manual checklist in PR template | Automated deny/warn on violation |
| Post-incident "what broke the rule?" | Audit log of policy decisions |
| Inconsistent interpretation | Same rule in dev and prod |

PaC complements but does not replace peer review and threat modeling.

---

## 25.2 Policy evaluation points

```
Developer → PR → [Lint/Scan: Checkov] → Plan → [OPA/Sentinel] → Apply → Runtime [Gatekeeper/Kyverno]
```

| Stage | Tools | Input format |
|-------|-------|----------------|
| Static IaC scan | Checkov, tfsec, KICS | `.tf`, `.yaml`, `.dockerfile` |
| Plan-time | OPA (conftest), Sentinel | `terraform plan` JSON |
| K8s admission | OPA Gatekeeper, Kyverno | Kubernetes API requests |
| General purpose | Open Policy Agent (OPA) | JSON |

---

## 25.3 Checkov — static IaC scanning

**Checkov** (Bridgecrew/Prisma) scans Terraform, CloudFormation, Kubernetes, Dockerfiles, and more.

```bash
pip install checkov
checkov -d infra/                          # Directory scan
checkov -f main.tf --framework terraform
checkov -d . --skip-check CKV_AWS_20         # Skip specific check
checkov -d . --soft-fail                     # Warn only (not for prod)
```

Example finding: S3 bucket without encryption or public access block.

Suppress false positives inline:

```hcl
resource "aws_s3_bucket" "logs" {
  #checkov:skip=CKV_AWS_18:Access logging handled centrally
  bucket = "acme-logs"
}
```

`.checkov.yml` for CI:

```yaml
quiet: false
compact: true
framework:
  - terraform
  - dockerfile
soft-fail: false
skip-check:
  - CKV_AWS_144  # Document why in SECURITY.md
```

GitHub Actions:

```yaml
- name: Checkov scan
  uses: bridgecrewio/checkov-action@master
  with:
    directory: infra/
    framework: terraform
    soft_fail: false
```

---

## 25.4 Open Policy Agent (OPA) and Rego

**OPA** is a general-purpose policy engine. Policies are written in **Rego**. **conftest** runs Rego against JSON/YAML files.

Install: `brew install conftest` or download from openpolicyagent.org.

Policy: `policy/s3.rego`

```rego
package terraform.s3

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not resource.change.after.server_side_encryption_configuration
  msg := sprintf("S3 bucket %s must enable encryption", [resource.address])
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  resource.change.after.acl == "public-read"
  msg := sprintf("S3 bucket %s must not be public", [resource.address])
}
```

Generate plan JSON and test:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
conftest test plan.json -p policy/
```

OPA on Kubernetes (**Gatekeeper**):

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    labels: ["team", "cost-center"]
```

Violating pods are rejected at admission time.

---

## 25.5 HashiCorp Sentinel (Terraform Cloud/Enterprise)

**Sentinel** is HashiCorp's policy language for Terraform Cloud/Enterprise. It integrates directly with the run pipeline.

Example: restrict instance types

```python
# policy/limit-instance-type.sentinel
import "tfplan/v2" as tfplan

allowed = ["t3.micro", "t3.small", "t3.medium"]

main = rule {
  all tfplan.resource_changes as _, rc {
    rc.type is not "aws_instance" or
    rc.change.after.instance_type in allowed
  }
}
```

Enforcement levels:

| Level | Behavior |
|-------|----------|
| **advisory** | Log only |
| **soft-mandatory** | Overridable with permission |
| **hard-mandatory** | Cannot apply |

Sentinel has first-class Terraform plan imports (`tfplan`, `tfconfig`, `tfstate`). OPA is more portable across tools; Sentinel is tightly coupled to HashiCorp ecosystem.

---

## 25.6 Comparison matrix

| Feature | Checkov | OPA/conftest | Sentinel |
|---------|---------|--------------|----------|
| Languages | Python checks | Rego | Sentinel DSL |
| Terraform plan | Indirect (HCL) | Plan JSON | Native |
| K8s admission | Limited | Gatekeeper | N/A |
| License | Apache 2.0 | Apache 2.0 | BSL / TFC |
| Best for | Quick security baseline | Multi-tool policy | TFC enterprise governance |

Use **Checkov** for broad static scans, **OPA** for custom plan logic and Kubernetes, **Sentinel** if you are standardized on Terraform Cloud with hierarchical policies.

---

## 25.7 Building a policy program

1. **Start with deny-list basics** — public exposure, unencrypted storage, open security groups
2. **Map to compliance** — tag each rule to CIS, SOC2, or internal standard
3. **Warn then enforce** — `soft-fail` for 2 weeks, then hard fail
4. **Exception process** — ticket ID in `#checkov:skip` or OPA `data.exceptions`
5. **Measure** — track violations per team; fix generators not just resources

`policy/exceptions.json` for OPA:

```json
{
  "exceptions": [
  {
    "resource": "aws_s3_bucket.legacy_logs",
    "policy": "terraform.s3.deny",
    "reason": "TICKET-4521 migration Q4",
    "expires": "2026-12-31"
  }
  ]
}
```

```rego
exception[resource] {
  ex := data.exceptions[_]
  resource := ex.resource
  time.parse_rfc3339_ns(ex.expires) > time.now_ns()
}
```

---

## 25.8 CI pipeline integration

```yaml
jobs:
  policy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform plan -out=tfplan
      - run: terraform show -json tfplan > plan.json
      - run: checkov -d infra/ --quiet
      - run: conftest test plan.json -p policy/ --all-namespaces
```

Fail the build on any `deny` rule. Store policy repos separately for platform teams to version independently.

---

## 25.9 Chapter summary

- **Policy as Code** automates compliance and prevents recurring misconfigurations.
- **Checkov** provides out-of-the-box IaC security checks with minimal setup.
- **OPA/Rego** is flexible for Terraform plans, Kubernetes admission, and custom JSON APIs.
- **Sentinel** integrates with Terraform Cloud for plan-time enforcement in enterprise workflows.
- Combine static scan + plan-time policy + runtime admission for defense in depth.

---

## 🧪 Lab 25.1

1. Run Checkov on a Terraform project; fix three high-severity findings.
2. Write a Rego policy denying `0.0.0.0/0` ingress on security groups.
3. Integrate Checkov and conftest into a GitHub Actions workflow.

---

## 🧪 Lab 25.2

1. Install OPA Gatekeeper on a test cluster and deploy a `require-labels` constraint.
2. Create an exception file with expiring waivers for one resource.
3. Document a team policy: which checks are hard-fail vs advisory.

---

## Review questions

1. What is the difference between static IaC scanning and plan-time policy evaluation?
2. When would you use Gatekeeper instead of only Checkov?
3. Why should policy exceptions have expiration dates?
4. How does Sentinel's `soft-mandatory` differ from `hard-mandatory`?
5. Name three resource types you would prioritize in a new PaC rollout.

---

*Next: [Chapter 26 — Docker Fundamentals](../part-07-containers/chapter-26-docker-fundamentals.md)*
