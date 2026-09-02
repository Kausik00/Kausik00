# Chapter 80: Capstone — 12-Week Production-Like Platform Lab

This capstone is a **week-by-week build** of a production-shaped platform: AWS-like networking, Kubernetes, GitOps, observability, identity, and a small business app with SLOs. It is the practice counterpart to Chapter 59’s design-only capstone. You will operate what you build: break it, page yourself, and write the postmortem.

**Scenario: ShopStream lab.** A checkout API, a catalog API, Postgres, and a worker that writes orders to a queue. One “platform team” (you) and one “app team” (also you, wearing a different hat).

| Attribute | Lab target |
|-----------|------------|
| Availability SLO | 99.5% on lab hours (generous; still measure) |
| Latency SLO | p99 `< 400ms` on `GET /catalog` from in-cluster |
| Security | No long-lived cloud keys in Git; restricted PSA |
| Delivery | Image digest + GitOps |
| Cost | Destroy at end of week if using paid cloud; or kind + local stacks |

You may run **track A (cloud)** on a personal AWS account with budget alarms, or **track B (local)** with `kind` + Terraform against `kind`/`k3d` and Docker Compose Postgres. The weekly *outcomes* are the same; commands differ.

Do not skip weeks 1–2. Unstable Linux/Git hygiene will haunt week 8.

---

## 80.1 Rules of the lab

1. **Everything in Git** except live secrets. Use SOPS or a cloud secret manager.
2. **One change per PR** to the env repo after week 4.
3. **No `:latest` in any cluster you call “prod.”**
4. **Write a runbook stub** the same day you add a service.
5. **Budget cap.** AWS: `$` hard limit, `aws budgets`, and a destroy script.
6. **Timebox.** ~8–12 focused hours per week. Park extras on a `stretch/` branch.

Definition of done for the whole capstone: another engineer can clone the repos, follow README, and reach a green synthetic check without Slack-you.

---

## 80.2 Repository layout (create in week 1)

```
shopstream-platform/          # infra + cluster addons + GitOps root
  modules/                    # vpc, eks, rds or kind
  live/lab/
  clusters/lab/               # Argo apps
shopstream-apps/
  catalog/
  checkout/
  worker/
  charts/ or kustomize/
shopstream-runbooks/
  sev.md
  cpu.md
  ...
```

CI: GitHub Actions or GitLab CI on both platform and apps.

---

## 80.3 Week 1 — Foundations, identity, and the “prod” laptop

**Goals.** Reproducible shell, Git workflow, secrets discipline, lab journal.

**Build.**

- Install: `kubectl`, `helm`, `terraform`, `jq`, `yq`, `cosign` (or plan to), `kustomize`.
- Create a `lab` AWS user **or** decide kind-only. Enable MFA.
- Write `JOURNAL.md`: date, hours, what broke.
- Git: trunk-based, `main` protected locally with a personal rule: no direct commits after week 2.

**Exercises.**

```bash
# Prove you can inspect a host
uname -a; df -h; ss -lntp | head
# Git
git config --global init.defaultBranch main
```

**Deliverable.** README in `shopstream-platform` stating track A/B, region, and budget.

**Stretch.** Age/SOPS key generated; documented recovery if the key is lost (print QR to a password manager).

---

## 80.4 Week 2 — Networking and a tiny “VPC”

**Track A.** Terraform VPC module from Chapter 74: 2 AZs minimum (3 if budget allows), private + public subnets, NAT (single NAT OK for lab), flow logs optional.

**Track B.** Document the `kind` network: extra port mappings, a local registry.

**Exercises.**

```bash
terraform -chdir=live/lab init
terraform -chdir=live/lab plan
# After apply:
aws ec2 describe-nat-gateways --query 'NatGateways[].State'
# kind:
kind create cluster --name shopstream --config kind.yaml
```

**Deliverable.** Diagram (mermaid in README) of subnets and what is public.

**Failure drill.** Remove a route to NAT (or docker network) and watch image pulls fail. Restore. Write five lines in the journal: symptom, cause, fix.

---

## 80.5 Week 3 — Kubernetes baseline

**Goals.** Cluster + node group (or kind nodes) + `kubectl` as yourself, not as cluster-admin for apps.

**Build.**

- EKS 1.29+ or kind.
- Install: metrics-server, a StorageClass that works.
- Namespaces: `platform`, `shop`, `monitoring`.
- PSA labels: `restricted` on `shop` (fix your manifests until they pass).

```bash
kubectl apply -f namespaces.yaml
kubectl cluster-info
kubectl get nodes -o wide
```

**Deliverable.** A `hello` Deployment in `shop` with securityContext from Chapter 73, Service, and `curl` via port-forward.

**Stretch.** Install Calico/Cilium NetworkPolicy and prove default-deny breaks DNS, then fix.

---

## 80.6 Week 4 — CI for apps: build, scan, push digest

**Goals.** Catalog service is a 50-line HTTP app (Go or Python) returning JSON products.

**Pipeline.**

1. Unit test
2. Docker build (multi-stage)
3. Trivy/Grype scan (fail on CRITICAL)
4. Push `ghcr.io/YOU/catalog@sha256:...`
5. Open a PR in the GitOps repo **or** update a kustomize digest (manual this week is OK)

```yaml
# sketch
- uses: docker/build-push-action@SHA
  with:
    push: true
    tags: ghcr.io/org/catalog:${{ github.sha }}
```

Then retag by digest in the deploy manifest.

**Deliverable.** Passing CI on `main`; image in registry; pod running that digest.

**Anti-goal.** Do not deploy with `latest`. If you did, redo the week.

---

## 80.7 Week 5 — GitOps and environments

**Install.** Argo CD or Flux in `platform`.

**Apps.** `catalog` Application pointing at `shopstream-apps/deploy/lab`.

**Rules.**

- Argo auto-sync on `lab`; **manual sync** if you add a fake `prod` later.
- `kustomize build` in CI must match what Argo applies (`argocd app diff`).

**Deliverable.** Change a ConfigMap in Git → synced in ≤ 3 minutes. Screenshot or log snippet in JOURNAL.

**Drill.** `kubectl edit deploy` in cluster (cowboy). Watch GitOps revert. Feel the lesson.

---

## 80.8 Week 6 — Data store, secrets, migrations

**Build.** RDS Postgres (or Compose). Checkout API with `DATABASE_URL` from Secrets Manager / ExternalSecret / SOPS.

**Migration Job** from Chapter 73: `backoffLimit: 1`, image digest **same** as app.

```bash
kubectl -n shop create job --from=cronjob/migrate manual-1  # if you used CronJob
# or apply Job YAML
kubectl -n shop logs job/checkout-migrate
```

**Deliverable.** Expand-only migration (`ALTER TABLE ... ADD COLUMN`) then app using the column. Document rollback (column unused).

**Drill.** Scale checkout to 10 with pool 20 against `max_connections=50` and watch it burn. Fix pool math. This *is* case study 4 in miniature.

---

## 80.9 Week 7 — Ingress, TLS, DNS

**Build.** Ingress controller, cert-manager or mkcert for lab, hostname `catalog.lab.example.test` (nip.io or `/etc/hosts`).

**Monitoring.** A blackbox/synthetic curl from outside the cluster (GitHub scheduled workflow or local cron) hitting **HTTPS**.

```bash
curl -I https://catalog.YOUR_HOST/healthz
openssl s_client -connect catalog.YOUR_HOST:443 </dev/null 2>/dev/null | openssl x509 -noout -dates
```

**Deliverable.** Certificate expiry alert (even if a Prometheus rule you only test with a fake `abs(expiry - now) < 10y` inverted in a unit test, plus a real dashboard).

**Drill.** Point the synthetic at HTTP by mistake; confirm your week-7 self would have missed CivicPass (Chapter 76). Fix the probe.

---

## 80.10 Week 8 — Observability and SLOs

**Stack.** kube-prometheus-stack **or** Grafana Cloud free tier. App exposes `/metrics`.

**SLIs.**

```promql
sum(rate(http_requests_total{app="catalog",status!~"5.."}[5m]))
/
sum(rate(http_requests_total{app="catalog"}[5m]))
```

**Alerts.** One SLO burn (even a simple `error_ratio > 2% for 10m`) and one saturation (`CPU > 85%`).

**Deliverable.** Grafana dashboard: golden signals + Postgres connections. Alert that fires when you `chmod` a bad image or `raise` in a handler.

**Trace stretch.** OpenTelemetry sidecar or library; one trace from Ingress to DB.

---

## 80.11 Week 9 — HPA, PDB, NetworkPolicy, load

**Build.** HPA CPU 70%, min 2, max 6. PDB `minAvailable: 1`. NetworkPolicy: DNS + Postgres + ingress namespace only.

**Load.**

```bash
hey -z 2m -c 20 https://catalog.YOUR_HOST/items
k6 run load.js
```

**Deliverable.** Graph of replicas vs latency. A short write-up: did you hit the DB first or the app?

**Drain drill.**

```bash
kubectl drain NODE --ignore-daemonsets --delete-emptydir-data
```

Confirm PDB blocks if you drain too aggressively; fix replica count.

---

## 80.12 Week 10 — Identity, supply chain, policy

**Build.**

- IRSA or kube2iam-free equivalent: checkout reads only its secret.
- Kyverno/Gatekeeper: deny `:latest`, require `runAsNonRoot`.
- Cosign sign in CI; admission verify **or** a CI check that the digest is signed (lab-honest).

**OIDC for CI.** GitHub → cloud role with `sub` = **this repo + refs/heads/main** only.

**Deliverable.** A PR from a feature branch **cannot** apply prod Terraform. Document the trust policy.

**Attack-lite (authorized, your lab).** Create a workflow on a dummy repo that *would* have matched `repo:org/*`. Show the JWT `sub` in logs. Then tighten.

---

## 80.13 Week 11 — Incidents, chaos, runbooks

**Runbooks.** Copy Chapter 75 templates into `shopstream-runbooks` and fill **your** command names.

**Game day (90 min).**

1. Kill CoreDNS replicas → 1.
2. Deploy a 500-loop handler; use GitOps rollback.
3. Fill a node disk with a junk Job (carefully, not overlay).
4. Rotate a “leaked” dummy token.

**Deliverable.** One postmortem using the blameless template. Include timeline from Grafana and Git.

**SEV table.** Define SEV-3 vs SEV-2 for a lab with no real customers (hint: SLO burn + data loss still SEV-1 even in lab if you drop the database).

```bash
# chaos lite
kubectl -n kube-system scale deploy/coredns --replicas=1
```

Restore immediately after notes.

---

## 80.14 Week 12 — Hardening, cost, demo, teardown

**Hardening checklist.**

| Item | Pass? |
|------|-------|
| No cluster-admin kubeconfig in Git | |
| Restricted PSA on shop | |
| NetworkPolicy on checkout | |
| Backups: RDS snapshot or `pg_dump` to object storage | |
| Restore tested once | |
| Budget dashboard | |
| README for a stranger | |
| Destroy script `make down` | |

**Demo (20 min recording or live).**

1. PR to catalog → CI → GitOps → metrics
2. Rollback
3. Show SLO dashboard
4. Show a NetworkPolicy deny (from a debug pod)

**Teardown.**

```bash
terraform -chdir=live/lab destroy
kind delete cluster --name shopstream
```

Confirm cloud bill is zero-ish after 48h. Snapshots you forget are the classic leftover cost.

**Write the final architecture** (one page) and three things you would do in week 13 (multi-cluster, service mesh, or real multi-account). Do **not** start them until the teardown and journal are done.

---

## 80.15 Rubric (self-grade)

| Area | 0 | 1 | 2 |
|------|---|---|---|
| Reproducibility | Works only on your laptop | README + scripts | Stranger can boot lab |
| Delivery | SSH kubectl apply | CI builds | GitOps digest |
| Reliability | No SLO | Dashboard | Alert + game day |
| Security | Keys in Git | Secrets manager | OIDC + policy + PSA |
| Ops | No notes | Journal | Runbooks + postmortem |

**Ship the capstone** if you score ≥ 8/10. Below that, repeat the weakest week.

---

## 80.16 Suggested daily cadence inside a week

| Block | Time | Work |
|-------|------|------|
| Plan | 20 min | Write the week’s success test |
| Build | 3–5 h | Implement |
| Break | 1 h | Inject one failure |
| Write | 45 min | JOURNAL + runbook + README |
| Idle | overnight | Let GitOps/CI run; read logs in the morning |

Skipping “Break” produces a portfolio that has never been paged.

---

## 80.17 Minimal app specs

**catalog.** `GET /items`, `GET /healthz`, `GET /readyz` (ready if config loaded), `/metrics`.

**checkout.** `POST /orders` with idempotency key header; writes to Postgres; 503 if pool wait > 200ms.

**worker.** Reads a table or queue; no public Ingress.

All three: non-root, read-only rootfs, probes, PDB, requests/limits.

---

## 80.18 Common ways this capstone fails

| Failure | Fix |
|---------|-----|
| Week 12 is the first Git commit | You built a snowflake; start over from week 4 with Git |
| Terraform in the same repo as app with `apply` on every push | Split pipelines; lock state |
| kind in week 3, EKS in week 12, nothing matches | Pick a track and stay |
| Observability only `kubectl logs` | You cannot SLO |
| Never restored a backup | You do not have a backup |
| Cluster-admin for the app SA | Redo week 10 |

---

## 80.19 Mapping weeks to handbook chapters

| Week | Chapters |
|------|----------|
| 1 | Linux encyclopedia, Git |
| 2 | Terraform catalog, VPC |
| 3–5 | YAML catalog, CI |
| 6–7 | Secrets, Ingress |
| 8–9 | Prometheus, HPA, incidents |
| 10 | Security, OIDC |
| 11 | Runbooks, case studies |
| 12 | Capstone design (ch. 59) + this lab |

---

## 80.20 After the twelve weeks

You now have evidence: repos, dashboards, a postmortem, and a destroy script. That packet is stronger in interviews than a list of certifications. Take Chapter 71 questions and answer them **using this platform** (“In my lab, PDB blocked drain because…”).

If you continue, the next platform increment is **multi-environment promotion of the same digest** (lab → staging → prod) with a human approval on prod GitOps, not a new Dockerfile. That single rule prevents half the outages in Chapter 76.

Stop here, teardown, and rest. A platform you cannot destroy cleanly is not yet a platform.

---

## 80.21 Week-by-week acceptance tests (copy into CI later)

| Week | Command or check that must pass |
|------|----------------------------------|
| 1 | `git status` clean; JOURNAL has an entry |
| 2 | `terraform plan` after apply is empty |
| 3 | `kubectl get ns shop` and hello pod Ready |
| 4 | registry digest referenced in YAML equals CI digest |
| 5 | App auto-sync Healthy in Argo/Flux |
| 6 | `POST /orders` persists a row; migrate Job Succeeded |
| 7 | `echo \| openssl s_client` shows not-expired cert |
| 8 | Grafana shows request rate; a test alert fired once |
| 9 | Drain of one node keeps catalog Ready ≥ 1 |
| 10 | Kyverno/Gatekeeper denies a privileged pod in shop |
| 11 | Postmortem file exists with timestamps |
| 12 | `make down` or terraform destroy completes; budget ticket closed |

If you cannot automate a check, write it as a checklist in the PR template. Capstones die when “done” is a feeling.

---

## 80.22 Pairing and time estimates

Solo: 8–12 hours/week is honest if you already know Docker. If Kubernetes is new, week 3–5 may take 15 hours; steal hours from stretch goals, not from journals.

Pair: split platform vs app hats explicitly. The “app” person is not allowed cluster-admin. That constraint is the point.

---

## 80.23 Sample `kind.yaml` (track B)

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: shopstream
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
        protocol: TCP
      - containerPort: 443
        hostPort: 8443
        protocol: TCP
  - role: worker
  - role: worker
```

Ingress on kind needs a documented extra overlay (kind’s ingress-nginx instructions). Do not pretend kind is EKS: no IRSA unless you mock it; still implement PSA, NetworkPolicy, and GitOps so weeks 8–11 remain valid.

---

## 80.24 Closing certification (optional, for you)

Print this and sign it:

> I operated ShopStream lab for twelve weeks. I can roll back a digest, restore a database snapshot, explain my OIDC `sub`, and destroy the environment. I will not put `:latest` in production.

The signature is silly; the capabilities are not. Chapter 71 interviewers are listening for those four sentences with details only someone who **built the path** can provide.
