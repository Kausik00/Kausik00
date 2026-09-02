# Chapter 36: Kubernetes RBAC, Pod Security, and Hardening

*DevOps Handbook — Pages 167–171 of this PDF edition*
---

## 36.1 Defense in depth for Kubernetes

Cluster security spans authentication (who), authorization (what they can do), admission control (what can be created), network policy (who can talk to whom), and workload hardening (how pods run). No single control is sufficient—layer them.

```
Request → AuthN (cert/OIDC) → AuthZ (RBAC) → Admission (PSA/OPA) → Pod sandbox → NetworkPolicy
```

---

## 36.2 Authentication overview

Human users should not use long-lived client certificates in production. Prefer **OIDC** integration (Google, Azure AD, Okta) via `kubectl` and cloud IAM for CI.

Service accounts authenticate **in-cluster** workloads:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api
  namespace: production
```

```yaml
spec:
  serviceAccountName: api
  containers:
    - name: api
      image: ghcr.io/acme/api:1.0
```

Each ServiceAccount gets a mounted token (bound to audience in K8s 1.24+). Use **IRSA** (EKS), **Workload Identity** (GKE), or **Azure Workload Identity** to map SA → cloud IAM role—never static cloud keys in pods.

```bash
kubectl auth can-i create deployments --namespace production
kubectl auth can-i --list --as=system:serviceaccount:production:api
```

---

## 36.3 RBAC — Roles and Bindings

RBAC grants permissions via **Role** (namespace) or **ClusterRole** (cluster-wide), bound with **RoleBinding** or **ClusterRoleBinding**.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployer
  namespace: staging
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ci-deployer
  namespace: staging
subjects:
  - kind: User
    name: github-actions-ci
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: deployer
  apiGroup: rbac.authorization.k8s.io
```

Least privilege verbs:

| Verb | Risk |
|------|------|
| `get`, `list`, `watch` | Read |
| `create`, `update`, `patch` | Modify |
| `delete` | Destructive |
| `*` | Avoid |

**ClusterRole** for read-only auditors:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: view-all
rules:
  - apiGroups: ["*"]
    resources: ["*"]
    verbs: ["get", "list", "watch"]
```

Bind to group `viewers` from OIDC. Never grant `cluster-admin` casually—use break-glass accounts with MFA and audit logging.

---

## 36.4 Aggregated roles and default bindings

Built-in ClusterRoles: `view`, `edit`, `admin`, `cluster-admin`. Namespace `RoleBinding` to `cluster-admin` is still namespace-scoped for namespaced resources but powerful.

Audit bindings:

```bash
kubectl get rolebindings,clusterrolebindings --all-namespaces
kubectl describe clusterrolebinding cluster-admin
```

Remove default permissions for unauthenticated or overly broad groups in managed clusters.

---

## 36.5 Pod Security Admission (PSA)

**Pod Security Admission** replaces deprecated PodSecurityPolicy. Namespace labels enforce **privileged**, **baseline**, or **restricted** profiles.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

| Profile | Constraints |
|---------|-------------|
| **privileged** | Unrestricted |
| **baseline** | No hostNetwork, hostPID, privileged containers |
| **restricted** | Non-root, drop caps, seccomp, no privilege escalation |

Restricted-compliant pod excerpt:

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: api
      image: ghcr.io/acme/api:1.0
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir: {}
```

Test violations:

```bash
kubectl label namespace production pod-security.kubernetes.io/enforce=restricted --overwrite
kubectl apply -f pod.yaml   # Should fail if non-compliant
```

---

## 36.6 OPA Gatekeeper and Kyverno

Admission controllers enforce custom policies beyond PSA.

**Kyverno** — validate/mutate/generate:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-non-root
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-runasnonroot
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "Containers must run as non-root"
        pattern:
          spec:
            containers:
              - securityContext:
                  runAsNonRoot: true
```

**Gatekeeper** uses Rego (see Chapter 25). Start with PSA labels, add policy engines for org-specific rules (required labels, approved registries, resource limits).

---

## 36.7 Workload hardening checklist

| Control | Implementation |
|---------|----------------|
| Non-root user | `runAsUser: 10001`, `runAsNonRoot: true` |
| Read-only rootfs | `readOnlyRootFilesystem: true` + tmpfs volumes |
| Drop capabilities | `capabilities.drop: [ALL]` |
| No privileged | `privileged: false` |
| Resource limits | Prevent noisy neighbor / DoS |
| Seccomp/AppArmor | `seccompProfile: RuntimeDefault` |
| Image pull policy | `IfNotPresent` + pinned tags/digests |
| NetworkPolicy | Default deny + explicit allow |

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: "1"
    memory: 512Mi
```

Pods without limits may be BestEffort QoS and evicted first under pressure.

---

## 36.8 Secrets, audit logs, and API security

Enable **audit logging** on API server (managed clouds: control plane logs). Ship to SIEM; alert on `secrets` access and `clusterrolebinding` changes.

Restrict **etcd** and **API server** network access. Disable anonymous auth. Rotate credentials.

**RBAC for Secrets**:

```yaml
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]
```

Limit to operators and controllers—not all developers.

---

## 36.9 Node and supply chain security

- **Minimal node OS** — Bottlerocket, COS, hardened AMIs
- **Auto-upgrade** node pools on CVE patches
- **Admission** — only signed images from approved registries (Chapter 29)
- **Falco** — runtime threat detection (syscall anomalies)
- **Vulnerability scanning** — workload images in CI and admission

Disable mounting Docker socket into pods (`/var/run/docker.sock`)—instant cluster compromise vector.

---

## 36.10 Incident response primitives

```bash
# Contain compromised pod
kubectl cordon node-name
kubectl delete pod compromised-pod --grace-period=0
kubectl scale deployment/suspicious --replicas=0

# Investigate
kubectl auth can-i --list --as=system:serviceaccount:ns:sa
kubectl get events -A --sort-by='.lastTimestamp'
kubectl logs -n kube-system -l component=kube-apiserver
```

Maintain runbooks for credential rotation, etcd restore, and compromised service account token revocation.

---

## 36.11 Chapter summary

- **RBAC** enforces least privilege—prefer namespace Roles over cluster-admin.
- **Service accounts** should map to cloud IAM via workload identity, not static keys.
- **Pod Security Admission** enforces baseline/restricted profiles at namespace level.
- Layer **admission policies**, **NetworkPolicies**, and **runtime monitoring** for production hardening.
- Enable **audit logs** and test restricted pod specs before enforcing in production namespaces.

---

## 🧪 Lab 36.1

1. Create a Role allowing deploy updates only in `staging`; bind to a test user or SA.
2. Label a namespace `restricted` and fix a Deployment until it passes PSA.
3. Run `kubectl auth can-i` checks validating your RBAC design.

---

## 🧪 Lab 36.2

1. Install Kyverno or Gatekeeper; deny containers running as root cluster-wide.
2. Apply default-deny NetworkPolicy plus explicit allows for one app stack.
3. Review API audit logs (or simulate with `kubectl` commands) for sensitive resource access.

---

## Review questions

1. What is the difference between a Role and a ClusterRole?
2. Which PSA profile should production app namespaces use?
3. Why should pods not use cluster-admin ServiceAccounts?
4. Name three fields required for a restricted Pod Security profile.
5. How do admission controllers differ from RBAC?

---

*Next: [Chapter 37 — CI/CD Pipeline Design](../part-09-cicd/chapter-37-cicd-pipeline-design.md)*
