# Chapter 57: FinOps and Cost-Aware Engineering

*DevOps Handbook — Pages 278–281 of this PDF edition*
---

## 57.1 Cloud cost as engineering concern

Cloud's pay-as-you-go model shifts infrastructure from CapEx (predictable depreciation) to OpEx (variable, opaque bills). Without discipline, costs scale faster than revenue—the **FinOps** discipline brings **financial accountability** to cloud spending through collaboration between engineering, finance, and business.

FinOps Foundation principles:

1. **Teams need to collaborate** — Finance, engineering, leadership share ownership
2. **Everyone takes ownership** — Engineers see and optimize their spend
3. **Reports should be accessible and timely** — Near real-time visibility
4. **Decisions are driven by business value** — Cost vs performance tradeoffs explicit
5. **Take advantage of the variable cost model** — Scale down, spot instances, right-size

FinOps is a **continuous cycle**: Inform → Optimize → Operate.

---

## 57.2 Cost visibility and allocation

You cannot optimize what you cannot attribute.

**Tagging strategy** (mandatory tags enforced by policy):

| Tag | Purpose |
|-----|---------|
| `team` | Cost center owner |
| `service` | Application attribution |
| `environment` | dev/staging/prod |
| `cost-center` | Finance chargeback |
| `project` | Initiative tracking |

AWS SCP / Tag Policies enforce tags at organization level. Kubernetes labels mirror tags for in-cluster cost tools.

Tools:

| Tool | Scope |
|------|-------|
| **AWS Cost Explorer / CUR** | AWS detailed billing |
| **GCP Billing Export + BigQuery** | GCP analysis |
| **Azure Cost Management** | Azure spend |
| **Kubecost / OpenCost** | Kubernetes cost by namespace/pod |
| **CloudHealth / Cloudability** | Multi-cloud FinOps platforms |
| **Infracost** | Terraform plan cost estimates in CI |

OpenCost on Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opencost
  namespace: opencost
spec:
  template:
    spec:
      containers:
        - name: opencost
          image: opencost/opencost:latest
          env:
            - name: PROMETHEUS_SERVER_ENDPOINT
              value: "http://prometheus:9090"
```

Dashboard shows cost per namespace, deployment, label—allocating cluster overhead by CPU/RAM usage.

---

## 57.3 Right-sizing and waste elimination

Common waste sources:

| Waste | Detection | Remediation |
|-------|-----------|-------------|
| **Idle resources** | CloudWatch/GCP metrics low utilization | Stop dev instances nights/weekends |
| **Oversized instances** | CPU < 20% sustained | Downsize instance type |
| **Unattached EBS volumes** | Cost anomaly reports | Snapshot and delete |
| **Old snapshots** | Age-based report | Lifecycle policy |
| **Over-provisioned K8s requests** | Kubecost efficiency score | Reduce requests/limits |
| **Forgotten environments** | Tag + age audit | TTL automation |
| **Data transfer** | Network cost breakdown | CDN, VPC endpoints, region locality |

Right-sizing workflow:

1. Identify top 20 cost drivers (Pareto: 80% spend in 20% resources)
2. Analyze 30-day utilization metrics
3. Test smaller size in staging
4. Apply change with rollback plan
5. Measure cost delta next billing cycle

**AWS Compute Optimizer**, **GCP Recommender**, **Azure Advisor** — automated right-sizing suggestions.

---

## 57.4 Pricing models and savings

| Model | When to use |
|-------|-------------|
| **On-demand** | Variable, unpredictable workloads |
| **Reserved Instances / Savings Plans** | Steady-state baseline (1–3 year commit) |
| **Spot / Preemptible** | Fault-tolerant batch, CI runners, stateless workers |
| **Committed use discounts** | GCP CUD, Azure RI |

Spot instance pattern for CI:

```yaml
# Kubernetes node pool — spot for CI workloads
nodeSelector:
  workload-type: ci-batch
tolerations:
  - key: "spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
```

Mix: 70% reserved for baseline, 30% on-demand/spot for burst—model in spreadsheet before committing.

---

## 57.5 Cost in CI/CD and IaC

Shift cost awareness left:

**Infracost** in PR comments:

```yaml
- name: Infracost
  uses: infracost/actions/setup@v3
- run: |
    infracost breakdown --path terraform/ --format json \
      --out-file infracost-base.json
    infracost diff --path terraform/ \
      --compare-to infracost-base.json
```

Developers see "+$450/month" before merging Terraform expanding RDS instance.

Policies:

- Budget alerts at 80%, 100%, 120% of forecast
- Auto-shutdown Lambda for non-prod tagged `auto-shutdown=true`
- Maximum instance size guardrails in Terraform policy (OPA: deny `p4d.24xlarge` in dev)

---

## 57.6 Unit economics

Connect cloud spend to business metrics:

| Metric | Formula |
|--------|---------|
| **Cost per customer** | Monthly infra / active customers |
| **Cost per transaction** | Infra / transactions |
| **Cost per API request** | Service cost / request volume |
| **Margin per feature** | Revenue - allocated infra - support |

Engineering decisions framed in unit economics:

> "Caching reduces DB cost $2K/month and improves latency—ROI positive in 2 weeks."

Finance partnership: monthly **FinOps review** with engineering managers reviewing team dashboards—not surprise bills.

---

## 57.7 FinOps maturity stages

| Stage | Characteristics |
|-------|-----------------|
| **Crawl** | Basic billing visibility, manual reports |
| **Walk** | Tagging enforced, team dashboards, anomaly alerts |
| **Run** | Unit economics, automated optimization, CI cost gates |
| **Fly** | Predictive forecasting, autoscaling cost-aware, culture embedded |

---

## 57.8 Chapter summary

- FinOps aligns engineering, finance, and business on cloud cost accountability.
- Tagging and tools (Cost Explorer, Kubecost, Infracost) enable visibility and allocation.
- Right-sizing, reserved capacity, and spot instances optimize spend without sacrificing reliability.
- Unit economics and CI cost feedback integrate financial awareness into daily engineering.

---

## 🧪 Lab 57.1 — Cost allocation tags

1. Define mandatory tag schema for Terraform modules.
2. Apply OPA/Checkov policy denying untagged resources.
3. Export cost report grouped by `team` tag (or simulate with labeled resources).

---

## 🧪 Lab 57.2 — Infracost in CI

1. Add Infracost to Terraform repo CI on pull requests.
2. Open PR changing instance type; review cost diff comment.
3. Document team policy for cost increase approval threshold.

---

## Review questions

1. What are the three FinOps lifecycle phases?
2. Why is tagging essential for cloud cost allocation?
3. Compare reserved instances and spot instances use cases.
4. How does Kubecost attribute Kubernetes cluster costs?
5. What is unit economics in cloud engineering context?
6. Name three common sources of cloud waste.
7. How can IaC CI pipelines prevent costly infrastructure changes?

---

*Continue: Chapter 58 — MLOps Overview*
