# Chapter 78: Practice Exam — Advanced

*DevOps Handbook — Pages 450–458 of this PDF edition*

Fifty multiple-choice questions covering Kubernetes, Terraform, SRE, and security. One best answer each. Explanations are part of the study material.

Pass guideline: **38/50** without notes. If you score high on Kubernetes but fail OIDC/IAM items, you are not “secure enough to operate prod.”

---

## 78.1 Kubernetes (Q1–Q18)

**Q1.** A Pod stays `Pending` with `FailedScheduling: 0/12 nodes available: insufficient memory`. The scheduler:

- A. Ignores requests
- B. Sums container **requests** (and some overhead) against node allocatable
- C. Uses limits only
- D. Uses the JVM `-Xmx`

**Answer: B.**

**Q2.** `CrashLoopBackOff` after a deploy. First log command:

- A. `kubectl logs --previous`
- B. `kubectl exec`
- C. `docker rm`
- D. `kubeadm reset`

**Answer: A.** Current container may have no useful logs yet.

**Q3.** Readiness probe failures cause:

- A. Immediate SIGKILL
- B. Removal from Service Endpoints while the container keeps running
- C. Node cordon
- D. etcd snapshot

**Answer: B.**

**Q4.** Liveness probe on a dependency (database ping) is dangerous because:

- A. It is required
- B. Dependency blips restart all pods, amplifying the outage
- C. Kubernetes forbids it
- D. It disables HPA

**Answer: B.**

**Q5.** PDB `minAvailable: 100%` with 1 replica:

- A. Improves HA
- B. Blocks voluntary drains (cluster upgrades stuck)
- C. Stops node crashes
- D. Replaces HPA

**Answer: B.** PDBs do not survive hardware death.

**Q6.** ClusterIP Service traffic is typically implemented by:

- A. A userspace proxy pod always
- B. kube-proxy programming iptables/ipvs/nft DNAT to pod IPs
- C. CoreDNS only
- D. Ingress only

**Answer: B.**

**Q7.** `image: myapp:latest` plus `imagePullPolicy: IfNotPresent` risks:

- A. Nothing
- B. Nodes keeping different cached images all named latest
- C. Faster rollbacks
- D. Admission always blocking

**Answer: B.**

**Q8.** HPA on CPU plus VPA auto-update on the same Deployment:

- A. Recommended
- B. Often conflicting (replica vs request fights)
- C. Required on EKS
- D. Replaces PDB

**Answer: B.**

**Q9.** NetworkPolicy with empty `podSelector: {}` in a namespace:

- A. Selects no pods
- B. Selects all pods in the namespace (for that policy’s selector semantics)
- C. Selects all cluster pods
- D. Disables CNI

**Answer: B.** Empty podSelector matches all pods in the namespace.

**Q10.** StatefulSet ordinal PVC: deleting a pod:

- A. Deletes PVC by default
- B. Keeps PVC; identity is stable
- C. Converts to Deployment
- D. Always loses data

**Answer: B.** (Unless you use the experimental auto-delete PVC policy.)

**Q11.** `automountServiceAccountToken: false` is useful when:

- A. You need more RBAC
- B. The app does not call the API; reduces stolen token risk
- C. You cannot use probes
- D. HPA breaks

**Answer: B.**

**Q12.** A mutating admission webhook timed out, `failurePolicy: Fail`. Effect:

- A. No effect
- B. API creates/updates that match the webhook can fail cluster-wide for those resources
- C. Only logs
- D. etcd sealed

**Answer: B.**

**Q13.** QoS Guaranteed means:

- A. No limits
- B. Requests equal limits for all containers
- C. BestEffort
- D. Burstable always

**Answer: B.**

**Q14.** `topologySpreadConstraints` vs required anti-affinity:

- A. Spread is usually gentler for even zonal placement
- B. Anti-affinity is always better
- C. They are identical
- D. Spread ignores zones

**Answer: A.**

**Q15.** `kubectl drain` respects:

- A. Involuntary hardware failure
- B. PDBs for voluntary eviction
- C. Nothing
- D. Only DaemonSets

**Answer: B.** DaemonSets are typically not evicted.

**Q16.** Headless Service (`clusterIP: None`):

- A. Load balances via kube-proxy ClusterIP
- B. DNS returns pod IPs (for STS identity)
- C. Requires Ingress
- D. Disables DNS

**Answer: B.**

**Q17.** `progressDeadlineSeconds` exceeded on a Deployment:

- A. Success
- B. Rollout marked failed (progressing condition)
- C. Cluster delete
- D. PDB delete

**Answer: B.**

**Q18.** Restricted Pod Security Admission blocks:

- A. `runAsNonRoot` + drop ALL
- B. Privileged, hostPath (typically), hostNetwork, etc.
- C. Resource requests
- D. ConfigMaps

**Answer: B.**

---

## 78.2 Terraform (Q19–Q30)

**Q19.** Remote state locking exists to:

- A. Encrypt S3
- B. Prevent concurrent applies corrupting state
- C. Replace IAM
- D. Speed plans

**Answer: B.**

**Q20.** Putting `provider "aws"` inside every child module:

- A. Best practice
- B. Makes aliasing and region passing painful; prefer inherit from root
- C. Required
- D. Disables count

**Answer: B.**

**Q21.** `terraform import` :

- A. Destroys the resource
- B. Maps existing cloud object into state
- C. Formats HCL
- D. Rotates keys

**Answer: B.**

**Q22.** Changing a `force-new` attribute (e.g., some RDS) without care:

- A. In-place update always
- B. Destroy/create — data loss risk
- C. No-op
- D. Only tags

**Answer: B.**

**Q23.** `moved` blocks:

- A. Move cloud resources between accounts magically
- B. Tell Terraform a resource address renamed without destroy
- C. Replace backends
- D. Skip locking

**Answer: B.**

**Q24.** Workspaces vs separate state dirs:

- A. Workspaces always safer
- B. Separate dirs/backends give clearer blast radius for prod
- C. Identical
- D. Workspaces encrypt better

**Answer: B.**

**Q25.** Sensitive outputs:

- A. Are omitted from all logs forever
- B. Are redacted in some UI but still in state — protect the state file
- C. Cannot exist
- D. Disable plans

**Answer: B.**

**Q26.** `count = 0` on a module:

- A. Illegal
- B. Removes all resources in that module from this config
- C. Pauses billing only
- D. Locks state

**Answer: B.**

**Q27.** Policy as code (Checkov/OPA) in CI should fail on:

- A. Color of tags
- B. Public RDS, open 0.0.0.0/0 SSH, unencrypted volumes (as policy dictates)
- C. `fmt` only
- D. Provider version pins

**Answer: B.** (fmt is separate.)

**Q28.** `prevent_destroy` lifecycle:

- A. Stops `plan`
- B. Errors apply that would destroy that resource
- C. Prevents `fmt`
- D. Replaces backup

**Answer: B.**

**Q29.** Two roots reading each other’s state can deadlock if:

- A. They use locking on apply only — actually apply order must be DAG; circular remote state is a design smell
- B. Terraform forbids remote state
- C. S3 versioning
- D. KMS rotation

**Answer: A.** Avoid cycles; publish via SSM or a dedicated data account.

**Q30.** Pinning module `version = "2.4.1"` :

- A. Prevents all bugs
- B. Reproducible consumes; upgrade is an explicit PR
- C. Disables outputs
- D. Required by HCL

**Answer: B.**

---

## 78.3 SRE (Q31–Q40)

**Q31.** Error budget for 99.9% monthly availability is about:

- A. 1 minute
- B. 43 minutes
- C. 1 day
- D. Zero

**Answer: B.**

**Q32.** A good SLI for an interactive API:

- A. Node CPU
- B. Fraction of successful requests faster than a threshold
- C. Number of commits
- D. Pod count

**Answer: B.**

**Q33.** Multi-window multi-burn-rate alerting is designed to:

- A. Page on every blip and ignore slow burns
- B. Catch fast catastrophic burns and slow leaks without excessive noise
- C. Replace all dashboards
- D. Maximize tickets

**Answer: B.**

**Q34.** When error budget is exhausted, SRE typically:

- A. Ships more features
- B. Freeze risky launches; invest in reliability
- C. Delete SLOs
- D. Disable monitoring

**Answer: B.**

**Q35.** MTTR optimization without MTTD:

- A. Is complete
- B. Still leaves users failing until you notice
- C. Replaces SLIs
- D. Is DORA lead time

**Answer: B.**

**Q36.** Load shedding should:

- A. Drop health checks first
- B. Protect critical paths; fail low-priority work
- C. Never return 503
- D. Increase retries without jitter

**Answer: B.**

**Q37.** Blameless postmortem still requires:

- A. No owners
- B. Action items with owners
- C. HR punishment
- D. Deleting logs

**Answer: B.**

**Q38.** Retry storms are reduced by:

- A. Synchronized immediate retries
- B. Jittered backoff, retry budgets, idempotency
- C. Removing timeouts
- D. Larger HPA max only

**Answer: B.**

**Q39.** SLO of 100%:

- A. Best practice
- B. Impossible/impractical; infinite cost; no error budget for change
- C. Required for finance
- D. Same as 99.999%

**Answer: B.**

**Q40.** Chaos experiments require:

- A. Prod database drop on day one
- B. Hypothesis, observability, abort, small blast radius
- C. No buy-in
- D. Disabling alerts

**Answer: B.**

---

## 78.4 Security (Q41–Q50)

**Q41.** IRSA / workload identity beats node instance roles because:

- A. It is slower
- B. Permissions bind to a specific ServiceAccount, not every pod on the node
- C. It disables AWS
- D. It replaces NetworkPolicy

**Answer: B.**

**Q42.** Base64 in Kubernetes Secret YAML in Git is:

- A. Encryption
- B. Encoding only — treat as plaintext
- C. HSM
- D. Signed

**Answer: B.**

**Q43.** Tight OIDC `sub` condition should include:

- A. `*` for all repos
- B. Exact repository and ref or environment
- C. Only `aud`
- D. The org name only

**Answer: B.**

**Q44.** `pull_request_target` with untrusted checkout is dangerous because:

- A. It is slow
- B. The workflow runs in the base repo context and may expose secrets
- C. It cannot clone
- D. GitHub forbids Actions

**Answer: B.**

**Q45.** First action on a leaked AWS access key:

- A. Rewrite git history
- B. Disable/revoke the key
- C. Tweet
- D. Rotate after the weekend

**Answer: B.**

**Q46.** SBOM helps you:

- A. Page faster
- B. Inventory components for CVE response
- C. Replace tests
- D. Resize PVCs

**Answer: B.**

**Q47.** Privileged pods + hostPath + docker.sock is a:

- A. Hardening pattern
- B. Container escape / node takeover pattern
- C. Required for HPA
- D. PSA restricted default

**Answer: B.**

**Q48.** etcd encryption at rest:

- A. Makes Git Secrets safe
- B. Protects Secrets on disk/backups of the control plane, not from RBAC-authorized API reads
- C. Replaces TLS
- D. Disables audit

**Answer: B.**

**Q49.** Least privilege for a deploy SA in one namespace:

- A. `cluster-admin`
- B. Role with create/patch on needed resources in that namespace
- C. Node IAM `*`
- D. `system:masters`

**Answer: B.**

**Q50.** Defense in depth for a public API:

- A. Only WAF
- B. WAF + TLS + authn/z in app + NetworkPolicy + least-privilege IAM + supply-chain signing
- C. Only VPC
- D. Security groups without auth

**Answer: B.**

---

## 78.5 Answer grid

| Q | Ans | Q | Ans | Q | Ans | Q | Ans | Q | Ans |
|---|-----|---|-----|---|-----|---|-----|---|-----|
| 1 | B | 11 | B | 21 | B | 31 | B | 41 | B |
| 2 | A | 12 | B | 22 | B | 32 | B | 42 | B |
| 3 | B | 13 | B | 23 | B | 33 | B | 43 | B |
| 4 | B | 14 | A | 24 | B | 34 | B | 44 | B |
| 5 | B | 15 | B | 25 | B | 35 | B | 45 | B |
| 6 | B | 16 | B | 26 | B | 36 | B | 46 | B |
| 7 | B | 17 | B | 27 | B | 37 | B | 47 | B |
| 8 | B | 18 | B | 28 | B | 38 | B | 48 | B |
| 9 | B | 19 | B | 29 | A | 39 | B | 49 | B |
| 10 | B | 20 | B | 30 | B | 40 | B | 50 | B |

---

## 78.6 Study notes for common traps

**Pending vs CrashLoop.** Pending never ran; CrashLoop ran and died. Different tools.

**PDB vs HA.** PDB is for planned disruption. One replica + PDB = freeze upgrades, not magic availability.

**Terraform destroy.** Any unexpected destroy in prod plan is a stop-the-line event.

**OIDC wildcards.** `repo:org/*:*` is how “read-only” roles become account takeovers.

**SLI honesty.** CPU is not user happiness. HTTP 200 is not “no double charge.”

Re-take this exam after finishing the YAML catalog, Terraform catalog, and security chapters in this handbook. The goal is to **explain the distractors**, not memorize B.

---

## 78.7 Scenario set (short answer practice)

Write four-sentence answers, then compare:

**S1.** etcd disk latency is 20ms p99, API `LIST pods` is slow. What do you stop doing first?  
Model: stop watch/list storms, check controllers, fix disk; do not “add replicas of the app.”

**S2.** Terraform plan replaces `aws_db_instance`. You need a parameter change.  
Model: do not apply; check `apply_immediately` vs maintenance; use replica/blue-green if replacement is required.

**S3.** Error budget 10% remaining, 20 days left, a feature wants a schema drop.  
Model: refuse drop; expand/contract; the budget is for unknown risk, not known reckless DDL.

**S4.** A GitHub `sub` of `repo:acme/*:ref:refs/heads/*`.  
Model: any repo any branch; attacker PR on a public repo may still be blocked *unless* `pull_request_target` or secrets on forks; still too wide for prod roles.

---

## 78.8 Kubernetes numeric trivia worth knowing

| Fact | Typical default / value |
|------|-------------------------|
| terminationGracePeriodSeconds | 30 |
| progressDeadlineSeconds | 600 |
| ndots in pods | 5 |
| CrashLoop backoff | exponential, capped (~5 min) |
| HPA default CPU | 80% in older examples; always set explicitly |

Do not memorize every API field; do memorize the ones that cause outages when left default.

---

## 78.9 Mapping misses to chapters

| Miss cluster | Study |
|--------------|--------|
| Pending / probes / PDB | 73 |
| State / replace / lock | 74 |
| SLO / burn / retries | 47, 75 |
| OIDC / IRSA / SA | 51, 76.6 |

Retake only the missed domain (18 K8s questions) before a full 50. Advanced exams punish **half-remembered defaults**.
