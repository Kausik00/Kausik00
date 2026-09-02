# Chapter 71: DevOps Interview Questions

*DevOps Handbook — Pages 381–391 of this PDF edition*

This chapter is a working interview kit, not a trivia list. Each question includes a **model answer**, what interviewers are actually probing, and follow-ups you should be ready for. Treat the answers as outlines: speak them in your own words, then deepen with a story from a system you have operated.

Use this chapter in three modes:

1. **Cold drill** — cover a question, speak for 90 seconds, then compare to the model.
2. **Whiteboard** — pick architecture questions and draw the system first.
3. **Panel rehearsal** — mix Linux, Kubernetes, CI/CD, SRE, and security in one sitting.

| Domain | Question range | Typical interviewer |
|--------|----------------|---------------------|
| Linux & systems | Q1–Q20 | Platform / SRE |
| Kubernetes | Q21–Q40 | Platform / DevOps |
| CI/CD | Q41–Q55 | DevOps / staff engineer |
| SRE & reliability | Q56–Q70 | SRE / engineering manager |
| Security | Q71–Q85 | Security / platform |

---

## 71.1 How interviewers score answers

Most DevOps interviews reward **trade-off reasoning** more than memorized flags. A strong answer has four layers:

| Layer | Example |
|-------|---------|
| Direct answer | “I would use a RollingUpdate with a PDB of `minAvailable: 1`.” |
| Why | “So we never drop below one ready replica during node drains.” |
| Failure mode | “If the new image fails readiness, the rollout stalls instead of taking the last pod.” |
| Experience | “We hit this when kubelet restarts coincided with a deploy; PDB saved us.” |

Weak answers stop at tools. Strong answers name **signals, blast radius, and rollback**.

---

## 71.2 Linux and operating systems (Q1–Q20)

**Q1. A server is at 100% CPU. How do you find the cause?**

Model answer: Start with `uptime` or `top` to distinguish load average vs CPU. `mpstat -P ALL 1` shows per-core saturation and `%iowait`. Identify the process with `top`/`htop` (shift-P) or `pidstat -u 1`. If user CPU is high, sample with `perf top` or `py-spy`/`pprof` depending on language. If `%wa` is high, it is storage, not compute—switch to `iostat -xz 1` and `iotop`. Always note whether the spike is one core (single-threaded app) or all cores (fork bomb, noisy neighbor, crypto miner).

Follow-up: How do you tell steal time on a VM? Look at `%st` in `top`/`vmstat`; high steal means the hypervisor is oversubscribed.

**Q2. Explain load average on Linux.**

Load average is the exponential moving average of runnable plus uninterruptible processes (D state, usually I/O). On a 4-CPU box, load 4.0 means the run queue is roughly fully utilized; load 8.0 means a backlog. Compare 1/5/15 minute numbers to see if the spike is rising or decaying. Load can be high with idle CPU if many tasks are in uninterruptible I/O.

**Q3. A process is in D state. What does that mean and what do you do?**

Uninterruptible sleep, almost always waiting on I/O or an NFS/RPC call. You cannot `kill -9` it until the kernel call returns. Identify the syscall with `ps -o pid,stat,wchan:32,cmd` or `cat /proc/<pid>/stack`. Check disks (`dmesg`, SMART), NFS `df -h` hangs, and iSCSI. Last resort is reboot or unmount after isolating the mount.

**Q4. Difference between `kill`, `kill -9`, and `kill -15`.**

Default `kill` sends SIGTERM (15): the process can catch it, flush, and exit. SIGKILL (9) cannot be caught; the kernel tears the task down. Prefer TERM, wait, then KILL. Sending KILL to PID 1 or to a JVM without a chance to dump can leave WAL/index files dirty.

**Q5. How does Linux OOM killer choose a victim?**

Each process has `oom_score` derived from memory use and `oom_score_adj`. Higher score is killed first. You can protect critical agents with `oom_score_adj=-1000` (use sparingly). Diagnose with `dmesg | grep -i oom` and cgroup memory.current vs max. In Kubernetes this maps to the QoS class and the node-pressure eviction, then OOM.

**Q6. Explain cgroups vs namespaces.**

Namespaces isolate what a process *sees* (PID, mount, net, UTS, IPC, user, cgroup, time). cgroups limit what a process *can consume* (CPU, memory, io, pids). Containers are both plus a union filesystem and a runtime. A process can be namespaced without cgroup limits (dangerous) or limited without isolation.

**Q7. Walk through diagnosing a disk-full production host.**

`df -h` for filesystem capacity, `df -i` for inodes (tiny files). `du -xhd1 /` to find directories, then `find /var -xdev -size +100M`. Check deleted-but-open files: `lsof +L1` or `lsof | grep '(deleted)'`—restart the writer or truncate via `/proc/<pid>/fd/N`. Logrotate misconfig and container overlay growth are common. Never `rm` blindly under `/var/lib/docker` or `/var/lib/kubelet`.

**Q8. What is inodes exhaustion?**

A filesystem can have free bytes but zero inodes. Typical on mail spools, session files, or millions of npm cache files. `df -i`, then `find dir -xdev | wc -l`. Fix by deleting many small files, or recreate the FS with more inodes if this is a known pattern.

**Q9. Explain `strace` vs `lsof` vs `tcpdump`.**

`strace` traces syscalls of a process (open, read, connect). `lsof` lists open files/sockets. `tcpdump` captures packets on an interface. Use strace for “why is this stuck?”, lsof for “what is holding this port/file?”, tcpdump for “what is on the wire?”. On production, prefer `perf`, eBPF (`bpftrace`), or a short strace with `-p` and `-e trace=network`.

**Q10. How do you find which process holds port 443?**

```bash
ss -lntp | grep ':443'
# or
lsof -iTCP:443 -sTCP:LISTEN
```

On older boxes `netstat -lntp`. In containers, the listener may be in another netns; `nsenter` or check the ingress/node-proxy.

**Q11. systemd: a service fails to start. How do you debug?**

`systemctl status foo.service`, `journalctl -u foo.service -b --no-pager`. Check `WantedBy`, `After=`, `ConditionPathExists`, and `ProtectSystem`. Run the `ExecStart` manually as the service user. `systemd-analyze verify` and `systemd-delta`. For restart loops, look at `StartLimitBurst` and `Restart=always`.

**Q12. What is the difference between `/etc/hosts`, nsswitch, and DNS?**

Name resolution order is `nsswitch.conf` (`files dns ...`). `/etc/hosts` is the files database. DNS is queried via resolvers in `/etc/resolv.conf` (often stubbed by systemd-resolved). A wrong nsswitch or a search domain can make “it works on my laptop” failures. `getent hosts name` uses NSS; `dig` bypasses NSS and talks DNS directly—this distinction is a common interview trap.

**Q13. Explain ulimits and why a Java service dies with “too many open files”.**

`ulimit -n` / `nofile` caps FDs per process. systemd `LimitNOFILE=` overrides. Each socket, file, and JAR is an FD. Raise limits *and* find leaks (`lsof -p PID | wc -l` over time). In containers, both the container runtime and the app must be aligned.

**Q14. How does Linux routing work at a high level?**

Packets match the routing table (`ip route`) longest-prefix, then policy routing (`ip rule`) if present. Local delivery vs forward depends on `ip_forward`. NAT is netfilter (`iptables`/`nft`) in POSTROUTING/PREROUTING. Cloud metadata routes and VPC CNI add extra tables—always dump `ip rule` and `ip route show table all`.

**Q15. What is a TIME_WAIT socket and why can you run out?**

After a TCP closer, the socket stays TIME_WAIT for 2*MSL to absorb delayed segments. High connection churn (short HTTP/1.0, health checks) can exhaust ephemeral ports. Mitigate with keep-alive, HTTP/2, connection pooling, `net.ipv4.ip_local_port_range`, and only carefully `tcp_tw_reuse`. Do not enable `tcp_tw_recycle` (removed; broke NAT).

**Q16. How do you inspect kernel logs after a panic or OOM?**

`journalctl -k -b -1` for previous boot, `dmesg -T`, pstore/`/var/crash` if kdump is enabled. For repeated hung tasks, look at `blocked for more than 120 seconds` and the call trace.

**Q17. Explain setuid, capabilities, and why you should avoid setuid binaries.**

setuid runs as file owner (often root). Capabilities split root into bits (`CAP_NET_BIND_SERVICE`, `CAP_SYS_ADMIN`). Prefer file capabilities or systemd `AmbientCapabilities=` over setuid. Audit with `find /usr -perm -4000`.

**Q18. How do you measure disk latency?**

`iostat -xz 1` (`await`, `svctm` obsolete, use `aqu-sz` and `%util`). `iotop -oPa`. `bpftrace`/`biosnoop`. Application-level: fsync latency histograms. On cloud, EBS burst credits and gp2 vs gp3 matter.

**Q19. What is the difference between hard and soft links?**

Hard link: another directory entry to the same inode, same filesystem, cannot link directories (normally). Soft link: a path string, can dangle, can cross filesystems. Deleting the original name does not delete data until link count is 0.

**Q20. Walk through a network namespace debug for a container that cannot reach the internet.**

Check veth pair, bridge/cni IP, default route inside the netns (`ip netns exec` or `nsenter -t PID -n ip r`), iptables MASQUERADE on the host, `rp_filter`, and DNS (`/etc/resolv.conf` copied at start). `tcpdump -i vethXXX` vs host eth0 tells you if packets leave the ns.

---

## 71.3 Kubernetes (Q21–Q40)

**Q21. A Pod is stuck in Pending. How do you debug?**

`kubectl describe pod` Events: insufficient CPU/memory, PVC unbound, node selector/taint mismatch, PVC in another zone, or `PriorityClass`. `kubectl get events --sort-by=.lastTimestamp`. Check scheduler logs only if describe is silent. For PVC: StorageClass, topology, and CSI driver health.

**Q22. CrashLoopBackOff vs Error vs ImagePullBackOff.**

CrashLoop: container starts then exits; backoff delay increases. Look at `kubectl logs --previous`. ImagePullBackOff: registry auth, tag, or network. Error: often init container or admission. Always check init containers separately.

**Q23. Explain requests vs limits.**

Requests: scheduler + CPU proportional share + QoS. Limits: cgroup hard cap; CPU throttling, memory OOM. Unset limits can starve neighbors; requests >> actual waste capacity. Burstable QoS is common; Guaranteed is for latency-critical.

**Q24. How does a Service of type ClusterIP work?**

API object + Endpoints/EndpointSlice. kube-proxy programs iptables/ipvs or nft to DNAT ClusterIP:port to a pod IP. Traffic never hits a userspace “service process” in iptables mode. Headless (`clusterIP: None`) returns pod IPs via DNS for StatefulSets.

**Q25. Ingress vs Gateway API vs Service Mesh.**

Ingress: L7 HTTP routing via an ingress controller. Gateway API: role-oriented CRDs (Gateway, HTTPRoute) with richer matching. Mesh (Istio/Linkerd): sidecar or ambient data plane for mTLS, retries, observability between services. Do not install a mesh “for retries” if an Ingress + HPA would do.

**Q26. How do rolling updates actually work?**

Deployment creates a new ReplicaSet, ramps `maxSurge`/`maxUnavailable`. Readiness gates pod eligibility. If the new pods never become ready, rollout hangs (good). `kubectl rollout status` and `rollout undo`. For StatefulSet, updates are ordinal by default (`RollingUpdate` partition).

**Q27. What is a PDB and when does it block a drain?**

PodDisruptionBudget constrains *voluntary* disruptions (drain, cluster upgrade). It does not stop node crashes. `minAvailable`/`maxUnavailable`. If you set `minAvailable: 100%` with one replica, drains deadlock. Always test `kubectl drain --dry-run=server`.

**Q28. HPA vs VPA vs KEDA.**

HPA scales replica count on CPU/memory/custom metrics. VPA recommends or sets request/limit (can evict). KEDA scales on events (queue depth, cron) including to/from zero. Combining HPA+VPA on the same metric is a classic footgun.

**Q29. How do you debug DNS inside a cluster?**

`kubectl run tmp --rm -it --image=busybox -- nslookup kubernetes.default`. Check CoreDNS pods, `kube-dns` service, ndots:5 causing extra search lookups, and NetworkPolicy dropping 53. `tcpdump` on CoreDNS. Node local DNS cache is a common production pattern.

**Q30. NetworkPolicy default-deny: what breaks?**

DNS, kubelet probes if they rely on extra hops, ingress controller to pods, and cross-namespace metrics scrapes. Start with allow DNS + same-namespace + ingress from ingress-nginx namespace. Test with a canary namespace.

**Q31. Explain taints, tolerations, affinity.**

Taints repel pods unless they tolerate. Node affinity attracts to labeled nodes. Pod affinity/anti-affinity place relative to other pods (spread vs colocate). Topology spread constraints are preferred over brittle anti-affinity for HA.

**Q32. StatefulSet vs Deployment.**

StatefulSet: stable identity, ordinal PVC, ordered start/stop. Use for Kafka, ZooKeeper, etcd-like. Deployment: interchangeable replicas. Never put a leader-elected database on a Deployment with a shared PVC.

**Q33. What happens when a node dies?**

kubelet heartbeats fail; node goes NotReady. After `pod-eviction-timeout` (legacy) / taint manager `node.kubernetes.io/unreachable`, pods are rescheduled. PVCs may be zone-locked. Sessions die unless you designed for it. `--pod-eviction-timeout` is not instantaneous; plan SLOs accordingly.

**Q34. How do you safely run a Job that must not double-run?**

`ttlSecondsAfterFinished`, `backoffLimit`, `parallelism: 1`, `completions: 1`, idempotent work, and a lease/lock in the app. For cron, `concurrencyPolicy: Forbid`. Watch clock skew and missed schedules on API downtime.

**Q35. RBAC: a deploy pipeline cannot create Ingress. How do you grant least privilege?**

Role/RoleBinding in the target namespace on `ingresses` in `networking.k8s.io`. Prefer Role over ClusterRole. Bind a dedicated ServiceAccount used by the CI kubeconfig. Audit with `kubectl auth can-i create ingresses --as=system:serviceaccount:ci:deployer -n prod`.

**Q36. etcd is slow. Symptoms and first checks?**

API latency, watch storms, slow list of large objects. Check etcd fsync latency, disk, fragmentations (`etcdctl endpoint status`), and huge CRDs. Avoid kubectl loops listing all pods cluster-wide every second.

**Q37. Init containers vs sidecars vs native sidecars.**

Init: run to completion before app. Sidecar: long-running helper (proxy, log shipper). Native sidecars (restartable init) start first and stay. Order and shared volumes matter for secrets hydration.

**Q38. How do you handle secrets in Kubernetes without putting them in Git?**

External Secrets Operator / CSI secrets store pulling from Vault/AWS SM, sealed-secrets, or SOPS. Never base64 in YAML committed to Git (base64 is not encryption). Rotate by updating the external secret and rolling pods if they do not watch.

**Q39. Probe design: liveness vs readiness vs startup.**

Liveness: kill if stuck (use sparingly; a false fail causes restart storms). Readiness: remove from Service. Startup: delay liveness for slow JVM. Probe the real dependency carefully—probing the DB from every pod can DDoS the DB.

**Q40. Multi-tenant cluster isolation—how far can namespaces go?**

Namespaces + RBAC + NetworkPolicy + ResourceQuota + LimitRange + PodSecurity admission. Not a hard security boundary for hostile tenants; use separate clusters or gVisor/Kata for untrusted code. Quote: namespaces are administrative, not a VM.

---

## 71.4 CI/CD (Q41–Q55)

**Q41. Design a CI pipeline for a containerized API.**

Stages: lint/unit → SAST/SCA → build (multi-stage, SBOM) → image scan → sign (cosign) → push digest (not `:latest`) → deploy to preview env → integration tests → promote to staging → prod with change ticket and canary. Cache dependencies; pin actions by SHA.

**Q42. Why pin GitHub Actions to a SHA?**

Tags like `@v4` can move. A compromised action tag supplies attacker code with your secrets. Pin `uses: actions/checkout@<sha>` and use Dependabot to update.

**Q43. GitOps vs push-from-CI.**

GitOps (Argo CD/Flux): cluster agents pull desired state from Git; Git is the source of truth; drift detection. Push: CI kubeconfigs apply YAML. GitOps is better for audit and multi-cluster; CI push is simpler for a single cluster. Hybrid: CI builds images, GitOps deploys by digest.

**Q44. How do you prevent a bad image from reaching production?**

Admission: Kyverno/OPA checking signature, signed digest, no `:latest`, required labels, resource requests. Registry immutability. Environment promotion of the *same digest*. Automated rollback on SLO burn.

**Q45. What is a deployment strategy you would pick for a stateful checkout service?**

Not a naive all-at-once Deployment. Prefer blue/green or canary with session stickiness or fully stateless checkout tokens. DB migrations expand-contract. Feature flags for payment paths. PDB + HPA. If using Kafka, drain consumers before killing pods.

**Q46. Jenkins vs GitHub Actions vs GitLab CI.**

Jenkins: flexible, you run the metal, plugin risk. GHA: SaaS convenience, org security depends on OIDC and fork PRs. GitLab: integrated registry/environments. Choose based on identity, secret model, and who patches runners.

**Q47. How do CI runners stay secure?**

Ephemeral VMs/containers per job, no shared `/var/run/docker.sock` for untrusted PRs, OIDC to cloud instead of long-lived keys, network egress allowlists, and separate privileged builders. Fork PRs must not get production secrets.

**Q48. Explain artifact vs image vs chart promotion.**

Build once. Promote the immutable artifact (container digest, Helm chart version pointing at that digest) through environments. Rebuilding per environment causes “works in staging” drift.

**Q49. How do you test infrastructure changes in CI?**

`terraform fmt`, `validate`, `tflint`, `checkov`/`tfsec`, plan against a persistent test workspace, and policy (OPA). Apply to a sandbox account. Never auto-apply prod without human approval and a plan file.

**Q50. Trunk-based vs GitFlow for DevOps teams.**

Trunk-based with short-lived PRs and feature flags maps to high DORA performance. GitFlow long-lived release branches delay integration. Use GitFlow only if you must support multiple shipped versions (embedded).

**Q51. What are DORA metrics and how can they be gamed?**

Deployment frequency, lead time, CFR, MTTR. Gaming: tiny dummy deploys, ignoring failed canaries, redefining “incident”. Pair with customer SLIs.

**Q52. Canary analysis—what do you look at?**

Error ratio, latency histograms, saturation, business KPIs (checkout conversion), and logs for new exceptions. Statistical comparison to baseline, not a single CPU chart. Automated (Flagger/Argo Rollouts) with a manual abort.

**Q53. How do you handle database migrations in CI/CD?**

Expand/contract, backward-compatible deploys, migration job *before* or *with* expand, never drop columns in the same release that stops writing them. Locking: use `migrate` tools with advisory locks. Run against a production-sized clone in staging.

**Q54. Secret scanning in CI.**

Pre-commit + server-side (GitHub secret scanning, gitleaks, trufflehog). Rotate immediately on leak. Block the merge. Educate that `.env` in Docker build context is a leak.

**Q55. Why is `:latest` a production incident waiting to happen?**

Tags move. Two nodes can run different binaries. Rollbacks become guesswork. Always deploy by digest `image@sha256:...`.

---

## 71.5 SRE and reliability (Q56–Q70)

**Q56. SLO vs SLI vs SLA vs error budget.**

SLI: quantitative measure of user happiness (availability, latency). SLO: target on that SLI. SLA: legal/commercial promise, usually looser. Error budget: `1 - SLO`, the allowed unreliability for change. When budget is burned, freeze features.

**Q57. Pick SLIs for a payments API.**

Availability: non-5xx and non-timeouts for `POST /charge` excluding client 4xx except 429 if you own throttling. Latency: p99 < 300ms excluding known batch endpoints. Freshness if async. Do not use CPU as an SLI.

**Q58. How do you implement error-budget alerting (multiwindow, multi-burn)?**

Google SRE: alert on burn rate over short and long windows so you catch fast burns and slow leaks without paging on blips. Example: 14.4x burn over 1h and 6h, plus 6x over 6h and 3d.

**Q59. Incident command: you are the first responder. What do you do?**

Declare severity, page IC if needed, start a dedicated channel, mitigate first (rollback, increase capacity, fail over), communicate timestamps, preserve evidence, hand off. Do not debug in the customer Twitter thread.

**Q60. MTTR vs MTTD vs MTTA.**

Detect, acknowledge, restore. Optimizing restore with bad detection still hurts users. Instrument the full timeline in the postmortem.

**Q61. When is a rollback safer than a roll-forward?**

When the change is the likely cause, rollback is practiced, and schema is compatible. Roll-forward when rollback is impossible (one-way migration) or the bug is environmental. Practice both.

**Q62. Thundering herd and retry storms.**

Clients retry in sync after a blip, multiplying load. Use jittered exponential backoff, retry budgets, circuit breakers, and idempotency keys. Load-test retries, not just happy path.

**Q63. Capacity planning vs autoscaling.**

Autoscaling handles *known* diurnal patterns with headroom; it cannot provision cloud quotas, IP space, or DB connections instantly. Plan peaks (launches) with pre-warming and load tests.

**Q64. What is saturation as a golden signal?**

Utilization of a constrained resource: thread pools, DB connections, CPU, queue depth. High saturation precedes latency and errors. Graph saturation next to latency.

**Q65. Postmortem: blameful vs blameless.**

Blameless: inspect systems, incentives, and missing guardrails. Still assign *owners for actions*. A blameless culture that never ships action items is theater.

**Q66. How do you SLO a batch pipeline?**

Freshness (data not older than X), completeness (% expected rows), and correctness samples. Alert on watermark lag, not on pod restarts.

**Q67. Load shedding.**

When overloaded, drop or degrade low-priority work to save the core path. Return 503 with Retry-After. Protect auth and payments. Practice it; accidental shedding of health checks is a self-DDoS.

**Q68. Why is “pager fatigue” a reliability problem?**

Noisy pages train people to ignore the pager. Then the real page is missed. SLO-based paging, runbook links, and inhibition rules are part of the product.

**Q69. Chaos engineering in an interview.**

Hypothesis, small blast radius, observability in place, abort conditions, game days. Do not start with killing the database in prod. Netflix’s principles: experiment to learn, not to punish.

**Q70. You have 99.9% monthly availability SLO. How many minutes is that?**

30 days ≈ 43,200 minutes; 0.1% ≈ 43.2 minutes. Interviewers like you to know 99.9 ≈ 43 min/month, 99.99 ≈ 4.3 min, 99.95 ≈ 22 min.

---

## 71.6 Security (Q71–Q85)

**Q71. Least privilege for a deploy role in AWS.**

No `*:*`. Scope to ECR push of specific repos, EKS `eks:DescribeCluster` plus a Kubernetes SA mapped via IRSA, not a static `AWS_ACCESS_KEY` on the runner. CloudTrail on. Access analyzer.

**Q72. What is IRSA / workload identity?**

Pod ServiceAccount bound to an IAM role via OIDC. Tokens are projected and rotated. Beats node instance roles which grant every pod on the node the same AWS power.

**Q73. Supply chain: what is an SBOM and provenance?**

SBOM (CycloneDX/SPDX) lists components. SLSA provenance says how/where it was built. Sign both. Admission verifies signature before the cluster runs the image.

**Q74. How do you respond to a leaked cloud key in GitHub?**

Revoke/disable the key first (containment), then rotate dependents, git history purge is secondary to revocation, CloudTrail for usage, incident ticket, and secret scanning org-wide. Assume compromise of anything the key could do.

**Q75. Container escape mental model.**

Privileged pods, docker.sock mounts, hostPath, CAP_SYS_ADMIN, kernel vulns. Mitigate: PodSecurity restricted, no privileged, read-only rootfs, drop caps, seccomp, user namespaces. Keep nodes patched.

**Q76. NetworkPolicy vs Security Group vs WAF vs Mesh mTLS.**

Different layers. SG: cloud L3/L4. NP: in-cluster L3/L4 (implementation dependent). WAF: HTTP exploits at edge. mTLS: service identity. Defense in depth; none replaces authn/z in the app.

**Q77. Dependency scanning vs SAST vs DAST.**

SCA: known CVEs in libraries. SAST: source patterns. DAST: running app attacks. You need all three plus secrets scanning. Prioritize by exploitability and internet exposure, not CVSS alone.

**Q78. How do you store TLS certificates?**

ACM or cert-manager with DNS-01, short-lived certs, automated rotation. Private keys never in Git. Monitor expiry (`ssl_expire` checks). For mTLS internal, SPIFFE/SPIRE or mesh.

**Q79. Log4Shell-style incident: first 24 hours.**

Inventory (SBOM, image grep), patch or WAF virtual patch, rotate creds that the app could leak, hunt logs for exploit strings, rebuild images, communicate. Do not wait for a perfect inventory to start WAF rules.

**Q80. Explain OIDC in CI for cloud auth.**

The IdP (GitHub) signs a JWT; cloud verifies `aud`/`sub` (repo, branch, environment). No long-lived keys. Misconfigured `sub` wildcards are the usual hole.

**Q81. Kubernetes admission controllers you would enable.**

PodSecurity (restricted), deny privileged, deny `:latest`, require requests, deny hostNetwork, image verification. Start in warn/audit then enforce.

**Q82. What is a confused deputy in CI?**

A pipeline with high privilege is tricked (malicious PR, poisoned cache) into using those privileges. Separate privileged release jobs from PR CI.

**Q83. Encryption at rest vs in transit vs application-level.**

Disk/volume encryption (EBS, etcd encryption), TLS, and envelope encryption of fields (KMS). etcd secret encryption config is not a substitute for not putting secrets in etcd if you can avoid it.

**Q84. How do you audit who kubectl-exec’d into prod?**

API audit logs, `exec` verb, SIEM, break-glass roles with reason annotation, and session recording if required. Disable exec in prod if policy says so; use ephemeral debug pods with approval.

**Q85. Zero-trust for internal microservices—practical version.**

Authenticate every request (mTLS or JWT), authorize per action, no flat VPC trust, least privilege network, and device/workload identity. It is a direction, not a product SKU.

---

## 71.7 Behavioral and system-design prompts

**Q86. Tell me about a production outage you caused or witnessed.**

STAR: situation, your role, mitigation, customer impact, lasting change (test, alert, runbook). Interviewers listen for ownership and *system* fixes, not heroics.

**Q87. Design CI/CD + Kubernetes for a 20-person product org.**

Sketch: monorepo or polyrepo, build once, GitOps, two clusters (nonprod/prod) or one cluster with strong tenancy, platform team owns golden paths, developers ship via paved road. Mention cost, IAM, and observability as first-class.

**Q88. A deploy increased p99 latency 3x but error rate is flat. What now?**

Not a no-op. Check saturation, GC, lock contention, N+1 queries, noisy neighbor, region imbalance, and canary size. Roll back if error budget burn on latency SLO.

**Q89. How do you onboard a new service to the platform?**

Template: Dockerfile, Helm/Kustomize, SLO dashboard, alerts, NetworkPolicy, HPA, PDB, runbook stub, on-call, data classification. Self-service via a portal beats wiki pages.

**Q90. Conflict: developers want cluster-admin in prod.**

Explain blast radius and audit. Offer namespace admin, break-glass with time-bound bindings, and better self-service (logs, port-forward alternatives). Escalate to policy, not a hallway yes.

---

## 71.8 Hands-on / live terminal questions

Expect to share a screen and:

```bash
# Find the noisest process
ps aux --sort=-%cpu | head
# Why is this disk full?
df -hT; df -i
# Who talks to Postgres?
ss -tnp | grep 5432
# Kubernetes
kubectl get pods -A --field-selector=status.phase!=Running
kubectl describe pod -n prod PAYMENT
kubectl logs -n prod PAYMENT --previous --tail=200
```

Practice talking while typing. Silence looks like guessing.

---

## 71.9 Model “deep dive” answers (condensed)

**Deep dive A — Kubernetes networking path for `curl http://orders/api` from a pod**

DNS: CoreDNS via `nameserver` in resolv.conf, search `svc.cluster.local`. ClusterIP: kube-proxy DNAT to pod IP. CNI routes or overlays to the node. Return path must symmetric (conntrack). NetworkPolicy evaluated. If Istio, sidecar intercepts outbound. This story, told clearly, beats listing CNI product names.

**Deep dive B — Linux page cache vs application memory**

`free -h`: available includes reclaimable cache. Do not panic because “used” looks high. `vmtouch`/`cachestat`. Databases often bypass with O_DIRECT. Mixing page cache and container limits without understanding eviction causes mysterious I/O storms.

**Deep dive C — Terraform state race**

Two pipelines apply without locking: state drift, duplicate resources, or lost resources. Remote backend + DynamoDB/blob lease lock, serialized applies per workspace, and CI concurrency groups.

---

## 71.10 Cheat sheet of numbers interviewers like

| Fact | Value |
|------|--------|
| 99.9% monthly downtime | ~43 minutes |
| 99.99% | ~4.3 minutes |
| Default Kubernetes terminationGracePeriod | 30s |
| DNS ndots default in pods | 5 |
| TCP TIME_WAIT | typically 60s on Linux |
| HTTP 429 vs 503 | client vs server overload semantics |

---

## 71.11 Study plan for two weeks before interviews

| Day | Drill |
|-----|--------|
| 1–2 | Linux: processes, systemd, networking, strace |
| 3–4 | Kubernetes: schedule, Service, Ingress, probes, RBAC |
| 5 | Terraform state, modules, IAM |
| 6 | CI: GitHub Actions OIDC, image promotion |
| 7 | SLO math, incident command |
| 8 | Security: IRSA, supply chain, NP |
| 9 | Whiteboard two architectures |
| 10 | Mock panel with mixed questions |
| 11 | Weak-topic repair |
| 12 | Rest and light command drills |
| 13 | Behavioral stories written down |
| 14 | Sleep, do not cram new tools |

Record yourself. Filler words drop when you use the four-layer answer: answer, why, failure mode, story.

---

## 71.12 Closing

Interviews are compressed operations: can you **debug under uncertainty**, **choose a reversible action**, and **communicate**. The 90 questions above cover the surface area of a mid-to-senior DevOps/SRE loop. Pair this chapter with the Linux encyclopedia, YAML catalog, and incident runbooks in this part so your examples stay concrete.
