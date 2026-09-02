# Chapter 54: Compliance Automation and Audit Trails

*DevOps Handbook — Pages 263–267 of this PDF edition*
---

## 54.1 Compliance in continuous delivery

Regulated industries—finance, healthcare, government—must demonstrate **controls** are designed and operating effectively: SOC 2, ISO 27001, PCI DSS, HIPAA, FedRAMP, GDPR. Traditional compliance meant annual audits with manual evidence collection. **Compliance automation** embeds controls in pipelines and infrastructure, producing **continuous evidence**.

DevOps alignment:

| Traditional compliance | Automated compliance |
|------------------------|----------------------|
| Annual spreadsheet audit | Continuous control monitoring |
| Manual change tickets | Git history + approved PRs |
| Screenshot of firewall | IaC + drift detection |
| Quarterly access review | IAM analytics + automated reports |

Goal: **audit-ready by default**—evidence generated as a side effect of normal operations.

---

## 54.2 Control frameworks mapping

Map technical controls to framework requirements:

| Framework domain | Technical implementation |
|------------------|-------------------------|
| **Access control** | IAM, RBAC, MFA, SSO |
| **Change management** | Git PR approval, CI gates, deployment logs |
| **Encryption** | TLS, KMS, encrypted volumes |
| **Logging/monitoring** | Centralized logs, immutable audit trails |
| **Vulnerability management** | SCA/SAST gates, patch SLAs |
| **Backup/DR** | Automated backups, tested restore |
| **Incident response** | On-call, postmortems, retention |

**SOC 2 Trust Service Criteria** (Security, Availability, Processing Integrity, Confidentiality, Privacy) map to pipeline and platform controls. **PCI DSS** requires segmentation, logging, vulnerability scanning for cardholder data environments.

Maintain a **control matrix** spreadsheet/database linking control ID → implementation → evidence source → owner.

---

## 54.3 Audit trails — what to log

Immutable audit logs for:

| Event type | Examples |
|------------|----------|
| **Authentication** | Login, MFA, failed attempts |
| **Authorization** | IAM policy change, role assignment |
| **Data access** | Admin read of customer data |
| **Infrastructure change** | Terraform apply, kubectl apply |
| **Deployment** | Who deployed what commit when |
| **Secret access** | Vault/AWS Secrets Manager read |
| **Security findings** | Scan results, waiver approvals |

Kubernetes audit policy:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  - level: Metadata
    omitStages: [RequestReceived]
  - level: RequestResponse
    verbs: ["create", "update", "patch", "delete"]
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]
  - level: RequestResponse
    verbs: ["create", "update", "patch", "delete"]
    resources:
      - group: "rbac.authorization.k8s.io"
        resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
```

Ship audit logs to SIEM (Elastic Security, Splunk) with **WORM** storage (S3 Object Lock) for tamper evidence.

CloudTrail (AWS) / Cloud Audit Logs (GCP) / Activity Log (Azure)—enable organization trail, log integrity validation.

---

## 54.4 Policy as Code for compliance

Encode compliance rules as executable policy:

**Checkov** CIS benchmarks:

```bash
checkov -d terraform/ --framework terraform --check CKV_AWS_* \
  --download-external-modules true \
  --output sarif --output-file-path checkov.sarif
```

**OPA/Conftest** custom org policies:

```rego
# require S3 bucket encryption
package terraform.s3

deny[msg] {
  resource := input.resource.aws_s3_bucket[name]
  not input.resource.aws_s3_bucket_server_side_encryption_configuration[name]
  msg := sprintf("S3 bucket %s missing encryption config", [name])
}
```

**Cloud Custodian** — AWS/GCP/Azure compliance automation:

```yaml
policies:
  - name: s3-require-encryption
    resource: aws.s3
    filters:
      - type: bucket-encryption
        state: false
    actions:
      - type: notify
      - type: mark-for-op
        op: encrypt
```

Run in CI (prevent) and scheduled scans (detect drift).

---

## 54.5 Continuous control monitoring

**CCM** tools aggregate evidence:

| Tool | Function |
|------|----------|
| **Vanta** | Automated SOC 2 evidence |
| **Drata** | Continuous compliance monitoring |
| **Secureframe** | Control tracking |
| **OpenSCAP** | NIST/CIS scanning |
| **InSpec** | Compliance profiles as code |

Custom dashboard example metrics:

- % production resources passing Checkov CIS
- Mean patch time for critical CVEs
- % employees with MFA enabled
- PR approval compliance rate (no self-merge to main)

Automated evidence collection:

```yaml
# Weekly compliance report job
- name: Collect evidence
  run: |
    checkov -d infra/ -o json > evidence/checkov-$(date +%F).json
    aws iam generate-credential-report
    aws iam get-credential-report --query Content --output text | base64 -d > evidence/iam-$(date +%F).csv
    aws s3 cp evidence/ s3://compliance-evidence-bucket/$(date +%Y/%m/%d)/ --recursive
```

---

## 54.6 Change management automation

Auditors ask: "How do you control production changes?"

Automated answer:

1. All changes via **Git PR** with required reviewers
2. Branch protection: status checks (CI, security scans) must pass
3. Deployment linked to commit SHA in CI logs and GitHub Deployments API
4. **Immutable infrastructure** — no SSH manual edits
5. Emergency break-glass procedure documented with retroactive PR

Terraform Cloud / Atlantis audit trail:

```
PR #1234 → plan posted → approved → apply → state updated → audit log entry
```

Separation of duties: developer proposes (PR), different person approves, CI applies—SOD for SOC 2.

---

## 54.7 Data privacy and retention

GDPR/CCPA requirements:

- **Data inventory** — Map PII flows (SBOM-like for data)
- **Retention policies** — ILM on logs (Chapter 45)
- **Right to erasure** — Procedures in runbooks
- **DPIA** — Data Protection Impact Assessment for new features

Log redaction at ingest—never store full credit card numbers in application logs.

Retention schedule:

| Data type | Retention | Rationale |
|-----------|-----------|-----------|
| Application logs | 90 days | Operations |
| Audit logs | 7 years | Regulatory |
| CI artifacts | 1 year | Reproducibility |
| Backups | Per RPO/RTO policy | DR |

---

## 54.8 Audit preparation workflow

Before external audit:

1. **Control matrix review** — Update implementations
2. **Evidence spot check** — Sample 30 days of deployment logs, access reviews
3. **Exception documentation** — Risk acceptance for waived findings
4. **Personnel interviews** — Engineers explain actual process matches documentation
5. **Pen test / vuln scan reports** — Current within policy window

During audit: provide read-only access to evidence repository—not production systems.

Post-audit: remediate findings, update automation to prevent recurrence.

---

## 54.9 Chapter summary

- Compliance automation maps framework controls to pipeline, IaC, and platform implementations.
- Immutable audit trails (K8s audit, CloudTrail, Git, Vault logs) provide continuous evidence.
- Policy-as-code (Checkov, OPA, Cloud Custodian) prevents and detects drift.
- CCM platforms and scheduled evidence jobs reduce audit scramble; maintain control matrix ownership.

---

## 🧪 Lab 54.1 — Kubernetes audit logging

1. Enable audit policy on test cluster logging RequestResponse for Secrets and RBAC.
2. Create and delete a Secret; query audit logs for event chain.
3. Forward logs to Elasticsearch; create Kibana dashboard of admin actions.

---

## 🧪 Lab 54.2 — Compliance evidence pipeline

1. Run Checkov against Terraform sample with intentional misconfigurations.
2. Export SARIF/JSON to `evidence/` directory with timestamp.
3. Document control matrix entry linking CIS benchmark to Checkov check ID and evidence file.

---

## Review questions

1. How does Git-based change management satisfy audit change control requirements?
2. What events must Kubernetes audit logs capture for security compliance?
3. Compare continuous compliance monitoring vs annual audit preparation.
4. What is separation of duties in CI/CD, and why implement it?
5. How do ILM policies support GDPR retention requirements?
6. Name three tools for policy-as-code compliance scanning.
7. What evidence would you provide for a "vulnerability management" control?

---

*Continue: Chapter 55 — Platform Engineering*
