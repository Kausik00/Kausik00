# Chapter 38: GitHub Actions — Workflows, Secrets, Runners

*DevOps Handbook — Part IX, Pages 746–770*

---

## 38.1 GitHub Actions architecture

**GitHub Actions** is GitHub's native CI/CD platform. Workflows are triggered by repository events (push, pull request, schedule, manual dispatch) and execute as one or more **jobs** on **runners**—virtual machines or containers that run your steps.

Core components:

| Component | Description |
|-----------|-------------|
| **Workflow** | YAML file in `.github/workflows/` defining automation |
| **Event** | Trigger (`push`, `pull_request`, `workflow_dispatch`, etc.) |
| **Job** | A set of steps that run on the same runner |
| **Step** | Individual task: run a script or use an **action** |
| **Action** | Reusable unit (checkout, setup-node, deploy) |
| **Runner** | Execution environment (GitHub-hosted or self-hosted) |
| **Artifact** | Files persisted between jobs or after workflow completion |
| **Environment** | Named deployment target with optional protection rules |

```
Repository Event → Workflow → Job(s) → Step(s) → Action / run script
                                    ↓
                              Runner (ubuntu, windows, macOS, or custom)
```

GitHub Actions integrates tightly with GitHub: PR checks, branch protection, environments, and OIDC federation for cloud deployments without long-lived credentials.

---

## 38.2 Workflow syntax fundamentals

Every workflow begins with a name, trigger, and jobs block:

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, release/*]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment
        required: true
        type: choice
        options: [staging, production]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  id-token: write   # Required for OIDC to AWS/GCP/Azure

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
          cache: true
      - run: go test ./... -race -coverprofile=coverage.out
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage.out
```

Key syntax elements:

| Key | Purpose |
|-----|---------|
| `on` | Events and filters (paths, branches, tags) |
| `jobs.<id>.needs` | Job dependency graph |
| `jobs.<id>.if` | Conditional execution |
| `jobs.<id>.strategy.matrix` | Parallel builds across OS/versions |
| `${{ }}` | Expression syntax for contexts and functions |
| `env` | Environment variables at workflow, job, or step level |

**Contexts** provide runtime data: `github`, `env`, `job`, `steps`, `secrets`, `vars`. Use `github.sha`, `github.ref_name`, and `github.event_name` for dynamic behavior.

---

## 38.3 Reusable workflows and composite actions

Avoid duplicating pipeline logic across repositories with **reusable workflows** and **composite actions**.

Reusable workflow (called from another repo's workflow):

```yaml
# .github/workflows/reusable-test.yml
on:
  workflow_call:
    inputs:
      node-version:
        required: true
        type: string
    secrets:
      NPM_TOKEN:
        required: true
    outputs:
      image-tag:
        description: Built image tag
        value: ${{ jobs.build.outputs.tag }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ steps.meta.outputs.tag }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        run: echo "tag=${{ github.sha }}" >> $GITHUB_OUTPUT
```

Caller workflow:

```yaml
jobs:
  call-reusable:
    uses: ./.github/workflows/reusable-test.yml
    with:
      node-version: "20"
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Composite actions bundle multiple steps into one `uses:` reference—ideal for org-wide lint or deploy patterns stored in a dedicated `actions` repository.

---

## 38.4 Secrets, variables, and security

Secrets must never appear in logs. GitHub automatically masks values registered as secrets.

| Secret scope | Visibility |
|--------------|------------|
| Repository secrets | Single repo workflows |
| Environment secrets | Jobs targeting named environment |
| Organization secrets | Selected repos in org |
| Dependabot secrets | Dependabot workflows only |

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy with API key
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_API_KEY }}
        run: ./scripts/deploy.sh
```

**Security best practices:**

1. **Least privilege** — Set `permissions:` explicitly; default was historically overly broad.
2. **Pin actions** — Use commit SHA or version tag (`@v4`), not `@main`.
3. **OIDC over static keys** — Federate to AWS IAM, Azure, GCP without storing cloud credentials in GitHub.
4. **Environment protection** — Require reviewers for production; limit branches that can deploy.
5. **Fork PR safety** — Workflows from forks do not receive secrets unless explicitly configured (and carefully).

OIDC example for AWS:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsDeploy
      aws-region: us-east-1
```

Repository **variables** (`vars`) store non-sensitive configuration (region names, feature flags) visible to collaborators with appropriate access.

---

## 38.5 Runners: hosted vs self-hosted

**GitHub-hosted runners** are managed by GitHub (Ubuntu, Windows, macOS). They are ephemeral, pre-installed with common tools, and billed by minute (included minutes on free/team plans, then usage-based).

**Self-hosted runners** run on your infrastructure—on-premises VMs, Kubernetes, or cloud instances you control.

| Aspect | GitHub-hosted | Self-hosted |
|--------|---------------|-------------|
| Maintenance | GitHub | You |
| Custom software | Limited image | Full control |
| Network access | Public internet | Private VPC, internal APIs |
| Cost model | Per-minute | Your infra + runner software |
| Isolation | Fresh VM per job | Shared or dedicated per label |
| Scale | Automatic | You add runners |

Self-hosted runner registration:

```bash
# On your runner machine
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf actions-runner-linux-x64-2.311.0.tar.gz
./config.sh --url https://github.com/myorg/myrepo --token RUNNER_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

Use **runner labels** (`runs-on: [self-hosted, linux, gpu]`) to route jobs. For Kubernetes, projects like **Actions Runner Controller (ARC)** scale ephemeral runners as pods.

**Runner groups** (organization level) restrict which repos can use which runners—critical for security when runners access internal networks.

---

## 38.6 Matrix builds, caching, and artifacts

Matrix strategies run the same job across multiple configurations:

```yaml
jobs:
  test-matrix:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pip install -r requirements.txt && pytest
```

**Caching** speeds dependency installation:

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: npm-${{ runner.os }}-${{ hashFiles('**/package-lock.json') }}
    restore-keys: npm-${{ runner.os }}-
```

**Artifacts** pass build outputs between jobs or retain them for download:

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: dist
    path: dist/
    retention-days: 7
```

Use artifacts for test reports, built binaries, or Terraform plans—not for large Docker images (push to a registry instead).

---

## 38.7 Environments, deployments, and approvals

**Environments** model deployment targets (staging, production) with optional rules:

- Required reviewers before job runs
- Wait timer (e.g., 5 minutes before prod deploy)
- Branch restrictions (only `main` deploys to prod)
- Environment-specific secrets

```yaml
jobs:
  deploy-prod:
    needs: test
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://app.example.com
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            github.rest.repos.createDeployment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.sha,
              environment: 'production',
              auto_merge: false,
              required_contexts: []
            })
      - run: ./deploy.sh production
```

The **deployments API** surfaces deployment history in the GitHub UI, linking commits to running releases.

---

## 38.8 Debugging and troubleshooting

| Problem | Diagnostic approach |
|---------|---------------------|
| Workflow not triggering | Check `on:` filters, branch names, path filters |
| Secret empty in fork PR | Expected behavior; use `pull_request_target` only with extreme care |
| Action version break | Pin SHA; read action changelog |
| Runner offline | Check self-hosted runner service, token expiry |
| Job queued forever | Org concurrency limits; no available runners |
| Expression errors | Enable debug logging: `ACTIONS_STEP_DEBUG: true` |

Enable workflow run logs retention in repo settings. Use **workflow visualization** in the Actions tab to inspect job graphs.

---

## 38.9 Chapter summary

- GitHub Actions workflows are event-driven YAML pipelines composed of jobs and steps on runners.
- Secure pipelines with scoped permissions, pinned actions, OIDC, and environment protection rules.
- Choose hosted runners for simplicity; self-hosted for private network access and custom tooling.
- Reusable workflows, matrix builds, caching, and artifacts scale CI across teams and tech stacks.

---

## 🧪 Lab 38.1 — Multi-environment deploy pipeline

1. Create `.github/workflows/deploy.yml` with jobs: `lint`, `test`, `build`, `deploy-staging`, `deploy-production`.
2. Configure a `staging` environment with no approval and `production` with required reviewer.
3. Add OIDC or repository secrets for your target cloud.
4. Use a matrix to test on Node 18 and 20.
5. Upload test coverage as an artifact; verify download after run.
6. Trigger via `workflow_dispatch` and confirm environment gates block production until approval.

---

## 🧪 Lab 38.2 — Self-hosted runner in Docker

1. Register a self-hosted runner in a test organization (or use a disposable repo).
2. Run the runner in a Docker container with label `docker-runner`.
3. Create a workflow targeting `runs-on: [self-hosted, docker-runner]` that accesses an internal mock service on `host.docker.internal`.
4. Document cleanup: remove runner registration and revoke token.

---

## Review questions

1. What is the difference between a **job**, a **step**, and an **action**?
2. Why should you prefer OIDC over storing AWS access keys in GitHub Secrets?
3. When would you choose a self-hosted runner over a GitHub-hosted runner?
4. Explain how `concurrency` groups prevent duplicate deploys.
5. What security risk does `pull_request_target` introduce, and when is it justified?
6. How do environment protection rules support Continuous Delivery without Continuous Deployment?
7. Describe two ways to share pipeline logic across multiple repositories.

---

*Continue: Chapter 39 — Jenkins Pipelines as Code*
