# Chapter 32: Kubernetes Workloads — Pod, Deployment, StatefulSet, DaemonSet

*DevOps Handbook — Part VIII, Pages 606–630*

---

## 32.1 Pods — the atomic unit

A **Pod** is the smallest deployable unit in Kubernetes: one or more containers sharing network and storage namespaces, scheduled together on one node.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web
  labels:
    app: web
spec:
  containers:
    - name: nginx
      image: nginx:1.25-alpine
      ports:
        - containerPort: 80
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 500m
          memory: 256Mi
      livenessProbe:
        httpGet:
          path: /
          port: 80
        initialDelaySeconds: 10
        periodSeconds: 10
      readinessProbe:
        httpGet:
          path: /
          port: 80
        periodSeconds: 5
```

| Probe | Purpose |
|-------|---------|
| **liveness** | Restart if deadlocked |
| **readiness** | Include in Service endpoints |
| **startup** | Slow-start apps before liveness kicks in |

**Sidecar pattern** — helper container in same pod:

```yaml
spec:
  containers:
    - name: app
      image: myapp:1.0
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
    - name: log-shipper
      image: fluent/fluent-bit:2
      volumeMounts:
        - name: logs
          mountPath: /var/log/app
  volumes:
    - name: logs
      emptyDir: {}
```

Pods are ephemeral—do not manage them directly in production. Use controllers.

---

## 32.2 Deployments — stateless apps

A **Deployment** manages ReplicaSets to run N identical pod replicas with rolling updates and rollbacks.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: ghcr.io/acme/api:v1.2.0
          ports:
            - containerPort: 8080
          env:
            - name: LOG_LEVEL
              value: info
```

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/api
kubectl set image deployment/api api=ghcr.io/acme/api:v1.3.0
kubectl rollout history deployment/api
kubectl rollout undo deployment/api
kubectl scale deployment/api --replicas=5
```

### Rolling update flow

```
v1 v1 v1  →  v1 v1 v2  →  v1 v2 v2  →  v2 v2 v2
```

`maxUnavailable: 0` ensures capacity during rollout; `maxSurge` allows extra pods temporarily.

---

## 32.3 ReplicaSets and labels

Deployments own **ReplicaSets**; ReplicaSets own **Pods**. Labels in `selector.matchLabels` must match pod template labels.

```bash
kubectl get rs
kubectl get pods --show-labels
```

Never change immutable selector fields on existing Deployments—create a new Deployment instead.

---

## 32.4 StatefulSets — stable identity and storage

**StatefulSets** assign stable network IDs (`web-0`, `web-1`) and persistent storage per replica. Use for databases, Kafka, ZooKeeper.

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
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

Headless Service for stable DNS:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
    - port: 5432
```

Pod DNS: `postgres-0.postgres-headless.default.svc.cluster.local`

StatefulSet pods are created/deleted in order (0, 1, 2…). Scaling and updates are slower but predictable.

---

## 32.5 DaemonSets — one pod per node

**DaemonSets** run a pod on every (or selected) node—agents, log collectors, CNI plugins, node exporters.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      tolerations:
        - operator: Exists
      containers:
        - name: exporter
          image: prom/node-exporter:v1.8.2
          ports:
            - containerPort: 9100
```

`tolerations: operator: Exists` schedules on tainted control plane nodes if needed.

---

## 32.6 Jobs and CronJobs

**Job** — run to completion:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: ghcr.io/acme/api:v1.2.0
          command: ["npm", "run", "migrate"]
```

**CronJob** — scheduled jobs:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-report
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: report
              image: ghcr.io/acme/reporter:latest
```

---

## 32.7 Choosing a workload type

| Workload | Controller | When |
|----------|------------|------|
| HTTP API, workers | Deployment | Stateless, horizontal scale |
| Postgres cluster | StatefulSet | Stable ID + PVC per pod |
| Log agent | DaemonSet | Per-node background service |
| Migration, batch | Job | Run once to completion |
| Reports, backups | CronJob | Time-based |

---

## 32.8 Pod scheduling controls

```yaml
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app: api
          topologyKey: kubernetes.io/hostname
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app: api
```

**Taints and tolerations** repel pods unless tolerated:

```yaml
# Node taint: dedicated=gpu:NoSchedule
spec:
  tolerations:
    - key: dedicated
      operator: Equal
      value: gpu
      effect: NoSchedule
```

---

## 32.9 Chapter summary

- **Pods** run containers; use probes and resource requests/limits.
- **Deployments** manage stateless apps with rolling updates and rollbacks.
- **StatefulSets** provide stable identity and storage for stateful systems.
- **DaemonSets** run per-node agents; **Jobs/CronJobs** handle batch work.
- Match workload type to data and scaling requirements—do not run databases as bare Deployments without understanding data loss risk.

---

## 🧪 Lab 32.1

1. Deploy a 3-replica nginx Deployment; practice rollout, rollback, and scale.
2. Add liveness and readiness probes; break the app and observe restarts vs traffic removal.
3. Deploy a StatefulSet with `volumeClaimTemplates` and verify ordered pod names.

---

## 🧪 Lab 32.2

1. Create a DaemonSet node-exporter and confirm one pod per node.
2. Run a Job migration container and inspect completion status.
3. Add pod anti-affinity so replicas spread across nodes/zones.

---

## Review questions

1. What happens if readiness probe fails but liveness passes?
2. Why do StatefulSets need a headless Service?
3. When should you use a Job instead of a Deployment with restartPolicy Never?
4. What do `maxSurge` and `maxUnavailable` control during rollouts?
5. Why is running PostgreSQL as a single-replica Deployment risky?

---

*Next: [Chapter 33 — K8s Services and Ingress](./chapter-33-k8s-services-ingress.md)*
