# Chapter 10: Branching Strategies and Code Review

*DevOps Handbook — Pages 40–44 of this PDF edition*
---

## 10.1 Branches as a collaboration contract

Git branches are movable pointers to commits. How your team uses branches defines **release cadence**, **review culture**, and **incident risk**. There is no universal "best" strategy—only trade-offs aligned with deployment frequency, team size, and compliance needs.

Common strategies:

| Strategy | Summary | Typical deployment |
|----------|---------|-------------------|
| **Trunk-based development (TBD)** | Short-lived branches; merge to `main` daily | Continuous (many times/day) |
| **GitHub Flow** | `main` + feature branches + PR | On merge to `main` |
| **Git Flow** | `main`, `develop`, release/hotfix branches | Scheduled releases |
| **Release branches** | Stabilize on `release/x.y` before prod | Versioned releases |

DevOps maturity correlates with **shorter branch lifetime** and **smaller changesets**.

---

## 10.2 Trunk-based development in depth

Trunk-based development keeps **`main` always releasable**. Developers integrate frequently—ideally at least once per day.

Practices:

1. **Feature flags** hide incomplete work instead of long-lived branches.
2. **Small PRs** (< 400 lines changed is a common guideline) review faster and fail less.
3. **Branch lifetime** measured in hours or days, not weeks.
4. **Automated gates** — CI must pass before merge; no manual "it works on my machine."

```
developer → short feature branch → PR → CI → review → merge to main → deploy
```

Anti-patterns for TBD:

- "Integration branch" that lives for a sprint.
- Merging without CI green because "we'll fix later."
- Shared long-lived branches per environment (`dev`, `qa`, `prod` in Git)—prefer **promote artifacts**, not cherry-pick commits.

---

## 10.3 Git Flow and when it still fits

Git Flow (Vincent Driessen) defines:

- **`main`** — production releases only (tags).
- **`develop`** — integration branch for next release.
- **`feature/*`** — from develop, merge back to develop.
- **`release/*`** — stabilize version, bugfix only.
- **`hotfix/*`** — emergency fix from `main`, back-merge to develop.

It suits **shrink-wrapped software**, mobile apps with store review, or regulated release windows. Costs:

- Merge complexity between `develop`, `release`, and `main`.
- Slower feedback loops vs trunk-based.
- Temptation to batch large releases.

Many cloud-native teams **simplified Git Flow to GitHub Flow + tags** for semver.

---

## 10.4 Pull requests and merge mechanics

### Merge commit vs squash vs rebase

| Method | History | Pros | Cons |
|--------|---------|------|------|
| **Merge commit** | Preserves branch topology | True audit trail | Noisy graph |
| **Squash merge** | One commit on main | Clean main history | Loses granular commits |
| **Rebase merge** | Linear history | Readable log | Rewrites SHAs on branch |

Platform teams often standardize on **squash to main** for product repos and **merge commits** for open-source where contributor attribution matters.

### Protected branches

Configure on GitHub/GitLab:

- Require PR before merge to `main`.
- Require **status checks** (CI jobs) to pass.
- Require **approving reviews** (1–2 depending on risk).
- Block force-push and deletion.
- Optional: require signed commits.

---

## 10.5 Code review: purpose and culture

Code review is **not** a gate for senior engineers to flex syntax preferences. It is a **risk reduction and knowledge sharing** mechanism.

Goals:

1. Catch defects, security issues, and operational gaps before production.
2. Spread context so bus factor > 1.
3. Enforce team standards (tests, observability, docs) consistently.

### What reviewers should examine

| Area | Questions |
|------|-----------|
| **Correctness** | Does it do what the ticket says? Edge cases? |
| **Tests** | Adequate coverage for changed behavior? |
| **Observability** | Logs, metrics, traces for new paths? |
| **Security** | Injection, authz, secrets, dependencies? |
| **Operability** | Rollback, config, migrations, feature flags? |
| **Performance** | N+1 queries, unbounded loops, cache behavior? |

### Author responsibilities

- Keep PRs **focused**—one logical change.
- Write a **clear description**: problem, approach, test plan, rollout notes.
- Self-review the diff before requesting others.
- Respond to feedback with commits or comments; don't take review personally.

### Reviewer etiquette

- Distinguish **blockers** from **nits** (`nit:` prefix).
- Approve when you'd be comfortable **on-call** for the change.
- Time-box reviews—slow reviews stall delivery and hurt morale.

---

## 10.6 Size and speed metrics

Google's research and DORA reports align: **small batches** and **fast review** improve stability.

Track informally:

| Metric | Healthy signal |
|--------|----------------|
| PR size (lines) | Median under ~200–400 |
| Time to first review | < 4 business hours |
| Time to merge | < 1 day for most PRs |
| Revert rate | Low; postmortems when reverts happen |

If review latency exceeds a day, fix process (rotation, alerts) before adding more tools.

---

## 10.7 Release tags and semantic versioning

Even with continuous deployment, **tags** mark releases for support and changelogs:

```bash
git tag -a v1.4.0 -m "Release 1.4.0: payment retry logic"
git push origin v1.4.0
```

**Semantic versioning (semver):**

- **MAJOR** — incompatible API change.
- **MINOR** — backward-compatible feature.
- **PATCH** — backward-compatible bug fix.

CI can build container images as `myapp:1.4.0` and `myapp:1.4.0-<git-sha>` for traceability.

---

## 10.8 Handling hotfixes

With trunk-based flow:

1. Branch from `main` (or fix forward on main directly if policy allows).
2. Minimal fix + test; fast-track review.
3. Merge; deploy; monitor.
4. Postmortem if customer-impacting.

With Git Flow:

1. `hotfix/*` from tagged `main`.
2. Merge to `main` and `develop`.
3. Tag patch release.

Either way: **deploy the same artifact** built from the merged commit—never hand-edit production.

---

## 10.9 Chapter summary

- Match branching strategy to **release frequency** and compliance—not hype.
- Trunk-based + feature flags supports **continuous delivery**; Git Flow suits **scheduled releases**.
- Protect `main` with **CI gates and reviews**; prefer small PRs.
- Code review reduces risk and spreads knowledge when done with **respect and clarity**.
- Tag releases with **semver** for supportability even if deploys are continuous.

---

## 🧪 Lab 10.1 — Strategy comparison

1. For a hypothetical SaaS (daily deploys) and a mobile app (monthly store release), pick a branching strategy for each.
2. Write one paragraph justifying each choice using trade-offs from this chapter.
3. List three protected-branch rules you would enable on `main`.

---

## 🧪 Lab 10.2 — Mock code review

1. Open a small PR in a practice repo (or use a provided diff).
2. Leave three comments: one blocker, one suggestion, one nit.
3. As author, respond and push a fix for the blocker.
4. Record time from PR open to merge; aim under 30 minutes for this exercise.

---

## Review questions

1. What is the main goal of trunk-based development?
2. Name the five branch types in classic Git Flow.
3. Compare squash merge vs merge commit for mainline history.
4. List four areas a DevOps-minded code reviewer should check beyond syntax.
5. When might Git Flow be preferable to trunk-based development?

---

*Next: [Chapter 11 — GitHub/GitLab Workflows](./chapter-11-github-gitlab-workflows.md)*
