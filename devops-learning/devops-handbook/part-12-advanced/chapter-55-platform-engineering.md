# Chapter 55: Platform Engineering and Internal Developer Platforms

*DevOps Handbook — Part XII, Pages 1081–1100*

---

## 55.1 From DevOps to platform engineering

As organizations scale, each product team rebuilding CI templates, Kubernetes manifests, and observability stacks creates **cognitive load** and inconsistency. **Platform engineering** builds an **Internal Developer Platform (IDP)**—a curated set of tools, templates, and self-service capabilities that enable developers to ship software efficiently without becoming infrastructure experts.

Platform team mission (CNCF definition):

> Treat platform as a product; optimize for developer experience and organizational outcomes.

Platform engineering vs related roles:

| Role | Focus |
|------|-------|
| **DevOps** | Culture + automation bridging dev and ops |
| **SRE** | Reliability, SLOs, toil reduction |
| **Platform engineering** | Self-service golden paths, IDP product |
| **Infrastructure team** | Raw compute, network, storage |

Platform teams succeed when developers **choose** the platform because it accelerates work—not because mandates force compliance.

---

## 55.2 Internal Developer Platform components

Typical IDP layers:

```
┌─────────────────────────────────────────────────────────┐
│ Developer Portal (Backstage, Cortex, Port)              │
│  Service catalog, docs, scaffolder, scorecards          │
├─────────────────────────────────────────────────────────┤
│ Golden paths: deploy web app, add cron job, expose API  │
├──────────────┬──────────────┬──────────────┬────────────┤
│ CI/CD        │ Runtime      │ Observability│ Security   │
│ templates    │ (K8s/EKS)    │ stack        │ scanning   │
├──────────────┴──────────────┴──────────────┴────────────┤
│ Infrastructure: Terraform modules, networking, IAM      │
└─────────────────────────────────────────────────────────┘
```

Key capabilities:

| Capability | Purpose |
|------------|---------|
| **Service catalog** | Discoverable services, owners, dependencies |
| **Software templates** | Cookie-cutter repo + CI + infra |
| **Environment provisioning** | Dev/staging/prod namespaces or accounts |
| **Deployment abstraction** | GitOps, Helm charts, deploy buttons |
| **Secrets integration** | Vault/ESO wired by default |
| **Observability bundle** | Dashboards, alerts pre-configured |
| **Documentation** | TechDocs, runbooks linked from portal |

---

## 55.3 Backstage — reference IDP portal

**Backstage** (CNCF, Spotify-origin) is the most adopted open-source developer portal.

Features:

- **Software Catalog** — YAML entity descriptors (`catalog-info.yaml`)
- **Software Templates (Scaffolder)** — Create repos from templates
- **TechDocs** — Docs-as-code in repo
- **Plugins** — Kubernetes, Argo CD, Grafana, CI visibility

Catalog entity:

```yaml
# catalog-info.yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: order-api
  description: Order processing microservice
  annotations:
    github.com/project-slug: myorg/order-api
    backstage.io/techdocs-ref: dir:.
  tags:
    - python
    - kubernetes
spec:
  type: service
  lifecycle: production
  owner: team-checkout
  system: commerce
  dependsOn:
    - resource:default/postgres-orders
  providesApis:
    - order-api-rest
```

Scaffolder template (simplified):

```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: python-microservice
  title: Python Microservice on EKS
spec:
  parameters:
    - title: Service info
      required: [name, owner]
      properties:
        name:
          type: string
        owner:
          type: string
          ui:field: OwnerPicker
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
        repoUrl: github.com?repo=${{ parameters.name }}&owner=myorg
    - id: register
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps.publish.output.repoContentsUrl }}
```

---

## 55.4 Golden paths and paved roads

**Golden path** — Opinionated, supported workflow for common tasks:

> "Create a REST API → get CI, EKS deployment, Prometheus metrics, and security scans automatically."

**Paved road** vs **unpaved road**:

| Paved (golden) | Unpaved (escape hatch) |
|----------------|------------------------|
| Supported by platform team | Team owns fully |
| Fast onboarding | Flexibility for edge cases |
| Security/compliance built-in | Custom review required |
| SLAs on platform uptime | Best effort |

Document escape hatches—forcing all workloads through inadequate abstractions drives shadow IT.

Measure golden path adoption: % new services created via scaffolder vs manual.

---

## 55.5 Platform as a product

Apply product management to platform:

| Product practice | Platform application |
|------------------|---------------------|
| User research | Developer interviews, surveys |
| Roadmap | Quarterly platform priorities |
| Metrics | DORA, time-to-first-deploy, CSAT |
| SLAs | IDP availability, template freshness |
| Support | #platform-support Slack, office hours |
| Deprecation policy | Notice before breaking template changes |

**Team Topologies** (Part I): platform team is an **enabling team** or **platform team** interacting via **X-as-a-Service** with stream-aligned product teams.

Avoid **Ivory tower platform**—embed platform engineers in product teams periodically; consume your own golden paths ("eat your own dog food").

---

## 55.6 Infrastructure abstractions

Platform hides complexity behind APIs:

| Raw infrastructure | Platform abstraction |
|--------------------|----------------------|
| Terraform modules | "Create environment" button |
| Kubernetes YAML | Helm chart with values |
| IAM policies | Pre-approved roles per service type |
| Network policies | Automatic based on service catalog |

**Humanitec**, **Crossplane**, **Kratix** — platform orchestration patterns composing infra resources from service definitions.

Crossplane Composite Resource:

```yaml
apiVersion: platform.example.com/v1alpha1
kind: XServiceEnvironment
metadata:
  name: order-api-staging
spec:
  serviceName: order-api
  environment: staging
  region: us-east-1
  # Platform controller provisions RDS, EKS namespace, secrets, DNS
```

Developers declare intent; platform controllers reconcile infrastructure.

---

## 55.7 Developer experience metrics

| Metric | Meaning |
|--------|---------|
| **Time to first PR** | New hire productivity |
| **Time to production** | Golden path efficiency |
| **Template usage rate** | Platform adoption |
| **Developer satisfaction (CSAT)** | Qualitative health |
| **Toil tickets to platform** | Gaps in self-service |
| **Cognitive load survey** | Team Topologies assessment |

Improve metrics iteratively—platform backlog prioritized by developer pain, not loudest stakeholder.

---

## 55.8 Anti-patterns

| Anti-pattern | Consequence |
|--------------|-------------|
| Platform without users | Wasted investment |
| Mandatory only, no DX | Shadow infrastructure |
| Endless customization | Unmaintainable templates |
| No versioning | Breaking all consumers at once |
| Ops team renamed "platform" | No product mindset change |
| Ignoring security/compliance | Golden path bypassed for speed |

---

## 55.9 Chapter summary

- Platform engineering delivers an IDP with catalog, templates, and self-service golden paths.
- Backstage exemplifies developer portals integrating CI, runtime, docs, and ownership.
- Treat platform as a product with metrics, SLAs, and paved roads plus documented escape hatches.
- Infrastructure abstractions (Crossplane, GitOps) hide complexity while enforcing standards.

---

## 🧪 Lab 55.1 — Backstage software catalog

1. Deploy Backstage locally or via demo instance.
2. Register three sample services with `catalog-info.yaml`.
3. Enable TechDocs plugin for one service; view rendered docs.

---

## 🧪 Lab 55.2 — Golden path template

1. Create scaffolder template: Node.js app + Dockerfile + GitHub Actions CI.
2. Scaffold new service; verify repo contains working pipeline.
3. Document golden path README with onboarding steps (< 30 min to first deploy).

---

## Review questions

1. How does platform engineering differ from traditional DevOps team?
2. What components belong in an Internal Developer Platform?
3. Explain golden paths and why offer unpaved road escape hatches.
4. What Backstage features support service discovery and documentation?
5. How should platform teams measure success?
6. What is Team Topologies' view of platform teams?
7. Name two anti-patterns in platform engineering initiatives.

---

*Continue: Chapter 56 — Multi-Cloud and Hybrid Patterns*
