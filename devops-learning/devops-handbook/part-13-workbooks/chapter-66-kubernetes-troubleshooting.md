# Chapter 66: Kubernetes Troubleshooting

*DevOps Handbook — Pages 341–348 of this PDF edition*

*DevOps Handbook — Workbook*
---

## 66.1 Troubleshooting is a search of the control loop

Kubernetes does not “run containers.” It **reconciles** declared objects toward observed state. When users say “the cluster is down,” they usually mean one of: the API is unreachable, workloads are not Ready, traffic does not flow, or data in etcd is wrong. This workbook is a production search procedure for **CrashLoopBackOff**, **Pending** pods, **networking**, **etcd**, **kubelet**, **events**, and **debug containers**.

Always start with: **which object is unhappy, on which node, since when, according to whom** (kubelet vs control plane vs CNI).

```bash
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | tail -40
kubectl get pods -A --field-selector=status.phase!=Running
kubectl top nodes
kubectl get --raw='/readyz?verbose'
kubectl get --raw='/healthz?verbose'
```

If `/readyz` fails, you are not in application-debug land—you are in **control-plane** land. Do not delete pods to “fix” a dead apiserver.

---

## 66.2 Reading Events without drowning

Events are **best-effort**, rate-limited, and TTL-evicted (typically one hour). They are still the fastest signal.

```bash
kubectl describe pod web-7d9f8c-abcde
kubectl get event -n prod --field-selector involvedObject.name=web-7d9f8c-abcde
kubectl get event -A --field-selector reason=FailedScheduling
```

| Reason | Typical meaning |
|--------|-----------------|
| `FailedScheduling` | Scheduler cannot place (resources, taints, affinity, PVC) |
| `FailedAttachVolume` | CSI/attacher/node mismatch |
| `FailedMount` | Mount timeout, fstab-like errors, SELinux |
| `BackOff` | Crash loop |
| `Unhealthy` | Probe failed |
| `Killing` | Preemption, preStop, or kubelet eviction |
| `FailedCreatePodSandBox` | CNI |
| `InspectFailed` / `ErrImagePull` | Registry, creds, image name |
| `NodeNotReady` | kubelet/PLEG/network |

**Metrics server vs events:** CPU `Insufficient cpu` is scheduler math; it does not mean the node is idle if requests are inflated. Always print **requests/limits** alongside `kubectl describe node`.

---

## 66.3 Pending pods: a decision tree

A Pending pod never got a node, or never finished sandbox setup.

```bash
kubectl get pod -o wide
kubectl describe pod <pod>
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints,READY:.status.conditions[?(@.type==\"Ready\")].status
```

### 66.3.1 Scheduler Pending (`FailedScheduling`)

| Message fragment | What to check |
|------------------|---------------|
| `Insufficient cpu/memory` | Requests vs allocatable; DaemonSets already consumed |
| `didn't match Pod's node affinity` | `nodeSelector`, topology, zone PVC |
| `untolerated taint` | `NoSchedule` taints, GPU taints |
| `0/N nodes are available: ... volume` | WaitForFirstConsumer, zone mismatch |
| `pod has unbound immediate PersistentVolumeClaims` | StorageClass, provisioner, quota |
| `node(s) had taint {node.kubernetes.io/disk-pressure}` | Node pressure (kubelet eviction) |

```bash
kubectl describe node <node> | sed -n '/Allocated resources/,/Events/p'
kubectl get pvc -n prod
kubectl get storageclass
kubectl get csidriver
```

**PriorityPreemption:** a low-priority pod can stay Pending forever while the cluster “has space” on paper because preemption is disabled or PDBs block victims.

### 66.3.2 Sandbox Pending (`ContainerCreating` forever)

If scheduled but stuck `ContainerCreating`, describe for `FailedCreatePodSandBox`. That is **CNI, CRI, or volume**—not the application image.

```bash
# on the node (or via debug)
journalctl -u kubelet -u containerd --since -15m
crictl pods
crictl ps -a
```

---

## 66.4 CrashLoopBackOff and ImagePull

CrashLoop is the kubelet applying backoff after a container exits non-zero or fails a startup probe.

```bash
kubectl logs <pod> -c <container> --previous
kubectl logs <pod> --all-containers --timestamps
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState}'
```

**Always `--previous`.** The current log may be empty because the container lasted 200 ms.

| Exit | Hint |
|------|------|
| 0 + restartPolicy Always | Probe or command completed; still restarted |
| 1 / 2 | App error; read logs |
| 137 | SIGKILL: OOM (cgroup) or `kill -9` |
| 139 | SIGSEGV |
| 255 | Shell / generic |

**OOM:** `Last State: Reason: OOMKilled`. Raise limit **or** fix leak. Raising without a request can still surprise the scheduler (bin packing). Align request≈p95, limit=ceiling.

**Probes:** A process that listens slowly will be killed by `startupProbe`/`livenessProbe`. Distinguish **liveness killing a healthy busy app** (too aggressive) from a real deadlock. For a 90-second JVM warmup, use startupProbe; do not lengthen liveness forever.

```yaml
startupProbe:
  httpGet: { path: /readyz, port: 8080 }
  failureThreshold: 30
  periodSeconds: 5
livenessProbe:
  httpGet: { path: /healthz, port: 8080 }
  periodSeconds: 20
  timeoutSeconds: 3
readinessProbe:
  httpGet: { path: /readyz, port: 8080 }
```

**ErrImagePull / ImagePullBackOff:**

```bash
kubectl describe pod | grep -A5 'Failed to pull'
# auth: imagePullSecrets vs node IAM (EKS) vs Workload Identity
```

Wrong tag `latest` moved; rate limits on Docker Hub; private registry TLS MITM; `linux/arm64` on `amd64` nodes (`Failed to create pod sandbox` sometimes, or exec format error crash).

---

## 66.5 Workload networking: Services, kube-proxy, CNI, DNS

When “the service does not connect,” split **pod IP**, **ClusterIP**, **NodePort/LB**, **Ingress**, **NetworkPolicy**, **DNS**.

```bash
kubectl get svc,endpoints,endpointslice -n prod
kubectl get pod -n kube-system -l k8s-app=kube-dns -o wide
kubectl run netshoot --rm -it --image=nicolaka/netshoot -- /bin/bash
# from a debug pod:
dig kubernetes.default.svc.cluster.local
curl -sv http://cluster-ip:80
```

| Symptom | Likely |
|---------|--------|
| Endpoints empty | Selector mismatch, no Ready pods |
| Endpoints full, ClusterIP timeout | kube-proxy/dataplane, conntrack, NPdeny |
| Works pod-to-pod IP, fails Service | kube-proxy mode, hairpin, NAT |
| Works in cluster, fails from VPC | NLB annotations, SG, externalTrafficPolicy |
| Intermittent | conntrack race, stale EndpointSlice, DNS ndots (Chapter 62) |

**NetworkPolicy:** default-deny in namespace + missing egress to DNS (port 53) looks like “the app cannot resolve.” Allow CoreDNS.

**CNI specific:** Calico Felix, Cilium Hubble, AWS VPC CNI IP warm pool exhaustion (`failed to assign an IP`). Always check **ENI/IP capacity** on EKS before blaming the Deployment.

```bash
kubectl get ipamd-config -A   # if using aws-node extras
kubectl describe node | grep -i 'max pods\|eni'
```

**Overlays vs routing:** traceroute from netshoot to another pod IP tells you if you have encapsulation.

---

## 66.6 kubelet: the node agent that is often the real outage

kubelet problems present as `NotReady`, `PLEG is not healthy`, disk pressure, or pods stuck Terminating.

```bash
# on node
systemctl status kubelet
journalctl -u kubelet -o short-precise --since -30m
df -h /var/lib/kubelet /var/lib/containerd
crictl stats
```

| kubelet issue | Notes |
|---------------|--------|
| DiskPressure | Image GC, log rotation, emptyDir |
| MemoryPressure | Evictions; check QoS classes |
| PIDPressure | Fork bomb / leaking processes |
| PLEG timeout | Runtime hung; too many pods; slow disk |
| Certificate rotate fail | Node cannot talk to apiserver |
| Static pod manifest error | Control-plane static pods on masters |

**Stuck Terminating:** finalizers (`foregroundDeletion`, custom operators, CSI). Force-delete hides the bug:

```bash
kubectl get pod <p> -o yaml | grep -A20 finalizers
# fix the controller; only then:
kubectl delete pod <p> --grace-period=0 --force   # last resort
```

**Clock skew** on nodes breaks TLS to apiserver and lease updates. `timedatectl` belongs in node NotReady runbooks (Chapter 61).

---

## 66.7 etcd: when the cluster’s memory is sick

etcd holds cluster state. Symptoms: slow API, timeouts, `etcdserver: request timed out`, leader flaps, alarms `NOSPACE`.

```bash
# on control plane / via etcdctl with cluster certs
etcdctl --endpoints=https://127.0.0.1:2379 endpoint health -w table
etcdctl endpoint status -w table
etcdctl alarm list
etcdctl defrag
```

| Issue | Response |
|-------|----------|
| NOSPACE | Compact + defrag; raise quota only with a plan |
| High fsync latency | Disk; **do not** run etcd on contended burstable volumes |
| Member down | Restore from snapshot only with documented procedure |
| Split brain | Odd member count; unique peer URLs |

**Compaction** is normal. **Restore** is a declared incident. Practice restore on a **non-prod** control plane. Take snapshots **off-node**.

```bash
etcdctl snapshot save /backup/etcd-$(date -u +%F).db
etcdctl snapshot status /backup/etcd-....db
```

Kubernetes objects that explode etcd: huge Secrets, CRDs with unbounded status, Events flooding (ironic), many Endpoints. Watch **object counts** and etcd **db size**.

Managed control planes (EKS/GKE/AKS) hide etcd; you still watch API latency SLIs (`apiserver_request_duration`) and etcd metrics if exposed.

---

## 66.8 Control plane API and controllers

```bash
kubectl get --raw='/metrics' | grep apiserver_request_duration
kubectl -n kube-system get le | head
kubectl get apiservices
```

A bad webhook (`ValidatingWebhookConfiguration`) can make **all** deploys hang (`context deadline exceeded`). Fail-open vs fail-closed matters (Chapter 69). During an incident, temporarily bypassing a broken webhook is a known break-glass—with an audit ticket.

```bash
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations
```

---

## 66.9 Ephemeral debug containers and node debug

```bash
# requires EphemeralContainers feature (GA)
kubectl debug -it <pod> --image=nicolaka/netshoot --target=<app-container>
kubectl debug node/<node> -it --image=busybox
```

**Distroless** app containers have no shell: debug containers are the supported path. Share process namespace (`shareProcessNamespace: true`) if you must `strace` the app PID (Chapter 61) inside the pod.

**Security:** debug images with extra tools expand blast radius. Use a **signed internal debug image**, not random Docker Hub as root on prod nodes.

```bash
kubectl auth can-i create pods/ephemeralcontainers -n prod
```

RBAC should not grant debug on prod to everyone who can `get pods`.

---

## 66.10 Worked incident: CrashLoop after config change

**Events:** `Liveness probe failed: HTTP 500`, then `BackOff`.

**Logs --previous:** migration lock timeout against Postgres.

**Wrong fix:** delete pod (resets backoff, same crash).

**Right fix:** disable liveness temporarily **only** if it prevents recovery (rare); fix DB; `kubectl rollout undo`; add startupProbe; make migration a Job with one replica, not an initContainer stampede (thundering herd on schema_migrations lock).

**Secondary:** 30 replicas all running initContainer migrations. Scale to 1 for migrate, then scale out.

---

## 66.10.1 CSI and stuck volumes

Volume incidents look like Pending or `Multi-Attach error for volume`. Read-Write-Once volumes cannot attach to two nodes. A pod that is Terminating on node A while scheduling on node B will sit in `ContainerCreating` until the attachment releases.

```bash
kubectl get pv,pvc -A
kubectl describe pvc <name>
kubectl get volumeattachment
# CSI logs
kubectl -n kube-system logs -l app=ebs-csi-controller --tail=100
```

**Recovery:** ensure the old pod is fully gone (finalizers), then wait for detach. Force-deleting without detach completion just races. For StatefulSets, do not delete PVCs unless you intend to orphan data.

NFS/SMB mounts that hang put the pod in `D` state on the node (Chapter 61). kubelet cannot complete teardown; the node may go NotReady. Fix the storage appliance first.

---

## 66.10.2 HPA, VPA, and “the cluster scaled to zero”

Autoscaling problems: HPA cannot see metrics (`unable to get metrics for resource cpu`), so replica count stays at min while load rises—Pending is not the symptom, **latency** is. Confirm metrics-server or Prometheus adapter:

```bash
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes
kubectl describe hpa -n prod
```

Cluster Autoscaler vs Karpenter: unschedulable pods should trigger node claims. If the provisioner lacks a matching instance type for a huge `memory` request, pods stay Pending with `can't fit`. Read the autoscaler log, not only `describe pod`.

---

## 66.11 Performance and eviction

```bash
kubectl describe node | grep -A20 'Evicted'
kubectl get pod -A --field-selector=status.reason=Evicted
```

QoS: Guaranteed (request=limit) evicted last. BestEffort first. Burstable in the middle. Design so **critical daemons** are Guaranteed.

---

## 🧪 Lab 66.1 — Pending because of requests

1. On kind/minikube, create a pod requesting `cpu: 100` (100 cores).
2. Read `FailedScheduling`.
3. Fix the request. Confirm Running.

---

## 🧪 Lab 66.2 — CrashLoop and --previous

1. Deploy a pod with `command: ["sh","-c","echo boom; exit 1"]`.
2. Fetch logs with and without `--previous`.
3. Add a liveness probe against a port that never listens; contrast probe-kill vs exit 1.

---

## 🧪 Lab 66.3 — Empty Endpoints

1. Service selector `app=web`; pod label `app=web2`.
2. `kubectl get endpoints`.
3. Fix labels; curl ClusterIP from a debug pod.

---

## 🧪 Lab 66.4 — Debug distroless

1. Run a distroless/static pod (or `gcr.io/distroless/static` with a pause-like command if needed).
2. `kubectl exec` fails. Use `kubectl debug` with netshoot.
3. Document the RBAC needed.

---

## 🧪 Lab 66.5 — Webhook outage simulation (careful)

1. Install a ValidatingWebhook that points at a Service with no pods.
2. Try to create a pod; observe timeout.
3. Delete the webhook configuration; confirm API recovers.
4. **Never** do this on a shared prod cluster.

---

## 66.12 Field cookbook

| Symptom | First five commands |
|---------|---------------------|
| Pod Pending | `describe pod`, `get nodes`, `get pvc`, events, `describe node` resources |
| CrashLoop | `logs --previous`, `describe`, events, `get pod -o yaml` status |
| No traffic | `get ep,slice`, netshoot curl, NetworkPolicy, DNS |
| Node NotReady | kubelet journal, `df`, `crictl`, clock |
| API slow | `readyz`, etcd health, webhooks, `kubectl get apiservices` |

---

## Review questions

1. Why can Events be missing for an incident that started six hours ago?
2. Difference between Pending (unscheduled) and ContainerCreating? Which components are in play?
3. An OOMKilled container had free node memory. Explain cgroup vs node memory.
4. Why is `--previous` mandatory in CrashLoop investigations?
5. Empty Endpoints: give two causes that are not “kube-proxy is down.”
6. How does a default-deny NetworkPolicy break DNS?
7. When is `--force` delete of a Terminating pod justified, and what must you inspect first?
8. What etcd alarm requires compaction/defrag, and what is the risk of raising quota blindly?
9. How can a ValidatingWebhook take down deployments cluster-wide?
10. Who should be allowed to `kubectl debug node` in production, and why is the debug image a supply-chain concern?

---

## Further practice

Chapters 31–36 for architecture; Chapter 62 for packet-level CNI proof; Chapter 61 for node OS; Chapter 69 for admission webhooks as a security control that can also outage you.
