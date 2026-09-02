# Chapter 37: CI/CD Concepts and Pipeline Design

*DevOps Handbook — Pages 172–174 of this PDF edition*
---

## 37.1 Continuous Integration (CI)

**CI** means developers merge code to a shared branch **frequently** (at least daily), and each merge triggers an **automated build and test** pipeline.

Goals:

- Detect integration bugs early
- Keep `main` always deployable
- Reduce merge hell from long-lived branches

---

## 37.2 Continuous Delivery vs Continuous Deployment

| Practice | Definition |
|----------|------------|
| **Continuous Delivery** | Every change is releasable; deploy to prod is a **manual** (or one-click) decision |
| **Continuous Deployment** | Every change that passes tests is **automatically** deployed to production |

Most enterprises use **Continuous Delivery** with approval gates for production.

---

## 37.3 Pipeline stages

A typical pipeline:

```
┌─────────┐   ┌───────┐   ┌──────┐   ┌────────┐   ┌────────┐   ┌────────┐
│ Source  │ → │ Build │ → │ Test │ → │ Scan   │ → │ Stage  │ → │ Deploy │
│ (Git)   │   │       │   │      │   │ SAST/  │   │ deploy │   │ prod   │
└─────────┘   └───────┘   └──────┘   │ SCA    │   └────────┘   └────────┘
                                      └────────┘
```

| Stage | Activities |
|-------|------------|
| **Source** | Webhook on push/PR |
| **Build** | Compile, docker build, artifact upload |
| **Test** | Unit, integration, contract tests |
| **Scan** | SAST, dependency scan, container scan, IaC scan |
| **Stage deploy** | Deploy to staging; smoke tests |
| **Prod deploy** | Blue/green, canary, or rolling; approval gate |

---

## 37.4 GitHub Actions example

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm

      - run: npm ci
      - run: npm run lint
      - run: npm test -- --coverage

      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Scan image
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          severity: CRITICAL,HIGH
          exit-code: 1

  deploy-staging:
    needs: build-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: ./scripts/deploy.sh staging ${{ github.sha }}
```

---

## 37.5 Branching and trunk-based development

**Trunk-based development** (recommended for CI/CD):

- Short-lived feature branches (< 2 days)
- Frequent merges to `main`
- Feature flags hide incomplete work

Avoid long-running `develop` branches that diverge from production reality.

---

## 37.6 Deployment strategies

| Strategy | How it works | Risk |
|----------|--------------|------|
| **Rolling** | Replace instances gradually | Medium |
| **Blue/green** | Switch traffic between two identical envs | Low downtime |
| **Canary** | Route small % traffic to new version | Lowest blast radius |
| **Recreate** | Tear down old, start new | Downtime |

---

## 37.7 Pipeline secrets and artifacts

- Store secrets in **GitHub Secrets**, **Vault**, or cloud secret managers—never in YAML.
- Pin action versions (`@v4`, commit SHA) for supply chain security.
- Upload build artifacts (JAR, Docker image digest) for downstream deploy jobs.
- Sign artifacts (Sigstore/cosign) for provenance.

---

## 37.8 DORA metrics in your pipeline

Track:

1. **Deployment frequency** — How often you deploy to prod
2. **Lead time for changes** — Commit to prod duration
3. **Change failure rate** — % of deploys causing incidents
4. **MTTR** — Time to restore after failure

Instrument pipelines to emit these metrics to your observability platform.

---

## 37.9 Chapter summary

- CI validates every merge; CD/CD automates release to staging/prod.
- Design pipelines with **build → test → scan → deploy** stages.
- Prefer trunk-based dev, pinned dependencies, and safe deployment strategies.

---

## 🧪 Lab 37.1

Build a full GitHub Actions pipeline for a sample app: lint, test, Docker build, Trivy scan, and deploy to staging on merge to `main`.

---

*Continue: Chapter 38 — GitHub Actions Deep Dive (outline in TOC)*
