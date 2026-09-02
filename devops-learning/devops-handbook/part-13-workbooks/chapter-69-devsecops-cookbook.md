# Chapter 69: DevSecOps Cookbook

*DevOps Handbook — Workbook*
---

## 69.1 Security that runs every day, not once a year

DevSecOps is not a scanner logo in a slide. It is **repeatable controls** in CI, **admission** on the cluster, **signed artifacts** at deploy time, and **drills** that prove secrets can rotate without folklore. This cookbook assumes Chapters 49–54 exist; here we assemble them into **runnable** checklists, YAML, and game-day scripts.

| Control | Where it bites | Failure if skipped |
|---------|----------------|-------------------|
| Pipeline scanners | Merge | CVE and secrets land on `main` |
| Admission | Deploy | Unsigned or privileged pods run |
| Image signing | Promote | Tag `latest` from an attacker registry |
| Secrets rotation | Incident + calendar | Stolen creds remain valid |
| Runtime (Falco) | After start | Malware in a signed image |

Defense in depth: CI can be bypassed (`kubectl` from a laptop). Admission can be bypassed (break-glass). Runtime is last. **None** is optional in production.

---

## 69.2 Pipeline scanners: what each gate is for

A single “scan” job that prints a 40 MB HTML and always exits 0 is theater.

### 69.2.1 Recommended pipeline order

1. **Secrets** (gitleaks, detect-secrets, GitHub scanning)—fail closed.
2. **SAST** (Semgrep, CodeQL)—language-appropriate; suppressions in code review.
3. **SCA / lockfile** (npm audit, govulncheck, pip-audit, Dependabot).
4. **IaC** (Checkov, tfsec, KICS) on the same PR as Terraform/K8s.
5. **Container** (Grype, Trivy) on the **produced image digest**, not only the Dockerfile.
6. **DAST** (ZAP) on a **preview environment**, not on production.
7. **License** if legal requires it.

```yaml
# sketch: fail on secrets, high CVE in image
- name: gitleaks
  run: gitleaks detect --redact --exit-code 1
- name: trivy image
  run: |
    trivy image --severity HIGH,CRITICAL --exit-code 1 \
      --ignore-unfixed \
      ghcr.io/acme/shop@${DIGEST}
```

**ignore-unfixed** is a policy choice: it reduces noise, it also accepts known-broken libraries. Document it.

**Baseline files** (`.gitleaks.toml`, Semgrep `exclude`) must be CODEOWNERS-protected. Otherwise engineers exclude `*.go`.

### 69.2.2 Triage protocol

| Finding | Action |
|---------|--------|
| Secret in Git | Rotate **immediately** (69.5); rewrite history only per Chapter 63 policy |
| Critical CVE in **used** library | Block merge or ticket with SLA |
| Critical CVE in unused transitive | Upgrade or `govulncheck` reachability |
| Misconfig `privileged: true` | Block |
| License GPL in proprietary | Legal, not a night-shift decision |

**Reachability** (Snyk, govulncheck, Google osv-scanner) reduces “5000 CVEs.” Without it, teams ignore scanners.

### 69.2.3 Scanner supply chain

Pin scanner versions and **their** image digests. A compromised Action that “scans” can exfiltrate the OIDC token (Chapter 67). Run scanners from **internal mirrors**.

---

## 69.3 Admission control: Gatekeeper, Kyverno, ValidatingAdmissionPolicy

Admission webhooks intercept API requests. They are **production dependencies** (Chapter 66: a dead webhook hangs deploys).

### 69.3.1 Policy examples worth enforcing

| Policy | Rationale |
|--------|-----------|
| Disallow `privileged` | Host takeover |
| Disallow `hostNetwork` / `hostPID` | Node escape |
| Require non-root | Defense in depth |
| Require `readOnlyRootFilesystem` where possible | Persistence |
| Require resource requests | Noisy neighbor / scheduler |
| Deny `:latest` | Mutability |
| Require signed images (cosign/kyverno verify) | Supply chain |
| Deny NodePort in prod ns | Accidental exposure |
| Require NetworkPolicy in new namespaces | Default deny |

Kyverno verify images (conceptual):

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-images
spec:
  validationFailureAction: Enforce
  rules:
    - name: signed-by-acme
      match:
        any:
          - resources:
              kinds: [Pod]
      verifyImages:
        - imageReferences: ["ghcr.io/acme/*"]
          attestors:
            - entries:
                - keys:
                    publicKeys: |-
                      -----BEGIN PUBLIC KEY-----
                      ...
                      -----END PUBLIC KEY-----
```

**Audit then Enforce.** Turn on `Audit` for two weeks, fix workloads, then `Enforce`. Surprise Enforce is an outage.

### 69.3.2 ValidatingAdmissionPolicy (CEL)

Native Kubernetes CEL policies reduce webhook latency and **fail closed** with the API server. Use for simple checks; keep complex image verify in Kyverno/OPA.

### 69.3.3 Break-glass

```yaml
# labeled namespace or annotation
admission.company.com/break-glass: "INC-12345"
```

Policy ignores when annotation present **and** a controller **expires** it (24h). Log every break-glass to SIEM. Without expiry, break-glass is a second prod.

### 69.3.4 Webhook HA

Multiple replicas, PDB, `failurePolicy: Fail` for **security** policies (prefer closed) vs `Ignore` for **best-effort** mutations. Security with `Ignore` is off when the webhook is down—the exact moment an attacker might choose.

Test fail-closed in staging: scale webhook to zero and confirm **creates are denied**, then restore.

---

## 69.4 Image signing and verification in the path to prod

### 69.4.1 Cosign + GitHub OIDC (keyless)

```bash
cosign sign --yes ghcr.io/acme/shop@$DIGEST
cosign verify ghcr.io/acme/shop@$DIGEST \
  --certificate-identity-regexp='https://github.com/acme/shop/.*' \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

Keyless ties identity to **CI identity**. Attackers who can run GitHub Actions on that repo can sign. Protect the repo (2FA, CODEOWNERS, no fork OIDC to sign prod—Chapter 67).

**Keyed** signing (KMS/HSM) for higher assurance: only the CD role in prod account can sign **release** tags.

### 69.4.2 Promotion

```
CI build → sign + SBOM attest → staging admit verify → prod admit verify
```

Do not re-sign in prod from a different identity unless that is an explicit **release engineer** role.

### 69.4.3 Tag vs digest

Admission must verify the **digest** the controller will run. Mutating webhooks that change the image after verify are a bypass—order policies, or use digest-only in manifests (GitOps).

```yaml
image: ghcr.io/acme/shop@sha256:abc...
```

Argo CD / Flux should **fail** if a tag moved. Pin in Git.

### 69.4.4 Provenance

Verify `predicateType` SLSA or SPDX in Kyverno `attestations`. A signed malware image is still malware; signing proves **origin**, not **goodness**. Scanners remain.

---

## 69.5 Secrets rotation drills

Rotation that has never been rehearsed **will fail during a breach**.

### 69.5.1 Inventory

Maintain a **secrets register** (Vault paths, AWS IAM keys, GitHub PATs, TLS certs, DB passwords, webhook secrets, WiFi PSK, package tokens):

| Field | Example |
|-------|---------|
| Name | `prod/shop/postgres` |
| Owner team | checkout |
| Location | RDS + Vault + k8s ExternalSecret |
| TTL | 30 days |
| Blast radius | PII DB |
| Last drill | 2026-06-01 |
| Runbook | url |

Unknown secrets cannot be rotated. Start with cloud IAM credential reports and GitHub PAT lists.

### 69.5.2 Drill types

| Drill | Cadence | Success |
|-------|---------|---------|
| App DB password | Quarterly | Zero-downtime dual-password or brief brownout within SLO |
| CI OIDC (no secret) | Annual tabletop | Confirm no static keys remain |
| TLS leaf | 60 days before expiry | Automated renew (cert-manager) |
| GitHub org tokens | Quarterly | Apps still green |
| Cloud access keys | Monthly until count = 0 | None remain |
| Encryption keys (KMS) | Rare | Re-encrypt plan exists |

### 69.5.3 Zero-downtime DB rotation pattern

1. Create new password in RDS/Vault.
2. Configure DB to accept **both** (if engine supports) **or** deploy app with retry.
3. Push new secret via External Secrets; rolling restart.
4. Confirm connections on new password (`pg_stat_activity`).
5. Revoke old password.
6. If step 4 fails, **rollback secret** still works because old is valid until 5.

Practice this on staging **with** the same External Secrets operator version.

### 69.5.4 Kubernetes secrets are not rotation

Updating a Secret does not always restart pods. Use Reloader, hash annotations, or CSI driver volume that **re-reads**. Document per workload.

```yaml
# checksum annotation pattern (helm)
checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
```

### 69.5.5 Emergency leak response

1. Revoke/rotate **first** (contain).
2. Then forensic Git history (Chapter 63).
3. Then notify per compliance (Chapter 54).
4. Scanner baseline update so the leaked string does not page forever **after** rotation (false sense if you only suppress).

---

## 69.5.6 CI/CD secrets and OIDC drills

Static `AWS_ACCESS_KEY_ID` in GitHub should trend to **zero**. Drill:

1. Inventory GitHub secrets, GitLab variables, Jenkins credentials, AWX credentials (Chapter 65).
2. For each cloud key: disable in IAM, prove pipelines fail, replace with OIDC (Chapter 67), prove pipelines pass.
3. Record the list in the secrets register.

**Registry tokens** (`gcloud auth print-access-token` in a log) are as bad as AWS keys. Prefer workload identity to push images.

**Webhook secrets** (GitHub → Jenkins) get leaked in debug dumps. Rotate and require HTTPS + IP allowlists.

Time-box: a rotation drill that takes two days is not an incident-ready control. Target **one hour** for the top ten secrets with two people.

---

## 69.6 Runtime and supply chain leftovers

- **Falco** rules for unexpected shell in prod containers (Chapter 53).
- **NetworkPolicy** default deny + DNS allow (Chapter 66).
- **Pod Security Standards** `restricted` on prod namespaces.
- **SBOM stored** with the image; generate **again** at deploy if legally required.
- **Binary authorization** (GCP) / **AWS Signer** / **Ratify** as alternatives to Kyverno verify.

---

## 69.7 Worked incident: leaked cloud key in a PR that was “only a screenshot”

**Event:** Slack screenshot of `terraform plan` included an access key from a misconfigured provider debug log. Key was 11 minutes in a public channel.

**Response:** Disable key in IAM **immediately**. CloudTrail for API calls in that window. Rotate equivalent keys. Add `no_debug` on provider. Add gitleaks + Slack DLP. Drill: “can we disable a key in 5 minutes at 03:00?” Time it.

**Admission:** the key was not in a container image; scanners on Git would have caught a committed key, not a screenshot. **Human** DLP still matters.

---

## 69.7.1 Threat model for a typical microservice path

Walk the golden path (Chapter 70) as an attacker:

| Step | Threat | Control |
|------|--------|---------|
| Scaffold | Malicious template PR | CODEOWNERS, signed commits (Chapter 63) |
| CI | Poisoned Action / cache | SHA pins, cache rules (Chapter 67) |
| Build | Typosquat dependency | Lockfile, SCA, private proxy |
| Push | Overwrite tag | Immutable tags, digest, signing |
| GitOps | Unsigned YAML | Signed commits, restricted AppProject |
| Admit | Privileged pod | Kyverno/PSA |
| Run | Reverse shell | Falco, NP deny egress to internet if possible |
| Secrets | Env dump | Vault agent, no secrets in logs |

Tabletop this with product + platform + security once a quarter. The output is **tickets**, not a PDF.

---

## 69.8 Policy as code CI for cluster policies

Kyverno/Gatekeeper policies live in Git. CI:

```bash
kyverno apply policies/ --resource fixtures/privileged-pod.yaml | grep fail
kubeconform -strict manifests/
conftest test deployment.yaml
```

Fixtures: **known-bad** pods must fail; **known-good** must pass. Without fixtures, policies rot.

---

## 🧪 Lab 69.1 — Pipeline gates

1. Commit a fake AWS key in a throwaway repo (`AKIA` pattern) on a branch.
2. Run gitleaks; confirm fail.
3. Add `.gitleaks.toml` allowlist **wrongly** for all files; show the bypass.
4. Restore fail-closed; protect the config via CODEOWNERS.

---

## 🧪 Lab 69.2 — Admission audit vs enforce

1. On kind, install Kyverno or Pod Security `restricted`.
2. Apply a privileged pod in `Audit`; confirm it runs and an audit event exists.
3. Switch to `Enforce`; confirm deny.
4. Scale the webhook to 0 (if using Kyverno); record API behavior vs `failurePolicy`.

---

## 🧪 Lab 69.3 — Cosign verify

1. Build a local image; `cosign sign` with a lab keypair.
2. `cosign verify` succeeds.
3. `docker tag` the image to another name **without** copying signatures; verify fails.
4. Write why admission must use digest.

---

## 🧪 Lab 69.4 — Secret rotation tabletop + mini-live

1. Fill a secrets register with five fictional secrets.
2. Tabletop: leaked GitHub PAT. Who revokes, where, how apps get a new one?
3. Live (staging): change a dummy app’s API token via Secret + rolling restart; prove old token 401s.
4. Time the live drill; set a target for next quarter.

---

## 🧪 Lab 69.5 — Policy unit fixtures

1. Write a Kyverno/OPA policy: deny `latest`.
2. Fixture `image: nginx:latest` (fail) and `nginx@sha256:...` (pass).
3. Run in CI.

---

## 69.9 Exception management

Every scanner org accumulates **wontfix**. Require:

- Ticket ID, expiry date, owner, residual risk
- Auto-fail when expiry passes
- Public dashboard of exceptions older than 90 days for CISO

Infinite exceptions are the same as no scanner.

---

## 69.10 Mapping to compliance

| Control | SOC2 / ISO flavor |
|---------|-------------------|
| Pipeline scanners | Change management, vuln mgmt |
| Admission | Secure configuration |
| Signing | Integrity of releases |
| Rotation drills | Access revocation |
| Audit logs | Detective |

Map but **do not** let the audit calendar be the only cadence. Drills are engineering.

---

## Review questions

1. Why must container scans run on the digest you deploy, not only on the Dockerfile?
2. What is the risk of `failurePolicy: Ignore` on a validating security webhook?
3. Why Audit-then-Enforce for new cluster policies?
4. Signing proves origin. What does it **not** prove?
5. How can a mutating webhook bypass image verification?
6. Outline a dual-password DB rotation. Where do Kubernetes consumers usually fail?
7. Why CODEOWNERS on scanner suppressions?
8. Fork PR + keyless cosign: what identity problem remains?
9. Give three secrets that will not appear in Git but still need rotation drills.
10. How do policy fixtures prevent “Kyverno YAML that never denied anything”?

---

## Further practice

Chapters 49–54 for depth; 63 for history rewrite after secrets; 66 for webhook outages; 67 for OIDC. This cookbook is the **weekly** path those chapters should land on.
