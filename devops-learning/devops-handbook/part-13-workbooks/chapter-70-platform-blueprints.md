# Chapter 70: Platform Blueprints

*DevOps Handbook — Pages 373–380 of this PDF edition*

*DevOps Handbook — Workbook*
---

## 70.1 Platform as a product with a blueprint, not a wiki of clusters

Chapter 55 introduced platform engineering and Backstage. This workbook is the **blueprint layer**: golden paths that developers actually finish, a Backstage catalog that is truthful, **cluster tenancy** that isolates blast radius, and **IDP metrics** that tell you whether the platform is winning.

A platform without golden paths is a shared Kubernetes account. A golden path without tenancy is a noisy-neighbor incident. Tenancy without metrics is a cost center nobody can defend.

| Blueprint piece | Question it answers |
|-----------------|---------------------|
| Golden path | “How do I ship a service the blessed way?” |
| Software catalog | “Who owns this, and where does it run?” |
| Tenancy | “What can this team break?” |
| IDP metrics | “Is the platform faster than shadow IT?” |

---

## 70.2 Golden paths: design, scope, and versioning

A **golden path** is an opinionated, supported journey: create service → CI → env → observability → deploy. Shadow paths (copy a repo, tweak YAML) should still work but get **less** support.

### 70.2.1 Path catalog (typical SaaS org)

| Path | Output | Not for |
|------|--------|---------|
| `http-service-go` | Repo, CI, Helm/Kustomize, SLO dashboard, PDB | Batch jobs |
| `scheduled-job` | CronJob, retries, alerting on last-success | User traffic |
| `static-frontend` | CDN/S3, GitHub Pages alternative | SSR unless documented |
| `data-pipeline` | Composer/Airflow/Argo Workflows template | OLTP |
| `internal-library` | Release please, package registry | Deployable services |

**Fewer paths, deeper support.** Twelve half-broken cookies are worse than three excellent ones.

### 70.2.2 Properties of a good path

1. **Runnable in < 30 minutes** to a URL in nonprod (IDP metric).
2. **Sane defaults:** non-root, requests/limits, NetworkPolicy, PodDisruptionBudget, HPA stub, `/healthz`.
3. **Extension points:** extra Helm values, not forks of the template.
4. **Versioned:** `golden-paths/http-service-go@v4` in Backstage software templates.
5. **Upgradeable:** a `template version` annotation and a bot PR for security patches in the skeleton (Dependabot on the template repo **and** a path to downstream).
6. **Docs in the repo** (TechDocs) generated from the same template.

### 70.2.3 Anti-golden-path

- Template that scaffolds 2018 Jenkins plus a unique Terraform state per microservice in the **app** repo with no module versions (Chapter 64).
- Template that requires opening three tickets to platform for DNS, certs, and namespace.
- Template whose CI does not pass on an empty service.

**Self-service rule:** if a human platform engineer must click for the **happy path**, it is not golden yet. Tickets are for **exceptions** (public internet, PCI subnet, extra quota).

### 70.2.4 Scaffolder sketch (Backstage)

```yaml
# template.yaml (abridged)
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: http-service-go
  title: HTTP Service (Go)
spec:
  owner: group:platform
  type: service
  parameters:
    - title: Service
      properties:
        name: { type: string, pattern: '^[a-z0-9-]+$' }
        owner: { type: string, ui:field: OwnerPicker }
        description: { type: string }
  steps:
    - id: fetch
      action: fetch:template
      input:
        url: ./skeleton
        values:
          name: ${{ parameters.name }}
          owner: ${{ parameters.owner }}
    - id: publish
      action: publish:github
      input:
        repoUrl: github.com?owner=acme&repo=${{ parameters.name }}
    - id: register
      action: catalog:register
```

Skeleton contains `catalog-info.yaml`, `.github/workflows/ci.yml` that **calls reusable workflows @v3** (Chapter 67), `deploy/` with digest-friendly Helm, and `SLO.md` defaults (Chapter 68).

**Tests for templates:** CI on the template repo that **renders** the skeleton and runs `go test` / `helm lint` on the output. Broken templates are platform Sev-2.

---

## 70.3 Backstage: catalog truth, not a second CMDB that lies

### 70.3.1 Entity model you should actually use

| Kind | Use |
|------|-----|
| Component | Deployable or library |
| API | OpenAPI/gRPC contract |
| Resource | Database, bucket, topic |
| System | Product grouping |
| Domain | Business area |
| Group / User | Ownership (IdP sync) |
| Location | Where YAML lives |

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: shop-checkout
  annotations:
    github.com/project-slug: acme/shop-checkout
    backstage.io/techdocs-ref: dir:.
    prometheus.io/rule: shop-checkout
    argocd/app-name: shop-checkout-prod
    grafana/dashboard-uid: shop-red
  tags: [go, pci]
spec:
  type: service
  lifecycle: production
  owner: group:checkout
  system: system:shop
  dependsOn:
    - resource:default/shop-pg
    - api:default/shop-checkout-grpc
```

**Annotations** are how plugins deep-link. If Grafana UID is missing, the observability plugin is a 404—the catalog is then **worse** than a spreadsheet.

### 70.3.2 Ingestion

- **Discovery:** GitHub org scan for `catalog-info.yaml`.
- **Push:** template registers on scaffold.
- **IdP:** LDAP/Okta groups → `Group` entities. Manual YAML owners **drift**.

**Scorecards** (Spotify, Cortex, or custom): production services must have owner, on-call, SLO dashboard, pager, and `lifecycle`. A Component without owner is **unpageable**—block golden-path deploy to prod.

### 70.3.3 TechDocs and runbooks

Docs that live only in Confluence will rot. TechDocs in-repo + a `runbook.md` linked from alert annotations (Chapter 68) is the loop.

### 70.3.4 Backstage as a credentialed app

SSO, audit plugin usage, and **no** production kubeconfig in the Backstage pod with cluster-admin. Use **short-lived** tokens per plugin (on-behalf-of is hard; at least namespace-scoped deploy tokens). A compromised Backstage is a **cluster** incident.

---

## 70.4 Cluster tenancy blueprints

Tenancy is **who shares a failure domain**.

### 70.4.1 Models

| Model | Isolation | Typical |
|-------|-----------|---------|
| Namespace + RBAC + quotas + NetworkPolicy | Soft | Internal microservices |
| Namespace per team per env | Soft+ | Most IDPs |
| Dedicated node pool / taints | Medium | Noisy/GPU/PCI |
| Dedicated cluster | Hard | Untrusted, regulated, blast-radius |
| Dedicated account + cluster | Hardest | Prod PCI, very large orgs |

**Soft tenancy** is enough when you trust teams **not** to be hostile and you enforce admission (Chapter 69). It is **not** enough for untrusted compute (students, third-party plugins).

### 70.4.2 Namespace contract

Every tenant namespace gets:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata: { name: compute }
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    persistentvolumeclaims: "10"
---
apiVersion: v1
kind: LimitRange
metadata: { name: defaults }
spec:
  limits:
    - type: Container
      defaultRequest: { cpu: 100m, memory: 128Mi }
      default: { cpu: "1", memory: 512Mi }
```

Plus: default NetworkPolicy deny ingress except from ingress-controller and same-ns; egress allow DNS + required CIDRs; PSA `restricted`; Kyverno; External Secrets; ServiceAccount without `automount` unless needed.

**Cost:** label `team`, `cost-center` on namespace for kubecost/OpenCost (Chapter 57).

### 70.4.3 Multi-cluster

Control-plane failure, regional DR, and noisy CNI: **more than one cluster** for prod is normal. GitOps `ApplicationSet` (Chapter 56) stamps tenants. Golden path deploys to **environment**, not to a cluster name developers memorize.

**Hosted control plane / vcluster / Capsule / Hierarchical namespaces:** pick **one** tenancy product. Nested complexity without a story will not be supported at 3 a.m.

### 70.4.4 Data tenancy

A namespace is not a database. RDS instances per team vs shared with schemas: **credentials and backups** define tenancy more than k8s. Blueprint: platform provides **data-store golden path** (Terraform module v3) that tags ownership and backup vaults.

---

## 70.5 GitOps and the platform runtime

Argo CD / Flux: tenants get an **AppProject** limited to their namespace and allowed repos. They cannot point Argo at random Helm charts from the internet without an allowlist (supply chain).

```yaml
# AppProject sketch
spec:
  destinations:
    - namespace: team-checkout-*
      server: https://kubernetes.default.svc
  sourceRepos:
    - 'https://github.com/acme/shop-checkout'
    - 'https://github.com/acme/golden-charts'
```

Platform **root app** deploys: ingress, cert-manager, policy, observability agents, tenancy operator. Tenants **cannot** Helm-upgrade those.

---

## 70.6 IDP metrics: DORA for the platform

If you cannot measure, you will gold-plate. Minimum dashboard:

| Metric | Definition | Why |
|--------|------------|-----|
| Time to hello-world | Scaffold → first successful nonprod URL | Golden path friction |
| PR lead time on golden CI | Median | Template quality |
| % deploys via golden path | Count | Adoption |
| Shadow-IT tickets | “We used a random cluster” | Failure of adoption |
| Platform availability SLO | API, registry, CI, Backstage | Chapter 68 |
| MTTR of platform Sev-1 | Incidents | Reliability |
| Quota wait time | Ticket age for extra CPU | Self-service gaps |
| Template success rate | Scaffolder jobs | Broken cookies |
| Scorecard pass rate | Production services meeting bar | Governance |
| Support load | Tickets / 100 developers | Toil |

**DORA for product teams** still belongs to them (Chapter 42). Do not steal credit. Platform success is **their** DORA improving **and** support tickets falling.

**Surveys:** NPS twice a year. Qualitative “I still file a ticket for DNS” beats a green dashboard.

**Instrumentation:**

- Scaffolder: emit metric `idp_scaffold_completed_total{template,result}`
- Argo: time from Git SHA to Synced
- CI: queue time (Chapter 67)
- Backstage: catalog freshness (entities stale > 7d)

Alert when **scaffold failure rate** > 10% (template regression) or **Backstage 5xx** (developers will bypass the IDP).

---

## 70.7 Reference architecture (one picture in words)

```
Developer → Backstage (SSO)
  ├─ Scaffolder (golden path v4) → GitHub repo + catalog-info
  ├─ TechDocs / scorecards / “create namespace” plugin
  └─ Links: Argo, Grafana, PagerDuty, Vault
GitHub → reusable workflows@v3 → OIDC → registry (signed images)
Flux/Argo → tenant ns (quotas, NP, PSA)
Platform cluster(s) → policy + observability + ingress
Terraform (platform state) → accounts, DNS, IAM, clusters
```

**Human gates:** prod environment approval (Chapter 67), not a platform engineer for every service.

---

## 70.8 Worked initiative: “v3 template broke PCI services”

**Event:** Platform released `http-service-go@v3` dropping a sidecar that injected a cert. PCI services failed mTLS. Adoption metric looked great (everyone upgraded) while checkout error budget burned (Chapter 68).

**Blueprint fixes:**

1. SemVer **major** for sidecar removal; changelog; opt-in flag two versions.
2. Scorecard: `pci` tag must have mTLS check in CI.
3. Canary the template on two non-PCI services first (IDP metric: % canary).
4. Contract test: rendered Helm must keep `annotations.pci/mtls=required` for tagged services.

Platform releases need the **same** discipline as app releases.

---

## 70.9 Org and operating model

- **Platform product manager** (even part-time): roadmap, not only tickets.
- **Intake:** exceptions via catalog plugin, SLA 2 business days.
- **Inner source:** app teams can PR golden paths; platform reviews.
- **On-call:** platform SLO pages platform; app CrashLoop pages app (label routing, Chapter 68).
- **Sunset:** announce removal of path v1 with a date; running v1 is a scorecard fail after date.

---

## 🧪 Lab 70.1 — Golden path skeleton test

1. Create a cookiecutter or Backstage skeleton with a Go `main` and Helm chart.
2. CI job: render → `go test` → `helm lint`.
3. Break the skeleton on purpose; see CI fail.
4. Add a VERSION file and changelog for a breaking values.yaml rename.

---

## 🧪 Lab 70.2 — catalog-info completeness

1. Write `catalog-info.yaml` with owner, system, grafana UID annotation.
2. Intentionally omit owner; write a CI check (`yq`) that fails.
3. Document how Backstage Group sync would replace a hardcoded user.

---

## 🧪 Lab 70.3 — namespace tenancy pack

1. On kind, apply Quota, LimitRange, default-deny NetworkPolicy, PSA labels.
2. Deploy a privileged pod; confirm deny (Chapter 69).
3. Deploy a well-formed nginx; confirm allow.
4. Hit quota; record the event message a developer would see.

---

## 🧪 Lab 70.4 — IDP metrics stub

1. Define four Prom metrics (scaffold success, CI queue, Argo sync duration, Backstage up).
2. Draw a Grafana row “IDP.”
3. Write two alerts: scaffold fail rate, Backstage burn (Chapter 68 style).
4. Add a table of **targets** (not just graphs).

---

## 🧪 Lab 70.5 — AppProject confinement

1. In a lab Argo CD (or paper YAML), create an AppProject limited to `team-a-*`.
2. Show a manifest that would be rejected (wrong ns or Helm repo).
3. Explain how this complements cluster RBAC.

---

## 70.10 Adoption playbook

1. Dogfood the golden path with the platform team’s own services.
2. Migrate **one** friendly product team; measure time-to-hello-world.
3. Publish scorecards as **advisory** then **gating** for new prod services.
4. Turn off custom CI support for new services after date T.
5. Keep an **escape hatch** with explicit cost (you own the YAML, you own the pager extras).

Forcing migration of all legacy on day one creates shadow IT. Metrics tell you when the hatch is too popular.

---

## 70.11 Checklist: launching an IDP MVP

| Item | Done? |
|------|-------|
 | SSO on portal | |
 | One golden path with tested skeleton | |
 | Reusable CI pinned | |
 | Nonprod namespace self-service | |
 | Prod deploy gated by environment + signed images | |
 | Catalog ingestion from Git | |
 | Default dashboards + pager annotation | |
 | Quota + PSA + NetworkPolicy pack | |
 | Platform SLO + scaffold metrics | |
 | Docs: “how to exception” | |

Do not wait for a perfect service mesh to launch the MVP. Launch a **thin** path, then thicken.

---

## Review questions

1. Why is “twelve templates” often worse than three for a platform team?
2. List five properties of a golden path that is actually golden.
3. How do Backstage annotations connect incidents to Grafana? What fails if UIDs drift?
4. Contrast namespace tenancy with cluster-per-team. When is the latter worth the cost?
5. What belongs in a tenant namespace “starter pack”?
6. Why version golden paths with SemVer like Terraform modules?
7. Name four IDP metrics and a **bad** vanity metric (e.g., “plugins installed”).
8. How should pages route between platform and product on-call?
9. Why test **rendered** templates in CI instead of only the Scaffolder UI?
10. Design an AppProject allowlist that reduces supply-chain risk for Helm charts.

---

## Further practice

This chapter closes Part XIII. Use it as a **capstone workbook** with Chapter 59 (system design): draw ShopStream on this blueprint—catalog entities, path choice, tenant ns, SLOs, and the three IDP metrics you would put on the executive slide.
