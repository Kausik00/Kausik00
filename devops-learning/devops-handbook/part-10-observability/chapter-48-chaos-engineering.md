# Chapter 48: Chaos Engineering and Game Days

*DevOps Handbook — Pages 231–235 of this PDF edition*
---

## 48.1 Proactive resilience testing

Production fails in unexpected ways—despite staging environments, tests, and code review. **Chaos engineering** deliberately injects failures into systems to validate resilience **before** real outages expose gaps.

> "Chaos engineering is the discipline of experimenting on a system in order to build confidence in the system's capability to withstand turbulent conditions in production." — Principles of Chaos Engineering

Not reckless destruction: chaos experiments are **hypothesis-driven**, **controlled**, **measured**, and **bounded** in blast radius.

Relationship to other practices:

| Practice | Focus |
|----------|-------|
| **Testing** | Known expected behavior |
| **Chaos engineering** | Unknown failure modes, emergent behavior |
| **Game days** | Scheduled team exercises simulating incidents |
| **DR drills** | Region/account failover |

Netflix **Chaos Monkey** (2011) randomly terminated production instances—proving redundancy worked. The practice evolved into comprehensive fault injection platforms.

---

## 48.2 Principles of chaos engineering

1. **Build a hypothesis around steady state** — Define normal (SLO metrics, error rate, latency).
2. **Vary real-world events** — Server failure, network partition, dependency timeout, disk full.
3. **Run experiments in production** — Staging lacks scale and traffic patterns (start in non-prod, graduate to prod with safeguards).
4. **Automate experiments** — Manual one-offs do not scale; continuous verification.
5. **Minimize blast radius** — Start small (one pod, one AZ, 1% traffic).

Experiment workflow:

```
Steady state metrics → Inject fault → Observe deviation → Rollback → Document findings
         ↑                                                      │
         └────────────── Fix weakness, add runbook ─────────────┘
```

---

## 48.3 Failure modes to inject

| Category | Examples |
|----------|----------|
| **Infrastructure** | Kill pod/VM, drain node, AZ failure |
| **Network** | Latency, packet loss, DNS failure, partition |
| **Dependency** | Upstream 503, slow responses, certificate expiry |
| **Resource** | CPU/memory pressure, disk fill, connection pool exhaustion |
| **Application** | Exception injection, feature flag misconfiguration |
| **Data** | Replica lag, split-brain simulation |
| **Human** | On-call unreachable (game day scenario) |

Prioritize failures matching **real incident history**—postmortem action items often become chaos experiments.

---

## 48.4 Chaos tools landscape

| Tool | Environment | Capabilities |
|------|-------------|--------------|
| **Litmus Chaos** | Kubernetes | CRD-based experiments, hub of scenarios |
| **Chaos Mesh** | Kubernetes | Pod kill, network chaos, IO chaos, stress |
| **Gremlin** | K8s, VM, bare metal | SaaS/enterprise fault injection |
| **AWS FIS** | AWS | EC2 stop, AZ impairment, RDS failover |
| **Azure Chaos Studio** | Azure | Managed chaos experiments |
| **Toxiproxy** | Dev/test | Network condition proxy |
| **Pumba** | Docker | Container chaos |

Litmus experiment example:

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: api-pod-delete
  namespace: production
spec:
  appinfo:
    appns: production
    applabel: "app=api"
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: CHAOS_INTERVAL
              value: "10"
            - name: FORCE
              value: "false"
```

Chaos Mesh NetworkChaos (latency):

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: delay-inventory
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      app: order-api
  delay:
    latency: "500ms"
    correlation: "100"
    jitter: "50ms"
  direction: to
  target:
    selector:
      namespaces:
        - production
      labelSelectors:
        app: inventory-service
```

---

## 48.5 Safe experimentation guardrails

Before running in production:

| Guardrail | Purpose |
|-----------|---------|
| **Abort conditions** | Auto-stop if error rate > threshold |
| **Business hours vs off-peak** | Limit user impact window |
| **One variable at a time** | Isolate cause and effect |
| **Rollback plan** | Immediate experiment halt mechanism |
| **Stakeholder notification** | Support, leadership aware |
| **Exclude critical paths initially** | Payment during peak—defer |
| **Observability first** | Cannot validate hypothesis without metrics |

Integrate with **OpenTelemetry/Prometheus** dashboards dedicated to experiment runs.

**Steady state hypothesis** example:

> "When one API pod is terminated, p99 latency remains < 500ms and error rate < 0.1% because Kubernetes reschedules within 30s and HPA maintains capacity."

If hypothesis fails: fix ( PDB, probes, HPA tuning), do not dismiss the experiment.

---

## 48.6 Game days

**Game days** are scheduled, cross-functional exercises—often simulating major incidents without continuous automated chaos.

Structure (4-hour example):

| Time | Activity |
|------|----------|
| 0:00 | Briefing, roles assigned, rules of engagement |
| 0:15 | Inject scenario (facilitator triggers faults) |
| 0:15–2:00 | Team responds as real incident |
| 2:00 | End injection, debrief hot wash |
| 2:30 | Document gaps, update runbooks |

Scenarios:

- Primary database failover
- Region loss (traffic shift drill)
- Certificate expiry on ingress
- DDoS simulation (with provider coordination)
- Supply chain compromise response

Facilitator **does not** fix—observes communication, decision quality, tooling gaps.

Include: engineering, SRE, support, comms, product—for SEV-1 realism.

Frequency: quarterly per critical service; annual org-wide DR game day.

---

## 48.7 From experiment to improvement

Chaos findings feed backlog:

| Finding | Remediation |
|---------|-------------|
| No PDB on critical Deployment | Add PodDisruptionBudget |
| HPA too slow | Tune metrics, reduce cooldown |
| Retry storm on dependency failure | Circuit breaker + bulkhead |
| Alert did not fire | Fix SLO burn alert |
| Runbook outdated | Update with verified steps |

Track **resilience score**: % of critical services with passing monthly chaos experiments.

Automate regression: experiment suite runs in staging on every release candidate.

---

## 48.8 Organizational maturity

| Maturity | Behavior |
|----------|----------|
| **Level 0** | No chaos; surprises in prod |
| **Level 1** | Ad-hoc manual tests in staging |
| **Level 2** | Scheduled game days, documented scenarios |
| **Level 3** | Automated chaos in staging CI |
| **Level 4** | Continuous limited chaos in production with guardrails |
| **Level 5** | Chaos-driven architecture; resilience SLOs |

Start at Level 1–2; production chaos requires strong observability and org trust.

---

## 48.9 Chapter summary

- Chaos engineering validates resilience through controlled, hypothesis-driven failure injection.
- Tools like Litmus and Chaos Mesh inject infrastructure and network faults in Kubernetes.
- Guardrails (abort conditions, blast radius limits) make production experiments safe.
- Game days train teams on incident response; findings improve architecture, alerts, and runbooks.

---

## 🧪 Lab 48.1 — Pod delete experiment

1. Deploy sample app with 3 replicas, PDB, and HPA in test cluster.
2. Run Litmus or kubectl delete pod experiment during load test.
3. Measure recovery time and error rate; document hypothesis pass/fail.

---

## 🧪 Lab 48.2 — Mini game day

1. Design a 1-hour scenario: dependency returns 503 for 10 minutes.
2. Facilitate team response with IC and scribe roles.
3. Debrief: what broke, what worked, 3 action items.

---

## Review questions

1. State the five principles of chaos engineering.
2. Why run experiments in production rather than only in staging?
3. What abort conditions would you set for a pod-delete experiment?
4. Compare chaos engineering and game days.
5. Name three failure modes worth injecting for a microservices API.
6. How should a failed chaos hypothesis be handled?
7. What organizational prerequisites are needed before production chaos?

---

*Continue: Chapter 49 — Shift-Left Security*
