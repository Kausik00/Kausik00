# Chapter 41: Deployment Strategies — Blue/Green, Canary, Feature Flags

*DevOps Handbook — Pages 193–197 of this PDF edition*
---

## 41.1 Why deployment strategy matters

Releasing software is not binary—"deploy or don't deploy." How you roll out changes determines **downtime**, **blast radius**, **rollback speed**, and **confidence**. A pipeline that builds and tests flawlessly still causes outages if production traffic shifts incorrectly.

Deployment strategies sit at the intersection of **CI/CD**, **infrastructure**, and **application design**. This chapter covers rolling, recreate, blue/green, canary, and feature flags—with Kubernetes and load balancer examples.

| Strategy | Downtime | Rollback speed | Infra cost | Complexity |
|----------|----------|----------------|------------|------------|
| Recreate | Yes | Slow (redeploy) | Low | Low |
| Rolling | Minimal | Moderate | Low | Low |
| Blue/green | Near zero | Fast (switch) | 2× during cutover | Medium |
| Canary | None | Fast (traffic shift) | Partial duplicate | High |
| Feature flags | None | Instant (toggle) | Low | App changes |

---

## 41.2 Rolling deployment

**Rolling** replaces instances incrementally: old and new versions run simultaneously until all instances update.

Kubernetes default `Deployment` strategy:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
        - name: api
          image: registry.example.com/api:v2.3.0
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
```

| Parameter | Effect |
|-----------|--------|
| `maxSurge` | Extra pods above desired count during rollout |
| `maxUnavailable` | Pods that can be down during rollout |

**Pros:** No duplicate full environment; built into K8s. **Cons:** Mixed versions during rollout—API compatibility required; slow rollback if new image already propagated.

---

## 41.3 Recreate deployment

**Recreate** terminates all old instances before starting new ones—simple but causes downtime.

```yaml
strategy:
  type: Recreate
```

Use for: stateful batch jobs, maintenance windows, or when only one version can run (license constraints). Avoid for user-facing services with SLA requirements.

---

## 41.4 Blue/green deployment

**Blue/green** maintains two identical environments—**blue** (current production) and **green** (new version). After validating green, traffic switches atomically.

```
                    ┌─────────────┐
  Users ──────────► │ Load        │ ──► Blue  (v1)  ← current
                    │ Balancer    │
                    └─────────────┘ ──► Green (v2)  ← idle, then validated
                           │
                    switch target group / Ingress
```

AWS ALB example (conceptual):

1. Green ASG or target group runs v2 behind same ALB with zero weight.
2. Run smoke tests against green via internal DNS or test header.
3. Swap listener rules: green 100%, blue 0%.
4. Keep blue warm for quick rollback.

Kubernetes with two Deployments and Service selector swap—or use **Argo Rollouts** blue/green:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api-rollout
spec:
  replicas: 5
  strategy:
    blueGreen:
      activeService: api-active
      previewService: api-preview
      autoPromotionEnabled: false
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: registry.example.com/api:v2.3.0
```

**Pros:** Instant rollback (switch back to blue); clear validation window on preview URL. **Cons:** Double resource cost during transition; database schema migrations need careful handling (expand/contract pattern).

---

## 41.5 Canary deployment

**Canary** routes a small percentage of traffic to the new version, monitors metrics, then progressively increases traffic.

```
Traffic:  95% ──► stable (v1)
           5% ──► canary (v2)  →  50/50  →  100% v2
```

Istio VirtualService example:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api
spec:
  hosts:
    - api.example.com
  http:
    - route:
        - destination:
            host: api-stable
          weight: 95
        - destination:
            host: api-canary
          weight: 5
```

**Flagger** (Kubernetes) automates canary analysis using Prometheus metrics:

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: api
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  service:
    port: 8080
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99
        interval: 1m
      - name: request-duration
        thresholdRange:
          max: 500
        interval: 1m
```

Canary success criteria typically include: error rate, latency p99, business KPIs (conversion rate). Automated rollback triggers when thresholds breach.

**Pros:** Smallest blast radius; data-driven promotion. **Cons:** Requires observability, traffic management, and often service mesh or advanced ingress.

---

## 41.6 Feature flags (dark launches)

**Feature flags** decouple **deployment** (code in production) from **release** (feature visible to users). Code ships disabled; operators enable for internal testers, then percentage of users, then everyone.

```python
from flagsmith import Flagsmith

flagsmith = Flagsmith(environment_key=os.environ["FLAGSMITH_KEY"])

def checkout_handler(request):
    flags = flagsmith.get_identity_flags(str(request.user.id))
    if flags.is_feature_enabled("new_checkout_flow"):
        return new_checkout(request)
    return legacy_checkout(request)
```

Flag management platforms: **LaunchDarkly**, **Flagsmith**, **Unleash**, **Split.io**, or open-source **GO Feature Flag**.

| Flag type | Use case |
|-----------|----------|
| **Release** | Gradual rollout of new UI/API |
| **Ops/kill switch** | Disable expensive endpoint under load |
| **Experiment** | A/B test variants |
| **Permission** | Entitlements, beta access |

Best practices:

- Flags are **temporary**—remove after full rollout (flag debt causes untestable combinatorial states).
- Default to **off** in production; explicit enablement.
- Audit flag changes; tie to incident runbooks for kill switches.
- Test both flag states in CI where feasible.

Feature flags complement canary: canary validates infrastructure and baseline metrics; flags control user-visible behavior within the same binary.

---

## 41.7 Database migrations and deployment coupling

Schema changes break naive blue/green:

| Phase | Pattern |
|-------|---------|
| **Expand** | Add new column/table; old code ignores it |
| **Migrate data** | Backfill asynchronously |
| **Contract** | Remove old column after all code uses new |

Never deploy code that requires a schema change **before** the schema is backward-compatible. Tools: **Flyway**, **Liquibase**, **Alembic**—run migrations as pipeline stage with rollback plans.

---

## 41.8 Choosing a strategy

Decision tree:

1. **Zero downtime required?** → Eliminate recreate.
2. **Strong observability + traffic control?** → Canary.
3. **Need instant rollback without redeploy?** → Blue/green or feature flags.
4. **Simple stateless app, K8s?** → Rolling often sufficient.
5. **Hide incomplete features on main?** → Feature flags + trunk-based development.

Many organizations combine: **rolling** for frequent small patches, **canary** for high-risk services, **feature flags** for product experimentation.

---

## 41.9 Chapter summary

- Deployment strategy determines outage risk and rollback speed—not just pipeline success.
- Rolling and recreate suit simpler cases; blue/green enables instant traffic reversal.
- Canary reduces blast radius when metrics-driven automation validates new versions.
- Feature flags separate code deployment from feature release; manage flag lifecycle diligently.
- Coordinate database migrations with expand/contract to support parallel versions.

---

## 🧪 Lab 41.1 — Kubernetes rolling vs recreate

1. Deploy a sample app with 3 replicas and `RollingUpdate` (`maxUnavailable: 0`).
2. Update image tag; watch `kubectl rollout status` and observe zero downtime with readiness probes.
3. Change strategy to `Recreate`; repeat update and measure downtime with `curl` in a loop.

---

## 🧪 Lab 41.2 — Feature flag rollout

1. Deploy open-source Unleash or Flagsmith locally.
2. Wrap a sample endpoint with a feature flag defaulting to off.
3. Enable for 10% of user IDs; verify split behavior.
4. Document flag removal checklist for post-rollout cleanup.

---

## Review questions

1. Compare rolling and blue/green in terms of rollback speed and resource cost.
2. What metrics would you use to automate canary promotion?
3. Why must feature flags be removed after full rollout?
4. Explain the expand/contract pattern for database migrations.
5. When is recreate deployment acceptable?
6. How do feature flags differ from canary deployments?
7. What role does a service mesh play in canary releases?

---

*Continue: Chapter 42 — DORA Metrics and Continuous Improvement*
