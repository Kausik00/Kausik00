# Chapter 42: DORA Metrics and Continuous Improvement

*DevOps Handbook — Part IX, Pages 826–840*

---

## 42.1 What DORA measures

The **DevOps Research and Assessment (DORA)** program, led by Nicole Forsgren, Jez Humble, and Gene Kim, identified four metrics that distinguish high-performing software delivery organizations from low performers. Published in *Accelerate* (2018) and updated in annual **State of DevOps** reports, these metrics provide a **evidence-based** framework—not vanity metrics like lines of code or story points.

The four **DORA metrics**:

| Metric | Definition | Elite benchmark (indicative) |
|--------|------------|------------------------------|
| **Deployment frequency** | How often code deploys to production | Multiple per day |
| **Lead time for changes** | Commit to production duration | Less than one hour |
| **Change failure rate** | % of changes causing failure in prod | 0–15% |
| **Time to restore service (MTTR)** | Recovery time after incident | Less than one hour |

A fifth metric—**reliability** (availability, latency SLOs)—was added in later research as a companion to delivery speed: speed without stability is unsustainable.

---

## 42.2 Why these four metrics matter

Traditional KPIs often optimize local maxima: development velocity without operational stability, or uptime achieved by never deploying. DORA metrics capture **both** speed and stability—the CALMS balance from Part I.

High performers demonstrate:

- Small, frequent changes (lower risk per change)
- Fast feedback when something breaks
- Culture of learning, not blame

Low performers often show:

- Infrequent, large releases ("release trains" without automation)
- Long manual testing phases
- Heroics during outages instead of systematic recovery

**Important:** Metrics drive behavior. Gaming DORA (deploying trivial config changes to inflate frequency) destroys trust. Use metrics for **improvement**, not individual performance review.

---

## 42.3 Measuring deployment frequency

**Deployment frequency** counts production deployments over time—typically per day or per week per service or team.

What counts as a deployment:

| Counts | Does not count |
|--------|----------------|
| New app version to prod | Deploy to staging only |
| Config/IaC change affecting prod | Failed deploy that never served traffic |
| Hotfix rollout | Restart without version change (debatable—document policy) |

Instrumentation:

```yaml
# GitHub Actions — emit deployment event
- name: Record deployment
  if: success()
  run: |
    curl -X POST "${METRICS_API}/deployments" \
      -H "Authorization: Bearer ${{ secrets.METRICS_TOKEN }}" \
      -d '{
        "service": "order-api",
        "environment": "production",
        "commit_sha": "'"${{ github.sha }}"'",
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"'
      }'
```

Sources: CI/CD deployment logs, GitHub Deployments API, GitLab environments, Argo CD sync events, Spinnaker pipeline history.

Aggregate by **team** or **service**—not entire company—so teams see actionable data.

---

## 42.4 Measuring lead time for changes

**Lead time for changes** is the elapsed time from **code committed** to **running successfully in production**.

```
Lead Time = prod_deploy_timestamp - first_commit_timestamp
```

For a feature spanning multiple commits, use the merge commit to `main` or the tag triggering release—**define consistently**.

Break down lead time into segments (value stream map):

| Segment | Typical bottlenecks |
|---------|---------------------|
| Code review wait | Large PRs, reviewer availability |
| CI queue + duration | Slow tests, insufficient runners |
| Approval gates | Manual change advisory boards |
| Deploy execution | Manual steps, change windows |

Example calculation from Git + CI:

```python
# Pseudocode: compute lead time for a deployment
deploy = get_production_deployment(service="api", sha="abc123")
commit_time = git.commit(deploy.sha).committed_at
lead_time_hours = (deploy.finished_at - commit_time).total_seconds() / 3600
record_metric("lead_time_hours", lead_time_hours, labels={"service": "api"})
```

Reducing lead time usually means: trunk-based development, automated tests, parallel CI, automated promotion, and eliminating manual handoffs.

---

## 42.5 Change failure rate

**Change failure rate** = (deployments causing prod failure) / (total deployments) in a period.

Define **failure** explicitly:

- Rollback required
- Hotfix within 24 hours of deploy
- SEV-1/SEV-2 incident linked to a change
- SLO breach attributed to deployment (via incident tagging)

```sql
-- Example: weekly change failure rate per service
SELECT
  service,
  COUNT(*) FILTER (WHERE caused_incident) * 100.0 / COUNT(*) AS failure_rate_pct
FROM deployments
WHERE environment = 'production'
  AND deployed_at >= NOW() - INTERVAL '7 days'
GROUP BY service;
```

Link deployments to incidents in your incident tool (PagerDuty, Jira, incident.io) via **deployment ID** or **commit SHA** in incident metadata.

Improve change failure rate with: automated testing, canary analysis, feature flags, and post-deploy smoke tests—not by deploying less frequently (that hides problems in bigger batches).

---

## 42.6 Time to restore service (MTTR)

**MTTR** (Mean Time to Restore) measures how quickly service returns to normal after an incident—distinct from **MTTD** (detect) and **MTTR** repair vs **MTBF** (between failures).

```
MTTR = incident_resolved_at - incident_started_at
```

Use **customer-impacting** start time (SLO breach or alert), not internal discovery time, for user-centric measurement.

Improve MTTR with:

- Runbooks and automated remediation
- Observability (Chapter 43–47)
- Blameless postmortems with action items
- Chaos engineering validating recovery paths
- On-call rotation and escalation policies

Track MTTR separately for **deployment-related** vs **infrastructure** incidents to target improvements.

---

## 42.7 Performance clusters and benchmarking

DORA research clusters organizations into **elite, high, medium, low** performers based on metric combinations—not single metrics in isolation.

| Cluster | Typical profile |
|---------|-----------------|
| **Elite** | On-demand deploys, sub-hour lead time, low CFR, fast restore |
| **High** | Daily–weekly deploys, day-scale lead time |
| **Medium** | Monthly deploys, weeks lead time |
| **Low** | Quarterly+ deploys, months lead time |

Compare teams to **past self**, not blindly to FAANG elite—context (regulated industry, legacy monolith) matters. Use benchmarks to set **directional goals**.

---

## 42.8 Building a metrics program

Implementation roadmap:

1. **Define** — Document what counts as deploy, failure, production for each service.
2. **Instrument** — CI/CD hooks, deployment APIs, incident linkage.
3. **Visualize** — Dashboards (Grafana, Datadog, custom) per team.
4. **Review** — Weekly team reviews; monthly cross-team patterns.
5. **Improve** — Pick one bottleneck from lead time breakdown per quarter.
6. **Protect culture** — No individual DORA targets; blameless analysis.

Sample dashboard panels:

- Deploy frequency (7-day rolling)
- Lead time p50 / p95
- Change failure rate (30-day)
- MTTR (30-day)
- Deployments vs incidents overlay chart

---

## 42.9 Continuous improvement loops

DORA metrics feed **Plan-Do-Check-Act (PDCA)** and **Three Ways** (Part I):

| Three Way | DORA connection |
|-----------|-----------------|
| Flow | Lead time, deployment frequency |
| Feedback | Change failure rate, MTTR |
| Continual learning | Postmortems, experiment with pipeline changes |

Combine with **SPACE** framework (Developer productivity—Satisfaction, Performance, Activity, Communication, Efficiency) to avoid over-optimizing deploy count at developer experience expense.

Space for improvement without DORA data: value stream mapping workshops, identifying wait states, automating top three manual steps.

---

## 42.10 Chapter summary

- DORA's four metrics—deployment frequency, lead time, change failure rate, MTTR—measure delivery speed and stability together.
- Define measurement policies consistently; instrument CI/CD and incident systems.
- Improve metrics through systemic changes (automation, testing, observability)—not by gaming numbers.
- Benchmark against past performance; use metrics in blameless continuous improvement cycles.

---

## 🧪 Lab 42.1 — Deployment event pipeline

1. Add a post-deploy step to your CI pipeline that POSTs deployment metadata to a spreadsheet, database, or metrics endpoint.
2. Tag each deployment with service name, environment, commit SHA, and duration.
3. Build a simple dashboard (Grafana or spreadsheet chart) showing deployment frequency over 2 weeks of test data.

---

## 🧪 Lab 42.2 — Lead time value stream map

1. Pick one recent production release.
2. Record timestamps: first commit, PR opened, PR merged, CI complete, staging deploy, prod deploy.
3. Calculate segment durations; identify the largest wait state.
4. Propose one automation or process change targeting that bottleneck.

---

## Review questions

1. Name the four core DORA metrics and what each measures.
2. Why should DORA metrics not be used for individual performance evaluation?
3. How do you define whether a deployment "failed" for change failure rate?
4. What is the difference between lead time for changes and CI pipeline duration?
5. How does MTTR relate to observability and incident response practices?
6. What lead time segments would you investigate first in a team with 5-day lead time?
7. How do elite performers differ from low performers in deployment frequency patterns?

---

*Continue: Chapter 43 — Monitoring Fundamentals*
