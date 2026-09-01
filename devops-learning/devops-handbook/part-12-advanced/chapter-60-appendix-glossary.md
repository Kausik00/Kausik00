# Chapter 60: Appendix — Cheatsheets, Glossary, and Index

*DevOps Handbook — Part XII, Pages 1181–1200*

---

## 60.1 kubectl quick reference

```bash
# Context and namespaces
kubectl config use-context prod
kubectl get pods -n production -o wide

# Deployments
kubectl rollout status deployment/api -n production
kubectl rollout undo deployment/api -n production
kubectl scale deployment/api --replicas=5

# Debugging
kubectl logs -f deployment/api -c api --tail=100
kubectl exec -it pod/api-xxx -- /bin/sh
kubectl describe pod api-xxx
kubectl get events --sort-by=.metadata.creationTimestamp

# Resources
kubectl top pods -n production
kubectl apply -f manifest.yaml --dry-run=server
kubectl diff -f manifest.yaml

# Port forward
kubectl port-forward svc/api 8080:80
```

---

## 60.2 Docker quick reference

```bash
# Build and run
docker build -t myapp:v1 .
docker run -d -p 8080:80 --name myapp myapp:v1
docker exec -it myapp sh

# Cleanup
docker system prune -a --volumes  # caution: removes unused data
docker logs -f myapp

# Multi-stage build pattern
# FROM golang:1.22 AS builder
# FROM gcr.io/distroless/static-debian12
```

---

## 60.3 Terraform quick reference

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform state list
terraform import aws_instance.web i-0abc123
terraform fmt -recursive
terraform validate

# Workspace
terraform workspace select staging
terraform workspace list
```

---

## 60.4 Git essentials

```bash
git status
git log --oneline --graph -20
git diff main...feature-branch
git rebase -i HEAD~3
git stash push -m "wip"
git cherry-pick abc1234

# Recover
git reflog
git reset --hard HEAD@{2}
```

---

## 60.5 Linux troubleshooting

```bash
# Processes
ps aux | grep nginx
systemctl status nginx
journalctl -u nginx -f --since "10 min ago"

# Network
ss -tlnp
curl -vI https://example.com
dig +short example.com
traceroute example.com

# Disk
df -h
du -sh /var/log/*
lsof +D /path/to/dir

# Resources
top -o %CPU
free -h
vmstat 1 5
iostat -x 1 3
```

---

## 60.6 PromQL cheatsheet

```promql
# Rate and errors
rate(http_requests_total[5m])
sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))

# Latency percentiles
histogram_quantile(0.99, sum(rate(http_duration_bucket[5m])) by (le, service))

# Resource usage
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Predict disk full (4h)
predict_linear(node_filesystem_free_bytes[1h], 4*3600) < 0

# Absent metric alert helper
absent(up{job="api"})
```

---

## 60.7 CI/CD YAML snippets

GitHub Actions concurrency:

```yaml
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: true
```

GitLab rules:

```yaml
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

Jenkins declarative post:

```groovy
post {
  always { cleanWs() }
  failure { emailext subject: "Failed", body: "${env.BUILD_URL}" }
}
```

---

## 60.8 Security tool commands

```bash
# Secret scan
gitleaks detect --source . -v

# Container scan
trivy image myapp:latest
trivy fs --severity CRITICAL,HIGH .

# SBOM
syft packages dir:. -o cyclonedx-json > sbom.json
grype sbom:sbom.json

# Sign and verify
cosign sign myregistry/myapp:v1
cosign verify myregistry/myapp:v1

# IaC scan
checkov -d terraform/ --framework terraform
```

---

## 60.9 Observability checklist

| Signal | Minimum instrumentation |
|--------|-------------------------|
| Metrics | RED per service; USE per node |
| Logs | JSON with timestamp, level, service, trace_id |
| Traces | W3C traceparent on all HTTP/gRPC exits |
| Alerts | SLO burn + symptom-based pages only |
| Dashboards | Golden signals per service + infra overview |

---

## 60.10 SLO error budget reference

| SLO | Monthly downtime budget | Quarterly budget |
|-----|-------------------------|------------------|
| 99% | ~7.2 hours | ~21.6 hours |
| 99.9% | ~43 minutes | ~2.16 hours |
| 99.95% | ~22 minutes | ~1.08 hours |
| 99.99% | ~4.3 minutes | ~13 minutes |

Formula: `budget = (1 - SLO) × period_seconds`

---

## 60.11 Glossary

| Term | Definition |
|------|------------|
| **Alert fatigue** | Desensitization from excessive non-actionable alerts |
| **Argo CD** | GitOps continuous delivery tool for Kubernetes |
| **Blue/green** | Deployment with two environments; traffic switch for cutover |
| **Canary** | Gradual traffic shift to new version with monitoring |
| **CI/CD** | Continuous Integration / Continuous Delivery or Deployment |
| **Container** | Lightweight isolated process bundle with filesystem |
| **DAST** | Dynamic Application Security Testing on running apps |
| **DevSecOps** | Integrating security into DevOps lifecycle |
| **DORA metrics** | Deployment frequency, lead time, change failure rate, MTTR |
| **Error budget** | Allowed unreliability: 1 − SLO |
| **Feature flag** | Runtime toggle decoupling deploy from release |
| **FinOps** | Cloud financial management discipline |
| **GitOps** | Declarative infra/apps with Git as source of truth |
| **Golden path** | Supported self-service workflow in platform engineering |
| **Helm** | Kubernetes package manager |
| **IaC** | Infrastructure as Code |
| **IDP** | Internal Developer Platform |
| **Ingress** | Kubernetes HTTP routing into cluster |
| **Kubernetes** | Container orchestration platform |
| **MLOps** | ML lifecycle automation and operations |
| **MTTR** | Mean Time to Restore service |
| **Observability** | Inferring internal state from external outputs |
| **OIDC** | OpenID Connect federated identity |
| **OPA** | Open Policy Agent for policy decisions |
| **Pod** | Smallest deployable unit in Kubernetes |
| **Prometheus** | Open-source metrics TSDB and scraper |
| **Rego** | OPA policy language |
| **Runbook** | Step-by-step operational procedure |
| **SAML** | Security Assertion Markup Language for SSO |
| **SAST** | Static Application Security Testing |
| **SBOM** | Software Bill of Materials |
| **SCA** | Software Composition Analysis for dependencies |
| **Shift-left** | Moving activities earlier in SDLC |
| **SLO/SLI/SLA** | Service Level Objective/Indicator/Agreement |
| **SLSA** | Supply-chain Levels for Software Artifacts |
| **SRE** | Site Reliability Engineering |
| **Terraform** | IaC tool by HashiCorp |
| **Toil** | Manual repetitive operational work |
| **Trunk-based development** | Short-lived branches merged frequently to main |
| **Vault** | HashiCorp secrets management |
| **WAF** | Web Application Firewall |

---

## 60.12 Handbook chapter index

| Part | Chapters | Topics |
|------|----------|--------|
| I | 1–4 | DevOps culture, CALMS, careers |
| II | 5–8 | Linux, systemd, networking, bash |
| III | 9–11 | Git, branching, collaboration |
| IV | 12–15 | Networking, HTTP/TLS, load balancing |
| V | 16–19 | Python, Go, templating, testing |
| VI | 20–25 | IaC, Terraform, Ansible, Packer, policy |
| VII | 26–30 | Docker, compose, registries, Podman |
| VIII | 31–36 | Kubernetes, Helm, GitOps, RBAC |
| IX | 37–42 | CI/CD, Actions, Jenkins, GitLab, deploy, DORA |
| X | 43–48 | Observability, Prometheus, ELK, OTel, SLO, chaos |
| XI | 49–54 | DevSecOps, scanning, secrets, supply chain, compliance |
| XII | 55–60 | Platform eng, multi-cloud, FinOps, MLOps, capstone |

Cross-reference: [AWS Handbook](../aws-handbook/00-table-of-contents.md) for cloud-specific service depth.

---

## 60.13 Recommended reading

| Book | Author(s) | Topic |
|------|-----------|-------|
| *The DevOps Handbook* | Kim, Humble, Debois, Willis | DevOps practices |
| *Accelerate* | Forsgren, Humble, Kim | DORA research |
| *Site Reliability Engineering* | Google | SRE principles |
| *The Phoenix Project* | Kim, Spafford, Behr | DevOps narrative |
| *Team Topologies* | Skelton, Pais | Organization design |
| *Kubernetes Up & Running* | Hightower, Burns, Beda | K8s operations |
| *Terraform: Up & Running* | Brikman | IaC patterns |
| *Security DevOps* | Bellomo et al. | DevSecOps |

Online: [opentelemetry.io](https://opentelemetry.io), [prometheus.io](https://prometheus.io), [slsa.dev](https://slsa.dev), [finops.org](https://www.finops.org)

---

## 60.14 Certification paths (optional)

| Certification | Focus |
|---------------|-------|
| AWS Solutions Architect / DevOps Pro | AWS platform |
| CKA / CKAD / CKS | Kubernetes admin, app dev, security |
| Terraform Associate | IaC |
| LFCS / LFCE | Linux |
| GIAC / Security+ | Security foundations |

Certifications validate knowledge; hands-on labs in this handbook build practical skill.

---

## 60.15 Final review questions (handbook-wide)

1. Explain the Three Ways and how Parts IX–X implement the Second and Third Ways.
2. Design a CI pipeline listing stages from commit to production with security gates.
3. How do SLOs, error budgets, and DORA metrics interact in organizational decision-making?
4. Compare Terraform, Kubernetes, and GitOps responsibilities in platform architecture.
5. Describe a supply chain security program covering SBOM, signing, and admission control.
6. When would you choose Elasticsearch vs Loki for logging?
7. What capabilities belong in an Internal Developer Platform vs team-owned services?

---

## 60.16 Chapter summary

- This appendix provides command cheatsheets for daily DevOps operations.
- The glossary defines key terms used throughout the handbook.
- The chapter index and reading list support continued learning beyond these pages.

---

*End of DevOps Handbook — Return to [Table of Contents](../00-table-of-contents.md)*
