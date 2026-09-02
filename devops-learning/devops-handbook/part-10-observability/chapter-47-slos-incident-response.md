# Chapter 47: SLOs, Error Budgets, and Incident Response

*DevOps Handbook — Pages 226–230 of this PDF edition*
---

## 47.1 Reliability as a product decision

Uptime is not maximized at 100%—infinite reliability costs infinite money and slows feature delivery. **Site Reliability Engineering (SRE)** treats reliability as a **product feature** with an explicit target negotiated between engineering and business.

**Service Level Objective (SLO)** — Target reliability (e.g., 99.9% availability over 30 days).

**Service Level Indicator (SLI)** — Measured metric (e.g., successful requests / total requests).

**Service Level Agreement (SLA)** — Contract with customers (often looser than internal SLO).

**Error budget** — Allowed unreliability: `1 - SLO`. If SLO is 99.9%, budget is 0.1% (~43 minutes downtime/month).

When error budget is ** exhausted**, freeze risky releases and invest in reliability. When budget is **healthy**, ship features aggressively.

---

## 47.2 Choosing SLIs and SLOs

SLIs must reflect **user experience**, not internal convenience.

| Service type | Good SLI | Poor SLI |
|--------------|----------|----------|
| Request/response API | Success rate + latency | CPU utilization |
| Data pipeline | Freshness, completeness | Worker pod count |
| Storage | Durability, read success | Disk free space alone |

Example API SLIs:

```promql
# Availability SLI (30-day window)
sum(rate(http_requests_total{status!~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Latency SLI: proportion under 300ms
sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

SLO targets (illustrative):

| Tier | Availability | Latency (p99) |
|------|--------------|---------------|
| Critical payment | 99.99% | < 200ms |
| Core API | 99.9% | < 500ms |
| Internal tooling | 99.5% | < 2s |

Document SLOs in a **SLO document** per service: SLI definition, query, target, window, owners, escalation.

---

## 47.3 Error budgets in practice

Error budget calculation (30-day rolling):

```
Budget = (1 - SLO) × total_events
Consumed = failed_events or slow_events
Remaining = Budget - Consumed
```

Burn rate alerts predict budget exhaustion before window ends:

| Burn rate | Meaning | Action |
|-----------|---------|--------|
| 1× | On track to exhaust exactly at window end | Monitor |
| 2× | Exhaust in half the window | Investigate |
| 14.4× | Exhaust in ~2 days at 99.9% monthly | Page on-call |

Multi-window burn alert (Google SRE):

```yaml
# Conceptual — implement via Prometheus recording rules
# Fast burn: 2% budget in 1 hour → page
# Slow burn: 5% budget in 6 hours → ticket
```

Policy when budget depleted:

1. Stop non-critical releases
2. Focus engineering on reliability work
3. Executive visibility—product tradeoff discussion
4. Resume feature velocity when budget recovers

Error budgets **align** dev and ops: shared metric replaces "ops blocks deploys" vs "dev ignores stability."

---

## 47.4 Incident severity and lifecycle

**Incident** — Unplanned interruption or degradation requiring coordinated response.

Severity levels (example):

| Severity | Impact | Response |
|----------|--------|----------|
| **SEV-1** | Customer-facing outage, revenue impact | Immediate all-hands, exec comms |
| **SEV-2** | Major degradation, workaround exists | On-call + team lead within 15m |
| **SEV-3** | Minor impact, limited users | Business hours response |
| **SEV-4** | Cosmetic, no user impact | Backlog |

Incident lifecycle:

```
Detect → Triage → Mitigate → Resolve → Postmortem → Follow-up
   │         │          │          │
 Alerts   Incident    Rollback   Root cause
 paging   commander   scale up   verified
```

Roles:

| Role | Responsibility |
|------|----------------|
| **Incident Commander (IC)** | Coordinates response, decisions, comms |
| **Technical Lead** | Drives debugging and mitigation |
| **Communications Lead** | Status page, stakeholder updates |
| **Scribe** | Timeline, actions log |

---

## 47.5 On-call and escalation

Effective on-call requires:

- **Runbooks** — Step-by-step for known alerts
- **Dashboards** — Golden signals per service linked from alerts
- **Escalation policy** — Primary → secondary → manager
- **Handoff** — Document active issues between shifts
- **Toil limits** — On-call should not mean endless manual work

PagerDuty/Opsgenie escalation example:

1. Primary on-call (5 min)
2. Secondary on-call (10 min)
3. Engineering manager (15 min)
4. Incident commander pool (SEV-1)

**Alert quality** directly affects on-call burnout—every page must require human action (Chapter 43).

---

## 47.6 Incident response procedures

**Detection** — Automated alerts on SLO burn, synthetic probes, customer reports.

**Triage checklist:**

1. Confirm user impact (not false positive)
2. Assign severity and IC
3. Open incident channel (`#inc-2026-09-01-api-outage`)
4. Start timeline document
5. Communicate status page update within 15 min (SEV-1)

**Mitigation over root cause** — Restore service first (rollback, failover, scale, feature flag off), investigate after.

Common mitigations:

| Symptom | Fast mitigation |
|---------|-----------------|
| Bad deploy | Rollback to previous version |
| Traffic spike | Scale horizontally, rate limit |
| Dependency down | Circuit breaker, degrade gracefully |
| Data corruption | Stop writes, restore from backup |

**Resolution** — Verify SLI recovery, close incident, schedule postmortem within 5 business days.

---

## 47.7 Blameless postmortems

Postmortem documents **what happened**, **why** (contributing factors, not single root cause), and **action items**—without blaming individuals.

Template sections:

1. Summary (one paragraph)
2. Impact (duration, users affected, SLO breach)
3. Timeline (UTC timestamps)
4. Root cause analysis (5 whys, fishbone)
5. What went well / what went poorly
6. Action items (owner, due date, priority)
7. Lessons learned

Blameless culture encourages reporting near-misses—hidden failures repeat.

Action item tracking: treat reliability fixes like product backlog items with SLAs.

---

## 47.8 Status communication

**Status page** (Statuspage, Instatus, custom):

- Investigating → Identified → Monitoring → Resolved
- Update every 30–60 min during SEV-1
- Honest scope—avoid "all systems operational" when degraded

Internal vs external messaging:

- Internal: technical detail, hypothesis, commands run
- External: user impact, workaround, ETA if confident

---

## 47.9 Tooling integration

Integrate observability → incident → postmortem:

```
Prometheus alert → Alertmanager → PagerDuty → Slack #incidents
Deploy webhook → Timeline auto-entry
Grafana snapshot → Postmortem attachment
Jira/Linear → Action item tickets from postmortem template
```

Tag incidents with **deployment ID** and **trace IDs** for DORA change failure analysis.

---

## 47.10 Chapter summary

- SLOs define target reliability; SLIs measure it; error budgets balance feature velocity and stability.
- Burn rate alerts provide early warning before budget exhaustion.
- Incident response prioritizes mitigation, clear roles, and stakeholder communication.
- Blameless postmortems drive systemic improvements with tracked action items.

---

## 🧪 Lab 47.1 — Define SLOs for a sample service

1. Pick a sample HTTP API with Prometheus metrics.
2. Write SLI queries for availability and latency.
3. Set SLO target 99.9% / 30 days; calculate monthly error budget in minutes.
4. Create Grafana dashboard showing budget remaining.

---

## 🧪 Lab 47.2 — Tabletop incident exercise

1. Scenario: deploy causes 10% 5xx rate spike.
2. Assign roles (IC, tech lead, comms, scribe).
3. Run 30-minute simulated response: triage, mitigation decision, status update draft.
4. Write blameless postmortem with 3 action items.

---

## Review questions

1. Distinguish SLI, SLO, and SLA with an example.
2. How is error budget calculated for 99.95% over 30 days?
3. What should happen when error budget is exhausted mid-quarter?
4. Why prioritize mitigation over root cause during an active incident?
5. What makes a postmortem blameless, and why does it matter?
6. Explain multi-window burn rate alerting.
7. What SLIs would you choose for a batch data pipeline?

---

*Continue: Chapter 48 — Chaos Engineering and Game Days*
