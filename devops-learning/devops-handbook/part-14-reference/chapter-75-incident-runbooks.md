# Chapter 75: Incident Runbooks

*DevOps Handbook — Pages 427–434 of this PDF edition*

A runbook is a **decision procedure** you can follow at 03:00 with a noisy pager and a half-awake brain. This chapter defines severities, communication templates, and operational runbooks for CPU saturation, latency, Kubernetes control-plane/node issues, data loss, and security incidents.

If a step is missing evidence, skip to mitigation. Debugging without a rollback plan is how incidents become outages.

---

## 75.1 Severity definitions

| SEV | User impact | Example | Response |
|-----|-------------|---------|----------|
| **SEV-1** | Majority of customers cannot complete a core journey | Checkout 5xx > 20% globally | Immediate all-hands; IC + comms + scribe |
| **SEV-2** | Significant degradation or regional outage | One AZ or one product line down | Full IR; exec updates every 30 min |
| **SEV-3** | Limited customers or workaround exists | Single tenant, elevated latency | Business hours plus on-call |
| **SEV-4** | No customer impact; risk or tooling | Backup job failed, still recoverable | Ticket, next business day |
| **SEV-0** (optional) | Safety, legal, or active breach | Ransomware, data exfil | SEV-1 ops + security lead + legal |

Map SEV to **error budget and revenue**, not to how embarrassed engineering feels. A 10-minute global checkout outage is SEV-1 even if “only” 10 minutes.

Time targets (internal SLOs for the process itself):

| SEV | Detect → ack | First customer update | Mitigate target |
|-----|----------------|----------------------|-----------------|
| 1 | 5 min | 15 min | 30–60 min |
| 2 | 10 min | 30 min | 2 h |
| 3 | 30 min | if public, 2 h | 1 business day |

---

## 75.2 Roles

| Role | Does | Does not |
|------|------|----------|
| **Incident Commander (IC)** | Prioritizes, assigns, decides SEV, calls external comms | Deep-dive debugging |
| **Technical Lead (TL)** | Directs diagnosis and mitigation | Argue with IC about comms |
| **Scribe** | Timeline in the incident doc | Silent lurk |
| **Comms** | Status page, support macros, exec ping | Speculate on root cause |
| **SME** | Subject expert (DB, K8s, IAM) | Freelance changes without TL |

Rotate IC. The first pager can be IC until a handoff: “You have IC; I am TL on the database.”

---

## 75.3 Communication templates

### Incident channel topic

```
SEV-2 | checkout latency | IC=@sam | TL=@riya | started 2026-09-02 16:41Z | status: mitigating
```

### First internal update (paste every 15–30 min)

```
Time (UTC):
SEV:
Customer impact: (what % / which region / which API)
What we know:
What we are doing:
ETA of next update:
Need: (people, access, vendor ticket)
```

### Status page (public)

Do not name unconfirmed vendors. Do not say “human error.”

```
We are investigating elevated errors on checkout.
Customers may see timeouts or failed payments.
A fix is in progress. Next update in 30 minutes.
```

Resolved:

```
Checkout is operating normally as of 17:12 UTC.
Some customers may have seen failed payments between 16:41 and 17:05 UTC.
Retrying the payment will not double-charge (idempotency keys).
A follow-up postmortem will be published internally within 5 business days.
```

### Exec SMS (SEV-1/2)

```
SEV-1 ShopStream checkout. Impact: ~40% payments failing globally since 16:41Z.
Mitigation: rollback of checkout:sha-9f3c in progress. Next ping 17:10Z. IC Sam.
```

---

## 75.4 Universal first five minutes

1. **Ack the page** so it does not escalate twice.
2. **Open the incident doc** from the template; start the timer.
3. **Look at the golden signals** (traffic, errors, latency, saturation) for the *customer-facing* SLI, not CPU of a random node.
4. **Check what changed** (deploy, feature flag, cert, IAM, Terraform apply, traffic spike).
5. **Pick a mitigation** if a recent change is correlated: rollback, disable flag, fail over, shed load.

```bash
# Change windows
# GitHub: last deploys
# Argo: app history
kubectl -n shop rollout history deploy/checkout
```

Preserve evidence: do not `kubectl delete` the crashing pod until you have `logs --previous` and a describe, unless that pod is actively harming the node.

---

## 75.5 Runbook: CPU saturation (hosts or pods)

### Symptoms

- p99 latency up, errors maybe still low
- HPA flapping or already at maxReplicas
- Node CPU 90%+, throttling (`container_cpu_cfs_throttled_seconds`)
- Load average >> CPU count

### Diagnose

```bash
# Cluster
kubectl top nodes
kubectl top pods -n shop --sort-by=cpu
kubectl get hpa -A

# Node (via ssh or debug)
mpstat -P ALL 1
pidstat -u 1
```

Prometheus:

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="shop"}[5m])) by (pod)
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="checkout"}[5m])) by (le))
```

### Mitigate (in order)

1. **Scale horizontally** if the app is stateless and downstream can take it: `kubectl scale deploy/checkout --replicas=20` or raise HPA max.
2. **Shed load**: enable the “read-only catalog” flag; return 503 on non-checkout.
3. **Kill a runaway**: a debug pod, a CronJob `parallelism` accident, a fork bomb sidecar.
4. **Throttle neighbors**: nice/ionice is host-level; on K8s, evict BestEffort pods.
5. If **throttling** (limits too low): raise CPU limits *or* requests after checking quota; a 50m limit on a JVM is a self-DoS.

### Do not

- Reboot nodes as a first step (eviction storm).
- Set limits to thousands of millicores “to make graphs look green” without capacity.

### Exit criteria

CPU < 70% sustained, p99 back within SLO, HPA not at cap, and a note on whether this was organic traffic or a bug (busy loop, regex, N+1).

---

## 75.6 Runbook: Latency (p99 / timeouts)

### Symptoms

- Errors may be 504/499, not 500
- Apdex drop; customer “slow”
- DB `await` or lock graphs

### Split the path

| Hop | Check |
|-----|--------|
| DNS / CDN | `dig`, CloudFront 5xx vs origin |
| Ingress | nginx `request_time` vs `upstream_response_time` |
| App | span traces (OpenTelemetry) |
| DB | `pg_stat_activity`, locks |
| Deps | payment vendor, cache miss storm |

```bash
curl -w 'dns=%{time_namelookup} tcp=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}\n' -o /dev/null -s https://checkout.example.com/healthz
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=50
```

Jaeger/Tempo: find a slow trace ID from the 504 log line.

### Mitigate

1. Rollback if deploy ~ latency.
2. Increase timeouts **only** if the user-visible SLO allows; usually timeouts hide the fire.
3. Disable an expensive feature flag (recommendations, extra fraud calls).
4. Fail open vs fail closed: payments usually fail closed; catalog can fail open with stale cache.
5. Scale the bottleneck (RDS IOPS, Redis, not the innocent frontend).

### Connection pools

A classic: app replicas × `max_connections` per pod > Postgres `max_connections`. Latency looks like saturation; errors are `too many connections`. Mitigate: lower pool size, PgBouncer, scale down replicas.

---

## 75.7 Runbook: Kubernetes (pending pods, NotReady nodes, failed deploys)

### Pending pods

```bash
kubectl describe pod -n shop PEND | tail -40
kubectl get nodes -o wide
kubectl get pvc -n shop
kubectl get events -n shop --sort-by=.lastTimestamp | tail
```

| Event | Action |
|-------|--------|
| Insufficient cpu | scale nodes / reduce requests / kill waste |
| PVC pending | StorageClass, zone mismatch |
| Did not tolerate taint | fix tolerations or untaint mistake |
| Unschedulable after PDB | not pending—drain blocked |

### Node NotReady

```bash
kubectl describe node IP
# kubelet down? disk pressure? CNI?
```

Cordon implicitly via NotReady. If the node is a VM, check cloud console: underlying host, disk full (`DiskPressure`), PID pressure.

Mitigate: `kubectl drain` is wrong if already NotReady; the controller should evict. If stuck, delete the Node object only if the instance is terminated (or you will have a split brain). Prefer terminating the instance via the ASG/Karpenter.

### Failed rollout

```bash
kubectl rollout status deploy/checkout -n shop
kubectl get rs -n shop
kubectl logs -n shop deploy/checkout --previous
kubectl rollout undo deploy/checkout -n shop
```

If Argo CD, revert the Git commit or `argocd app rollback`.

### API server slow

- etcd disk
- too many watches
- admission webhooks timing out (a broken webhook = cluster looks “down”)

Mitigate: disable a failing mutating webhook (`failurePolicy: Ignore` is not always enough if timeout is long), scale API servers, stop `kubectl get pods -A` loops.

### CoreDNS down

Pods cannot resolve `kubernetes.default`. Recreate CoreDNS, check NetworkPolicy, check `forward` to VPC DNS.

---

## 75.8 Runbook: Data loss / corruption / ransomware-like deletion

Treat as **SEV-1** until proven that backups restore and blast radius is small.

### Immediate containment

1. **Stop writers** that might overwrite remaining copies: scale deploy to 0, disable CronJobs, block IAM `s3:DeleteObject` if S3 is being wiped.
2. **Snapshot now**: RDS snapshot, EBS snapshot, volume snapshot, `pg_dump` if the DB still reads.
3. **Do not run fsck / repair tools** until you have a copy.
4. **Preserve logs**: CloudTrail, kube audit, database WAL.

### Classify

| Class | Example | Path |
|-------|---------|------|
| Logical delete | `DELETE FROM orders` | PITR / undo table |
| Ransomware | encrypted files | isolate, restore from offline |
| Silent corruption | bad deploy wrote nulls | restore + reconstruct |
| Replica lag / failover to empty | promoted empty replica | demote, restore |

### Postgres PITR sketch

```bash
# Stop app
kubectl -n shop scale deploy/checkout --replicas=0
# Restore to new instance in AWS console or:
# aws rds restore-db-instance-to-point-in-time ...
# Cut DNS / config to new endpoint after verify
```

Verify with row counts, checksums, and a business query (`sum(amount) for today`).

### S3 versioning

If versioning was on, recover deleted versions. If not, this is a postmortem action item written in blood.

### Communication

Legal/privacy if personal data is gone. Do not promise “all data restored” until verification queries pass.

---

## 75.9 Runbook: Security incident (credential leak, intrusion, malware)

**Parallel tracks:** contain, investigate, communicate. Security lead is IC for SEV-0/1 security; ops IC if the containment is “take the site down.”

### Credential in GitHub

1. **Revoke** the key/token/IAM access key in the cloud console. This is minute 0.
2. Invalidate sessions (IAM, GitHub PATs, package registry).
3. CloudTrail / audit: was it used? From where?
4. Rotate everything in the blast radius (RDS passwords the key could read).
5. Remove from Git history *after* revoke; force-push is a product decision.
6. Enable org secret scanning; notify.

### Suspicious pod / crypto miner

```bash
kubectl get pods -A -o wide
kubectl describe pod
kubectl logs
# Isolate
kubectl label ns shop pod-security.kubernetes.io/enforce=restricted
# Delete workload, rotate any mounted secrets
```

Cordon the node if you suspect escape. Snapshot the disk for forensics before terminate if legal requires it.

### RCE in app

WAF rule, disable the feature, patch, rotate session keys, assume data access. Hunt logs for the exploit string.

### Phishing of an engineer with prod AWS

Disable user, invalidate console sessions, review CloudTrail for that principal, rotate access keys they owned.

### Comms / legal

Use the security template; do not post IOCs on the public status page. Notify if contracts/GDPR require it—legal decides, engineering supplies facts.

---

## 75.10 Decision tree: rollback vs patch-forward

```
Is there a deploy or flag in the last 2h correlated with impact?
  yes → rollback / flag off (default)
  no  → is a vendor dead?
          yes → failover or degrade
          no  → capacity?
                  yes → scale / shed
                  no  → live debug with time-boxed 15 min, then escalate
```

Time-box live debug. Infinite curiosity is how SEV-2 becomes SEV-1.

---

## 75.11 Handoff and recovery

When the customer SLI is healthy for the agreed soak (e.g. 30 min):

1. SEV downgrade.
2. Leave monitoring watch.
3. Schedule postmortem within 48h (SEV-1/2).
4. Capture action items with owners and dates.
5. Page the next on-call with a written handoff, not folklore.

Postmortem template headers: summary, impact, timeline, root causes (5 whys), what went well, action items, open questions.

---

## 75.12 Runbook ownership

Each production service lists in its README:

```
On-call: #oncall-shop
Dashboards: ...
SLO: 99.9% availability, p99 < 500ms checkout
Dependencies: RDS checkout, catalog HTTP, payments vendor
Rollback: argo app rollback shop-checkout
```

Review runbooks in game days. A runbook that has never been executed is fiction.

---

## 75.13 Quick command appendix

```bash
# Time + identity
date -u; kubectl config current-context

# Impact
kubectl -n shop get deploy,pods,hpa,pdb

# Logs
kubectl -n shop logs deploy/checkout --tail=100 --since=15m

# Rollback
kubectl -n shop rollout undo deploy/checkout

# Isolate traffic (example: bad canary)
kubectl -n shop scale rs/checkout-bad --replicas=0
```

Print SEV table and templates on the on-call wiki home. When the pager fires, you should not hunt for this chapter—you should already have the first paste template in the incident bot.

---

## 75.14 Runbook: certificate and TLS expiry

**Symptoms.** Browser warnings, mobile-only failures, 502 from load balancers that require valid origin certs, `certificate has expired` in app logs.

**Detect.** External synthetic on port 443 of the **customer hostname**; Prometheus `probe_ssl_earliest_cert_expiry`; cert-manager `Certificate` conditions.

**Mitigate.**

1. Confirm which cert (`openssl s_client -servername`).
2. If cert-manager: fix DNS01 IAM, `cmctl refresh`.
3. If ACM: re-validate DNS, attach to ALB/CloudFront.
4. Temporary: CloudFront or ALB with a valid cert while origin is fixed.
5. Never “just disable TLS” on the public edge.

**Exit.** Synthetics green from two regions; expiry > 14 days; ticket for why alerting was silent.

---

## 75.15 Runbook: CI/CD blocked or poisoned

**Symptoms.** Cannot deploy a fix; or a deploy is running untrusted code.

**Mitigate.**

1. If poison: **stop** workflows (`gh run cancel`), revoke OIDC roles, freeze Git `main`.
2. If blocked CI: break-glass deploy from a signed digest that already exists in the registry (documented command), not from a laptop `docker build`.
3. Page platform, not every app owner.

Document the break-glass kubeconfig: hardware key, 30-minute binding, audit reason.

---

## 75.16 After-hours staffing model

| SEV | Night |
|-----|--------|
| 1 | Full IC + TL; secondary auto-page 10 min |
| 2 | Primary + optional SME |
| 3 | Ticket; no page unless SLO burn |

If everything is SEV-1, nothing is. Recalibrate monthly from pages-per-week.

---

## 75.17 Evidence pack (what to attach to the ticket)

- UTC timestamps of start/mitigate/resolve
- Deploy SHAs and GitOps commit
- Graphs: SLI, saturation, downstream
- `kubectl describe` / Terraform plan id
- Customer comms copies

Do this before people log off. Memory is a terrible database.
