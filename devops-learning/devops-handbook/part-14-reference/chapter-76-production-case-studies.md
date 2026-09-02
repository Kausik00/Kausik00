# Chapter 76: Production Case Studies

*DevOps Handbook — Pages 435–440 of this PDF edition*

The following six case studies are **fictional** companies and timelines. They are realistic in the sense that every failure mode has happened, in some combination, at real organizations. Names, metrics, and vendors are invented for teaching. Read them as after-action reports: architecture, timeline, impact, root causes, and lasting changes.

Use each study as a tabletop: pause at “T+12 min” and write what *you* would do before reading the resolution.

---

## 76.1 Case study 1 — Northwind Payments: the canary that lied

**Context.** Northwind Payments processes card authorizations for mid-market e-commerce. Architecture: EKS, three replicas of `authz` behind NGINX ingress, RDS PostgreSQL Multi-AZ, Redis for idempotency keys. SLO: 99.95% success on `POST /v1/authorize` (excluding 4xx).

**Change.** A “harmless” upgrade of the HTTP client library to fix a CVE. CI built a new image, staging tests passed (2000 synthetic TPS, no payload diversity). Canary: Flagger, 10% of traffic, success rate on HTTP 200.

**Timeline (UTC).**

| Time | Event |
|------|--------|
| 14:02 | Canary starts. HTTP 200 ratio identical to baseline. |
| 14:11 | Support tickets: “charged twice.” |
| 14:18 | SEV-2 declared. IC notices p99 latency unchanged, error rate unchanged. |
| 14:25 | Traces show two upstream POSTs to the card network for some keys. |
| 14:31 | Rollback. Double-charges stop. Finance starts reconciliation. |

**What the canary missed.** The new client retried `POST` on TCP reset without the app-level idempotency header on the retry path. The card network saw two unique requests. The API still returned 200. **SLI was wrong for the business.**

**Architecture lesson.** Idempotency keys must be generated once per user intent and sent on every attempt, including client-library retries. Canary metrics must include **business counters** (duplicate `network_ref`, `authorize_once_total`). Staging load tests must inject resets.

**Fixes.** Retry budget in the mesh disabled for POST; library configured `retry: 0` for non-idempotent methods; Flagger metric `increase(duplicate_authz_total[2m])`; finance replay tool; chaos test: kill connections during authorize.

**Discussion questions.** What is your canary’s definition of success? Which mutations are invisible to HTTP codes?

---

## 76.2 Case study 2 — Harbor Health: DNS ndots and the 30% CPU tax

**Context.** Harbor Health runs 120 microservices on GKE. After a cost review, a platform engineer noticed kube-dns (CoreDNS) at 8 cores in a “small” cluster. App p99 had mysterious 15–40 ms spikes on internal calls.

**Investigation.** `tcpdump` on a node showed five extra DNS queries per application lookup because every pod had `ndots:5` and `search` of `namespace.svc.cluster.local svc.cluster.local cluster.local`. Short names like `redis` exploded into multiple queries. External names (`s3.amazonaws.com`) also searched internally first.

**Contributing design.** A “helpful” Helm chart set `dnsConfig` incorrectly on 40 services. NodeLocal DNSCache was not installed. NetworkPolicy allowed DNS but conntrack table was large.

**Impact.** Not a SEV-1, but **$14k/month** extra DNS capacity and tail latency on every call. During a CoreDNS deploy, the extra QPS tipped timeouts → cascading retries → SEV-2 for 11 minutes.

**Fixes.** `ndots: 2` where FQDNs are used; services talk to FQDNs (`redis.shop.svc.cluster.local.`); NodeLocal DNSCache; CoreDNS autoscaling on QPS; load test DNS at 2×.

**Lesson.** Platforms fail at the boring layer. Treat DNS as a production dependency with SLIs (latency, error, cache hit). Document `dnsConfig` in the golden Deployment.

---

## 76.3 Case study 3 — Atlas Freight: Terraform state split-brain

**Context.** Atlas Freight infra team, six engineers, one AWS org. State in S3, locking in DynamoDB—except the new GitHub Actions workflow used a **different state key** (`atlas/prod/eks` vs `prod/eks`) after a “cleanup” PR that renamed folders.

**What happened.** Two pipelines: the old Jenkins job and the new GHA workflow, both green, both applying. Jenkins still had the old key. Over a Friday afternoon, Jenkins `apply` removed a “duplicate” NAT gateway that GHA had just created in a second VPC module instance. Routes black-holed private subnets in AZ `c`.

**Impact.** SEV-1 for 47 minutes: all pods in AZ c could not pull images or reach RDS (RDS was fine; route to NAT and some VPC endpoints were not). The API error was `i/o timeout` talking to ECR.

**Detection.** Slow: HPA scaled up, new pods `ImagePullBackOff`. Existing pods kept running (no egress needed until refresh). A deploy during the window amplified blast radius.

**Root causes.** Two sources of truth; no `plan` reviewed for destroy of NAT; CI did not fail on unexpected destroys (`-detailed-exitcode` ignored); no ownership of the live directory.

**Fixes.** Single pipeline; S3 bucket policy denying the old key; `terraform plan` annotated in PR with **destroy** highlighting; `lifecycle { prevent_destroy }` on NAT/VPC; drift detector nightly; kill Jenkins.

**Lesson.** State is production data. Renaming folders is a migration with `terraform state mv` or `moved` blocks, not a cosmetic Git move.

---

## 76.4 Case study 4 — Lumen Media: the “unlimited” HPA and the database

**Context.** Lumen’s video metadata API ran on Kubernetes with HPA on CPU 50%, maxReplicas 80. RDS `db.r5.large`, `max_connections=200`. Each pod: connection pool 10.

**Trigger.** A crawler from a partner ignored `robots` and hit `/search?q=` with unique queries (cache miss). CPU per pod rose; HPA added pods: 20 → 45 → 80 in eight minutes.

**Failure math.** 80 × 10 = 800 attempted connections. Postgres refused new ones. Pods blocked in pool wait; CPU dropped; HPA wanted even more pods but was at max. Liveness probes hit the DB, failed, restart storm.

**SEV.** SEV-1, 22 minutes of 5xx. CDN cached some GET but search was uncacheable.

**Mitigation.** `kubectl scale deploy --replicas=8`; block partner /24 at WAF; raise RDS connections *temporarily* was considered and **rejected** (would only invite more pods). Disabled liveness-on-DB.

**Lasting architecture.** Pool size 3; PgBouncer; HPA max 20 until RDS sized; cache key for search; rate limit per API key; probes on `/healthz` local only; load-shed middleware at 80% pool wait.

**Lesson.** **Autoscaling the front of a hard-backed resource is a self-DoS.** Capacity plans must multiply `replicas × pool × databases`.

---

## 76.5 Case study 5 — CivicPass: certificate expiry and split-brain TLS

**Context.** CivicPass issues QR tickets. TLS: cert-manager + Let’s Encrypt DNS-01. A ClusterIssuer DNS challenge used a route53 role. Someone tightened IRSA on `cert-manager` and removed `route53:ChangeResourceRecordSet` for the challenge subdomain.

**Silent failure.** Certificates stopped renewing 30 days out. Prometheus `ssl_export` job was pointed at the *ingress controller HTTP* port, not 443, and stayed green. Human calendar reminder was in a departing engineer’s inbox.

**T+0.** First cert expired at 00:07 UTC Sunday. Android app pinned? No—but Safari failed. Half of users on iOS. Android OkHttp still worked against a second host with a different cert (marketing site). Support chaos.

**Mitigation.** Break-glass: restore IAM, `kubectl cert-manager refresh`, or upload a purchased cert. They bought 2 hours with CloudFront a custom cert while fixing cert-manager.

**Impact.** SEV-1, 73 minutes for iOS users; error budget for the month gone.

**Fixes.** Alert `certmanager_certificate_expiration_timestamp_seconds` < 14 days; synthetic TLS probe from outside; IAM tests in CI for the cert-manager role (policy simulator); two people own the runbook; staging uses the same issuer code path.

**Lesson.** **Expiry is the most boring SEV-1.** If your probe does not speak TLS to the customer hostname, you are not monitoring TLS.

---

## 76.6 Case study 6 — StackForge: the security “read-only” CI role that could

**Context.** StackForge, a SaaS for IaC, let customers attach cloud roles. Internally, GitHub Actions for the **docs** repo had `id-token: write` and an IAM role intended as `s3:GetObject` on the docs bucket. Trust policy `sub` was `repo:stackforge/*:*` (every repo, every ref).

**Incident.** A fork PR to a public **examples** repo ran Actions with secrets? Forks do not get secrets—*unless* the workflow is from `pull_request_target`. A stale workflow used `pull_request_target` to comment lints. Attacker PR ran in the context of the base repo, assumed the IAM role because `sub` matched `repo:stackforge/examples:ref:refs/pull/999/merge`… actually the `sub` for `pull_request_target` is the **base** ref. The role assumption succeeded. The attached policy had been copied from a template that included `iam:PassRole` and `lambda:UpdateFunctionCode` from an old experiment.

**Impact.** Attacker pushed a Lambda backdoor in a nonprod account, then pivoted via a forgotten peering. Detected by GuardDuty 4 hours later. No evidence of production data exfil, but **all CI OIDC roles** were rotated; customers notified of a potential supply-chain event.

**Fixes.** `sub` conditions: exact repo + `ref:refs/heads/main` + `environment: prod` for privileged roles; ban `pull_request_target`; OPA on IAM policies in Terraform; break-glass Lambda deploys only from signed artifacts; GuardDuty → page (it had been SEV-4).

**Lesson.** **OIDC is not safe by default.** The JWT is only as tight as your `StringEquals` conditions and the workflow trigger you chose.

---

## 76.7 Cross-cutting patterns

| Pattern | Seen in |
|---------|---------|
| Wrong SLI | Payments canary, CivicPass TLS probe |
| Multiplicative load | Lumen HPA × pool |
| Two control planes | Atlas Terraform, StackForge IAM templates |
| Boring dependencies | Harbor DNS, CivicPass certs |
| Retry amplification | Northwind, Lumen |

When you design a system, ask: **What graph would have lied?** Then add the graph that would have told the truth.

---

## 76.8 Tabletop facilitation guide

For each study, run 45 minutes:

1. 5 min: read architecture only.
2. 10 min: IC/TL roles, first actions.
3. Reveal timeline in chunks.
4. 10 min: customer comms draft.
5. 10 min: action items ranked by **prevent recurrence**.

Score teams not on speed of root cause but on **mitigation first** and **honest comms**.

---

## 76.9 Mapping studies to handbook parts

| Study | Handbook parts |
|-------|----------------|
| Northwind | CI/CD, tracing, SRE SLIs |
| Harbor | Linux/net, Kubernetes DNS |
| Atlas | Terraform state, CI |
| Lumen | HPA, RDS, probes |
| CivicPass | cert-manager, monitoring |
| StackForge | OIDC, supply chain, IAM |

---

## 76.10 What “good” looks like after these incidents

A mature platform would have: business-level canaries, DNS SLIs, one Terraform pipeline per state, HPA caps tied to datastore math, TLS synthetics from the internet, and OIDC trust that names a single repo and branch. None of that requires a new vendor. It requires **treating platforms as products with tests**.

Write your own seventh study from a real incident (sanitize). The writing is the learning: if you cannot explain the failure in two pages with a timeline, you do not yet understand it.

---

## 76.11 Deep dive — Northwind metrics that would have worked

A correct canary for payments is not `rate(http_requests_total{status="200"})`. Use:

- `increase(authorize_attempts_total[2m])` vs `increase(card_network_calls_total[2m])` — ratio should be ~1.
- Distinct `idempotency_key` cardinality vs successful auths.
- A **synthetic** that retries on reset and asserts a single `network_ref`.

Staging failed because it did not inject TCP resets. Add toxiproxy or a mesh fault `abort: 10%` on the egress to the card simulator. If the library retries POSTs, you will see duplicates *before* production.

Customer comms should say “some customers may have been charged twice; we are reversing duplicates” — not “elevated latency.” Honesty is part of the architecture: finance needs the same counters SRE uses.

---

## 76.12 Deep dive — Atlas Freight state migration playbook

The safe rename of a Terraform directory:

1. Copy configuration to the new path **without** deleting the old.
2. `terraform state pull` from old backend key; `state push` to new key **or** `terraform init -migrate-state`.
3. `plan` on the new key must be **empty**.
4. Disable the old pipeline with a failing `exit 1` job named `DO_NOT_APPLY`.
5. Only then delete the old files.

If two keys already diverged, **stop applying**. Diff the two state files (`terraform show -json`), pick a source of truth, import/remove until one plan is empty. Dual apply is data corruption.

---

## 76.13 Deep dive — Lumen connection budget worksheet

Before enabling HPA, fill:

| Item | Value |
|------|-------|
| Postgres `max_connections` | 200 |
| Reserved for superuser/admin | 20 |
| PgBouncer `max_client_conn` | 500 |
| PgBouncer pool_size to DB | 40 |
| App pool per pod | 5 |
| HPA max replicas | floor(40 / 5) = 8 if connecting **straight** to PG; with bouncer, clients can be higher |

Write the worksheet in the service README. Review it when someone “just raises maxReplicas for Black Friday.”

---

## 76.14 Executive summary template (use after any of these)

```
Incident:
Customer impact (duration, %):
Mitigation:
Trigger:
Underlying causes:
What we will change (3 items, owners, dates):
What we will not change (and why):
```

The last line fights action-item inflation. Not every incident requires a new vendor. Most require a graph, a cap, or a tighter IAM condition.

---

## 76.15 CivicPass and StackForge — extra lessons for platform teams

CivicPass is a monitoring design failure more than a cert-manager failure. The organization had three “green” dashboards: ingress controller CPU, HTTP 200 from an internal probe on port 80, and a calendar reminder owned by one person. None of those equal “the certificate the client validates.” A good TLS SLI is: *from the public internet, SNI hostname X, chain valid, notAfter > 14 days, HTTP 200 on /healthz*. Anything less is a proxy for a proxy.

StackForge is an identity design failure. OIDC did not “go rogue”; humans wrote `repo:stackforge/*:*` because it unblocked a demo. Six months later a public examples repo inherited the same org-level role. Platform teams should inventory **every** federated trust with a weekly Athena/CloudTrail query on `AssumeRoleWithWebIdentity` and alert on `sub` values that are not on an allowlist. If that sounds heavy, it is still cheaper than customer notification.

Together with Harbor (DNS) these studies argue for a **dependency SLO program**: DNS, TLS, identity, and Terraform locking get the same seriousness as the checkout API. They are not “platform chores”; they are user-facing failure modes with extra indirection.

---

## 76.16 Facilitator debrief questions

1. What graph would have lied in *your* last incident?
2. Where is our second control plane (old Jenkins, extra IAM role, extra DNS zone)?
3. What multiplicative load (replicas × pools × retries) is undocumented?
4. Which probe does not speak the customer protocol?
5. Which JWT `sub` is a wildcard because it was easier?

If the room cannot answer (5) from a screenshot of the IAM console in five minutes, you have a StackForge waiting to happen.
