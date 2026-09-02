# Chapter 59: Capstone — End-to-End Production System Design

*DevOps Handbook — Pages 287–292 of this PDF edition*
---

## 59.1 Capstone objectives

This chapter synthesizes the handbook into a **reference architecture** for a production-grade SaaS platform. You will design a system that embodies DevOps principles: automated delivery, observable operations, security by default, cost awareness, and reliable incident response.

Capstone scenario: **ShopStream** — a B2C e-commerce API handling product catalog, cart, checkout, and order fulfillment. Requirements:

| Requirement | Target |
|-------------|--------|
| Availability SLO | 99.9% (43 min/month error budget) |
| Latency SLO | p99 < 500ms for checkout API |
| Scale | 10K RPS peak, 50 microservices over 2 years |
| Compliance | PCI DSS for payment scope; SOC 2 Type II |
| Team | 8 stream-aligned teams + 1 platform team |
| Cloud | AWS primary (reference AWS Handbook for service depth) |

---

## 59.2 Architecture overview

```
                         ┌──────────────┐
                         │  CloudFront  │
                         │  + WAF       │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ ALB Ingress  │
                         └──────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        ┌──────────┐     ┌──────────┐     ┌──────────┐
        │ Catalog  │     │  Cart    │     │ Checkout │
        │ Service  │     │ Service  │     │ Service  │
        └────┬─────┘     └────┬─────┘     └────┬─────┘
             │                │                │
             └────────────────┼────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Event Bus (SNS/  │
                    │  SQS / Kafka MSK) │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Inventory│   │ Payment  │   │ Fulfill  │
        │ Service  │   │ (PCI zone)│   │ Service  │
        └──────────┘   └──────────┘   └──────────┘

Data: RDS PostgreSQL (per service), ElastiCache Redis, S3 assets
Observability: Prometheus/Grafana, Loki, Tempo, PagerDuty
Platform: EKS, Argo CD, Backstage, Vault/ESO
```

Design principles applied:

- **Domain-driven service boundaries** — Checkout team owns checkout SLO
- **Async where possible** — Order events via queue, not synchronous chains
- **PCI segmentation** — Payment service in isolated subnet; no PAN in logs
- **Fail closed** — Auth failures reject; circuit breakers on dependencies

---

## 59.3 Repository and team structure

**Team Topologies** mapping:

| Team | Services | Interaction |
|------|----------|-------------|
| Catalog | product-api, search-indexer | Stream-aligned |
| Checkout | cart, checkout, payment-gateway | Stream-aligned |
| Fulfillment | inventory, shipping, notifications | Stream-aligned |
| Platform | IDP, clusters, shared modules | Platform X-as-a-Service |
| Security | Policies, scanning, audit | Enabling |

Repository strategy: **polyrepo** with shared templates (one repo per service)—scaffolded via Backstage golden path.

Each service repo contains:

```
service-name/
├── src/
├── Dockerfile
├── helm/
├── terraform/          # Service-specific infra module
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── catalog-info.yaml
├── docs/
└── RUNBOOK.md
```

Monorepo optional for tightly coupled early-stage; migrate to polyrepo as teams scale.

---

## 59.4 CI/CD pipeline design

Per-service pipeline (GitHub Actions):

```
PR opened:
  lint → unit test → SAST (Semgrep) → SCA → IaC scan → build image →
  Trivy scan → push to ECR (SHA tag) → deploy preview (Review App)

Merge to main:
  integration tests → sign image (cosign) → generate SBOM →
  deploy staging (Argo CD sync) → DAST (ZAP baseline) →
  manual approval → canary 5% prod → metrics gate → full prod
```

Key configurations:

```yaml
# Excerpt — production deploy with canary via Argo Rollouts
deploy-production:
  needs: [build, scan, staging-smoke]
  environment: production
  steps:
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::ACCOUNT:role/GHA-Deploy-Prod
    - run: |
        cosign verify ${{ env.IMAGE }} --certificate-oidc-issuer=...
        argocd app set checkout-api -p image.tag=${{ github.sha }}
        argocd app sync checkout-api --prune
```

DORA instrumentation: deployment webhook to metrics backend on every prod sync.

Deployment strategies by service criticality:

| Service | Strategy |
|---------|----------|
| Catalog | Rolling |
| Checkout | Canary with automated analysis |
| Payment | Blue/green + manual approval |

Feature flags (LaunchDarkly) for checkout UI experiments decoupled from deploy cadence.

---

## 59.5 Infrastructure as Code

**Terraform** layered modules:

```
terraform/
├── modules/
│   ├── vpc/
│   ├── eks/
│   ├── rds/
│   └── service-deployment/
├── environments/
│   ├── staging/
│   └── production/
└── global/
    └── iam/
```

State: S3 backend + DynamoDB lock per environment. CI runs `terraform plan` on PR, `apply` on merge to environment branch.

**GitOps** (Argo CD) reconciles Kubernetes from `k8s-manifests` repo:

```
apps/
├── checkout-api/
│   ├── base/
│   └── overlays/
│       ├── staging/
│       └── production/
└── catalog-api/
    └── ...
```

Platform provisions EKS, networking, shared RDS proxy; teams own service overlays.

Policy gates: Checkov in CI; Gatekeeper in cluster (no privileged pods, required labels, signed images).

---

## 59.6 Security architecture

Defense in depth layers:

| Layer | Implementation |
|-------|----------------|
| Edge | WAF, rate limiting, TLS 1.3 |
| Identity | OAuth2/OIDC (Cognito/Auth0), mTLS service mesh (optional) |
| Network | VPC segmentation, NetworkPolicies, PCI isolated subnet |
| Secrets | Vault + ESO; dynamic DB creds for payment service |
| Supply chain | SBOM, cosign, Kyverno verifyImages |
| Runtime | Falco rules, PSA restricted |
| Compliance | Audit logs → SIEM; quarterly access reviews |

PCI scope minimization: payment service tokenizes via Stripe—ShopStream never stores PAN; SAQ A scope where possible.

Security scanning integrated per Chapter 49–54; critical CVE blocks prod deploy.

---

## 59.7 Observability and SRE

Per-service SLOs documented in `slos/checkout-api.yaml`:

```yaml
service: checkout-api
slos:
  - name: availability
    target: 99.9
    window: 30d
    sli:
      query: |
        sum(rate(http_requests_total{service="checkout",status!~"5.."}[5m]))
        / sum(rate(http_requests_total{service="checkout"}[5m]))
  - name: latency-p99
    target: 99.0  # 99% under 500ms
    window: 30d
    sli:
      query: |
        histogram_quantile(0.99, sum(rate(http_duration_bucket[5m])) by (le))
        < 0.5
```

Stack:

- **Metrics** — Prometheus + Grafana (kube-prometheus-stack)
- **Logs** — Fluent Bit → Loki (or OpenSearch for full-text SIEM)
- **Traces** — OpenTelemetry SDK → Collector → Tempo
- **Alerting** — Alertmanager → PagerDuty; multi-window burn alerts

Runbooks in repo `RUNBOOK.md` linked from Backstage. On-call rotation per team with escalation to platform for infra issues.

Incident process: SEV definitions, blameless postmortems within 5 days, action items in Jira.

Chaos: monthly Litmus pod-delete on staging; quarterly game day simulating payment dependency failure.

---

## 59.8 Data, DR, and scaling

| Component | Pattern |
|-----------|---------|
| PostgreSQL | RDS Multi-AZ; read replicas for catalog |
| Redis | ElastiCache cluster mode for session cache |
| Object storage | S3 + CloudFront for product images |
| Events | MSK Kafka for order stream; DLQ for failures |
| Search | OpenSearch fed by CDC from catalog DB |

**DR**: RPO 1 hour, RTO 4 hours—warm standby in second region (us-west-2); Route 53 failover drill quarterly.

**Autoscaling**: HPA on CPU/RPS custom metrics; Karpenter for node provisioning; scale-to-zero for dev namespaces (FinOps).

---

## 59.9 FinOps and platform metrics

Mandatory tags: `team`, `service`, `environment`, `cost-center`.

Kubecost dashboards per team; monthly FinOps review with unit economics:

- Cost per order processed
- Cost per active user
- Idle resource report automated weekly

Infracost on Terraform PRs; budget alerts at org and team level.

Platform team metrics: golden path adoption %, developer CSAT, time-to-first-deploy for new services.

---

## 59.10 Capstone delivery roadmap

Phased implementation (technical sequencing, not calendar estimates):

| Phase | Deliverables |
|-------|--------------|
| **1 — Foundation** | EKS, VPC, Terraform modules, Argo CD, observability stack |
| **2 — Platform** | Backstage, golden path template, ESO, CI templates |
| **3 — First service** | Catalog API end-to-end: CI, deploy, SLO, runbook |
| **4 — Critical path** | Checkout + payment with PCI segmentation, canary |
| **5 — Hardening** | Security gates, chaos, DR drill, compliance evidence |
| **6 — Scale** | Event bus, additional services, FinOps optimization |

Each phase ends with **definition of done**: deployed to staging, SLO dashboard live, runbook reviewed, security scan clean.

---

## 59.11 Design review checklist

Before production launch, verify:

- [ ] SLOs defined with error budget alerts
- [ ] CI: lint, test, SAST, SCA, container scan, IaC scan
- [ ] Signed images + admission policy enforced
- [ ] Secrets not in Git; ESO/Vault operational
- [ ] Centralized logs with trace correlation
- [ ] Runbooks and on-call rotation active
- [ ] DR failover tested within RTO target
- [ ] Tagging and cost dashboards per team
- [ ] Postmortem template and incident roles documented
- [ ] DORA metrics emitted from pipeline

---

## 59.12 Chapter summary

- ShopStream capstone integrates microservices, EKS, GitOps, CI/CD security, observability, and FinOps.
- Team Topologies and golden paths scale organizationally; polyrepo + templates balance autonomy and consistency.
- Layered security, SLO-driven operations, and phased delivery reduce risk while enabling continuous deployment.
- Use the design review checklist as a template for your own production systems.

---

## 🧪 Capstone Lab — Mini ShopStream

Build a reduced capstone (3 services: catalog, cart, checkout):

1. Scaffold services via template with shared CI pipeline.
2. Deploy to local k3d or cloud EKS with Argo CD.
3. Implement Prometheus metrics, one SLO dashboard, and alert.
4. Add Trivy scan gate and cosign sign (optional keyless).
5. Write RUNBOOK.md and conduct 30-minute game day (kill checkout pod).
6. Document architecture decision record (ADR) for one major choice.

---

## Review questions

1. How do you decompose ShopStream into team-aligned services?
2. Why isolate payment in a separate network segment?
3. Describe the full CI/CD path from PR to production canary.
4. Which observability signals form checkout SLOs?
5. How does the platform team enable stream-aligned teams without bottleneck?
6. What DR strategy meets RPO 1h / RTO 4h?
7. Walk through the capstone design review checklist for catalog-api.

---

*Continue: Chapter 60 — Appendix, Cheatsheets, Glossary*
