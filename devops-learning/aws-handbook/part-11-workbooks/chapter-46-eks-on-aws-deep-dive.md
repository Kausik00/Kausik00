# Chapter 46: EKS on AWS Deep Dive

Amazon Elastic Kubernetes Service (EKS) is Kubernetes with AWS operating the control plane. This workbook is the production companion to Chapter 19: cluster layout, IAM Roles for Service Accounts, networking models, node groups versus Fargate versus Auto Mode, add-ons, upgrades, and the labs that prove a pod can talk to AWS APIs *without* a node instance role that can also destroy the cluster.

---

## 46.1 What you still owe Kubernetes

EKS does not remove kube-apiserver semantics. You still design:

- Namespaces, RBAC, and admission
- Pod disruption budgets and topology spread
- Resource requests/limits and HPA/VPA/KEDA
- NetworkPolicy (plus AWS security groups for pods if you use the VPC CNI feature)
- Secrets (prefer external Secrets Manager / CSI, not plaintext in etcd)
- Observability (control plane logs, kube-state-metrics, OTel)

AWS adds: IAM, VPC CNI IP consumption, load balancer controller, EBS CSI, EFS CSI, GuardDuty for EKS, and a managed control plane you patch on a published Kubernetes version calendar.

---

## 46.2 Cluster topology cookbook

| Choice | Production default | Notes |
|--------|-------------------|-------|
| Endpoint access | Private, or public + CIDR allowlist | Public `0.0.0.0/0` to the API is a finding |
| Control plane logs | api, audit, authenticator, controllerManager, scheduler to CloudWatch | Cost vs forensic need; keep audit |
| Kubernetes version | N-1 of what EKS supports | Budget upgrades; do not sit on deprecated versions |
| AZs | Three | etcd and your workloads |
| Tenancy | One cluster per environment or per noisy-neighbor boundary | Mega-cluster RBAC is a program |

A common landing zone:

- Platform cluster (ingress, shared services) optional
- Production application cluster
- Non-prod cluster

Sharing prod and scratch namespaces in one cluster saves money and costs blast radius.

---

## 46.3 Data plane: managed node groups, Karpenter, Fargate

**Managed node groups (MNG):** ASG under the hood, Amazon Linux EKS AMI, rolling updates with surge. Simple and fine for steady capacity.

**Karpenter:** provisions right-sized EC2 in response to unschedulable pods, often faster bin-packing and better Spot. You still need a small MNG or Fargate for Karpenter itself and for core add-ons if you design it that way.

**Fargate:** no nodes to patch. Constraints on DaemonSets, privileged pods, and some CNI features. Good for bursty isolated workloads; watch pod startup time and cost at high CPU.

**EKS Auto Mode** (where available in your region/account model) further manages compute; still understand IAM and networking underneath.

```bash
aws eks create-cluster \
  --name prod \
  --role-arn arn:aws:iam::111122223333:role/eksClusterRole \
  --resources-vpc-config subnetIds=subnet-a,subnet-b,subnet-c,endpointPrivateAccess=true,endpointPublicAccess=false \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator"],"enabled":true}]}' \
  --kubernetes-version 1.31
```

Cluster role needs the AWS managed policies for EKS cluster. Node roles need the worker policies plus your least-privilege extras — but application AWS access should be **IRSA or Pod Identity**, not the node role.

---

## 46.4 Networking: VPC CNI and IP exhaustion

The Amazon VPC CNI assigns each pod an IP from the subnet (prefix delegation changes density). This is why Chapter 42 told you to use `/22` app subnets.

| Mode | Effect |
|------|--------|
| Secondary IPs on ENI | Classic; ENI/IP limits per instance family cap pods per node |
| Prefix delegation (`/28` prefixes) | Many more IPs per ENI; required for dense nodes |
| Security groups for pods | Extra ENIs; even hungrier for IPs |
| Custom networking | Pods use a different subnet than the node |

```bash
kubectl set env daemonset aws-node -n kube-system ENABLE_PREFIX_DELEGATION=true
```

Plan with the [max pods] formula for the instance type. If nodes show `Insufficient IPs`, you have a VPC problem, not a Kubernetes problem.

**Traffic:**

- In-cluster: ClusterIP, kube-proxy iptables/IPVS or kube-proxy-free eBPF on some setups
- North-south: AWS Load Balancer Controller (ALB Ingress / NLB Service)
- Egress: node NAT path or IPv6; do not give pods public IPs unless that is a measured design

---

## 46.5 IAM Roles for Service Accounts (IRSA) and EKS Pod Identity

IRSA annotates a ServiceAccount with a role ARN. The VPC CNI and webhook project a projected service account token. The pod uses `sts:AssumeRoleWithWebIdentity`.

```hcl
module "irsa_orders" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  role_name = "prod-orders"
  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["orders:orders-sa"]
    }
  }
  role_policy_arns = { app = aws_iam_policy.orders.arn }
}
```

Trust policy condition must pin `sub` to `system:serviceaccount:orders:orders-sa`. A trust of `system:serviceaccount:*` is a cluster-wide key.

EKS Pod Identity (newer association API) avoids per-cluster OIDC provider management. Learn both; your estate may mix them.

**Never** put `s3:*` on the node instance role “so pods can work.” Every pod on the node can then steal those credentials via IMDS unless you block IMDS (hop limit, or IMDSv2 plus network policy, or disable containers’ IMDS access). Default-deny IMDS for pods and grant IRSA.

---

## 46.6 Add-ons that are not optional in production

| Add-on | Why |
|--------|-----|
| vpc-cni | Pod networking |
| kube-proxy | Cluster networking (unless replaced) |
| coredns | DNS |
| aws-ebs-csi-driver | PersistentVolumes on EBS |
| aws-efs-csi-driver | Shared POSIX if needed |
| aws-load-balancer-controller | ALB/NLB from Ingress/Service |
| snapshot-controller | PVC snapshots |
| metrics-server | HPA |
| cluster-autoscaler or Karpenter | Scale nodes |
| GuardDuty EKS runtime / Agent | Threat detection |

Install add-ons as EKS managed add-ons where possible so AWS documents compatibility with the cluster version.

```bash
aws eks create-addon --cluster-name prod --addon-name aws-ebs-csi-driver --resolve-conflicts OVERWRITE
```

---

## 46.7 Ingress and Service patterns

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: orders
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:111122223333:certificate/uuid
    alb.ingress.kubernetes.io/wafv2-acl-arn: arn:aws:wafv2:...
spec:
  ingressClassName: alb
  rules:
    - host: orders.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: orders
                port:
                  number: 8080
```

`target-type: ip` requires pods to be directly routable (VPC CNI). Instance target type goes through node ports.

Internal ALBs for service-to-service across namespaces or accounts beat a mesh you do not staff — unless you do staff a mesh (App Mesh is not the default story in 2026; many teams use Istio, Cilium, or none).

---

## 46.8 Storage and stateful sets

EBS volumes are zonal. A StatefulSet must use a StorageClass in the same AZ as the pod. Topology-aware scheduling and `WaitForFirstConsumer` binding are the defaults you want.

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
provisioner: ebs.csi.aws.com
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
parameters:
  type: gp3
  encrypted: "true"
```

EFS for ReadWriteMany. Multi-AZ, but latency is not EBS. Do not put a high-QPS database on EFS.

---

## 46.9 Upgrades without heroics

1. Read the EKS release notes and Kubernetes deprecations (`kubectl convert`, removed APIs).
2. Upgrade add-ons to versions compatible with the *target* Kubernetes version.
3. Upgrade the control plane (`aws eks update-cluster-version`).
4. Upgrade node groups / Karpenter AMIs.
5. Validate: DNS, Ingress, CSI, a canary deployment, IRSA assume-role.

Control plane upgrade is typically in-place and brief. Nodes take longer. PodDisruptionBudgets that forbid all disruption will block you — and that is a gift, because it shows you cannot evacuate a node in an AZ event either.

---

## 46.10 Observability and security

- Control plane audit logs → CloudWatch → SIEM or Athena.
- GuardDuty EKS protection: API findings plus runtime (if enabled).
- NetworkPolicy default deny in sensitive namespaces.
- Kyverno or OPA Gatekeeper: deny privileged, require requests/limits, deny `:latest`.
- Secrets: CSI driver with Secrets Manager rotation.
- Image provenance: ECR image scanning, signed images, pull-through cache.

```bash
aws eks update-cluster-config --name prod --logging '{"clusterLogging":[{"types":["audit"],"enabled":true}]}'
```

---

## 46.11 Terraform sketch (module-level)

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "prod"
  cluster_version = "1.31"

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  enable_irsa = true

  cluster_endpoint_public_access  = false
  cluster_endpoint_private_access = true

  eks_managed_node_groups = {
    core = {
      instance_types = ["m7g.large"]
      min_size       = 3
      max_size       = 10
      desired_size   = 3
      ami_type       = "AL2023_ARM_64_STANDARD"
    }
  }

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
    aws-ebs-csi-driver = {}
  }
}
```

Pin module versions. Review the module’s IAM: some defaults are broader than your policy allows.

---

## 46.12 Lab 1 — Cluster, IRSA, and a private API

1. Create a three-AZ VPC with `/22` private subnets.
2. Create an EKS cluster with private endpoint. Access it from a jump instance or SSM + `aws eks update-kubeconfig` on a bastion that can reach the ENIs.
3. Deploy a Deployment + Service + Ingress (internal ALB).
4. Create an IRSA role that can `s3:ListBucket` on one bucket. Annotate the SA. Confirm `aws sts get-caller-identity` from the pod.
5. Confirm a pod *without* the SA cannot list the bucket.

---

## 46.13 Lab 2 — IP exhaustion

1. On a small subnet (`/28` leftover), launch a node group of `m5.large`.
2. Scale a Deployment to a high replica count.
3. Watch pending pods and CNI logs.
4. Enable prefix delegation or enlarge subnets. Re-run.

Write the max-pods number you observed versus the documentation.

---

## 46.14 Lab 3 — Upgrade dry-run

1. List deprecated APIs in the cluster (`pluto` or `kube-no-trouble`).
2. Practice a node group AMI bump with a surge of 1.
3. Delete a node while a PDB of `minAvailable: 1` is set on a two-replica app. Confirm eviction behavior.

---

## 46.15 Production checklist

| Area | Check |
|------|--------|
| Endpoint | Private or CIDR-limited public |
| Logging | Audit at minimum |
| IAM | IRSA/Pod Identity; node role minimal |
| CNI | Prefix delegation decision documented; subnet math done |
| Ingress | AWS LB controller, WAF, TLS |
| Nodes | Bottlerocket or AL2023; IMDSv2; encrypted EBS |
| Add-ons | Version-aligned with Kubernetes |
| Backup | Velero or equivalent for PVCs and cluster-scoped resources |
| Access | `aws-auth` ConfigMap *or* EKS access entries documented — do not mix blindly |

EKS access management (access entries) is replacing the classic `aws-auth` ConfigMap. Know which your cluster uses.

---

## 46.16 Review questions

1. Why can the node instance role not be the application’s AWS identity?
2. What does prefix delegation change?
3. Why is `WaitForFirstConsumer` important for EBS?
4. What happens if a PDB prevents all node drains during an AMI upgrade?
5. How does IRSA pin a role to one ServiceAccount?
6. When is Fargate a bad fit?
7. Why three AZs for a “small” production cluster?
8. What is `target-type: ip` on an ALB Ingress?
9. Why keep control plane audit logs even if they are noisy?
10. What breaks if you upgrade Kubernetes before the EBS CSI add-on?

**Answers (brief):** (1) Every pod can steal node credentials via IMDS. (2) Assigns `/28` prefixes so many more pod IPs fit per ENI. (3) Volume is created in the AZ where the pod actually lands. (4) Upgrade stalls; you also cannot evacuate in an incident. (5) OIDC `sub` condition. (6) DaemonSets, privileged networking, some CNI features, large privileged workloads. (7) Control plane and workload survival of an AZ. (8) ALB targets pod IPs directly. (9) Forensics and compliance of who called the API. (10) Volume attach/mount failures on new nodes or API incompatibilities.

---

## 46.17 Cluster access, aws-auth, and Access Entries

Older clusters map IAM principals in the `kube-system/aws-auth` ConfigMap. A syntax error there is how you lock everyone out except the cluster creator. Newer EKS access entries move that map into the EKS API.

```bash
aws eks list-access-entries --cluster-name prod
aws eks create-access-entry --cluster-name prod \
  --principal-arn arn:aws:iam::111122223333:role/sso-admins \
  --type STANDARD
aws eks associate-access-policy --cluster-name prod \
  --principal-arn arn:aws:iam::111122223333:role/sso-admins \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

Prefer least privilege: `AmazonEKSViewPolicy` for readers, namespace-scoped admin for app teams, cluster admin for platform only.

**Pod Security:** use the built-in Pod Security Admission (restricted) on prod namespaces. Privileged DaemonSets (CNI, runtime security) belong in `kube-system` with explicit exemptions.

**Multi-tenancy:** hard tenancy is separate clusters. Soft tenancy is namespaces + NetworkPolicy + quotas + separate IRSA roles. Do not sell soft tenancy as PCI isolation.

**GitOps:** Argo CD or Flux in a platform namespace, IRSA for deploy, no long-lived kubeconfig on laptops for prod apply. `kubectl` from SSO + short sessions.

**Add-on upgrade order example:** coredns and kube-proxy compatible versions, vpc-cni, CSI, then control plane, then nodes. Read the EKS documentation for the version you run; this paragraph is a reminder to have an order, not a substitute for release notes.

**Capacity:** kube-reserved and system-reserved on node groups so pods do not starve the node. Cluster Autoscaler expander strategy vs Karpenter disruption budgets: both can delete nodes under you if PDBs are missing.

---

**etcd and managed control plane:** you cannot SSH to etcd. Your reliability story is multi-AZ nodes, PDBs, and tested upgrades — not custom etcd snapshots. Use Velero for application state. Treat the control plane like RDS: you back up *your* resources, not the operator’s disk.

---

**Observability stack:** scrape kube-state-metrics and node-exporter via Amazon Managed Prometheus or self-hosted; send traces to X-Ray or OTel Collector. Control plane logs without application traces will not explain a slow checkout.

---

## 46.18 What to do next

Stateful platforms still need Chapter 47: RDS, Aurora, DynamoDB, and ElastiCache. Kubernetes does not replace a database backup story. Treat the data plane as a client of those services with IRSA and security groups, not as a place to run unreplicated MySQL “just for a week.”
