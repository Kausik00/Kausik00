# Chapter 49: Shift-Left Security in the Pipeline

*DevOps Handbook — Part XI, Pages 961–980*

---

## 49.1 DevSecOps and shift-left

**DevSecOps** integrates security into the software delivery lifecycle—not as a final gate before release, but as continuous practice from design through operation. **Shift-left** means moving security activities **earlier**—cheaper to fix vulnerabilities in IDE or PR than in production breach.

Traditional model:

```
Dev → Test → Security audit (weeks) → Deploy → Pen test → Incident
```

Shift-left model:

```
Threat model → Secure coding → Pre-commit → PR scan → CI scan → Deploy → Runtime monitor
```

Security becomes **everyone's responsibility** with platform-enabling tooling—not solely a separate security team blocking releases.

---

## 49.2 Security activities across the SDLC

| Phase | Activities |
|-------|------------|
| **Design** | Threat modeling (STRIDE), security requirements, data classification |
| **Develop** | Secure coding standards, IDE plugins, pre-commit hooks |
| **Build** | SAST, SCA, secret scanning, IaC scan |
| **Test** | DAST, fuzzing, penetration test automation |
| **Deploy** | Image signing, admission control, least-privilege IAM |
| **Operate** | Runtime detection, WAF, audit logs, incident response |
| **Respond** | Vulnerability disclosure, patch SLAs, forensics |

The **software supply chain** spans all phases—dependencies, build systems, registries, and deployment pipelines are attack surfaces (SolarWinds, Log4Shell lessons).

---

## 49.3 Threat modeling fundamentals

**STRIDE** categorizes threats:

| Letter | Threat | Example |
|--------|--------|---------|
| **S** | Spoofing | Fake JWT |
| **T** | Tampering | Modify API payload |
| **R** | Repudiation | Deny transaction without audit log |
| **I** | Information disclosure | Log leaking PII |
| **D** | Denial of service | Unbounded query |
| **E** | Elevation of privilege | IDOR to admin |

Process:

1. Draw data flow diagram (users, services, data stores)
2. Identify trust boundaries
3. Apply STRIDE per component
4. Prioritize mitigations (risk = likelihood × impact)
5. Track in backlog

Tools: **Microsoft Threat Modeling Tool**, **OWASP Threat Dragon**, Miro templates.

Output feeds security test cases and pipeline scan configuration.

---

## 49.4 Pipeline security gates

Integrate checks in CI without destroying developer velocity:

```
Commit → Secret scan → Lint/IaC policy → SAST → Unit tests → Build →
  Container scan → SCA → Sign artifact → Deploy (policy) → DAST (staging)
```

Gate philosophy:

| Severity | Policy example |
|----------|----------------|
| Critical | Block merge/deploy |
| High | Block deploy to prod; warn on PR |
| Medium | Ticket required; SLA 30 days |
| Low | Informational |

**Policy as Code** (OPA, Conftest) enforces gates consistently:

```rego
# deny deployment if critical CVEs in scan result
package deploy

deny[msg] {
  input.scan.critical_count > 0
  msg := sprintf("Critical vulnerabilities: %d", [input.scan.critical_count])
}
```

Balance **speed vs safety**: fast feedback on PR (< 10 min for secret/SAST); heavier scans async or nightly.

---

## 49.5 Secret scanning

Secrets in Git history are permanent until rotated. Scan **commits**, **PRs**, and **history**.

Tools:

| Tool | Integration |
|------|-------------|
| **GitLeaks** | Pre-commit, CI |
| **TruffleHog** | CI, deep history |
| **GitHub secret scanning** | Native on GitHub |
| **GitLab secret detection** | Native on GitLab |

Pre-commit hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

CI step:

```yaml
- name: Secret scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

On leak: **rotate immediately**, purge from history (`git filter-repo`) if exposed publicly—scanning alone is insufficient.

---

## 49.6 Secure defaults and platform guardrails

Platform engineering enables secure defaults:

- **Base images** — Hardened, scanned, regularly rebuilt
- **Template repos** — CI security jobs pre-configured
- **Namespace/network policies** — Deny-by-default in Kubernetes
- **IAM roles** — Short-lived credentials, no long-lived keys in repos
- **Dependency update bots** — Renovate, Dependabot with auto-merge for patches

**Golden paths** make the secure path the easy path—developers opt out explicitly, not opt in.

---

## 49.7 Security champions program

Scale security expertise without bottleneck:

| Role | Responsibility |
|------|----------------|
| **Central security** | Policy, tooling, compliance, escalation |
| **Security champion** (per team) | Triage findings, threat model reviews, training |
| **Developers** | Fix findings, secure coding |

Champions attend monthly syncs, get early tool access, relay team friction to security org.

Metrics: mean time to remediate (MTTR) vulnerabilities by severity, not raw finding count (discourages hiding issues).

---

## 49.8 Compliance integration

Map shift-left controls to frameworks:

| Control area | Pipeline automation |
|--------------|---------------------|
| Access control | IAM review in IaC scan |
| Change management | Git audit trail, approved PRs |
| Vulnerability mgmt | SCA/SAST gates, ticket integration |
| Logging/monitoring | Mandatory observability checks |
| Encryption | TLS policy, secret management validation |

Evidence collection: export CI scan reports, deployment logs, and policy decisions for SOC 2, ISO 27001, PCI audits—**continuous compliance** vs annual scramble.

---

## 49.9 Culture and psychological safety

Developers must report security concerns without fear. Blameless response to leaked secrets encourages fast rotation.

Training:

- OWASP Top 10 awareness
- Secure coding labs (SQLi, XSS in sandbox)
- Annual phishing simulations

Security team as **enabler** ("here's how to fix") not **gatekeeper** ("no").

---

## 49.10 Chapter summary

- Shift-left embeds security early: threat modeling, scanning, and policy gates in CI/CD.
- Secret scanning, SAST/SCA/DAST (Chapters 50–52), and policy-as-code form layered defense.
- Platform golden paths and security champions scale practices across teams.
- Balance blocking gates with remediation SLAs and developer experience.

---

## 🧪 Lab 49.1 — Pre-commit security stack

1. Add pre-commit with gitleaks and detect-private-key hooks to a sample repo.
2. Attempt to commit a fake AWS key; confirm hook blocks.
3. Add CI job duplicating secret scan for defense in depth.

---

## 🧪 Lab 49.2 — Threat model exercise

1. Draw data flow for a three-tier web app.
2. Apply STRIDE to API gateway and database boundary.
3. Produce 5 mitigations mapped to pipeline controls (scan type or policy).

---

## Review questions

1. What does "shift-left" mean in DevSecOps?
2. List security activities appropriate at design vs deploy phases.
3. Explain STRIDE with one example threat per category.
4. How should CI gates differ for critical vs medium findings?
5. Why rotate secrets immediately when leaked to Git?
6. What is a security champion, and why use this model?
7. How does shift-left support compliance audits?

---

*Continue: Chapter 50 — SAST, DAST, SCA, Container Scanning*
