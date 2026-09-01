# Chapter 1: What Is DevOps? History and Culture

*DevOps Handbook — Part I, Pages 1–15*

---

## 1.1 The problem DevOps solves

Before DevOps, software organizations often split into two camps:

- **Development** — wrote features quickly, measured by release velocity.
- **Operations** — kept systems stable, measured by uptime and incident count.

These goals frequently conflicted. Developers threw code "over the wall"; operators resisted change because every deployment risked an outage. Releases were rare, painful, and manual. When something broke in production, blame flowed in both directions.

**DevOps** is not a single tool or job title. It is a **cultural and technical movement** that unifies development and operations around shared goals: deliver value to users **fast** and **reliably**.

---

## 1.2 A working definition

> **DevOps** is the practice of aligning people, processes, and technology so that software can be built, tested, released, and operated continuously—with feedback loops that shorten the time from idea to production.

Key outcomes:

| Outcome | What it means |
|---------|---------------|
| **Shorter lead time** | Hours or days from commit to production, not months |
| **Higher deployment frequency** | Many small releases instead of rare big-bang releases |
| **Lower change failure rate** | Most changes succeed without rollback |
| **Faster recovery** | When failures happen, restore service quickly |

These four metrics are known as **DORA metrics** (DevOps Research and Assessment) and are the standard way to measure DevOps maturity.

---

## 1.3 Brief history

| Year | Milestone |
|------|-----------|
| 2007–2009 | Flickr, Etsy, and others share "10+ deploys per day" stories |
| 2009 | First **DevOpsDays** conference in Ghent, Belgium (Patrick Debois) |
| 2010 | "The Phoenix Project" novel popularizes DevOps narrative |
| 2013 | "The DevOps Handbook" (Gene Kim et al.) codifies practices |
| 2016+ | Cloud-native, containers, and Kubernetes accelerate adoption |
| 2020s | Platform engineering, GitOps, and AI-assisted ops emerge |

The term **DevOps** blends **Development** + **Operations**. It intentionally breaks down silos rather than creating a third silo called "DevOps team" that sits between dev and ops.

---

## 1.4 Culture before tools

A common mistake is buying Jenkins, Kubernetes, or Terraform and calling it "DevOps." Tools enable DevOps; they do not create it.

Cultural pillars:

1. **Shared ownership** — The team that builds a service also runs it ("you build it, you run it").
2. **Blameless postmortems** — Focus on systems and processes, not individuals, after incidents.
3. **Automation of toil** — Repetitive manual work is eliminated or codified.
4. **Continuous learning** — Experimentation, feedback, and improvement are expected.
5. **Customer focus** — Every decision ties back to user value.

---

## 1.5 DevOps practices (overview)

You will study each in depth later in this handbook:

| Practice | Summary |
|----------|---------|
| **Version control** | Everything in Git: code, config, IaC, docs |
| **CI/CD** | Automated build, test, deploy pipelines |
| **Infrastructure as Code** | Reproducible environments (Terraform, Ansible) |
| **Monitoring & observability** | Know what production is doing in real time |
| **Microservices & containers** | Smaller deployable units (optional but common) |
| **Security integration (DevSecOps)** | Security checks in the pipeline, not at the end |

---

## 1.6 Organizational models

### Functional silos (anti-pattern for DevOps)
Separate dev, QA, ops, and security teams with handoffs.

### Cross-functional product teams (recommended)
One team owns a product or service end-to-end: code, infra, on-call, roadmap.

### DevOps enablement / platform team
A **platform team** builds internal tools (CI templates, K8s clusters, golden paths) so product teams move faster. This is **not** a ticket-taking ops team—it is a **product for developers**.

---

## 1.7 What DevOps is NOT

- **Not "NoOps"** — Operations expertise is more important at scale, not less.
- **Not only for startups** — Enterprises adopt DevOps for compliance and speed.
- **Not replacing developers with operators** — It merges responsibilities skillfully.
- **Not a certification checkbox** — Culture and practice matter more than badges.

---

## 1.8 Your learning path in this handbook

```
Foundations → Automation → Containers → CI/CD → Observability → Security → Advanced
     ↑                                                              ↓
  Linux, Git, Networking ─────────────────────────────── Platform & SRE
```

Invest 70% of study time in **hands-on labs**. Reading without doing builds false confidence.

---

## 1.9 Chapter summary

- DevOps unifies dev and ops around **speed** and **reliability**.
- **Culture** (shared ownership, blameless learning) precedes tools.
- Measure progress with **DORA metrics**.
- Cross-functional teams and platform engineering are modern expressions of DevOps.

---

## 🧪 Lab 1.1 — Reflect on your current workflow

1. Map your (or a sample) team's path from code commit to production.
2. Count manual steps and handoffs.
3. Identify one bottleneck and one automation opportunity.
4. Write a one-paragraph "DevOps vision" for that team.

---

## Review questions

1. Name the four DORA metrics.
2. Why is "DevOps team" as a silo problematic?
3. What year and event is credited with coining "DevOps"?
4. Give one cultural and one technical practice of DevOps.

---

*Next: [Chapter 2 — CALMS, Three Ways, and Team Topologies](./chapter-02-calms-three-ways.md)*
