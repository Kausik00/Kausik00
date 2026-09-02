# Chapter 67: Production CI/CD Patterns

*DevOps Handbook — Workbook*
---

## 67.1 Pipelines as a product, not a folder of YAML

Production CI/CD is judged by **lead time, failure rate, recovery, and security of the supply chain**—not by how many actions are green. This workbook covers reusable workflows, OIDC to clouds, deployment environments and approvals, matrix builds, caching that does not leak, and supply-chain controls that survive an auditor and an incident.

Chapters 37–42 introduced pipeline design, GitHub Actions, Jenkins, GitLab, deployment strategies, and DORA. Here we treat the **platform CI** that fifty application teams consume.

| Pattern | Outcome |
|---------|---------|
| Reusable workflows / templates | One CVE fix in the template, not 200 copy-pastes |
| OIDC federation | No long-lived cloud keys in GitHub secrets |
| Environments | Prod is a named gate, not a branch name |
| Matrix | Coverage without sequential hours |
| Cache | Faster CI that does not serve poisoned artifacts |
| Supply chain | Provenance, signing, dependency review |

---

## 67.2 Reusable workflows and the contract with application teams

Copy-paste YAML is the enemy. The platform team publishes **versioned** workflows.

```yaml
# org/.github/workflows/go-ci.yml (in a central repo)
name: Go CI
on:
  workflow_call:
    inputs:
      go-version:
        type: string
        default: '1.22'
      working-directory:
        type: string
        default: '.'
    secrets:
      # avoid; prefer OIDC
      FOO:
        required: false
```

Consumer:

```yaml
jobs:
  ci:
    uses: acme/platform-workflows/.github/workflows/go-ci.yml@v3
    with:
      go-version: '1.22.5'
    permissions:
      id-token: write
      contents: read
```

**Pin to a tag or SHA**, not `@main`. `@main` means every consumer silently changes on Friday. SemVer the workflow repo like Terraform modules (Chapter 64).

### 67.2.1 Required contract fields

Document for each reusable workflow:

- Required `permissions:` (least privilege)
- Which OIDC roles it assumes
- Cache keys and eviction
- How to pass `working-directory` for monorepos
- Break-glass inputs (`skip_scan` with ticket ID—default false)

### 67.2.2 Composite actions vs reusable workflows

| | Composite action | Reusable workflow |
|--|------------------|-------------------|
| Runs in | Caller job | Separate jobs |
| Secrets | Inherits awkwardly | Explicit `secrets:` |
| Matrix | Caller controls | Nested limitations |
| Billing | Same job minutes | Extra jobs |

Use composites for **install CLI**; use reusable workflows for **standard CI/CD graphs** (lint → test → scan → build → push → deploy).

### 67.2.3 GitLab CI includes and Jenkins libraries

```yaml
# .gitlab-ci.yml
include:
  - project: 'acme/ci-templates'
    ref: v4.2.0
    file: '/go.yml'
```

Jenkins: `library 'platform@v4.2.0'`—same versioning rule. **Never** `@master` for prod CD.

Organization-level **required workflows** (GitHub) enforce scanners even if an app deletes local YAML. That is a feature, not a surprise, when communicated.

---

## 67.3 OIDC: clouds, registries, and the death of static keys

OpenID Connect federation lets the CI platform prove **who is running** (repo, ref, environment) to AWS STS, GCP WIF, Azure federated credentials, Vault, or Google WIF.

```yaml
# GitHub Actions
permissions:
  id-token: write
  contents: read
steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/gha-deploy-prod
      aws-region: us-east-1
```

Trust policy sketch (AWS):

- `token.actions.githubusercontent.com` as IdP
- Condition `sub` like `repo:acme/shop:ref:refs/heads/main` **or** `repo:acme/shop:environment:production`
- Prefer **environment** subject over branch: feature branches must not assume prod roles

**GitLab:** `CI_JOB_JWT` is legacy; use **id_tokens** in `.gitlab-ci.yml` with aud matching the cloud.

**Jenkins:** OIDC is possible via plugins; many orgs still use a single cloud key. Treat that as **debt** with a rotation drill (Chapter 69).

### 67.3.1 Failure modes

| Failure | Cause |
|---------|--------|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | Subject mismatch (fork PRs have different `sub`) |
| Fork PR deploys prod | Trust too broad (`repo:acme/*`) |
| Role too wide | CI can `iam:*` |
| Token audience mismatch | `aud` not in provider |
| Clock skew | runner NTP |

**Pull requests from forks** should never get `id-token` to prod. Use `pull_request_target` only with extreme care (it runs in the **base** repo context—classic injection).

---

## 67.4 Environments, protection rules, and progressive delivery

GitHub Environments, GitLab Environments, and Jenkins “production” gates encode:

- Required reviewers
- Wait timer
- Restricted branches
- Environment secrets (different from repo secrets)
- Deployment branches / tags only

```yaml
jobs:
  deploy:
    environment:
      name: production
      url: https://shop.example.com
    runs-on: ubuntu-latest
    steps:
      - name: helm upgrade
        run: helm upgrade --install shop ./chart -n prod
```

**Concurrency:**

```yaml
concurrency:
  group: deploy-prod-shop
  cancel-in-progress: false   # never cancel a prod apply
```

Cancelling a Terraform apply or Helm upgrade mid-flight is how you get half-migrated state (Chapter 64). For CI **tests**, `cancel-in-progress: true` is correct.

**Promotion artifact:** deploy the **same image digest** that passed staging, not a restage rebuild.

```bash
# good
helm upgrade shop ./chart --set image.tag=sha256:abc123...

# bad
docker build && push :prod   # new untested bits
```

Tie to Chapter 41: environment `staging` auto-deploy; `production` canary then full via Argo Rollouts or a second job with approval.

---

## 67.5 Matrix builds: coverage versus explosion

```yaml
strategy:
  fail-fast: false
  matrix:
    go: ['1.21', '1.22']
    os: [ubuntu-latest, macos-latest]
    include:
      - go: '1.22'
        os: ubuntu-latest
        race: true
    exclude:
      - go: '1.21'
        os: macos-latest
```

**fail-fast: true** hides the second OS failure. Production CI usually wants **all cells** reported.

**Explosion:** 4 languages × 3 OS × 5 shards = budget death. Split:

- PR: fast matrix (current language, linux)
- Nightly: full matrix
- Release tag: full + sign

**Dynamic matrix** from a changed-path script in monorepos (Chapter 63) so a docs-only PR does not compile 80 Go modules.

```json
{ "include": [ { "service": "billing" }, { "service": "checkout" } ] }
```

Guard the generator: a bug that returns **empty matrix** can skip tests and still go green. Fail if the matrix is empty when changes exist.

---

## 67.6 Caching: speed without poisoning

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/go-build
    key: go-${{ runner.os }}-${{ hashFiles('**/go.sum') }}
    restore-keys: |
      go-${{ runner.os }}-
```

Rules:

1. **Key on lockfiles**, not on `**/*.go` alone (too unique; never hit).
2. **Do not cache `node_modules` from untrusted PRs** into a key shared with main.
3. **Separate caches** per environment if credentials could leak into cache (rare but real with sloppy scripts writing `.env` into the cache path).
4. **GHA cache is not an artifact registry.** Do not cache Docker layers as a substitute for a registry; use registry + BuildKit cache exporters to GHCR.
5. **Poisoning:** a compromised PR that writes to a restore-key prefix used by `main` is a known class. Prefer `hashFiles` exact keys for `main`; restrict cache write permissions on forks.

GitLab `cache:` with `key: files` is the same idea. Jenkins `stash` is not a cache; it is a copy—do not stash `node_modules` across untrusted jobs.

**Bazel remote cache / sccache / Gradle remote:** authenticate writers; treat the cache as **infrastructure** with ACLs.

---

## 67.7 Runners: hosted, self-hosted, and ephemeral

| Runner | Risk |
|--------|------|
| GitHub-hosted | Shared CPU; supply of actions marketplace |
| Persistent self-hosted | Dirty workspace, leftover Docker, secret residue |
| Ephemeral (Actions Runner Controller, GitLab Kubernetes executor) | Preferred for prod CD |

Hardening persistent runners: wipe workspaces, no docker.sock unless isolated, don’t use the same runner for untrusted PRs and prod deploy.

**ARC (Actions Runner Controller)** on Kubernetes: scale to zero, ephemeral pods, but you now debug **pending runner pods** (Chapter 66) when CI queues.

---

## 67.8 Supply chain in the pipeline (practical)

Chapter 52 covers SBOM and Sigstore theoretically. Production CI implements:

```yaml
- name: Build
  run: docker build -t ghcr.io/acme/shop:${{ github.sha }} .

- name: SBOM
  run: syft ghcr.io/acme/shop:${{ github.sha }} -o spdx-json > sbom.json

- name: Scan
  run: grype sbom:sbom.json --fail-on high

- name: Sign
  run: cosign sign --yes ghcr.io/acme/shop@${{ steps.digest.outputs.digest }}

- name: Attest
  run: cosign attest --predicate sbom.json --type spdxjson ...
```

**SLSA provenance:** `actions/attest-build-provenance` or Lattos/GitLab provenance. Store attestations next to the image.

**Dependency review / Dependabot / renovate:** block merge on new `critical` CVE in lockfile. Pin Actions to SHA:

```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

SHA pins still need **renovation**. A tag can move; a SHA cannot.

**Secrets scanning** in CI (gitleaks, GitHub secret scanning) on every PR.

**Hermetic builds:** GOPROXY=off with vendored modules, or a verified proxy. Non-hermetic “go get latest” is not a production build.

---

## 67.9 Monorepo CI orchestration

- Path filters (Chapter 63)
- One reusable workflow per language
- A **merge queue** that runs the union of affected pipelines
- Artifact promotion via an internal **OCI registry**, not Git LFS

**Required checks** must be **dynamic** (GitHub check suites per directory) or you will require billing tests on a docs PR. Tools: `kodiak`, merge queues, or a single `ci-orchestrator` that reports a synthetic check `platform/ci-complete`.

---

## 67.10 Worked incident: OIDC role too wide + cache poison scare

**Event:** A contractor’s fork PR was able to assume a role that could `s3:PutObject` on the production Terraform state bucket because the trust policy was `repo:acme/*`.

**Response:** Tighten `sub` to `repo:acme/infra:environment:production`. Disable `id-token` on `pull_request` from forks. Rotate the role session… **cannot rotate past credentials that were not long-lived**, but **audit CloudTrail** for AssumeRoleWithWebIdentity from unexpected `sub`. Enable GitHub OIDC `environment` gating.

**Cache:** A separate finding showed `restore-keys: node-` allowed a PR to populate a prefix later used by main. Switched to exact keys + `scope` per workflow + no cache write on fork events.

---

## 67.10.1 Release evidence pack

Every production deploy job should upload an **evidence bundle** as a build artifact (retention aligned with compliance):

- Git SHA, workflow run URL, actor, environment
- Image digest(s) and cosign verify output
- SBOM filename and scanner exit codes
- Terraform plan summary or Helm diff
- Change ticket ID (required input)

This is what auditors and incident commanders ask for. If it only exists in a Slack message, it is gone in ninety days.

---

## 67.11 Observability of CI itself

CI is a production system. Export:

- Queue time, run time, failure rate (DORA **change failure** needs CI signal)
- Runner utilization
- Cache hit ratio
- Deploy job duration vs SLO (Chapter 68)

Alert when **prod deploy job** is queued > 15 minutes (frozen runner pool) or when **required check** is stuck (merge deadlock).

---

## 🧪 Lab 67.1 — Reusable workflow pin

1. Create a caller workflow that `uses: ./` local reusable file.
2. Add an input `message`.
3. Change the reusable file in a branch; show that `@main` callers move and `@sha` callers do not (simulate with two refs).
4. Write a VERSIONING.md for the workflow repo.

---

## 🧪 Lab 67.2 — OIDC trust conditions (paper + IAM simulator)

1. Draft an AWS trust policy that allows only `environment:production` from one repo.
2. List three `sub` values that must **fail** (fork, feature branch, another repo).
3. If you have a sandbox AWS account, create the IdP and prove a failed assume from a dummy token claim set (or GitHub environment dry-run).

---

## 🧪 Lab 67.3 — Matrix empty-fail

1. Write a job that builds a matrix JSON from `git diff`.
2. Force empty output.
3. Add a step that **fails** if `matrix.include` is empty **and** `github.event` is a PR that touches `services/**`.
4. Confirm docs-only PR still skips safely.

---

## 🧪 Lab 67.4 — Cache key hygiene

1. Cache `~/.npm` with a sloppy `restore-keys: npm-`.
2. Explain a poisoning scenario in writing.
3. Replace with exact `hashFiles('package-lock.json')` and fork protection notes.

---

## 🧪 Lab 67.5 — Sign a local image (kind/cosign)

1. `cosign sign-blob` or sign a kind-loaded image in a lab.
2. Verify with `cosign verify`.
3. Attach an SBOM attest. Record the digest that would be deployed.

---

## 67.12 Anti-patterns

| Anti-pattern | Replace with |
|--------------|--------------|
| `uses: org/action@v1` floating minor | SHA pin + renovate |
| Static AWS keys in GitHub | OIDC |
| Rebuild on prod | Promote digest |
| `cancel-in-progress` on Terraform | Concurrency without cancel |
| One 40-minute job | Matrix + caches + path filters |
| Deploy from fork PR | Environment + OIDC conditions |
| Unpinned reusable `@main` | Tagged platform workflows |
| Cache the world | Lockfile keys, no secrets in path |

---

## 67.13 Jenkins and GitLab notes (parity)

**Jenkins:** credentials binding + folder per environment; scripted `when { environment name: 'prod' }`; shared library version pins; avoid “anonymous trigger of prod.” Use GitHub/GitLab Branch Source with **trusted** vs **untrusted** PRs.

**GitLab:** `rules:`, `environment:production` with `protected`, `id_tokens`, `cache:key:files`, `needs:` DAGs, **release** resource, and **CI_JOB_TOKEN** allowlists so jobs cannot fetch arbitrary private packages.

The patterns are the same: **identity, promotion, pinning, isolation of untrusted code**.

---

## Review questions

1. Why pin reusable workflows to a tag/SHA rather than `@main`?
2. Compare composite actions and reusable workflows for a deploy graph with approvals.
3. Write an OIDC `sub` condition that prevents fork PRs from deploying production.
4. Why is `pull_request_target` dangerous?
5. When must `cancel-in-progress` be false?
6. How can an empty matrix cause a false-green PR?
7. Describe a cache poisoning path with `restore-keys` prefixes.
8. Why deploy by digest instead of by mutable tag `prod`?
9. What GitHub Environment features map to “protected deploy”?
10. List four supply-chain controls that belong **in CI** versus **in cluster admission** (Chapter 69).

---

## Further practice

Combine with Chapters 38–40 for syntax, 41 for rollout, 52 for SLSA theory, and 64 for Terraform OIDC apply. Production CI is the glue.
