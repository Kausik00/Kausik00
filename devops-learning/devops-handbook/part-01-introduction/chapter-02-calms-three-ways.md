# Chapter 2: CALMS, Three Ways, and Team Topologies

*DevOps Handbook — Pages 9–11 of this PDF edition*
---

## 2.1 The CALMS framework

**CALMS** is a mnemonic for assessing DevOps maturity across five dimensions:

| Letter | Dimension | Description |
|--------|-----------|-------------|
| **C** | Culture | Collaboration, trust, shared goals |
| **A** | Automation | Eliminate manual, error-prone work |
| **L** | Lean | Reduce waste, small batches, flow |
| **M** | Measurement | Data-driven decisions, DORA metrics |
| **S** | Sharing | Knowledge, tools, failures, successes |

### Culture (C)
Healthy DevOps culture means developers understand production constraints and operators understand business priorities. Psychological safety allows people to report problems early.

### Automation (A)
Automate builds, tests, deployments, infrastructure provisioning, and compliance checks. Manual runbooks become code. **Toil**—repetitive operational work that scales linearly with service growth—should be targeted for elimination.

### Lean (L)
Inspired by Toyota Production System: optimize **flow**, limit work in progress (WIP), and deliver **small batches**. Large releases hide defects; small releases surface them quickly.

### Measurement (M)
You cannot improve what you do not measure. Track deployment frequency, lead time, MTTR, change failure rate, plus business KPIs (revenue, user satisfaction).

### Sharing (S)
Internal conferences, shared Slack channels, communal dashboards, and open postmortems spread expertise. Tools and patterns are reused, not reinvented per team.

---

## 2.2 The Three Ways (Gene Kim)

From *The Phoenix Project* and *The DevOps Handbook*, the **Three Ways** describe the principles of DevOps flow:

### First Way: Flow (left to right)

Accelerate delivery from **development → operations → customer**.

- Make work visible (Kanban boards, pipeline status).
- Reduce batch sizes.
- Build quality in (automated tests at every stage).
- Never pass defects downstream.

**Example:** A commit triggers CI; only green builds reach staging; only approved artifacts reach production.

### Second Way: Feedback (right to left)

Amplify feedback from **production → development**.

- Monitor user experience and system health.
- Swarm on problems; shorten feedback loops.
- Developers get production access (with guardrails).

**Example:** Error rate spike in Grafana pages the on-call engineer; linked traces show the bad deploy; rollback is automated.

### Third Way: Continuous learning and experimentation

Create a culture of **improvement** and **risk-taking**.

- Blameless postmortems.
- Reserve time for improvement (20% ops time, hack days).
- Rehearse failures (game days, chaos engineering).

---

## 2.3 Team Topologies (Skelton & Pais)

Modern DevOps organizations structure teams intentionally:

| Team type | Purpose |
|-----------|---------|
| **Stream-aligned** | Delivers product features; primary value stream |
| **Platform** | Provides self-service infra (K8s, CI, databases) |
| **Enabling** | Coaches stream teams on new tech (temporary) |
| **Complicated-subsystem** | Owns deep specialty (e.g., video encoding, ML) |

### Interaction modes

- **Collaboration** — Two teams work closely for discovery.
- **X-as-a-Service** — Platform provides API/portal; stream teams consume.
- **Facilitating** — Enabling team mentors others.

**Anti-pattern:** One ops team serves 50 dev teams via tickets.  
**Better:** Platform team offers paved roads; stream teams deploy autonomously.

---

## 2.4 Conway's Law and reverse Conway maneuver

> *"Organizations design systems that mirror their communication structure."* — Melvin Conway

If dev and ops are separate departments, you will get separate deployment artifacts and fragile handoffs.

**Reverse Conway maneuver:** Structure teams the way you want the architecture to look. Want autonomous microservices? Give teams end-to-end ownership of each service.

---

## 2.5 Maturity model (informal)

| Level | Characteristics |
|-------|-----------------|
| **1 — Initial** | Manual deploys, silos, hero culture |
| **2 — Managed** | Some CI, version control, basic monitoring |
| **3 — Defined** | IaC, automated testing, standardized pipelines |
| **4 — Measured** | SLOs, DORA tracking, blameless postmortems |
| **5 — Optimizing** | Continuous experimentation, platform self-service |

Use this for self-assessment, not as a rigid certification ladder.

---

## 2.6 Chapter summary

- **CALMS** evaluates Culture, Automation, Lean, Measurement, Sharing.
- The **Three Ways** optimize flow, feedback, and learning.
- **Team Topologies** align org structure with delivery goals.
- Apply **Conway's Law** consciously when designing teams.

---

## 🧪 Lab 2.1 — CALMS assessment

Score your team 1–5 on each CALMS letter. Pick the lowest score and draft one actionable improvement per dimension.

---

## Review questions

1. What does the "L" in CALMS stand for, and what Lean concept supports it?
2. Describe the First Way in one sentence.
3. Name the four team types in Team Topologies.
4. What is a reverse Conway maneuver?

---

*Next: Part II — [Chapter 5: Linux Fundamentals](../part-02-linux/chapter-05-linux-fundamentals.md)*
