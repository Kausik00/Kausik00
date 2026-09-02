# Chapter 56: Multi-Cloud and Hybrid Patterns

*DevOps Handbook — Pages 273–277 of this PDF edition*
---

## 56.1 Why multi-cloud and hybrid exist

Organizations rarely start with a single cloud strategy. **Multi-cloud** uses two or more public clouds (AWS + GCP + Azure). **Hybrid cloud** combines on-premises data centers with public cloud. Drivers include:

| Driver | Example |
|--------|---------|
| **Acquisition** | Merged companies on different clouds |
| **Regulatory** | Data residency requires specific regions/providers |
| **Vendor negotiation** | Avoid lock-in for pricing leverage |
| **Best-of-breed** | GCP for ML, AWS for mature managed services |
| **Legacy** | Mainframe/on-prem cannot migrate quickly |
| **Disaster recovery** | Secondary region on different provider |

Multi-cloud is **hard**—operational complexity often exceeds benefits without deliberate architecture. Prefer **single cloud + multi-region** unless a clear requirement forces multi-cloud.

---

## 56.2 Architecture patterns

### Active-active multi-cloud

Traffic served from multiple clouds simultaneously—highest complexity:

```
                    Global DNS / CDN
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
         AWS EKS       GCP GKE      Azure AKS
            │             │             │
            └─────────────┼─────────────┘
                          │
                   Shared data layer (?)
```

Data consistency across clouds is the hard problem—avoid unless necessary.

### Active-passive DR

Primary on AWS; GCP/Azure standby for failover:

- Replicate data asynchronously (RDS cross-region, object replication)
- DNS failover (Route 53, Cloud DNS health checks)
- Regular DR drills (Chapter 48)

### Hybrid edge

On-prem core systems + cloud burst for scale:

```
On-prem: ERP, legacy DB
Cloud:   Web tier, analytics, ML training
Link:    Direct Connect / ExpressRoute / VPN
```

### Cloud-adjacent services

Keep sensitive data on-prem; process in cloud via encrypted links—**data gravity** pattern.

---

## 56.3 Portability strategies

| Layer | Portability approach |
|-------|---------------------|
| **Application** | Containers, 12-factor apps, standard APIs |
| **Orchestration** | Kubernetes (EKS, GKE, AKS similar but not identical) |
| **IaC** | Terraform/Pulumi with provider modules |
| **CI/CD** | Platform-agnostic pipelines (GitHub Actions, GitLab) |
| **Observability** | OpenTelemetry, Prometheus, Grafana |
| **Identity** | OIDC/SAML federation; avoid cloud-specific auth in app |
| **Data** | Hardest—managed DB services differ significantly |

**Abstraction cost**: Every portability layer adds indirection. Abstract **interfaces**, not every service feature.

Terraform multi-provider example:

```hcl
# modules/kubernetes-cluster — cloud-agnostic interface
variable "cluster_name" {}
variable "node_count" {}
variable "region" {}

# AWS implementation
module "eks" {
  source = "./aws-eks"
  count  = var.cloud == "aws" ? 1 : 0
  # ...
}

# GCP implementation
module "gke" {
  source = "./gcp-gke"
  count  = var.cloud == "gcp" ? 1 : 0
  # ...
}
```

---

## 56.4 Networking across clouds and on-prem

Hybrid connectivity options:

| Connection | Bandwidth | Latency | Use case |
|------------|-----------|---------|----------|
| **VPN** | Moderate | Higher | Dev/test, small workloads |
| **Direct Connect / ExpressRoute / Cloud Interconnect** | High | Low | Production hybrid |
| **SD-WAN** | Optimized routing | Variable | Multi-site enterprises |

Design considerations:

- **IP addressing** — Non-overlapping CIDR plans across clouds and on-prem
- **DNS** — Split-horizon or unified private zones
- **Firewall rules** — Centralized policy management
- **Latency** — Cross-cloud synchronous calls degrade UX

Service mesh (Istio multi-cluster) spans clusters across clouds—complex operational overhead.

---

## 56.5 GitOps and multi-cluster management

**GitOps** (Argo CD, Flux) scales to multi-cluster:

```yaml
# ApplicationSet — deploy to all clusters
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: api-all-clusters
spec:
  generators:
    - clusters:
        selector:
          matchLabels:
            env: production
  template:
    metadata:
      name: 'api-{{name}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/myorg/k8s-manifests
        path: apps/api/overlays/{{metadata.labels.cloud}}
      destination:
        server: '{{server}}'
        namespace: production
```

**Cluster API** provisions clusters consistently across providers.

**Rancher**, **Anthos**, **Azure Arc** — multi-cluster management planes with varying lock-in.

---

## 56.6 Data and state in multi-cloud

| Pattern | Description |
|---------|-------------|
| **Single primary DB** | One cloud owns data; others read via API |
| **Async replication** | Cross-cloud DB replication (lag, conflict resolution) |
| **Per-cloud data** | Regional data stays local; aggregate via analytics pipeline |
| **Object storage replication** | S3 CRR, GCS transfer, Azure Blob replication |

Avoid dual-write across clouds without strong consistency model—leads to split-brain.

Event-driven sync:

```
Cloud A DB change → Kafka/EventBridge → Cloud B consumer updates read replica
```

---

## 56.7 Operational model

| Challenge | Mitigation |
|-----------|------------|
| Different IAM models | Central identity (Okta) + cloud role federation |
| Skill fragmentation | Platform golden paths per cloud + shared K8s layer |
| Cost visibility | FinOps tagging standards (Chapter 57) |
| Incident response | Unified on-call, cross-cloud runbooks |
| Compliance | Consistent policy-as-code adapted per provider |

**Cloud center of excellence (CCoE)** — Governance without blocking teams: standards, modules, training—not approval for every resource.

---

## 56.8 When NOT to multi-cloud

Avoid multi-cloud when:

- Single region cloud meets all requirements
- Team lacks operational maturity for one cloud
- Motivation is vague "lock-in fear" without cost/benefit analysis
- Application is tightly coupled to one cloud's proprietary services (DynamoDB, BigQuery ML)

**Portable where it matters** (compute, containers); **embrace managed services** where velocity wins.

---

## 56.9 Chapter summary

- Multi-cloud and hybrid architectures address DR, compliance, legacy, and vendor strategy—at operational cost.
- Portability via containers, Kubernetes, Terraform, and OpenTelemetry reduces lock-in but adds abstraction.
- GitOps and cluster management tools scale deployments across cloud boundaries.
- Prefer single-cloud multi-region unless requirements clearly mandate multi-cloud; treat data as hardest portability layer.

---

## 🧪 Lab 56.1 — Terraform multi-provider module

1. Create Terraform module with `cloud` variable selecting AWS or GCP backend.
2. Provision test cluster on one provider; switch variable; plan second (destroy first if budget limited).
3. Document interface variables shared across implementations.

---

## 🧪 Lab 56.2 — Argo CD ApplicationSet

1. Register two clusters (or two namespaces simulating clusters) in Argo CD.
2. Deploy ApplicationSet syncing same app to both.
3. Update Git manifest; verify both destinations sync.

---

## Review questions

1. Distinguish multi-cloud, hybrid cloud, and multi-region single cloud.
2. Why is data the hardest layer to make portable across clouds?
3. Name three legitimate business drivers for multi-cloud architecture.
4. How does GitOps help manage multi-cluster deployments?
5. What networking options connect on-premises to public cloud?
6. When should an organization avoid multi-cloud strategy?
7. What role does a Cloud Center of Excellence play?

---

*Continue: Chapter 57 — FinOps*
