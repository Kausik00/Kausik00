# Chapter 3: DevOps vs SRE vs Platform Engineering

*DevOps Handbook — Part I, Pages 31–42*

---

## 3.1 Three related disciplines

**DevOps**, **Site Reliability Engineering (SRE)**, and **Platform Engineering** are often confused because they share goals: reliable systems, fast delivery, and reduced toil. They are complementary, not competing.

| Discipline | Origin | Primary focus |
|------------|--------|---------------|
| **DevOps** | Movement (2009+) | Culture + practices bridging dev and ops |
| **SRE** | Google (2003+, public ~2016) | Engineering approach to operations at scale |
| **Platform Engineering** | Industry evolution (2020s) | Internal platforms that accelerate product teams |

---

## 3.2 Site Reliability Engineering (SRE)

Google introduced **SRE** as "what happens when you ask a software engineer to design an operations function."

### Core SRE principles

1. **Embrace risk** — 100% uptime is impossible and expensive; use **error budgets** to balance reliability and velocity.
2. **Service level objectives (SLOs)** — Define measurable targets (e.g., 99.9% availability).
3. **Eliminate toil** — Manual, repetitive work that scales with traffic must be automated.
4. **Monitoring** — Systems must be observable; alerts fire on symptoms users feel.
5. **Release engineering** — Safe, gradual rollouts with fast rollback.
6. **Simplicity** — Prefer boring, well-understood technology.

### SRE team responsibilities

- Define and track SLOs/SLIs
- On-call rotation and incident response
- Capacity planning
- Performance and reliability testing
- Building automation to replace toil

### Error budget example

If SLO = 99.9% monthly availability, you have ~43 minutes of downtime budget. When budget is exhausted, **freeze feature releases** and focus on reliability until budget recovers.

---

## 3.3 Platform Engineering

**Platform engineering** treats the internal developer platform as a **product** whose customers are other engineers.

### What platform teams build

- Kubernetes clusters with guardrails
- CI/CD templates and golden pipelines
- Self-service databases, caches, and queues
- Developer portals (Backstage) with docs and service catalogs
- Standardized observability (dashboards, tracing, logging)

### Platform vs traditional ops

| Traditional ops | Platform engineering |
|-----------------|---------------------|
| Ticket queue for infra requests | Self-service APIs and portals |
| Snowflake servers | Standardized golden paths |
| "Call us to deploy" | Teams deploy autonomously with paved roads |

---

## 3.4 How they fit together

```
┌─────────────────────────────────────────────────────────┐
│  DevOps culture & practices (organization-wide)         │
│  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │ SRE team        │  │ Platform team               │ │
│  │ SLOs, on-call,  │  │ K8s, CI templates, IDP      │ │
│  │ incident mgmt   │  │ self-service infra          │ │
│  └────────┬────────┘  └──────────────┬──────────────┘ │
│           │                          │                │
│           └──────────┬───────────────┘                │
│                      ▼                                │
│           Stream-aligned product teams                │
│           (build features, own services)              │
└─────────────────────────────────────────────────────────┘
```

- **DevOps** sets the cultural north star.
- **SRE** ensures reliability is measurable and engineered.
- **Platform** removes friction so product teams ship faster.

---

## 3.5 Job titles in the market

Titles vary widely. Focus on **responsibilities**, not labels:

| Title | Often means |
|-------|-------------|
| DevOps Engineer | CI/CD, IaC, cloud infra, automation |
| SRE | SLOs, on-call, reliability tooling, toil reduction |
| Platform Engineer | Internal platform, K8s, developer experience |
| Cloud Engineer | AWS/Azure/GCP architecture and implementation |
| Infrastructure Engineer | Servers, networking, IaC |

Many roles blend all three disciplines.

---

## 3.6 Chapter summary

- **SRE** engineers reliability with SLOs, error budgets, and toil automation.
- **Platform engineering** provides self-service paved roads for developers.
- **DevOps** is the umbrella culture; SRE and platform are specialized implementations.

---

## 🧪 Lab 3.1

Draft SLOs for a sample API: pick one SLI (latency or availability), set a target, and calculate the monthly error budget in minutes.

---

*Next: [Chapter 6 — Processes and systemd](../part-02-linux/chapter-06-processes-systemd.md)*
