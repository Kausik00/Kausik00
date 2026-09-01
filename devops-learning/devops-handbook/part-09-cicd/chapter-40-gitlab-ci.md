# Chapter 40: GitLab CI and Multi-platform Comparison

*DevOps Handbook — Part IX, Pages 791–810*

---

## 40.1 GitLab CI/CD overview

**GitLab CI/CD** is built into GitLab—same platform for source control, merge requests, registry, and pipelines. Configuration lives in `.gitlab-ci.yml` at the repository root (or custom path). GitLab Runner executes jobs; GitLab Server (gitlab.com or self-managed) schedules pipelines.

Architecture:

```
.gitlab-ci.yml → GitLab CI/CD → Runner(s) → Job containers/shell
                      │
                      ├── Variables & CI/CD settings
                      ├── Environments & deployments
                      └── Container Registry / Package Registry
```

GitLab emphasizes **DevOps platform** consolidation: one vendor for SCM, CI, security scanning (Ultimate tier), and deployment tracking.

---

## 40.2 `.gitlab-ci.yml` fundamentals

```yaml
stages:
  - build
  - test
  - security
  - deploy

default:
  image: node:20-alpine
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - node_modules/

variables:
  NODE_ENV: test

build:
  stage: build
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 week

unit-test:
  stage: test
  script:
    - npm ci
    - npm run test:unit
  coverage: '/Lines\s*:\s*(\d+\.\d+)%/'

integration-test:
  stage: test
  services:
    - name: postgres:15
      alias: db
  variables:
    POSTGRES_DB: testdb
    POSTGRES_USER: test
    POSTGRES_PASSWORD: test
    DATABASE_URL: postgres://test:test@db:5432/testdb
  script:
    - npm run test:integration

deploy-staging:
  stage: deploy
  environment:
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    - ./deploy.sh staging
  needs:
    - build
    - unit-test
```

Core concepts:

| Concept | Description |
|---------|-------------|
| **Stage** | Ordered phase; jobs in same stage run in parallel |
| **Job** | Unit of work with `script` |
| **Runner** | Executes jobs (shared, group, project-specific) |
| **Artifact** | Files passed between jobs |
| **Cache** | Speed up dependency installs across pipelines |
| **Service** | Sidecar containers (DB, Redis) for tests |
| **Rules** | Modern conditional syntax replacing `only/except` |

---

## 40.3 Runners, executors, and isolation

**GitLab Runner** is a separate agent process registering to GitLab.

| Executor | Use case |
|----------|----------|
| **Docker** | Most common; job runs in container |
| **Kubernetes** | Ephemeral pods per job |
| **Shell** | Direct on VM; least isolation |
| **SSH** | Remote machine execution |
| **Instance** | Auto-scaled cloud VMs (Premium+) |

Register a runner:

```bash
gitlab-runner register \
  --url https://gitlab.com/ \
  --registration-token PROJECT_TOKEN \
  --executor docker \
  --docker-image alpine:latest \
  --description "docker-runner-01" \
  --tag-list "docker,linux"
```

Use **tags** in jobs: `tags: [docker, linux]`. **Protected runners** run only on protected branches—critical for production deploy jobs accessing sensitive credentials.

---

## 40.4 Variables, environments, and child pipelines

**CI/CD variables** scope: project, group, environment. Mark sensitive values as **masked** and **protected**.

```yaml
deploy-production:
  stage: deploy
  environment:
    name: production
    url: https://app.example.com
    deployment_tier: production
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
  script:
    - echo "Deploying $CI_COMMIT_TAG"
  variables:
    KUBE_CONTEXT: prod-cluster
```

**Manual jobs** (`when: manual`) implement approval gates. **Resource groups** serialize deploys to the same environment.

**Child pipelines** split monorepo CI:

```yaml
trigger-backend:
  trigger:
    include: backend/.gitlab-ci.yml
    strategy: depend
  rules:
    - changes:
        - backend/**/*
```

**Merge request pipelines** run on MR events; **merged results pipelines** test the post-merge state—reducing "green MR, red main" surprises.

---

## 40.5 GitLab-specific features

| Feature | Benefit |
|---------|---------|
| **Auto DevOps** | Opinionated default pipeline for build/test/deploy |
| **Review Apps** | Dynamic environments per MR |
| **Container Registry** | Built-in image storage tied to project |
| **Dependency Proxy** | Cache upstream Docker images |
| **Compliance pipelines** | Enforce stages across org (Ultimate) |
| **DAST/SAST templates** | Security jobs from template catalog |

Review App example:

```yaml
review:
  stage: deploy
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: https://$CI_ENVIRONMENT_SLUG.example.com
    on_stop: stop_review
  script:
    - deploy-review.sh
  rules:
    - if: $CI_MERGE_REQUEST_IID

stop_review:
  stage: deploy
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  when: manual
  script:
    - teardown-review.sh
```

---

## 40.6 Multi-platform CI/CD comparison

| Dimension | GitHub Actions | GitLab CI | Jenkins |
|-----------|----------------|-----------|---------|
| **Config file** | `.github/workflows/*.yml` | `.gitlab-ci.yml` | `Jenkinsfile` |
| **Hosting** | GitHub cloud/Enterprise | GitLab.com/self-managed | Self-hosted (typical) |
| **Runners** | Hosted + self-hosted | Runner required (shared or own) | Agents |
| **Marketplace** | Actions marketplace | CI templates, components | Plugins |
| **MR/PR integration** | Native checks | Native pipelines | Plugin-dependent |
| **OIDC to cloud** | Excellent | Supported | Plugin-dependent |
| **Learning curve** | Moderate YAML | Moderate YAML | Groovy + ops |
| **Cost** | Minutes-based | Per-user + compute | Infra + maintenance |

**Azure Pipelines** (YAML, Microsoft-hosted agents, Azure DevOps integration) fits Microsoft-centric orgs. **CircleCI**, **Buildkite**, and **Tekton** (Kubernetes-native) appear in cloud-native and high-scale scenarios.

Decision framework:

1. **Where is code hosted?** Align CI with SCM when possible.
2. **Compliance** — Data residency, air-gap, audit requirements.
3. **Runner strategy** — Shared vs dedicated, spot instances, K8s.
4. **Total cost** — License + compute + engineer maintenance.
5. **Ecosystem** — Required integrations (Jira, SonarQube, Vault).

---

## 40.7 Portable pipeline patterns

Regardless of platform, mature pipelines share structure:

```
lint → unit test → build artifact → security scan → integration test → deploy staging → deploy prod
```

Portable techniques:

- **Containerize builds** — Same Dockerfile locally and in CI
- **Make/task runners** — `make test` invoked identically everywhere
- **Composite/reusable units** — GitHub reusable workflows, GitLab `include:`, Jenkins shared libraries
- **Policy gates** — Fail on critical CVEs, coverage thresholds
- **Immutable artifacts** — Promote the same image digest staging → prod

Example GitLab `include` for shared org template:

```yaml
include:
  - project: 'platform/ci-templates'
    ref: main
    file: '/nodejs/build-test-deploy.yml'
```

---

## 40.8 Migration considerations

Migrating Jenkins → GitLab or GitHub:

1. Inventory jobs, plugins, credentials, and agent labels.
2. Rewrite pipelines incrementally (strangler pattern)—one service at a time.
3. Map credentials to new secret stores; rotate during migration.
4. Parallel-run old and new pipelines until confidence is high.
5. Decommission Jenkins agents only after traffic cutover.

Tooling like **GitHub Actions Importer** and community converters assist but require manual validation for complex Groovy logic.

---

## 40.9 Chapter summary

- GitLab CI/CD uses `.gitlab-ci.yml` with stages, jobs, runners, artifacts, and environments in one platform.
- Runners with Docker or Kubernetes executors provide flexible, isolated build environments.
- Compare CI platforms on hosting, runner model, integration depth, security, and operational cost—not syntax alone.
- Portable pipeline design (containers, shared templates, immutable artifacts) reduces vendor lock-in.

---

## 🧪 Lab 40.1 — GitLab pipeline with services

1. Create a GitLab project (gitlab.com free tier or self-managed).
2. Add `.gitlab-ci.yml` with Postgres `services` for integration tests.
3. Configure CI/CD variables for a mock deploy token (masked).
4. Add `deploy-staging` with `environment` and `rules` for `main` only.
5. Create an MR and verify MR pipeline runs; merge and confirm staging deploy.

---

## 🧪 Lab 40.2 — Platform comparison exercise

1. Implement the same three-stage pipeline (lint, test, docker build) in GitHub Actions and GitLab CI for one sample repo.
2. Document: lines of config, runner setup time, secret handling, and MR/PR integration UX.
3. Present a one-page recommendation for a hypothetical 50-developer org.

---

## Review questions

1. What is the role of GitLab Runner, and how does it differ from GitLab Server?
2. Explain `rules` vs deprecated `only/except` in GitLab CI.
3. How do **Review Apps** improve merge request workflows?
4. Name three criteria for choosing between GitHub Actions and GitLab CI.
5. What is a child pipeline, and when is it useful in monorepos?
6. Why should production deploy runners be **protected**?
7. What pipeline patterns remain portable across CI platforms?

---

*Continue: Chapter 41 — Deployment Strategies*
