# Chapter 79: Expanded Glossary

*DevOps Handbook — Pages 459–472 of this PDF edition*

Two hundred DevOps, SRE, platform, and cloud-native terms with **precise** definitions as used in this handbook. Alphabetized. Cross-references use *italics*.

If a vendor uses a word differently, the handbook meaning still applies in exams and runbooks.

---

## A–B

**Admission controller.** Kubernetes plugin that intercepts API requests after authn/z and may mutate or reject objects (e.g., Pod Security, webhooks).

**Affinity (pod/node).** Scheduling rules attracting pods to nodes or to other pods; contrast *anti-affinity* and *topology spread*.

**AMI.** Amazon Machine Image: template for EC2 instances (OS + snapshot + block mappings).

**Anti-affinity.** Scheduling rule that *spreads* pods so they do not share a topology domain.

**API server (kube-apiserver).** Front door of the Kubernetes control plane; all cluster state changes go through it to *etcd*.

**Apdex.** Ratio of satisfied vs tolerated vs frustrated requests based on a latency threshold; a coarse happiness index.

**Apply (Terraform).** The operation that makes real infrastructure match a plan; uses *state* and *locks*.

**Argo CD.** GitOps controller that reconciles Kubernetes objects from Git.

**Artifact.** Immutable build output (container digest, binary, package) promoted across environments.

**ASG.** Auto Scaling Group: AWS construct that maintains EC2 capacity.

**Audit log (K8s).** Record of API requests; required to know who `exec`’d or mutated RBAC.

**Autoscaling.** Automatic change of replica or node count from metrics; not a substitute for *capacity planning*.

**Availability zone (AZ).** Isolated datacenter-like domain in a cloud region; failure unit for HA design.

**Backend (Terraform).** Storage for *state* (S3, GCS, Terraform Cloud) plus optional locking.

**Backpressure.** Mechanism by which a system slows intake when downstream is saturated (*load shedding* is a form).

**Base image.** Container image a Dockerfile starts `FROM`; part of the *supply chain*.

**Blast radius.** The set of users/systems a failure or privilege can affect; minimize on purpose.

**Blue/green.** Two environments; switch traffic when green is healthy. Contrast *canary*, *rolling*.

**Build once, promote.** CI principle: the same *artifact* moves through test → prod without rebuild drift.

**Burn rate.** How fast an *error budget* is consumed relative to the SLO window.

**Burstable QoS.** Kubernetes class when requests ≠ limits; can be OOM-killed before *Guaranteed*.

---

## C

**CALMS.** Culture, Automation, Lean, Measurement, Sharing — a DevOps heuristic.

**Canary.** Gradual production exposure of a new version with comparison metrics.

**Capability (Linux).** Fine-grained privilege bit (e.g., `CAP_NET_BIND_SERVICE`) replacing parts of root.

**Capacity planning.** Human/process design of peaks, quotas, and pool sizes; complements autoscaling.

**cgroup.** Linux control group: resource accounting and limits; containers rely on it.

**Change fail rate (CFR).** DORA: fraction of deploys causing incidents/rollbacks.

**Chaos engineering.** Controlled experiments that test hypotheses about resilience.

**CI.** Continuous Integration: automatically build and test every change.

**CIDR.** Classless Inter-Domain Routing notation (`10.0.0.0/16`) for IP blocks.

**Circuit breaker.** Stop calling a failing dependency for a cooldown to avoid *retry storms*.

**ClusterIP.** Default Kubernetes *Service* type: virtual IP load-balanced in-cluster.

**CNI.** Container Network Interface: plugin that gives pods IPs and routes.

**ConfigMap.** Kubernetes object for non-secret configuration data.

**Conntrack.** Kernel connection tracking table used by NAT/firewall; can exhaust under churn.

**Container runtime.** Software that runs containers (containerd, CRI-O); kubelet talks CRI.

**Control plane.** The brains (API, scheduler, controllers, etcd) vs *data plane* (nodes/pods).

**Cosign.** Tool to sign and verify container images (Sigstore).

**CronJob.** Kubernetes controller that creates *Jobs* on a schedule.

**CSI.** Container Storage Interface: plugins for volumes.

**CVE.** Common Vulnerabilities and Exposures identifier for a published flaw.

**CWE.** Common Weakness Enumeration: class of software weakness.

---

## D

**DaemonSet.** Ensures a pod on (selected) nodes; used for agents (logs, CNI, node-exporter).

**Data plane.** Where user traffic runs: nodes, proxies, sidecars.

**Deployment.** Kubernetes controller for stateless replica *ReplicaSets* and rolling updates.

**Desired state.** Declarative target (Git, Terraform); controllers reconcile *actual state*.

**Digest (image).** `sha256:...` immutable content address; safer than a *tag*.

**DNS search / ndots.** Resolver behavior that can multiply queries inside pods.

**Docker.** Popular container UX; production Kubernetes usually uses containerd underneath.

**DORA metrics.** Deployment frequency, lead time, CFR, MTTR — delivery performance measures.

**Drift.** Reality diverged from declared IaC or GitOps; detect with plan/diff.

**Drain.** Evict pods from a node voluntarily; honors *PDB*.

---

## E–F

**EBS.** Elastic Block Store: AWS network-attached block volumes.

**EIP.** Elastic IP: static public IPv4 in AWS.

**EKS.** Elastic Kubernetes Service: AWS managed Kubernetes control plane.

**EndpointSlice.** Modern Kubernetes object listing pod IPs behind a Service.

**Error budget.** Allowed unreliability: `1 − SLO`; currency for change vs reliability.

**etcd.** Consistent key-value store holding Kubernetes cluster state.

**Event (K8s).** API object with a message about something that happened (scheduling fail).

**Expand/contract.** Safe schema migration: add compatible fields first; remove later.

**External Secrets.** Pattern/operator that syncs vault/cloud secrets into Kubernetes.

**Feature flag.** Runtime switch to enable/disable behavior without a new deploy.

**Flake.** Nondeterministic test failure; must be owned, not ignored.

**Flow log.** VPC packet metadata log for traffic analysis.

**FSGroup.** Pod securityContext setting that sets volume group ownership.

---

## G–I

**Gateway API.** Next-gen Kubernetes routing CRDs (Gateway, HTTPRoute).

**GitOps.** Desired cluster state in Git; an agent pulls and reconciles.

**Golden image.** Baked VM/container baseline (often Packer) with patches and agents.

**Golden signals.** Traffic, errors, latency, saturation (Google SRE).

**Guaranteed QoS.** All containers have equal request and limit; last to OOM under pressure.

**HCL.** HashiCorp Configuration Language used by Terraform.

**Headless Service.** `clusterIP: None`; DNS returns pod IPs.

**Helm.** Kubernetes package manager using charts/templates.

**HPA.** Horizontal Pod Autoscaler: scales replica count from metrics.

**Idempotency.** Repeating an operation has the same effect as doing it once (keys, IaC apply).

**Idempotency key.** Client-supplied token so retries do not double-charge.

**ImagePullBackOff.** Kubelet repeatedly failing to pull an image (auth, tag, network).

**IaC.** Infrastructure as Code: infrastructure defined in versioned files.

**IAM.** Identity and Access Management (cloud users, roles, policies).

**IRSA.** IAM Roles for Service Accounts: EKS OIDC binding of a K8s SA to an IAM role.

**Ingress.** Kubernetes API for HTTP(S) routing to Services via a controller.

**Init container.** Runs to completion before app containers start.

**Inode.** Filesystem object metadata; a volume can be full of inodes with free bytes.

**IPVS.** Linux in-kernel L4 load balancer; kube-proxy mode alternative to iptables.

---

## J–L

**Job.** Kubernetes one-shot (or parallel) finite workload.

**JSON.** Data format; common for APIs and some Kubernetes patches.

**KED A.** Kubernetes Event-Driven Autoscaling (scale on queues, cron, etc.).

**Kubelet.** Node agent that runs pods and reports to the control plane.

**kube-proxy.** Programs node networking for Services (unless replaced by eBPF dataplane).

**Kustomize.** Kubernetes native overlay tool (patches without templates).

**Lead time for changes.** DORA: time from commit to production.

**Least privilege.** Grant only the permissions required for a task; default deny.

**Limit (K8s).** Hard cgroup cap; CPU throttle or memory OOM if exceeded.

**LimitRange.** Namespace policy for default/min/max container resources.

**Load average.** Linux: runnable + uninterruptible task average over 1/5/15 minutes.

**Load balancer.** Distributes traffic (L4/L7); cloud NLB/ALB or in-cluster.

**Load shedding.** Intentionally dropping or degrading work to save the system.

**Lock (Terraform).** Mutual exclusion on a state backend during apply.

**livenessProbe.** Kubelet check; failure restarts the container.

---

## M–O

**mTLS.** Mutual TLS: both client and server present certificates (*service mesh*).

**Multi-AZ.** Deployed across availability zones for HA.

**Mutating webhook.** Admission webhook that changes objects (inject sidecars).

**Namespace (K8s).** Scope for names and policies; not a hostile multi-tenant hard wall.

**Namespace (Linux).** Isolation of PID, net, mnt, etc., for containers.

**NAT gateway.** Translates private subnet egress to a public IP.

**NetworkPolicy.** Kubernetes object restricting pod traffic (if CNI enforces it).

**NodePort.** Service type opening a port on every node; usually wrapped by a cloud LB.

**Observability.** Ability to infer internal state from *telemetry* (metrics, logs, traces).

**OIDC.** OpenID Connect: identity tokens used for *IRSA* and CI cloud auth.

**OOM killer.** Kernel (or cgroup) mechanism that kills processes when memory is exhausted.

**OPA.** Open Policy Agent: general policy engine; *Rego* language.

**Operator.** Controller that encodes operational knowledge for an application CRD.

**Overlay network.** Encapsulation (VXLAN etc.) so pods can IP across nodes.

---

## P–R

**Packer.** Tool to build golden images from a template.

**PDB.** PodDisruptionBudget: limits voluntary disruptions.

**PersistentVolume (PV) / PVC.** Cluster storage resource and the claim a pod uses.

**Plan (Terraform).** Preview of creates/updates/destroys before apply.

**Pod.** Smallest deployable Kubernetes unit: one or more containers sharing net/ipc.

**Pod Security Admission (PSA).** Built-in admission enforcing privileged/baseline/restricted.

**Policy as code.** Rules in Git (OPA, Sentinel, Checkov) evaluated in CI.

**Preemption.** Scheduler evicts lower-priority pods to place higher-priority ones.

**PriorityClass.** Kubernetes priority for scheduling and preemption.

**Probe.** See *liveness*, *readiness*, *startup*.

**Provider (Terraform).** Plugin that talks to an API (AWS, Kubernetes).

**Provisioning.** Creating infrastructure (contrast *configuration management*).

**Pull request (PR).** Proposed Git change with review and CI.

**QoS class.** Guaranteed / Burstable / BestEffort memory eviction order.

**Quota (ResourceQuota).** Namespace caps on aggregate resources.

**RBAC.** Role-based access control (Kubernetes roles/bindings or cloud IAM analog).

**readinessProbe.** Failure removes pod from Service endpoints.

**Reconciliation loop.** Controller repeatedly driving actual toward desired.

**Region.** Cloud geographic grouping of AZs.

**ReplicaSet.** Ensures N copies of a pod template; owned by Deployments.

**Request (K8s).** Scheduling guarantee and CPU weight; should reflect typical use.

**Retry budget.** Cap on retries to prevent *thundering herd*.

**Rollback.** Return to previous known-good artifact/config.

**Rolling update.** Gradually replace instances; Kubernetes Deployment default.

**Root cause.** Systemic factor that, if fixed, prevents recurrence — not just the trigger.

**Runbook.** Step-by-step operational procedure for a class of incident.

---

## S

**SAST.** Static Application Security Testing: analyze source without running it.

**Saturation.** How full a constrained resource is (threads, CPU, disk, connections).

**SBOM.** Software Bill of Materials: inventory of components.

**SCA.** Software Composition Analysis: known vulnerabilities in dependencies.

**Secret (K8s).** Object for sensitive data; *base64 is not encryption*.

**seccomp.** Syscall filter profile for processes/containers.

**SELinux / AppArmor.** MAC frameworks on Linux; additional confinement.

**Service (K8s).** Stable virtual identity and discovery for a set of pods.

**Service mesh.** Data plane for inter-service traffic (mTLS, retries, telemetry).

**ServiceAccount.** Kubernetes identity for pods; can bind to cloud roles (*IRSA*).

**SHA.** Cryptographic hash; Git commit id; image digest.

**Sidecar.** Helper container in a pod (proxy, log shipper).

**SIGKILL / SIGTERM.** Kill vs polite terminate; systemd and Kubernetes send TERM then KILL.

**SLI.** Service Level Indicator: quantitative measure of user-visible reliability.

**SLO.** Service Level Objective: target on an SLI.

**SLA.** Contractual reliability promise, usually looser than SLO.

**SLSA.** Supply-chain Levels for Software Artifacts: provenance framework.

**Spot / preemptible.** Cheap interruptible VMs; need drain-tolerant workloads.

**SRE.** Site Reliability Engineering: operations as a software problem with SLOs.

**StartupProbe.** Delays liveness until slow apps are up.

**State (Terraform).** Mapping of resources to real IDs; treat as production data.

**StatefulSet.** Workload with stable network identity and ordinal storage.

**StorageClass.** Template for dynamically provisioning PVs.

**Supply chain.** Path from source to running binary; signing, provenance, registries.

**Synthetic monitor.** Probes from outside that mimic user journeys.

**Sysctl.** Kernel parameter interface (`/proc/sys`).

**systemd.** Linux init and service manager; units, timers, journal.

---

## T–Z

**Tag (container).** Mutable pointer (e.g., `:latest`); prefer *digest* in prod.

**Taint / toleration.** Node taints repel pods unless they tolerate.

**Telemetry.** Metrics, logs, traces emitted by systems.

**Terraform.** Popular IaC tool with plan/apply and state.

**Thundering herd.** Many clients retry or start at once after a blip.

**Time-to-detect (MTTD).** Mean time to notice an incident.

**Time-to-restore (MTTR).** Mean time to restore service.

**TLS.** Transport Layer Security; certificates, expiry, protocols.

**Topology spread.** Even pod distribution across failure domains.

**Trace.** Causal graph of a request across services (*OpenTelemetry*).

**Twelve-factor.** Methodology for portable SaaS apps (config in env, etc.).

**ulimit.** Per-process resource limits (files, processes).

**Uninterruptible sleep (D state).** Task stuck in kernel I/O; not SIGKILL-able until it returns.

**Validating webhook.** Admission webhook that only allows/denies.

**VPC.** Virtual Private Cloud: isolated network in a public cloud.

**VPA.** Vertical Pod Autoscaler: recommends/sets CPU/memory requests.

**WAF.** Web Application Firewall: HTTP-layer filtering at the edge.

**Webhook.** HTTP callback; in K8s, admission or CI notifications.

**Workspace (Terraform).** Named state slice in one backend; use carefully vs directories.

**YAML.** Indentation-sensitive config format used heavily by Kubernetes.

**Zero-downtime deploy.** Technique aiming not to drop in-flight user work (PDB, preStop, draining).

**Zero trust.** Authenticate/authorize every request; do not trust network location alone.

---

## Extra terms (to complete the working vocabulary)

**12-week capstone.** This handbook’s structured platform-building lab (see Chapter 80).

**Alert fatigue.** Too many pages; humans stop responding — a reliability defect.

**Allowlist / denylist.** Preferred terms for permit/deny lists (replacing older jargon).

**AMI baking.** Building a *golden image* with Packer including patches.

**Annotation (K8s).** Non-identifying metadata (ingress class, checksums).

**API Gateway.** Managed or self-hosted HTTP front door with auth, routing, quotas.

**Autoscaler (cluster).** Adds/removes nodes (Cluster Autoscaler, Karpenter).

**AWS Organizations / OU / SCP.** Multi-account structure and guardrail policies.

**Backoff.** Increasing delay between retries; should include *jitter*.

**Bare metal.** Physical servers vs VMs/cloud.

**Bastion / jump host.** Constrained SSH entry; often replaced by SSM/oslogin.

**Bazel / Nix.** Hermetic build systems (advanced reproducible builds).

**Bearer token.** Credential in `Authorization` header; K8s SA tokens are bearers.

**Black Swan.** Rare high-impact event; still design for *graceful degradation*.

**Blue/green DNS cut.** Switching traffic by changing records; watch TTL.

**Bolt-on security.** Controls added after design; weaker than *shift left*.

**Bottleneck.** Slowest resource in a path; scale *that*, not random tiers.

**Break-glass.** Emergency privileged access with extra audit.

**Brownout.** Partial degradation rather than hard down.

**Buildkit.** Next-gen Docker build engine; better caching/secrets.

**Canary analysis.** Statistical comparison of canary vs baseline SLIs.

**Certificate Authority (CA).** Issues TLS certs; *cert-manager* automates.

**cgroup v2.** Unified hierarchy; modern Kubernetes default.

**Change advisory.** Process gate; keep lightweight or it fights DevOps.

**Chart (Helm).** Packaged set of Kubernetes manifests.

**Checkpoint / restore.** Advanced process snapshot (not common in app DevOps).

**Cloud-init.** VM first-boot configuration.

**Cluster-admin.** Superuser ClusterRole; almost never for apps.

**Columnar observability.** Wide events vs pure metrics (optional architecture).

**Compliance.** Mapping controls to frameworks (SOC 2, PCI, ISO).

**Config drift.** Same as *drift* for OS/config management.

**Consul / Eureka.** Service discovery systems (often replaced by K8s DNS).

**Container escape.** Break out of isolation to the host.

**Content trust.** Notary/signing verification before run.

**Control theory.** How autoscalers oscillate if poorly tuned.

**CRD.** Custom Resource Definition: extend the Kubernetes API.

**CSI snapshot.** Volume snapshot via CSI for backup.

**CVE aging.** Time-to-patch SLO for critical vulns.

**Daemon.** Long-running background process / *DaemonSet* agent.

**Dark launch.** Send shadow traffic to a new system without user impact.

**Data residency.** Legal constraint on where data lives.

**DDoS.** Distributed denial of service; mitigate at edge/WAF/CDN.

**Dead letter queue (DLQ).** Place for failed async messages.

**Declarative.** Say what, not how (K8s, Terraform).

**Dependency confusion.** Package-name attack against internal names.

**Deployment frequency.** DORA: how often you ship to prod.

**Device plugin.** Kubelet extension for GPUs etc.

**Distroless.** Minimal container images without a full OS userland.

**DNS TTL.** Cache lifetime; affects failover speed.

**Dockerfile.** Build recipe for an image.

**Dual homing.** Two providers/paths for resilience.

**Dynamic admission.** Webhooks vs compiled-in admission.

**Egress.** Outbound traffic; often forgotten in *NetworkPolicy*.

**Encryption at rest / in transit.** Disk/KMS vs TLS.

**Envelope encryption.** DEK encrypted by KEK (KMS).

**Ephemeral port.** Client-side TCP port from a range; can exhaust.

**Error budget policy.** Written rules for freeze vs ship.

**eBPF.** Safe kernel programmability for observability/networking.

**Eventual consistency.** Replicas converge; design retries/idempotency.

**Exec (kubectl).** Interactive command in a container; audit it.

**Exploitability.** Whether a CVE is reachable in *your* config.

**Fan-out.** One event to many consumers; watch retry amplification.

**Federated identity.** Trust tokens from an external IdP (*OIDC*).

**Finalizer.** Kubernetes hook delaying deletion until cleanup.

**FinOps.** Practice of cloud cost accountability.

**Fleet.** Many clusters/machines managed uniformly.

**Forward proxy vs reverse proxy.** Client-side vs server-side proxying.

**FUSE.** Filesystem in userspace; sometimes used by CSI.

**Garbage collection (K8s).** Cleaning unused images, objects with owners.

**Git SHA.** Specific commit; pin Actions and submodules to SHAs.

**Graceful shutdown.** Handle SIGTERM, finish in-flight, then exit (*preStop*).

**Helm hook.** Chart lifecycle job (migrate); easy to get wrong.

**Hermetic build.** Isolated, reproducible inputs.

**Horizontal vs vertical scale.** More replicas vs bigger instances.

**Hotfix.** Emergency patch; still needs the paved pipeline.

**HSTS.** HTTP header forcing HTTPS.

**IdP.** Identity provider (Okta, GitHub, Google).

**Immutable infrastructure.** Replace not mutate (new AMI/pod, not SSH patch).

**Ingress class.** Selects which controller implements an Ingress.

**In-place update.** Terraform/cloud change without replace; still can interrupt.

**Istio / Linkerd.** Service mesh implementations.

**Jitter.** Randomization added to backoff.

**JSON Patch / Strategic merge.** Kubernetes patch types.

**Just-in-time (JIT) access.** Time-bound privileges (*break-glass*).

**Karpenter.** High-performance node provisioner for EKS-style clusters.

**Keepalive.** Reuse TCP/HTTP connections to cut handshake cost.

**KMS.** Key Management Service for encryption keys.

**Kubectl context.** Which cluster/user your CLI talks to — verify before prod.

**Kyverno / Gatekeeper.** Policy engines as admission controllers.

**Label.** Identifying K8s metadata used by selectors.

**Lake / warehouse.** Analytics storage; not the OLTP *source of truth*.

**Latency SLO.** Objective on delay, often a percentile.

**Lease.** Coordination object (leader election).

**Lift and shift.** Move workloads with little re-architecture; limited DevOps gain.

**Linux capability bounding set.** Caps a process may ever gain.

**Log aggregation.** Centralize logs (ELK, Loki) with retention/PII rules.

**Loopback.** `127.0.0.1`; sidecars listen here often.

**Maintenance window.** Declared time for risky change; still need SLOs.

**Manifest.** A Kubernetes YAML document.

**Mean time to acknowledge (MTTA).** Pager pickup time.

**Metadata service (IMDS).** Cloud instance identity/creds endpoint; restrict.

**Metric cardinality.** Unique label combinations; high cardinality can DDoS Prometheus.

**Mirroring / registry cache.** Pull-through to survive Docker Hub limits.

**MITM.** Man-in-the-middle; TLS and pinning discussions.

**Module (Terraform).** Reusable IaC unit with inputs/outputs.

**Multi-tenancy.** Sharing a cluster/account among teams; isolation tiers vary.

**N+1 query.** Chatty DB access pattern; classic latency bug.

**NAT exhaustion.** Too many connections through a small NAT gateway.

**Near-zero RPO/RTO.** Backup objectives: data loss vs downtime targets.

**Node allocatable.** Resources kubelet advertises after reservations.

**Noise (alerting).** Pages that do not require action.

**Nominal vs effective permissions.** What IAM looks like vs what is reachable.

**Observability pipeline.** Agents → brokers → storage → UI.

**OLTP / OLAP.** Transactional vs analytic workloads; different reliability design.

**On-call.** Rotation responsible for pages; a product with runbooks.

**OpenTelemetry (OTel).** Standard for traces/metrics/logs APIs.

**Orchestrator.** System that places and heals workloads (Kubernetes).

**Outbox pattern.** Reliably emit events with DB transactions.

**Overcommit.** Selling more CPU/memory than physically present; risk of throttle/OOM.

**P99 / percentile.** Latency value below which 99% of samples fall.

**Paved road.** Official supported platform path (*golden path*).

**Peer review.** Human check; not a substitute for automated gates.

**Percentile vs average.** Averages hide tail pain; SLOs use percentiles.

**PGBouncer.** Connection pooler in front of Postgres.

**PID 1.** Init in a container; must reap zombies and handle signals.

**Pipeline.** Automated sequence of CI/CD jobs.

**PITR.** Point-in-time recovery for databases.

**Plan file.** Saved Terraform plan applied exactly in CD.

**Platform engineering.** Team building internal developer platform products.

**Pod overlay.** Network encapsulation for pod IPs.

**Poison pill.** Bad message that crashes consumers in a loop.

**Portability.** Ability to move workloads; often oversold vs paved AWS/GCP.

**Postmortem.** After-incident learning document (*blameless*).

**PreStop hook.** Runs before SIGTERM; used to delay shutdown for LB drain.

**Privilege escalation.** Gaining higher rights than intended.

**Progressive delivery.** Canary/flags/mesh-based gradual rollout.

**Prometheus.** Pull-based metrics system common in Kubernetes.

**Provenance.** Attestation of build origin (*SLSA*).

**Proxy protocol.** Pass client IP through TCP LBs.

**Public registry.** Docker Hub etc.; rate limits and supply-chain risk.

**Pull-through cache.** Local registry that fetches missing tags.

**Push vs pull deploy.** CI applies vs GitOps agent pulls.

**RTO / RPO.** Recovery time and recovery point objectives.

**Rate limit.** Cap on requests per key/IP.

**Read replica.** Asynchronous copy for read scale; lag is an SLI.

**Reaping.** Parent collecting child exit status; PID 1 problem.

**Reconciliation time.** How long until GitOps/controllers converge.

**Red/black.** Synonym of blue/green in some orgs.

**Rego.** OPA policy language.

**Replica.** One copy of a process/data set.

**Repo (Git).** Versioned source; also container registry repository.

**Request smuggling.** HTTP desync attack; WAF/proxy concern.

**Reserved concurrency.** Lambda/app cap protecting downstream.

**Residual risk.** Risk accepted after controls.

**ResourceVersion.** Kubernetes optimistic concurrency token.

**RestartPolicy.** Pod/container restart behavior (Always/OnFailure/Never).

**REST.** HTTP API style; retries need idempotency on non-GET.

**Retention.** How long logs/metrics/backups are kept.

**Revision (Deployment).** History entry for rollback.

**Risk register.** List of risks with owners — SRE-adjacent.

**Roll forward.** Fix by deploying a new version instead of rollback.

**Rootless.** Containers without root on the host (Podman/user namespaces).

**Rotation.** Periodic replacement of secrets/certs/keys.

**RPO zero.** No data loss; expensive; rarely global.

**Run-as-non-root.** Container user ≠ 0; PSA restricted expects it.

**Runtime security.** Detection/prevention on running workloads (Falco, etc.).

**S3.** AWS object storage; versioning matters for *data loss* runbooks.

**Sandbox.** Isolated execution (gVisor, Firecracker) for untrusted code.

**Scale-to-zero.** HPA/KEDA to no replicas; cold start tradeoff.

**Scheduler (kube-scheduler).** Binds pods to nodes.

**Secret scanning.** Detect keys in Git/CI.

**Security context.** Pod/container Linux security fields.

**Self-hosted runner.** CI worker you operate; patch and isolate it.

**Semantic versioning.** MAJOR.MINOR.PATCH for modules/charts.

**Service catalog.** Internal list of services, owners, SLOs.

**Session affinity.** Stickiness to a backend; hurts perfect randomness.

**SHA pinning.** Locking actions/images to hashes.

**Shift left.** Move tests/security earlier in delivery.

**Shogun / two-pizza team.** Team-size heuristics (ops culture).

**Sidecar injection.** Mesh/controller adds proxy automatically.

**Signal (SRE).** A metric that informs a decision; not all graphs are signals.

**Single point of failure (SPOF).** Component whose death takes the system down.

**SLA breach.** Legal/commercial miss; may not equal SLO miss.

**Sleep (preStop).** Crude drain delay; tune with data.

**Snapshot.** Point-in-time copy of disk/DB.

**Socket activation.** systemd starts service on incoming connection.

**Soft vs hard multi-tenancy.** Trust vs hostile isolation.

**Source of truth.** Authoritative system (Git, TF state, IdP).

**Spinnaker.** Multi-cloud CD platform (Netflix-origin).

**Split brain.** Two actives think they are primary (DB, state).

**SRE workbook.** Google’s SRE books; origin of many terms here.

**SSL.** Old name; use TLS.

**Staging.** Pre-prod environment; must resemble prod *enough*.

**Standard output / err.** Container logs default stream.

**Stateful vs stateless.** Disk/identity vs interchangeable replicas.

**Static pod.** Mirror pod from kubelet files; used for control plane.

**Status page.** Public incident comms.

**Storage IOPS.** Disk operations per second; cloud burst credits.

**Strangler fig.** Incrementally replace a monolith.

**Subnet.** CIDR slice of a VPC.

**Supervisor.** Process that restarts children (systemd, kubelet).

**Synchronous vs async.** Call waits vs message later; different failure design.

**Syslog.** Legacy logging protocol.

**Tag (AWS).** Metadata for cost and policy.

**Tail latency.** High percentiles; what users feel.

**Tarball.** `.tar` archive; still how images are layers.

**Technical debt.** Delayed engineering work with interest.

**Tenancy (database).** Separate DB vs row-level; blast radius.

**Terraform Cloud/Enterprise.** SaaS/remote run/state product.

**Test pyramid.** Many unit, fewer integration, few e2e.

**Tflint.** Terraform linter.

**Throughput.** Work per time; pair with latency.

**Ticketing.** Change/incident records; keep them useful.

**Time series.** Metrics stored as values over time.

**TLS handshake.** CPU and RTT cost; watch `time_appconnect`.

**Toil.** Manual repetitive ops SRE tries to eliminate.

**TokenRequest API.** Bound ServiceAccount tokens vs old secrets.

**Tooling sprawl.** Too many overlapping platforms.

**Topology key.** Label used for spread (`kubernetes.io/hostname`, zone).

**Traffic shadowing.** Copy live traffic to a test cluster.

**TTLSecondsAfterFinished.** Auto-clean Jobs.

**Tunnel (SSH/VPN).** Encrypted path; still not app authz.

**Twelve-factor config.** Config in environment, not baked secrets.

**Ubuntu/RHEL.** Common distros; commands differ (`apt` vs `dnf`).

**UnhealthyPodEvictionPolicy.** PDB behavior toward not-ready pods.

**Unix socket.** IPC endpoint on the filesystem (`docker.sock` risk).

**Untrusted input.** Anything from users/PRs/network.

**User namespace.** Maps container root to unprivileged host UID.

**Utilization.** Busy fraction; high utilization → *saturation*.

**vCPU.** Virtual CPU share; steal time if oversubscribed.

**Vendor lock-in.** Cost of leaving a cloud/API.

**Version skew.** Components on mixed versions (K8s skew policy).

**Virtual patch.** WAF rule buying time before a code fix.

**VolumeMount.** Bind of a volume into a container path.

**VPC endpoint / PrivateLink.** Private access to cloud APIs without NAT.

**Vulnerability.** Weakness that *might* be exploitable; prioritize by context.

**WaitGroup / connection pool.** App-level concurrency resources that saturate.

**Warm pool.** Pre-initialized capacity for faster scale-out.

**Watch (API).** Long-lived stream of object changes; etcd load.

**Waterfall.** Sequential SDLC; DevOps reacts against long queues.

**Webhook timeout.** Admission latency budget; failing closed is dangerous.

**Wheel group.** Traditional sudo group on some Unixes.

**Whitebox vs blackbox monitoring.** Internal metrics vs external probes.

**Work-stealing.** Scheduler pattern; also human on-call load.

**Workload identity.** Cloud analog of *IRSA* on GKE/Azure.

**Write-ahead log (WAL).** DB durability mechanism; PITR depends on it.

**X.509.** Certificate standard used by TLS.

**YAML anchor.** Reuse in YAML; can confuse Helm.

**Zombie process.** Dead child not reaped; PID 1 issue.

**Zone awareness.** Place replicas in different AZs.

---

## Using the glossary

When a meeting uses two meanings of *service* (K8s vs business), stop and name them. Precision is operational safety. Add org-specific terms (your product names, your SEV table) in an internal overlay, not by blurring these definitions.
