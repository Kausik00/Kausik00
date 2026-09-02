# Chapter 35: Helm, Kustomize, and GitOps (Argo CD)

*DevOps Handbook — Pages 161–166 of this PDF edition*
---

## 35.1 The packaging problem

Raw YAML does not scale: duplicated labels, repeated image tags across environments, and manual `kubectl apply` drift from Git. **Helm** packages charts; **Kustomize** overlays bases; **GitOps** (Argo CD, Flux) continuously reconciles cluster state from Git.

```
Git (desired state) → CI builds image → GitOps controller → Kubernetes (actual state)
```

---

## 35.2 Helm charts

A **chart** is a directory of templated Kubernetes manifests plus metadata.

```
mychart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── _helpers.tpl
└── charts/          # Subchart dependencies
```

`Chart.yaml`:

```yaml
apiVersion: v2
name: api
description: Bookstore API
type: application
version: 0.1.0
appVersion: "1.2.0"
```

`values.yaml`:

```yaml
replicaCount: 2
image:
  repository: ghcr.io/acme/api
  tag: "1.2.0"
  pullPolicy: IfNotPresent
service:
  type: ClusterIP
  port: 80
ingress:
  enabled: true
  host: api.example.com
resources:
  requests:
    cpu: 100m
    memory: 128Mi
```

`templates/deployment.yaml` excerpt:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: api
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: 8080
```

Commands:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm search repo nginx
helm install my-nginx bitnami/nginx --namespace web --create-namespace
helm upgrade my-nginx bitnami/nginx -f values-prod.yaml
helm list
helm uninstall my-nginx
helm template api ./mychart -f values-staging.yaml   # Render locally
```

Override per environment:

```yaml
# values-prod.yaml
replicaCount: 5
image:
  tag: "1.2.0"
ingress:
  host: api.example.com
```

---

## 35.3 Helm hooks and releases

**Hooks** run Jobs at pre/post install/upgrade (`helm.sh/hook: pre-upgrade`). Use for DB migrations—carefully, with rollback strategy.

**Release** = installed chart instance stored as Secrets in `sh.helm.release.v1.*` (history for rollback).

```bash
helm history api
helm rollback api 3
```

Helm 3 is **client-side only**—no Tiller. RBAC applies to the user or CI service account running Helm.

---

## 35.4 Kustomize — patch without templates

**Kustomize** is built into `kubectl apply -k`. No templating language—bases + overlays with patches and image transforms.

```
deploy/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   └── service.yaml
└── overlays/
    ├── staging/
    │   ├── kustomization.yaml
    │   └── patch-replicas.yaml
    └── production/
        ├── kustomization.yaml
        └── patch-resources.yaml
```

`base/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
commonLabels:
  app: api
```

`overlays/production/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namespace: production
replicas:
  - name: api
    count: 5
images:
  - name: ghcr.io/acme/api
    newTag: v1.2.0
patches:
  - path: patch-resources.yaml
configMapGenerator:
  - name: api-config
    literals:
      - LOG_LEVEL=warn
```

```bash
kubectl apply -k deploy/overlays/production
kubectl diff -k deploy/overlays/staging
```

| Tool | Strength | Weakness |
|------|----------|----------|
| **Helm** | Packaging, versioning, ecosystem charts | Go templates complexity |
| **Kustomize** | Simple overlays, native kubectl | Less packaging metadata |

Many teams use **Helm charts rendered by Kustomize** (`helm template | kustomize`) or Helm with post-render Kustomize.

---

## 35.5 GitOps principles

1. **Git is the source of truth** for desired cluster state
2. **Declarative** manifests (YAML, Helm, Kustomize)
3. **Automated reconciliation** — controller applies diffs
4. **Observable** — drift visible in UI/CLI

Anti-pattern: `kubectl apply` from laptops to production. GitOps makes changes via PR merge.

---

## 35.6 Argo CD

**Argo CD** watches Git repos and syncs Applications to clusters.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bookstore-api
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/acme-corp/gitops.git
    targetRevision: main
    path: apps/bookstore/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

```bash
argocd app list
argocd app diff bookstore-api
argocd app sync bookstore-api
argocd app rollback bookstore-api
```

**App of Apps** pattern bootstraps many Applications from one root manifest.

### Sync strategies

| Mode | Behavior |
|------|----------|
| **Manual** | Human clicks Sync |
| **Automated** | Sync on Git change |
| **selfHeal** | Revert manual kubectl edits |
| **prune** | Delete resources removed from Git |

Use **prune** cautiously with shared resources; test in staging first.

---

## 35.7 Promotion pipeline

Typical flow:

1. CI builds image → pushes `ghcr.io/acme/api:abc123`
2. CI or bot opens PR updating `newTag` in `overlays/staging`
3. Argo CD syncs staging; run smoke tests
4. PR promotes same tag to `overlays/production`
5. Argo CD syncs prod (manual approval optional via Argo CD projects)

**Image updater** tools (Argo CD Image Updater, Flux image automation) can write back to Git when new tags appear—pin policies to semver or regex.

---

## 35.8 Flux (brief comparison)

**Flux CD** uses GitRepository + Kustomization/HelmRelease CRDs:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: gitops
spec:
  url: https://github.com/acme-corp/gitops
  ref:
    branch: main
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: production
spec:
  sourceRef:
    kind: GitRepository
    name: gitops
  path: ./apps/bookstore/overlays/production
  interval: 5m
  prune: true
```

| | Argo CD | Flux |
|---|---------|------|
| UI | Rich web UI | CLI / Weave GitOps UI |
| Model | Application CRD | Modular controllers |
| Multi-cluster | ApplicationSet | Cluster API integration |

Both are CNCF graduated/incubating; choice often organizational.

---

## 35.9 Secrets in GitOps

Never plain Secrets in Git. Options:

- **Sealed Secrets** — encrypt for cluster-only decryption
- **SOPS** + KMS — Mozilla SOPS with age/PGP/cloud KMS
- **External Secrets** — reference cloud vault; not stored in Git

Argo CD supports helm-secrets, ksops plugins for encrypted manifests.

---

## 35.10 Chapter summary

- **Helm** packages and parameterizes Kubernetes apps; **Kustomize** patches bases per environment.
- **GitOps** reconciles cluster state from Git—eliminating ad-hoc kubectl changes.
- **Argo CD** and **Flux** automate deploys with visibility into drift and sync status.
- Protect secrets with encryption or external stores; promote images via Git PRs, not manual image bumps on nodes.

---

## 🧪 Lab 35.1

1. Package a Deployment + Service as a Helm chart; install with staging and prod values files.
2. Replicate the same app with Kustomize base + two overlays.
3. Compare rendered YAML from `helm template` vs `kubectl kustomize`.

---

## 🧪 Lab 35.2

1. Install Argo CD on a test cluster; deploy an Application from a Git repo.
2. Change a replica count in Git; observe auto-sync (if enabled).
3. Make a manual `kubectl scale` change; observe selfHeal revert it.

---

## Review questions

1. What is the difference between a Helm chart and a Helm release?
2. When would Kustomize be preferable to Helm?
3. What risks does `prune: true` introduce?
4. How does GitOps change the role of `kubectl apply` in production?
5. Name two approaches for storing secrets in a GitOps repository.

---

*Next: [Chapter 36 — K8s RBAC and Security](./chapter-36-k8s-rbac-security.md)*
