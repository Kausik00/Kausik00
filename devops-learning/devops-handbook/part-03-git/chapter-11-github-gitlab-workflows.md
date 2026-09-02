# Chapter 11: GitHub/GitLab Workflows — PRs, Issues, Actions Intro

*DevOps Handbook — Pages 45–49 of this PDF edition*
---

## 11.1 Platform-native Git workflows

Git is the protocol; **GitHub** and **GitLab** are collaboration platforms. They add pull/merge requests, issue tracking, CI/CD, permissions, and audit trails. DevOps engineers live in these UIs and APIs daily.

Concept mapping:

| Concept | GitHub | GitLab |
|---------|--------|--------|
| Pull request | **Pull Request (PR)** | **Merge Request (MR)** |
| CI system | **GitHub Actions** | **GitLab CI/CD** |
| Issue | Issue | Issue |
| Code owners | `CODEOWNERS` | `CODEOWNERS` |
| Environments | Environments + rules | Environments + protected branches |
| Package registry | GHCR | GitLab Container Registry |

Master one platform deeply; skills transfer with vocabulary swaps.

---

## 11.2 Issues and project hygiene

Issues are the **system of record** for work: bugs, features, tech debt, incidents.

Effective issue template fields:

| Field | Purpose |
|-------|---------|
| **Summary** | One-line title |
| **Context** | User impact, links to alerts |
| **Steps to reproduce** | For bugs |
| **Acceptance criteria** | For features |
| **Rollout / rollback** | For infra changes |

Link PRs to issues (`Fixes #123`) so merges auto-close tickets and audit trails stay connected.

Labels (`bug`, `infra`, `security`, `P1`) and milestones (sprints, releases) help prioritization—avoid label sprawl beyond ~15 types.

---

## 11.3 Pull request lifecycle (GitHub)

Typical flow:

```
1. Create branch from main     git checkout -b feat/retry-webhook
2. Commit with clear messages  git commit -m "feat: add webhook retry"
3. Push and open PR            gh pr create
4. CI runs on PR event
5. Reviewers approve
6. Merge (squash/merge/rebase per policy)
7. Deployment pipeline triggers on main
```

### PR description template

```markdown
## Summary
Brief description of change.

## Test plan
- [ ] Unit tests pass locally
- [ ] Staging deploy verified

## Rollout
Feature flag `webhook_retry` default off; enable 10% canary.

## Screenshots / logs
(if applicable)
```

Store templates in `.github/pull_request_template.md`.

---

## 11.4 CODEOWNERS and review routing

`CODEOWNERS` auto-requests reviewers based on path:

```
# .github/CODEOWNERS
*                    @platform-team
/terraform/          @infra-team @security
/apps/payments/      @payments-squad
```

GitLab equivalent lives at `.gitlab/CODEOWNERS` or project settings with **approval rules**.

This scales review without a central gatekeeper bottleneck—**domain experts** review their turf.

---

## 11.5 GitHub Actions introduction

GitHub Actions runs CI/CD in YAML workflows stored in `.github/workflows/`.

Minimal workflow:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest -q
```

Key concepts:

| Term | Meaning |
|------|---------|
| **Workflow** | YAML file; one or more jobs |
| **Job** | Runs on a runner VM; parallelizable |
| **Step** | Shell command or `uses:` action |
| **Action** | Reusable unit (checkout, setup-node) |
| **Runner** | GitHub-hosted or self-hosted machine |

Secrets: `Settings → Secrets and variables → Actions`. Reference as `${{ secrets.API_TOKEN }}`—never commit secrets.

---

## 11.6 GitLab CI introduction

GitLab CI uses `.gitlab-ci.yml` at repo root:

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

test:
  stage: test
  image: python:3.12-slim
  script:
    - pip install -r requirements.txt
    - pytest -q
  cache:
    paths:
      - .cache/pip

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
  only:
    - main
```

GitLab runners execute jobs; register shared or project-specific runners for private clusters.

---

## 11.7 Branch protection and environments

### GitHub environments

Define **staging** and **production** with:

- Required reviewers before deploy job runs.
- Wait timers for change windows.
- Secrets scoped per environment.

```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: production
    needs: [test]
    steps:
      - run: ./deploy.sh production
```

### GitLab protected environments

Similar via **protected branches**, **deployment tiers**, and **manual jobs** (`when: manual`).

---

## 11.8 Fork and open-source workflows

External contributors fork repos, push branches on their fork, and open PRs/MRs upstream.

Maintainers:

- Run CI on PRs from forks with **limited secrets** (GitHub uses `pull_request_target` carefully—security sensitive).
- Use **CLA bots** or DCO sign-off for legal compliance.
- Label `good first issue` to grow contributors.

---

## 11.9 Integrations DevOps teams use

| Integration | Use case |
|-------------|----------|
| **Slack / Teams** | PR and deploy notifications |
| **Jira / Linear** | Bi-directional issue sync |
| **Dependabot / Renovate** | Automated dependency PRs |
| **CODE scanning** | SAST on push |
| **OIDC to cloud** | Keyless AWS/GCP/Azure deploy from CI |

Example OIDC pattern (GitHub → AWS): configure IAM role trust for `token.actions.githubusercontent.com`; workflow assumes role without long-lived AWS keys.

---

## 11.10 Comparing Actions vs GitLab CI (practical)

| Dimension | GitHub Actions | GitLab CI |
|-----------|----------------|-----------|
| **Marketplace actions** | Huge ecosystem | Smaller; more shell/scripts |
| **Self-hosted runners** | Per repo/org | First-class runner manager |
| **Monorepo** | Path filters, reusable workflows | `rules:changes`, child pipelines |
| **Container registry** | GHCR integrated | Built into GitLab |
| **Enterprise** | GitHub Enterprise | GitLab dedicated/self-managed |

Many organizations use **both**—product on GitHub, internal mirrors on GitLab—so learn YAML patterns for each.

---

## 11.11 CLI automation: `gh` and `glab`

```bash
# GitHub CLI
gh pr create --title "feat: retry" --body "See template"
gh pr checks
gh run list --workflow ci.yml

# GitLab CLI (glab)
glab mr create --title "feat: retry"
glab pipeline status
```

Scripting PR creation and CI status in onboarding docs reduces friction for new engineers.

---

## 11.12 Chapter summary

- GitHub **PRs** and GitLab **MRs** are the hub for review, CI, and audit.
- Issues linked to PRs create traceability from idea to production.
- **CODEOWNERS** routes review to the right experts automatically.
- **GitHub Actions** and **GitLab CI** define pipelines as code in YAML.
- Use **environments**, branch protection, and OIDC for safe deployments.

---

## 🧪 Lab 11.1 — First GitHub Actions workflow

1. Add `.github/workflows/ci.yml` to a practice repo running `shellcheck` on `scripts/`.
2. Open a PR that breaks a script intentionally; confirm CI fails.
3. Fix and merge; confirm CI passes on `main`.
4. Add a job summary with `$GITHUB_STEP_SUMMARY`.

---

## 🧪 Lab 11.2 — GitLab mirror (optional)

1. If using GitLab, create `.gitlab-ci.yml` with lint + test stages.
2. Configure a manual `deploy_staging` job only on `main`.
3. Document required CI variables in README.

---

## Review questions

1. What is the GitLab equivalent of a GitHub Pull Request?
2. Where should CI workflow files live in GitHub vs GitLab repos?
3. How does CODEOWNERS improve review routing?
4. Why should production secrets be scoped to environments?
5. Name two integrations that reduce toil for DevOps teams on these platforms.

---

*Next: [Chapter 12 — OSI Model, TCP/IP, DNS Deep Dive](../part-04-networking/chapter-12-osi-tcpip-dns.md)*
