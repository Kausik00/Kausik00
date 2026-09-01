# Chapter 31: Kubernetes Architecture — Control Plane and Node Components

*DevOps Handbook — Part VIII, Pages 581–605*

---

## 31.1 What Kubernetes provides

**Kubernetes (K8s)** is a container orchestration platform that schedules workloads across a cluster, heals failed containers, scales replicas, rolls out updates, and exposes services. You declare **desired state** in YAML; controllers reconcile reality toward that state.

Kubernetes does not replace containers—it orchestrates **OCI images** running in **pods** on **nodes**, managed by a **control plane**.

---

## 31.2 Cluster architecture overview

```
                    ┌─────────────────────────────────────┐
                    │           Control Plane             │
                    │  ┌─────────┐  ┌─────────────────┐ │
                    │  │ API     │  │ etcd (state)    │ │
                    │  │ Server  │◀─│ consistent KV   │ │
                    │  └────┬────┘  └─────────────────┘ │
                    │       │                             │
                    │  ┌────┴────┬──────────┬──────────┐ │
                    │  │Scheduler│ Controller│ Cloud    │ │
                    │  │         │ Manager   │ Controller│ │
                    │  └─────────┘ └──────────┘ Manager  │ │
                    └──────────────────┬──────────────────┘
                                       │ API (HTTPS)
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
        ┌─────▼─────┐            ┌─────▼─────┐            ┌─────▼─────┐
        │ Worker    │            │ Worker    │            │ Worker    │
        │ Node      │            │ Node      │            │ Node      │
        │ kubelet   │            │ kubelet   │            │ kubelet   │
        │ kube-proxy│            │ kube-proxy│            │ kube-proxy│
        │ containerd│            │ containerd│            │ containerd│
        └───────────┘            └───────────┘            └───────────┘
```

---

## 31.3 Control plane components

### API Server (`kube-apiserver`)

The **front door** to the cluster. All tools (`kubectl`, controllers, kubelet) talk to the API server over HTTPS. It validates requests, persists objects to etcd, and enforces authentication/authorization.

```bash
kubectl cluster-info
kubectl get --raw /healthz
kubectl api-resources
```

### etcd

Distributed **key-value store** holding all cluster state: pods, services, secrets metadata, RBAC, etc. Production clusters run etcd with TLS, regular backups, and odd-numbered quorum (3 or 5 members).

```bash
# Backup (on etcd member — simplified)
ETCDCTL_API=3 etcdctl snapshot save backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
```

Never expose etcd to the internet.

### Scheduler (`kube-scheduler`)

Watches unscheduled pods and assigns them to nodes based on resources, affinity, taints/tolerations, and topology spread.

### Controller Manager (`kube-controller-manager`)

Runs control loops: ReplicaSet, Deployment, Node, Job, EndpointSlice controllers, etc. Example: Deployment controller creates ReplicaSets; ReplicaSet controller creates pods.

### Cloud Controller Manager (CCM)

Integrates with cloud APIs: node lifecycle, load balancers, routes, volumes. On EKS/GKE/AKS, the cloud provider manages much of this.

---

## 31.4 Node components

### kubelet

Agent on each node. Registers the node, watches pod specs assigned to it, pulls images, starts containers via the **CRI** (containerd, CRI-O), reports status, and runs probes.

### kube-proxy

Maintains network rules (iptables, ipvs, or eBPF) so **Services** get stable virtual IPs and load-balance traffic to pod endpoints.

### Container runtime

Runs containers. **containerd** is the default in modern distros; Docker was removed as a direct runtime after K8s 1.24 (use cri-dockerd shim only if needed).

```bash
kubectl get nodes -o wide
crictl ps                    # On node — CRI debugging
systemctl status kubelet
```

---

## 31.5 Kubernetes objects and namespaces

Everything is an API **resource** with `apiVersion`, `kind`, `metadata`, `spec`, `status`.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: demo
  namespace: dev
  labels:
    app: demo
spec:
  containers:
    - name: nginx
      image: nginx:1.25-alpine
      ports:
        - containerPort: 80
```

```bash
kubectl apply -f pod.yaml
kubectl get pods -n dev -o wide
kubectl describe pod demo -n dev
kubectl logs demo -n dev
kubectl delete pod demo -n dev
```

**Namespaces** isolate resources logically (not physically):

| Namespace | Typical use |
|-----------|-------------|
| `kube-system` | Control plane addons |
| `kube-public` | Public cluster info |
| `default` | Avoid in prod |
| `dev` / `staging` / `prod` | Environment separation |

---

## 31.6 kubectl and kubeconfig

`~/.kube/config` defines **clusters**, **users**, and **contexts**:

```yaml
contexts:
  - name: prod-eks
    context:
      cluster: prod-eks
      user: prod-eks-admin
      namespace: production
current-context: prod-eks
```

```bash
kubectl config get-contexts
kubectl config use-context staging-eks
kubectl config set-context --current --namespace=payments
```

Imperative vs declarative:

```bash
kubectl run nginx --image=nginx --port=80        # Imperative (avoid in prod)
kubectl apply -f deployment.yaml                 # Declarative (preferred)
kubectl diff -f deployment.yaml
```

---

## 31.7 Managed vs self-managed clusters

| Type | Examples | You manage |
|------|----------|------------|
| **Managed control plane** | EKS, GKE, AKS | Nodes, workloads, addons |
| **Self-managed** | kubeadm, kops | Control plane + nodes |
| **Local dev** | kind, minikube, k3d | Learning only |

Managed services patch control plane versions; you still own upgrades, node AMIs, CNI, and workload security.

---

## 31.8 Addons and the CNCF landscape

Common cluster addons:

| Addon | Purpose |
|-------|---------|
| **CNI** (Calico, Cilium, AWS VPC CNI) | Pod networking |
| **CoreDNS** | Service discovery DNS |
| **Metrics Server** | `kubectl top`, HPA |
| **Ingress controller** | HTTP routing |
| **CSI driver** | Persistent volumes |
| **cert-manager** | TLS certificates |

Install with Helm or cloud marketplace; pin versions and test upgrades in staging.

---

## 31.9 High availability and etcd sizing

Production control plane:

- **3+ API server** instances behind load balancer
- **3 or 5 etcd** members across failure domains
- Regular **etcd backup** and restore drills
- **Separate** etcd from worker nodes

Worker nodes:

- Spread across **availability zones**
- Use **PodDisruptionBudgets** during node drains
- **Cluster Autoscaler** adds/removes nodes based on pending pods

---

## 31.10 Chapter summary

- The **control plane** (API server, etcd, scheduler, controllers) manages desired state; **nodes** run workloads via kubelet and runtime.
- All interaction flows through the **API server**; protect it with RBAC, audit logs, and network policies.
- **etcd** is the source of truth—backup and secure it aggressively.
- Use **declarative YAML** and **kubectl apply**; understand namespaces and contexts for multi-environment work.

---

## 🧪 Lab 31.1

1. Create a local cluster with `kind` or `minikube`.
2. Deploy a pod, inspect it with `describe`, and view logs.
3. List control plane pods in `kube-system` and identify CoreDNS, kube-proxy.

---

## 🧪 Lab 31.2

1. Configure two contexts (e.g., kind + cloud sandbox) and switch between them.
2. Take an etcd snapshot on a kubeadm lab cluster (or document EKS backup approach).
3. Draw your org's cluster diagram: control plane ownership, node pools, addons.

---

## Review questions

1. Which component is the only one that writes to etcd for API requests?
2. What is the kubelet's relationship to the container runtime?
3. Why should etcd never be exposed publicly?
4. What is the difference between the scheduler and a controller?
5. Name three addons required for a minimally functional cluster network and DNS.

---

*Next: [Chapter 32 — K8s Workloads](./chapter-32-k8s-workloads.md)*
