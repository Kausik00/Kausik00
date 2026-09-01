# Chapter 19: EKS — Managed Kubernetes on AWS

*AWS Handbook — Part IV, Pages 376–400*

---

## 19.1 Why Amazon EKS?

**Amazon Elastic Kubernetes Service (EKS)** is AWS's managed Kubernetes offering. Kubernetes has become the de facto standard for container orchestration at scale, and EKS provides a certified, managed control plane with deep AWS integration.

Choose EKS when you need Kubernetes portability, a rich ecosystem (Helm, operators, service mesh), multi-cloud strategy, or your team already has Kubernetes expertise.

---

## 19.2 EKS architecture

```
┌──────────────────────────────────────────────────┐
│  EKS Control Plane (AWS managed)                  │
│  API Server · etcd · Scheduler · Controller Mgr   │
└────────────────────┬─────────────────────────────┘
                     │ API (443)
┌────────────────────▼─────────────────────────────┐
│  Worker Nodes (your responsibility)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Node 1    │  │ Node 2    │  │ Node 3    │      │
│  │ (Pods)    │  │ (Pods)    │  │ (Pods)    │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  EC2 · Fargate · Hybrid (EKS Anywhere)           │
└──────────────────────────────────────────────────┘
```

### What AWS manages

- Kubernetes control plane (API server, etcd, scheduler, controllers)
- Control plane high availability across 3 AZs
- Control plane patching and upgrades
- Integrated logging and monitoring

### What you manage

- Worker nodes (EC2, Fargate, or hybrid)
- Node scaling and patching
- Application deployments
- Networking (CNI plugin)
- Add-ons and cluster configuration

---

## 19.3 Cluster creation

### eksctl (recommended for getting started)

```bash
# Install eksctl
curl -sLO "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz"
tar -xzf eksctl_*.tar.gz -C /tmp && sudo mv /tmp/eksctl /usr/local/bin

# Create cluster with managed node group
eksctl create cluster \
  --name production \
  --region us-east-1 \
  --version 1.29 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 6 \
  --managed
```

### Terraform

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "production"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      min_size     = 2
      max_size     = 10
      desired_size = 3
      instance_types = ["t3.medium"]
    }
  }

  enable_cluster_creator_admin_permissions = true
}
```

---

## 19.4 Node groups

| Type | Description |
|------|-------------|
| **Managed node group** | AWS manages node lifecycle (launch, drain, terminate) |
| **Self-managed** | You manage ASG and node provisioning |
| **Fargate profile** | Serverless pods; no nodes to manage |

### Managed node group features

- Automatic AMI updates via EKS optimized AMIs
- Integrated with Cluster Autoscaler and Karpenter
- Rolling updates with drain and cordon
- Launch templates for customization

### Karpenter (recommended autoscaler)

**Karpenter** provisions nodes dynamically based on pending pod requirements—faster and more cost-efficient than Cluster Autoscaler:

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3.medium", "t3.large", "m5.large"]
  limits:
    cpu: 100
  disruption:
    consolidationPolicy: WhenUnderutilized
```

---

## 19.5 Networking

### VPC CNI

EKS uses the **Amazon VPC CNI plugin** — each pod gets a real VPC IP address:

- Plan IP capacity: each pod consumes an IP from the subnet.
- Use **prefix delegation** or **custom networking** for large clusters.
- Security groups can be applied directly to pods (Security Groups for Pods).

### Service types

| Type | AWS integration |
|------|-----------------|
| **ClusterIP** | Internal only |
| **NodePort** | Exposes on node port |
| **LoadBalancer** | Creates ALB/NLB via AWS Load Balancer Controller |
| **Ingress** | ALB Ingress Controller for HTTP routing |

### AWS Load Balancer Controller

```bash
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=production \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

---

## 19.6 IAM integration

### IRSA (IAM Roles for Service Accounts)

Pods assume IAM roles via OIDC federation — no need for node-level credentials:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/app-role
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      serviceAccountName: app-sa
      containers:
        - name: app
          image: my-app:latest
```

### EKS Pod Identity (newer)

Simpler alternative to IRSA; assigns IAM roles to pods via the EKS API without OIDC provider setup.

---

## 19.7 Essential add-ons

| Add-on | Purpose |
|--------|---------|
| **CoreDNS** | Cluster DNS |
| **kube-proxy** | Network proxy on nodes |
| **VPC CNI** | Pod networking |
| **EBS CSI Driver** | Persistent volumes (EBS) |
| **EFS CSI Driver** | Shared persistent volumes (EFS) |
| **Metrics Server** | HPA resource metrics |
| **Cluster Autoscaler / Karpenter** | Node autoscaling |

```bash
aws eks create-addon \
  --cluster-name production \
  --addon-name aws-ebs-csi-driver \
  --service-account-role-arn arn:aws:iam::123456789012:role/AmazonEKS_EBS_CSI_DriverRole
```

---

## 19.8 Storage

| Type | Use case | Provisioner |
|------|----------|-------------|
| **EBS (gp3)** | Single-pod persistent storage | EBS CSI Driver |
| **EFS** | Shared storage across pods | EFS CSI Driver |
| **FSx for Lustre** | High-performance computing | FSx CSI Driver |
| **emptyDir** | Ephemeral pod storage | Built-in |

### PersistentVolumeClaim example

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: gp3
  resources:
    requests:
      storage: 20Gi
```

---

## 19.9 Security

| Layer | Control |
|-------|---------|
| **Control plane** | Private endpoint, public endpoint, or both |
| **Network policies** | Calico or VPC CNI network policies |
| **Pod security** | Pod Security Standards (restricted, baseline) |
| **Secrets** | External Secrets Operator + Secrets Manager |
| **Image scanning** | ECR scanning, admission controllers |
| **Audit logging** | EKS control plane logs to CloudWatch |

```bash
aws eks update-cluster-config \
  --name production \
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator"],"enabled":true}]}'
```

---

## 19.10 Upgrades and operations

### Cluster upgrade path

1. Upgrade control plane to target Kubernetes version.
2. Upgrade add-ons (CoreDNS, kube-proxy, VPC CNI).
3. Upgrade node groups (rolling replacement).
4. Update application manifests for deprecated APIs.

```bash
# Check deprecated APIs
kubectl pluto detect-deprecated-apis --target-versions k8s=v1.29.0

# Upgrade control plane
aws eks update-cluster-version --name production --kubernetes-version 1.29
```

### Useful kubectl commands

```bash
kubectl get nodes -o wide
kubectl top nodes
kubectl get pods --all-namespaces -o wide
kubectl describe pod <name> -n <namespace>
kubectl logs -f <pod> -c <container>
```

---

## 19.11 EKS vs ECS decision matrix

| Factor | Choose EKS | Choose ECS |
|--------|-----------|-----------|
| Team Kubernetes expertise | Yes | No |
| Multi-cloud portability | Yes | No |
| AWS-native simplicity | No | Yes |
| Ecosystem (Helm, operators) | Yes | Limited |
| Operational overhead | Higher | Lower |
| Fargate support | Yes | Yes |

---

## 19.12 Chapter summary

- **EKS** provides a managed Kubernetes control plane with AWS integrations.
- **Managed node groups**, **Fargate**, and **Karpenter** handle worker capacity.
- **IRSA** and **Pod Identity** grant fine-grained IAM permissions to pods.
- **AWS Load Balancer Controller** and **EBS/EFS CSI drivers** are essential add-ons.
- Plan **IP capacity**, **upgrades**, and **security** from day one.

---

## 🧪 Lab 19.1 — EKS cluster deployment

1. Create an EKS cluster with eksctl (3-node managed node group).
2. Deploy a sample application with a LoadBalancer service.
3. Configure IRSA for an S3-accessing pod.
4. Install Metrics Server and verify `kubectl top nodes`.

## 🧪 Lab 19.2 — Persistent storage

1. Install the EBS CSI driver add-on.
2. Create a StorageClass, PVC, and Pod mounting the volume.
3. Write data to the volume, delete the pod, recreate it, and verify data persists.

---

## Review questions

1. What components of Kubernetes does AWS manage in EKS?
2. How does IRSA enable pods to access AWS services securely?
3. Why is IP address planning critical for EKS clusters?
4. What is the recommended order for EKS cluster upgrades?
5. When would you choose ECS over EKS?

---

*Next: [Chapter 20 — S3 Fundamentals](../part-05-storage/chapter-20-s3-fundamentals.md)*
