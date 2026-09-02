# Chapter 60: Architecture Capstone — Multi-Tier, EKS, and Data on AWS

*AWS Handbook — Pages 371–378 of this PDF edition*

This capstone is a **complete architecture walkthrough** for a fictional product, **Northwind Retail (NWR)**. It goes beyond Chapter 41's Well-Architected sketch: account layout, network, EKS platform, multi-tier services, data lake/warehouse, CI/CD, security, DR, cost, and a lab sequence you can implement in miniature. Treat it as a design you would defend in an architecture review.

NWR is a retailer: public website and mobile API, partner B2B API, catalog and search, checkout, fulfillment, and analytics. Primary Region `us-east-1`, DR `us-west-2`, landing zone as in Chapter 53.

---

## 60.1 Business requirements

| ID | Requirement |
|----|-------------|
| B1 | 99.9% availability for browse; 99.95% for checkout (stricter error budget) |
| B2 | Peak 8,000 RPS browse, 400 RPS checkout |
| B3 | PCI scope isolated from general retail |
| B4 | Catalog search < 200 ms p95 |
| B5 | Near-real-time inventory for stores (minutes, not hours) |
| B6 | Analytics: daily P&L plus ad-hoc SQL |
| B7 | Developers ship independently; platform team owns cluster and network |
| B8 | RPO 1 min checkout data; RTO 30 min Regional |

Non-requirements: multi-cloud active (cost); edge compute in stores (phase 2).

---

## 60.2 Account and OU layout

```
Workloads/Prod
  nwr-prod-web        # CloudFront, public ALB, WAF (or network account owns CloudFront)
  nwr-prod-eks        # EKS clusters, platform add-ons
  nwr-prod-data       # Lake, Glue, Redshift, MSK
  nwr-prod-pci        # Payment tokenization only
Workloads/Nonprod
  nwr-dev-*, nwr-stage-*
Security / Infra / Sandbox as Chapter 53
```

PCI account: no peering to data lake; **PrivateLink** for a tokenize API only. Card data never in EKS logs (admission policy + runtime).

Identity Center permission sets: `nwr-dev`, `nwr-sre`, `nwr-data`, `nwr-pci` (tiny group).

---

## 60.3 Network architecture

Hub-and-spoke TGW in Network Hub account (Chapter 57).

| VPC | CIDR example | Notes |
|-----|--------------|-------|
| Ingress / edge | 10.20.0.0/16 | ALB, optional GWLB |
| EKS prod | 10.21.0.0/16 | Private subnets, no IGW; egress via inspection |
| Data | 10.22.0.0/16 | Redshift, Glue ENIs, MSK |
| PCI | 10.23.0.0/16 | Isolated TGW route table |
| Egress/inspection | 10.30.0.0/16 | NAT, AWS Network Firewall / GWLB |

Interface endpoints in a **shared-services** VPC or per-VPC for ECR, S3 (gateway in each), Logs, STS, EKS. Do not hairpin image pulls through NAT (Chapter 57 FinOps).

Route 53 private hosted zones `prod.nwr.internal` associated with VPCs; Resolver outbound for `corp.nwr.internal`. Public `nwr.example` in a DNS account with change protection.

---

## 60.4 Edge and multi-tier traffic path

```
User
  → CloudFront (WAF, Shield, TLS, cache HTML/API GET where safe)
    → ALB (public, WAF optional second) in ingress VPC
      → TGW → EKS ingress (AWS Load Balancer Controller, internal ALB or NLB)
        → namespace storefront | checkout | search
```

**Browse (Tier-1 web):** mostly CloudFront + S3 for static; dynamic GraphQL/REST to storefront pods.

**Checkout (Tier-2 app):** shorter cache; POST not cached; sticky sessions avoided; state in DynamoDB (cart) and Aurora (orders).

**Partners (Tier-3 B2B):** PrivateLink or mTLS on a dedicated ALB, usage plans on API Gateway for partner REST, throttling per key.

Three-tier in the classic sense: **presentation** (CloudFront/S3/SSR pods), **application** (EKS services), **data** (Aurora/DynamoDB/OpenSearch). EKS does not replace the data tier.

---

## 60.5 EKS platform design

### Clusters

| Cluster | Purpose |
|---------|---------|
| `prod-a` | Customer-facing, two AZs min, preferably three |
| `prod-jobs` | Batch, Spark on EKS optional, noisy |
| `stage` | Like prod, smaller |
| `sandbox` | Platform experiments |

Separate **jobs** cluster so a Spark job cannot evict checkout.

### Node strategy

- **Managed node groups** (MNG) for baseline (Graviton where images allow).
- **Karpenter** for burst, diversity of instance types, Spot for jobs **not** for checkout.
- Checkout: On-Demand, `topologySpreadConstraints` across AZs, PDBs.
- Bottlerocket or AL2023 AMIs via Image Builder; IRSA everywhere; no node IAM for app AWS calls.

### Add-ons (platform catalog)

| Add-on | Role |
|--------|------|
| VPC CNI (prefix delegation) | IP density |
| CoreDNS + NodeLocal DNS | DNS latency |
| EBS CSI / EFS CSI | Volumes |
| AWS LB Controller | ALB/NLB |
| ExternalDNS | Route 53 |
| cert-manager | In-cluster TLS |
| Cluster Autoscaler or Karpenter | Capacity |
| Fluent Bit → CloudWatch/S3 | Logs |
| ADOT / X-Ray | Traces |
| Kyverno/OPA | Policies |
| External Secrets | SM/SSM |
| Karpenter disruption budgets | Safety |

### Multi-tenancy

Soft: namespaces, ResourceQuotas, NetworkPolicies (default deny), IRSA per service account. Hard: PCI **not** on this cluster.

Platform exposes a **Golden Path Helm/Argo CD ApplicationSet**. App teams do not create LoadBalancer services that spawn extra NLBs without annotation review (cost).

### Compute example (Deployment snippet)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout
  namespace: checkout
spec:
  replicas: 6
  template:
    spec:
      serviceAccountName: checkout
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
      containers:
        - name: app
          image: 222222222222.dkr.ecr.us-east-1.amazonaws.com/checkout@sha256:abc
          resources:
            requests: { cpu: "250m", memory: "512Mi" }
            limits: { memory: "512Mi" }
          readinessProbe:
            httpGet: { path: /healthz, port: 8080 }
            periodSeconds: 5
```

Images by **digest**. CPU limits optional (throttle debates); memory limits required to protect nodes.

---

## 60.6 Application decomposition

| Service | Runtime | State |
|---------|---------|--------|
| storefront | EKS | none (CDN) |
| catalog | EKS | Aurora PostgreSQL |
| search | EKS | OpenSearch |
| cart | Lambda or EKS | DynamoDB |
| checkout | EKS | Aurora + DynamoDB + SQS |
| inventory | EKS consumers | Aurora + Redis |
| notify | Lambda | SES/SNS |
| tokenize | ECS in PCI | Aurora isolated |

**Why cart on DynamoDB:** spike-friendly, global tables for DR. **Why orders on Aurora:** relational payments/fulfillment joins, Strong consistency for money.

Event backbone: **EventBridge** bus `nwr.prod` plus **SQS** for inventory workers (backpressure). MSK if partner ecosystem already Kafka; otherwise don't.

---

## 60.7 Data architecture

### Operational

- Aurora PostgreSQL Multi-AZ, **Global Database** to us-west-2 (RPO seconds, Chapter 54).
- RDS Proxy for any Lambda touching SQL.
- ElastiCache Redis for catalog hot keys (not source of truth).
- DynamoDB carts global table.
- OpenSearch for search; snapshots to S3; slow index rebuild is RTO for search (acceptable if catalog SQL remains).

### Analytical (lakehouse)

```
Sources (DMS CDC, Kinesis, S3 landing)
  → S3 bronze (raw, immutable)
  → Glue / Spark (EKS jobs cluster or Glue jobs) → silver (Parquet, partitioned)
  → gold (aggregates)
  → Redshift Serverless / RA3 for BI
  → Athena for ad-hoc on silver
  → Lake Formation / IAM for access
```

CDC: **DMS** from Aurora to S3 or Kinesis. Do not ETL by querying primary with unthrottled Tableau.

**MSK vs Kinesis:** if stream processing is light, Kinesis + Lambda; if Kafka contracts with stores, MSK in data VPC.

### ML (modest)

SageMaker in data account, pull gold features, no production writes except through events. Model artifacts in S3 versioned.

---

## 60.8 Security architecture

| Control | Implementation |
|---------|----------------|
| Identity | Identity Center + IRSA + OIDC for GitHub |
| Network | No public EKS API (or public + CIDR allow + private endpoint preferred) |
| Secrets | Secrets Manager, External Secrets, rotation |
| KMS | CMK per domain: data, ebs, s3-lake |
| WAF | CloudFront + ALB, SQLi/XSS, rate limits |
| GuardDuty EKS protection | Audit account |
| Runtime | Falco/GuardDuty runtime, Kyverno block privileged |
| Supply chain | ECR scan, signed images (Signer), Kyverno verify |
| PCI | Separate account, no PAN in events, tokenization API |

Pod Security: restricted PSS. No `hostNetwork` for apps.

---

## 60.9 CI/CD

```
GitHub (CODEOWNERS)
  → OIDC assume role in shared-services
  → CodeBuild or GitHub Actions: test, SAST, build image, push ECR (digest)
  → Staging deploy Argo CD
  → Integration tests + synthetics
  → Manual approval for prod (checkout)
  → Argo CD prod (automated for storefront static)
```

Database migrations: **expand/contract** in app pipelines with Flyway/Liquibase; never coupled to a breaking image in one shot.

Platform add-ons: separate repo, slower cadence, change calendar.

---

## 60.10 Observability and SLOs

| SLO | SLI | Alert |
|-----|-----|-------|
| Browse availability 99.9% | Synthetic + 5xx | Multi-window burn |
| Checkout latency p95 < 400 ms | ALB + tracing | Page SRE |
| Inventory lag < 5 min | Custom metric from consumer | Page data eng |

OpenTelemetry → ADOT Collector → X-Ray and/or Prometheus (AMP) + Grafana (AMG). Logs: Fluent Bit → OpenSearch or S3+Athena for long retention.

Trace sampling 5% browse, 100% checkout errors.

---

## 60.11 DR mapping

| Component | Pattern |
|-----------|---------|
| Static | CloudFront origin group S3 dual Region |
| EKS | Pilot light cluster in DR or warm nodegroup=0 + GitOps |
| Aurora | Global Database |
| DynamoDB | Global tables |
| Redis | Rebuild or Global Datastore |
| OpenSearch | Cross-cluster or snapshot restore (RTO budget) |
| Redshift | Snapshot copy; analytics RTO 24h OK |
| DNS | ARC routing controls gated on lag |

Fail over **checkout path** as one runbook, not "the cluster" independently of the database (Chapter 54).

---

## 60.12 Cost design

- Graviton nodes and Lambda.
- Spot for jobs cluster.
- CloudFront cache to cut origin.
- S3 Intelligent-Tiering on lake.
- NAT reduction via endpoints.
- Karpenter consolidation.
- Redshift Serverless auto pause.
- Right-size Aurora ACUs if Serverless v2; else reserved for steady writer.

Showback: cost allocation tags `nwr:service` from the catalog (Chapter 52).

---

## 60.13 Threat and failure scenarios (review table)

| Scenario | Response |
|----------|----------|
| AZ loss | Multi-AZ nodes, Aurora, ALB |
| Bad checkout deploy | Argo rollback, PDB, canary analysis |
| EKS control plane event | Multi-AZ control plane (AWS managed); apps stay |
| Ransomware on lake | Object Lock on bronze; separate backup account |
| Traffic spike | Karpenter + DDB on-demand + queue |
| Poison Kafka/MSK | DLQ, pause consumer |
| PCI suspected breach | Isolate PCI account SCP; tokenize API down (fail closed) |

---

## 60.14 Sequence diagram — place order

```
Client → CloudFront → ALB → checkout pod
checkout → DynamoDB (cart)
checkout → tokenize API (PrivateLink, PCI)
checkout → Aurora (order row PENDING)
checkout → SQS OrderPlaced
← 201 OrderID
inventory worker ← SQS → Aurora inventory
notify Lambda ← EventBridge ← (stream or worker emit)
```

Idempotency key from client prevents double charge. Tokenize failure → 402/503, no order row, or compensating cancel.

---

## 60.15 What we explicitly did not do

- One giant VPC for everything.
- Oracle on EC2 "because DBA said so" (migrate or RDS).
- Sharing the prod EKS cluster with Spark.
- Storing sessions on local disk (Chapter 55 trap).
- Multi-Region active-active for Aurora (conflict); we used global writer failover.
- Service mesh on day one — NetworkPolicy + mTLS later (App Mesh/Istio) if east-west threat model demands.

---

## 60.16 Lab — miniature capstone in sandbox

You will not build PCI. You will build a **thin vertical slice**.

1. VPC two AZs, private+public, NAT, S3 gateway endpoint.
2. EKS cluster (eksctl or CDK) with one MNG.
3. Deploy a `storefront` nginx and a `checkout` app (even a tiny Python) with IRSA writing to DynamoDB.
4. Public ALB via AWS LB Controller.
5. Aurora Serverless v2 **or** skip SQL and use DynamoDB only if timeboxed — if skipped, write in the design doc why production would still use Aurora.
6. SQS + worker deployment.
7. CloudWatch dashboard: 5xx, latency, DDB throttles.
8. Break SG to DynamoDB endpoint path or IRSA; use Chapter 59 to diagnose.
9. Destroy everything; confirm NAT and ELB costs stop.

**Success criteria:** A request creates a DynamoDB item and a queue message; dashboard shows the request; teardown complete.

---

## 60.17 Architecture decision records (keep these)

| ADR | Decision |
|-----|----------|
| ADR-001 | EKS not ECS: existing k8s skill, Karpenter, multi-service |
| ADR-002 | Aurora for orders: relational integrity |
| ADR-003 | DynamoDB carts: scale and global tables |
| ADR-004 | EventBridge+SQS not MSK phase 1 |
| ADR-005 | PCI account + PrivateLink |
| ADR-006 | GitOps (Argo CD) for cluster; pipelines for images |
| ADR-007 | us-west-2 warm/pilot DR |

ADRs prevent a new architect from "simplifying" PCI back into the main cluster.

---

## 60.18 Well-Architected lens recap

| Pillar | NWR implementation |
|--------|-------------------|
| Ops | GitOps, SLOs, runbooks 54/59 |
| Security | Accounts, IRSA, WAF, KMS |
| Reliability | Multi-AZ, global DB, queues |
| Performance | Cache, Graviton, OpenSearch |
| Cost | Spot jobs, endpoints, cache |
| Sustainability | Graviton, scale to zero jobs |

---

## 60.19 Exam and interview use

SAA: "multi-tier with ELB, ASG, RDS Multi-AZ" is the baby version of this. DOP: pipelines, GitOps, alarms. Specialty: TGW, PrivateLink PCI, hybrid Resolver. Interviews: tell **this story** end-to-end in 10 minutes, then go deep on one slice (usually IAM or data consistency).

---

## 60.19.1 Capacity sketch (order of magnitude)

Interviewers ask "how many nodes?" Sketch from RPS, not from vibes.

Browse 8,000 RPS, 50 ms CPU-on-pod average, 2 vCPU equivalent per pod at 400 RPS → about 20 storefront pods at peak, 6–8 at night. Checkout 400 RPS, heavier 80 ms, Aurora-bound: 10–15 pods, RDS Proxy, 16 vCPU writer as a starting Aurora size — then measure. Karpenter should see CPU heads-room of 20–30% so a deploy and an AZ blip do not coincide with saturation.

DynamoDB carts: 400 writes/s peak is trivial for on-demand. The dangerous table is inventory if you key on a single `SKU#hottoy` during a holiday — shard or queue updates.

OpenSearch: size for shard count and heap; search p95 is often JVM GC, not the ALB.

These numbers are **falsifiable**. Put them in a spreadsheet next to synthetics after week one in production.

---

## 60.20 Chapter checklist

- [ ] Can draw accounts, TGW, EKS, and data lake without notes.
- [ ] Know why checkout is not on Spot.
- [ ] Know why Spark is not on the customer cluster.
- [ ] DR is data-first, DNS-second.
- [ ] Miniature lab destroyed after.

Chapter 61 is interview Q&A: eighty questions that probe whether you internalized the handbook, including this capstone.
