# Chapter 50: SAST, DAST, SCA, and Container Scanning

*DevOps Handbook — Pages 241–246 of this PDF edition*
---

## 50.1 Application security testing taxonomy

Modern applications combine custom code, open-source dependencies, container images, and infrastructure configuration—each layer requires specialized scanning.

| Acronym | Full name | What it analyzes | When |
|---------|-----------|------------------|------|
| **SAST** | Static Application Security Testing | Source code without running | PR, CI build |
| **DAST** | Dynamic Application Security Testing | Running application (black-box) | Staging, pre-prod |
| **SCA** | Software Composition Analysis | Dependencies, licenses, CVEs | CI, daily scheduled |
| **IAST** | Interactive AST | Instrumented runtime + code | Optional hybrid |
| **Container scan** | Image/filesystem CVE scan | OS packages, layers | After docker build |
| **IaC scan** | Infrastructure as Code | Terraform, K8s manifests | PR, CI |

No single tool covers all—**defense in depth** layers findings with deduplication and prioritization.

---

## 50.2 SAST — static analysis

SAST parses source code and bytecode for vulnerability patterns: SQL injection, XSS, path traversal, hardcoded secrets, insecure crypto.

Popular tools:

| Tool | Languages | Notes |
|------|-----------|-------|
| **Semgrep** | Multi-language, custom rules | Fast, CI-friendly |
| **SonarQube** | 30+ languages | Quality + security |
| **CodeQL** | Multi (GitHub) | Semantic analysis |
| **Bandit** | Python | Python-specific |
| **gosec** | Go | Go-specific |
| **Checkmarx / Veracode** | Enterprise | Broad coverage |

Semgrep CI example:

```yaml
- name: Semgrep SAST
  uses: returntocorp/semgrep-action@v1
  with:
    config: >-
      p/security-audit
      p/owasp-top-ten
      p/ci
```

Custom Semgrep rule:

```yaml
rules:
  - id: sql-injection-concat
    patterns:
      - pattern: |
          $QUERY = "..." + $USER_INPUT + "..."
      - pattern: execute($QUERY)
    message: Possible SQL injection via string concatenation
    severity: ERROR
    languages: [python, javascript]
```

SAST limitations:

- **False positives** — Requires tuning and baselines
- **No runtime context** — Cannot see config-dependent bugs
- **Late custom rules** — Novel vulns need rule updates

Triage workflow: suppress with justification (`nosemgrep` comment + ticket), fix true positives within SLA.

---

## 50.3 DAST — dynamic testing

DAST probes **running** applications like an attacker—HTTP requests, form fuzzing, authentication bypass attempts.

Tools:

| Tool | Type |
|------|------|
| **OWASP ZAP** | Open-source proxy + automation |
| **Burp Suite** | Manual + automated (pro) |
| **Nuclei** | Template-based scanner |
| **StackHawk** | CI-integrated DAST |
| **Acunetix** | Commercial |

ZAP baseline scan in CI (against staging):

```yaml
- name: OWASP ZAP Baseline
  uses: zaproxy/action-baseline@v0.12.0
  with:
    target: https://staging.example.com
    rules_file_name: .zap/rules.tsv
    cmd_options: -a
```

DAST requires:

- Deployed environment with realistic data (sanitized)
- Authentication handling (ZAP contexts, scripts)
- Scope limits—never scan production without approval

Finds: misconfigured headers, exposed admin panels, reflected XSS, CSRF gaps—issues SAST may miss.

---

## 50.4 SCA — dependency analysis

**SCA** inventories direct and transitive dependencies, matches against CVE databases (NVD, GitHub Advisory), flags license violations.

Tools:

| Tool | Integration |
|------|-------------|
| **Dependabot** | GitHub native PRs |
| **Renovate** | Multi-platform, configurable |
| **Snyk** | SCA + container + IaC |
| **Grype** | Anchore ecosystem |
| **OWASP Dependency-Check** | Jenkins, CLI |

GitHub Dependabot config:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: npm
    directory: "/"
    schedule:
      interval: daily
    open-pull-requests-limit: 10
    groups:
      production-dependencies:
        patterns: ["*"]
        exclude-patterns: ["@types/*"]
```

Syft + Grype pipeline:

```bash
syft packages dir:. -o cyclonedx-json > sbom.json
grype sbom:sbom.json --fail-on critical
```

Prioritize by **exploitability** (EPSS score), **reachability** (is vulnerable code path used?), and **severity**—not all CVEs are exploitable in your context.

---

## 50.5 Container and image scanning

Container images bundle OS packages and application dependencies—both need scanning.

| Scanner | Focus |
|---------|-------|
| **Trivy** | OS + language deps, misconfig, secrets |
| **Grype** | CVE matching via SBOM |
| **Clair** | Layer-based analysis |
| **Snyk Container** | Integrated platform |
| **Amazon ECR scanning** | Native AWS |

Trivy in GitHub Actions:

```yaml
- name: Build image
  run: docker build -t myapp:${{ github.sha }} .

- name: Trivy scan
  uses: aquasecurity/trivy-action@0.24.0
  with:
    image-ref: myapp:${{ github.sha }}
    format: sarif
    output: trivy-results.sarif
    severity: CRITICAL,HIGH
    exit-code: 1

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: trivy-results.sarif
```

Scan **base images** regularly—pin to digest, not `:latest`. Rebuild golden images on CVE patches.

Distroless/minimal bases reduce attack surface and scan noise.

---

## 50.6 IaC and Kubernetes scanning

| Tool | Targets |
|------|---------|
| **Checkov** | Terraform, CloudFormation, K8s, Dockerfile |
| **tfsec / Trivy config** | Terraform |
| **kube-score** | Kubernetes best practices |
| **Polaris** | K8s policy validation |
| **Kubescape** | NSA/CIS benchmarks |

Checkov example:

```bash
checkov -d terraform/ --framework terraform \
  --check CKV_AWS_79,CKV_AWS_80 \
  --soft-fail-on LOW
```

Common findings: public S3 buckets, overly permissive security groups, containers running as root, missing resource limits.

---

## 50.7 Unified vulnerability management

Centralize findings from SAST, DAST, SCA, container scans:

```
CI tools → SARIF / API → DefectDojo / GitHub Security / Snyk dashboard
                              │
                         Prioritization
                         SLA tracking
                         Jira tickets
```

**SARIF** (Static Analysis Results Interchange Format) standardizes results across tools for GitHub Advanced Security integration.

Remediation SLAs (example):

| Severity | Fix SLA |
|----------|---------|
| Critical (exploitable) | 7 days |
| High | 30 days |
| Medium | 90 days |
| Low | Next quarter |

---

## 50.8 Reducing noise

| Technique | Benefit |
|-----------|---------|
| Baseline accepted risk | Stop re-alerting known issues |
| Reachability analysis | Focus on used vulnerable code |
| EPSS prioritization | Exploit probability scoring |
| Consolidate tools | One SCA source of truth |
| Fix upstream | Patch base image vs per-app |

Developer experience: surface findings in PR comments with fix guidance—not email-only reports ignored for weeks.

---

## 50.9 Chapter summary

- SAST analyzes source; DAST probes running apps; SCA tracks dependency CVEs; container scans cover image layers.
- Integrate scans in CI with severity gates; export SARIF for unified tracking.
- Combine tools for defense in depth; prioritize by exploitability and reachability.
- Maintain base images, dependency bots, and remediation SLAs for sustainable security.

---

## 🧪 Lab 50.1 — Full scan pipeline

1. Add Semgrep, Trivy (filesystem + image), and Dependabot to a sample Node.js + Docker project.
2. Introduce deliberate vulnerable dependency (`npm install lodash@4.17.20`); confirm SCA flags CVE.
3. Fix via upgrade; verify clean scan.

---

## 🧪 Lab 50.2 — DAST against staging

1. Deploy sample app to staging with intentional missing security header.
2. Run OWASP ZAP baseline; document finding.
3. Add header middleware; re-scan to confirm resolution.

---

## Review questions

1. Compare SAST and DAST—what can each detect that the other cannot?
2. Why scan container images after build, not only application dependencies?
3. What is SARIF, and why use it?
4. How do EPSS and reachability improve SCA prioritization?
5. Name three common Checkov findings in Terraform.
6. What are typical false positive sources in SAST, and how handle them?
7. Why should DAST run against staging, not production?

---

*Continue: Chapter 51 — Secrets Management*
