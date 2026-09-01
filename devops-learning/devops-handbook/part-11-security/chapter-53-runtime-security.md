# Chapter 53: Runtime Security — Falco and OPA Gatekeeper

*DevOps Handbook — Part XI, Pages 1041–1060*

---

## 53.1 Defense beyond the pipeline

Shift-left security catches vulnerabilities before deploy—but **runtime** threats remain: zero-days, insider abuse, container escapes, cryptomining, lateral movement after breach. **Runtime security** detects and responds to malicious behavior in executing systems.

Two complementary approaches:

| Approach | Mechanism | Example tools |
|----------|-----------|---------------|
| **Threat detection** | Monitor syscalls, K8s audit events | Falco, Sysdig, Aqua |
| **Policy enforcement** | Block non-compliant resources at admission | OPA Gatekeeper, Kyverno, Pod Security Admission |

Detection alerts; admission prevents. Use both.

---

## 53.2 Falco — cloud-native runtime detection

**Falco** (CNCF) detects unexpected behavior via **kernel events** (syscalls via eBPF or kernel module) and **Kubernetes audit logs**.

Detection examples:

- Shell spawned in container
- Unexpected outbound connection
- Sensitive file read (`/etc/shadow`)
- Privilege escalation attempt
- Write below `/etc` or `/usr/bin`

Architecture:

```
Kernel / K8s audit ──► Falco ──► Alerts ──► Slack/PagerDuty/Falcosidekick
                         │
                    Rules (YAML)
```

Install on Kubernetes (Helm):

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set driver.kind=ebpf
```

Custom rule:

```yaml
# /etc/falco/rules.d/custom-rules.yaml
- rule: Terminal shell in container
  desc: Detect shell spawned in running container
  condition: >
    spawned_process and container and
    proc.name in (bash, sh, zsh) and
    not proc.pname in (bash, sh, docker-init, tini)
  output: >
    Shell spawned in container
    (user=%user.name container=%container.name
     image=%container.image.repository cmdline=%proc.cmdline)
  priority: WARNING
  tags: [container, shell, mitre_execution]

- rule: Outbound connection to suspicious port
  desc: Unexpected outbound connection on non-standard port
  condition: >
    outbound and container and
    fd.sport != 443 and fd.sport != 80 and
    not fd.sip in (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  output: Suspicious outbound (container=%container.name connection=%fd.name)
  priority: NOTICE
```

Tune rules to reduce false positives—baseline normal behavior in staging first.

Response integration via **Falcosidekick**:

```yaml
config:
  slack:
    webhookurl: "https://hooks.slack.com/..."
    minimumpriority: warning
  pagerduty:
    routingkey: SECRET
    minimumpriority: error
```

---

## 53.3 Falco response actions

Detection alone is insufficient—define response playbooks:

| Alert | Response |
|-------|----------|
| Shell in prod container | Kill pod, page on-call, capture forensics |
| Cryptomining outbound | NetworkPolicy block, isolate node |
| Sensitive file access | Audit user/service account, revoke credentials |

**Falco Response Engine** (evolving) can trigger Kubernetes actions (delete pod, label node) via webhooks—use cautiously with human approval for destructive actions.

Combine with **NetworkPolicies** and **seccomp/AppArmor** profiles to limit blast radius when detection triggers.

---

## 53.4 OPA and Gatekeeper

**Open Policy Agent (OPA)** evaluates policy decisions via Rego language. **Gatekeeper** is OPA's Kubernetes admission controller—validates and mutates resources at create/update.

```
kubectl apply ──► API Server ──► Gatekeeper (OPA) ──► Allow/Deny
                                      │
                                 ConstraintTemplate
                                 Constraint
```

Install Gatekeeper:

```bash
kubectl apply -f https://raw.githubusercontent.com/open-policy-agent/gatekeeper/v3.14.0/deploy/gatekeeper.yaml
```

ConstraintTemplate (require labels):

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels
        violation[{"msg": msg}] {
          required := input.parameters.labels
          provided := input.review.object.metadata.labels
          missing := required[_]
          not provided[missing]
          msg := sprintf("Missing required label: %v", [missing])
        }
```

Constraint (enforce):

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    namespaces: ["production"]
  parameters:
    labels: ["team", "app"]
```

Block privileged containers:

```rego
package k8spsprivileged

violation[{"msg": msg}] {
  input.review.object.spec.containers[_].securityContext.privileged
  msg := "Privileged containers are not allowed"
}
```

Gatekeeper **mutation** (assign labels, defaults) via AssignMetadata, Assign mutations.

---

## 53.5 Policy libraries and Pod Security

Use community policy libraries:

- **Gatekeeper library** — CIS benchmarks, PSA equivalents
- **Kyverno policies** — Alternative YAML-native policy engine
- **Pod Security Admission (PSA)** — Built-in K8s 1.25+ (`restricted`, `baseline`, `privileged`)

Namespace labels for PSA:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
```

Compare:

| Engine | Language | Strength |
|--------|----------|----------|
| Gatekeeper/OPA | Rego | Flexible, complex policies |
| Kyverno | YAML | K8s-native, easier onboarding |
| PSA | Built-in | Baseline pod hardening |

Many orgs: PSA for baseline + Gatekeeper/Kyverno for org-specific rules.

---

## 53.6 Runtime security program

Layered Kubernetes security:

```
1. Pod Security Admission (restricted)
2. Gatekeeper/Kyverno admission policies
3. NetworkPolicies (default deny)
4. Falco runtime detection
5. Audit logging → SIEM
6. Regular policy review and game days
```

Metrics:

- Admission deny rate (misconfigurations vs attacks)
- Falco alert volume and true positive rate
- Time to remediate policy violations

---

## 53.7 Chapter summary

- Falco detects anomalous runtime behavior via kernel events and K8s audit with customizable rules.
- OPA Gatekeeper enforces Rego policies at Kubernetes admission—preventing non-compliant workloads.
- Combine admission control (prevent) with runtime detection (detect/respond).
- Use PSA, NetworkPolicies, and policy libraries for defense in depth.

---

## 🧪 Lab 53.1 — Falco shell detection

1. Install Falco on test cluster (eBPF driver).
2. Deploy nginx pod; exec bash inside container.
3. Confirm Falco alert in logs or Falcosidekick webhook.
4. Add exception rule for approved debug namespace.

---

## 🧪 Lab 53.2 — Gatekeeper privileged block

1. Install Gatekeeper; apply ConstraintTemplate blocking privileged pods.
2. Attempt `kubectl run` with `--privileged`; confirm denial.
3. Deploy compliant pod; confirm success.

---

## Review questions

1. Distinguish runtime detection from admission control with examples.
2. How does Falco obtain visibility into container behavior?
3. What are ConstraintTemplate and Constraint in Gatekeeper?
4. Write Rego logic conceptually to deny containers running as root.
5. Compare OPA Gatekeeper and Kyverno for Kubernetes policy.
6. How do Pod Security Admission levels differ?
7. What tuning is needed before Falco alerts page on-call?

---

*Continue: Chapter 54 — Compliance Automation*
