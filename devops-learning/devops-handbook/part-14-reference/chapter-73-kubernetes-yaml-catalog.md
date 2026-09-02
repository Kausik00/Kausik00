# Chapter 73: Kubernetes YAML Catalog

*DevOps Handbook — Pages 403–415 of this PDF edition*

This catalog is a set of **production-shaped** manifests you can copy into a GitOps repo. They are opinionated: explicit requests/limits, probes, PDBs, securityContext, and topology spread. Replace names, registries, and CIDRs. Do not paste into production without reviewing NetworkPolicy CIDRs and image digests.

Conventions:

| Field | Catalog default |
|-------|-----------------|
| Namespace | `shop` |
| App label | `app.kubernetes.io/name` |
| Images | digest-pinned comments |
| Probe port | named `http` |

Apply order for a new service: Namespace → ServiceAccount → ConfigMap/Secret → NetworkPolicy → PDB → Deployment/StatefulSet → Service → Ingress → HPA.

---

## 73.1 Namespace, quota, and defaults

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: shop
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: shop-quota
  namespace: shop
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    persistentvolumeclaims: "20"
    pods: "80"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: shop-limits
  namespace: shop
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 256Mi
      defaultRequest:
        cpu: 50m
        memory: 64Mi
      max:
        cpu: "4"
        memory: 8Gi
```

---

## 73.2 ServiceAccount and RBAC (app, not cluster-admin)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: checkout
  namespace: shop
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/checkout-irsa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: checkout-config-reader
  namespace: shop
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["checkout"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: checkout-config-reader
  namespace: shop
subjects:
  - kind: ServiceAccount
    name: checkout
    namespace: shop
roleRef:
  kind: Role
  name: checkout-config-reader
  apiGroup: rbac.authorization.k8s.io
```

---

## 73.3 ConfigMap and Secret (structure only)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: checkout
  namespace: shop
data:
  APP_ENV: production
  LOG_LEVEL: info
  CHECKOUT_TIMEOUT_MS: "800"
---
# Prefer ExternalSecret. This is the in-cluster shape only.
apiVersion: v1
kind: Secret
metadata:
  name: checkout-db
  namespace: shop
type: Opaque
stringData:
  DATABASE_URL: postgres://checkout:REDACTED@checkout-db:5432/checkout?sslmode=require
```

---

## 73.4 Deployment (stateless API)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout
  namespace: shop
  labels:
    app.kubernetes.io/name: checkout
    app.kubernetes.io/part-of: shopstream
spec:
  replicas: 3
  revisionHistoryLimit: 10
  progressDeadlineSeconds: 600
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        app.kubernetes.io/name: checkout
        app.kubernetes.io/part-of: shopstream
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: /metrics
    spec:
      serviceAccountName: checkout
      automountServiceAccountToken: true
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        fsGroup: 65532
        seccompProfile:
          type: RuntimeDefault
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: checkout
      terminationGracePeriodSeconds: 45
      containers:
        - name: checkout
          image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout@sha256:REPLACE
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
          envFrom:
            - configMapRef:
                name: checkout
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: checkout-db
                  key: DATABASE_URL
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: "1"
              memory: 512Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
          startupProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 5
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /readyz
              port: http
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 20
            timeoutSeconds: 2
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 8"]
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                topologyKey: kubernetes.io/hostname
                labelSelector:
                  matchLabels:
                    app.kubernetes.io/name: checkout
```

`maxUnavailable: 0` plus PDB keeps capacity during a rollout. `preStop sleep` gives kube-proxy/endpoint controllers time to drop the pod from Services before SIGTERM. Tune to your mesh.

---

## 73.5 Service and Ingress

```yaml
apiVersion: v1
kind: Service
metadata:
  name: checkout
  namespace: shop
  labels:
    app.kubernetes.io/name: checkout
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: checkout
  ports:
    - name: http
      port: 80
      targetPort: http
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: checkout
  namespace: shop
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/proxy-body-size: "2m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "30"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts: ["checkout.example.com"]
      secretName: checkout-tls
  rules:
    - host: checkout.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: checkout
                port:
                  name: http
```

Gateway API equivalent (HTTPRoute excerpt):

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: checkout
  namespace: shop
spec:
  parentRefs:
    - name: external-gw
      namespace: gateway-system
  hostnames: ["checkout.example.com"]
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: checkout
          port: 80
```

---

## 73.6 HorizontalPodAutoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: checkout
  namespace: shop
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: checkout
  minReplicas: 3
  maxReplicas: 20
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
        - type: Pods
          value: 4
          periodSeconds: 60
      selectPolicy: Max
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
```

Custom metrics require a metrics adapter. Start with CPU, add RPS when Prometheus adapter is production-ready.

---

## 73.7 PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: checkout
  namespace: shop
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout
  unhealthyPodEvictionPolicy: AlwaysAllow
```

`unhealthyPodEvictionPolicy` (1.27+) prevents a dead pod from blocking drains. Never set `minAvailable: 100%` on a single replica.

---

## 73.8 NetworkPolicy (default deny + DNS + ingress + metrics)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: checkout-default-deny
  namespace: shop
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: checkout
  policyTypes: ["Ingress", "Egress"]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: checkout-allow
  namespace: shop
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: checkout
  policyTypes: ["Ingress", "Egress"]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: checkout-db
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: shop
          podSelector:
            matchLabels:
              app.kubernetes.io/name: catalog
      ports:
        - protocol: TCP
          port: 80
```

If you use node-local-dns, allow that DaemonSet as well. Test with a `netshoot` pod.

---

## 73.9 StatefulSet (PostgreSQL-shaped, not a hosted RDS replacement)

This is for labs and non-critical stores. Production OLTP usually belongs on a managed database.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: checkout-db
  namespace: shop
spec:
  clusterIP: None
  selector:
    app.kubernetes.io/name: checkout-db
  ports:
    - name: postgres
      port: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: checkout-db
  namespace: shop
spec:
  serviceName: checkout-db
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout-db
  template:
    metadata:
      labels:
        app.kubernetes.io/name: checkout-db
    spec:
      securityContext:
        fsGroup: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: postgres
          image: postgres:16.3
          args: ["-c", "max_connections=200", "-c", "shared_buffers=256MB"]
          ports:
            - name: postgres
              containerPort: 5432
          env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: checkout-db-super
                  key: password
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: "2"
              memory: 2Gi
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "postgres"]
            periodSeconds: 5
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3
        resources:
          requests:
            storage: 50Gi
```

---

## 73.10 Job and CronJob

One-shot migration Job:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: checkout-migrate-20260902
  namespace: shop
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 86400
  activeDeadlineSeconds: 600
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: checkout
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: migrate
          image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout@sha256:REPLACE
          command: ["/app/migrate", "up"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: checkout-db
                  key: DATABASE_URL
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
```

Nightly report CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: checkout-reconciliation
  namespace: shop
spec:
  schedule: "15 5 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          serviceAccountName: checkout
          containers:
            - name: reconcile
              image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout@sha256:REPLACE
              command: ["/app/reconcile"]
              resources:
                requests:
                  cpu: 100m
                  memory: 128Mi
```

---

## 73.11 Kustomize overlay sketch

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: shop
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  - deploy.yaml
  - svc.yaml
  - ingress.yaml
  - hpa.yaml
  - pdb.yaml
  - netpol.yaml
images:
  - name: 123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout
    digest: sha256:REPLACE
```

---

## 73.12 Common kubectl apply/debug commands

```bash
kubectl apply -k overlays/prod
kubectl rollout status deploy/checkout -n shop
kubectl get hpa,pdb,netpol,ingress -n shop
kubectl describe ingress checkout -n shop
kubectl auth can-i list secrets --as=system:serviceaccount:shop:checkout -n shop
kubectl debug -it deploy/checkout -n shop --image=nicolaka/netshoot --target=checkout
```

---

## 73.13 Field rationale table

| Choice | Why |
|--------|-----|
| `runAsNonRoot` + drop ALL | Restricted PSA |
| named ports | HPA/Ingress stability when numbers change |
| `maxUnavailable: 0` | Capacity during rollout |
| topology spread on zone | AZ failure |
| read-only rootfs + emptyDir `/tmp` | Writable surface minimized |
| digest pin | Reproducible deploys |
| `concurrencyPolicy: Forbid` | No overlapping cron |
| headless Service for STS | DNS identity |

---

## 73.14 Anti-patterns

| Anti-pattern | Failure |
|--------------|---------|
| `image: app:latest` | Nodes diverge |
| no probes | Black-hole deploys |
| liveness on a dependency | Restart storms |
| shared RWX PVC for a Deployment | Corruption |
| `hostNetwork: true` for convenience | Node port fights, security |
| ClusterRole `*` for an app SA | Blast radius |
| NetworkPolicy ingress-only | Egress still open |
| HPA minReplicas 1 for HA API | Drain + crash = outage |

---

## 73.15 Checklist before first prod apply

1. Image digest exists in the prod registry.
2. Secret is not committed; ExternalSecret tested in staging.
3. Ingress host DNS and cert-manager issuer ready.
4. NetworkPolicy does not block CoreDNS.
5. PDB compatible with replica count.
6. HPA metrics-server healthy.
7. ResourceQuota will not immediately deny pods.
8. PodSecurity restricted does not block your securityContext.
9. Run `kubeconform` and `kustomize build \| kubectl apply --dry-run=server`.
10. Link dashboards and alerts to the new `job`/`app` labels.

Keep this catalog as the **paved road**. When a team needs a sidecar or a mesh, extend the template rather than inventing a snowflake Deployment per service.

---

## 73.16 ExternalSecret (production-shaped)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: checkout-db
  namespace: shop
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets
    kind: ClusterSecretStore
  target:
    name: checkout-db
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: shopstream/prod/checkout
        property: DATABASE_URL
```

After rotation, either restart pods or use a reloader that watches the Secret checksum annotation. Document which apps cache env at boot (most of them).

---

## 73.17 PriorityClass and disruption for platform vs apps

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: shop-critical
value: 1000000
globalDefault: false
description: "Checkout and payments — preempt batch"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: shop-batch
value: 1000
```

Set `priorityClassName: shop-critical` on checkout. Batch Jobs use `shop-batch` so a full node still places payments. Combine with ResourceQuota so a team cannot stamp 500 critical pods.

---

## 73.18 Vertical comments: probes that do not lie

| Probe | Should check | Must not check |
|-------|----------------|----------------|
| startup | process listens | full DB schema migrate |
| readiness | this instance can serve *this* request type | every downstream in the company |
| liveness | deadlock / stuck event loop | 500 from a dependency |

Example of a good `/readyz`: in-memory config loaded, local port open, optional *cached* DB ping with a long timeout budget so a 200ms DB blip does not flap Endpoints. Example of a bad `/healthz`: `SELECT 1` on the primary from every replica every 2s — that is a load test.

---

## 73.19 Rollout and traffic splitting (Argo Rollouts excerpt)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: checkout
  namespace: shop
spec:
  replicas: 4
  strategy:
    canary:
      maxSurge: 1
      maxUnavailable: 0
      steps:
        - setWeight: 10
        - pause: {duration: 10m}
        - setWeight: 50
        - pause: {duration: 10m}
      analysis:
        templates:
          - templateName: success-rate
        args:
          - name: service-name
            value: checkout
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout
  template:
    metadata:
      labels:
        app.kubernetes.io/name: checkout
    spec:
      containers:
        - name: checkout
          image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout@sha256:REPLACE
```

If you do not run Rollouts, emulate with two Deployments and an Ingress canary annotation. The **metric** matters more than the CRD: include business duplicates, not only HTTP 200 (see Chapter 76).

---

## 73.20 ServiceMonitor for Prometheus Operator

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: checkout
  namespace: shop
  labels:
    release: kube-prometheus-stack
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout
  namespaceSelector:
    matchNames: ["shop"]
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
```

NetworkPolicy must allow the Prometheus namespace to the metrics port. Forgetting this looks like “the app has no metrics” when it is a packet drop.

---

## 73.21 Debugging matrix (YAML-related)

| Symptom | Likely manifest issue |
|---------|------------------------|
| `CreateContainerConfigError` | missing Secret/ConfigMap key |
| `ErrImagePull` | wrong digest, no pull secret |
| `RunContainerError` | read-only rootfs, missing emptyDir |
| `CrashLoop` | command/args, missing env |
| `Pending` PVC | StorageClass / zone |
| `Forbidden` | RBAC, PSA, quota |
| 504 from Ingress | missing readiness, wrong Service selector |
| HPA `Unknown` | metrics-server or adapter |

Selector bugs are silent: Deployment labels `app: checkout` and Service `app: checkot` yield an empty Endpoints object. Always `kubectl get endpointslices -n shop`.

---

## 73.22 Resource sizing starting points (not gospel)

| Workload | Request CPU | Request mem | Limit mem | Notes |
|----------|-------------|-------------|-----------|-------|
| Go API | 100–200m | 128–256Mi | 256–512Mi | watch goroutine leaks |
| JVM API | 500m | 512Mi–1Gi | request=limit if Guaranteed | heap < limit |
| Node.js | 100–250m | 128–256Mi | 512Mi | |
| Redis (lab) | 100m | 256Mi | 512Mi | persistence separate |
| Batch Job | 100m | 128Mi | 1Gi | bursty |

Revisit with `VPA` recommendations in **recommendation** mode before you apply auto-update.

---

## 73.23 GitOps file layout for this catalog

```
deploy/
  base/           # this catalog
  overlays/
    lab/
    staging/
    prod/         # replica counts, hostnames, digests
```

Prod overlay should change **counts, hostnames, and image digest**, not rewrite securityContext. If prod “needs privileged,” that is a conversation, not an overlay one-liner.

Apply with:

```bash
kustomize build deploy/overlays/prod | kubeconform -strict
kustomize build deploy/overlays/prod | kubectl diff -f -
```

`kubectl diff` requires the same RBAC as apply; in CI use a read-only kubeconfig plus server-side dry-run where available.
