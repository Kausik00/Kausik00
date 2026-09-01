# DevOps Handbook — Master Table of Contents

**Target length:** ~1,200 pages (~480,000 words)  
**Audience:** Beginner → Advanced  
**Format:** Each numbered section ≈ one "page" of ~400 words in the final edition

---

## How to read this handbook

Work through **Parts I–XII** in order. Labs (marked 🧪) add hands-on time beyond page counts. Cross-reference the [AWS Handbook](../aws-handbook/00-table-of-contents.md) for cloud-specific depth.

---

## Part I — Introduction & Mindset (Pages 1–60)

| Ch | Title | Pages |
|----|-------|-------|
| 1 | What Is DevOps? History and Culture | 1–15 |
| 2 | CALMS, Three Ways, and Team Topologies | 16–30 |
| 3 | DevOps vs SRE vs Platform Engineering | 31–42 |
| 4 | Career Paths, Certifications, and Learning Strategy | 43–60 |

**Written:** [Chapters 1–4](./part-01-introduction/chapter-01-what-is-devops.md) (Introduction complete)

---

## Part II — Linux & Shell Mastery (Pages 61–140)

| Ch | Title | Pages |
|----|-------|-------|
| 5 | Linux Fundamentals: Filesystem, Users, Permissions | 61–85 |
| 6 | Processes, systemd, and Service Management | 86–105 |
| 7 | Networking on Linux: ip, ss, curl, dig | 106–120 |
| 8 | Bash Scripting for Automation | 121–140 |

**Written:** [Chapter 5](./part-02-linux/chapter-05-linux-fundamentals.md), [Chapter 6](./part-02-linux/chapter-06-processes-systemd.md), [Chapter 7](./part-02-linux/chapter-07-networking-linux.md), [Chapter 8](./part-02-linux/chapter-08-bash-scripting.md)

---

## Part III — Git & Collaboration (Pages 141–200)

| Ch | Title | Pages |
|----|-------|-------|
| 9 | Git Internals: Objects, Refs, and the DAG | 141–158 |
| 10 | Branching Strategies and Code Review | 159–175 |
| 11 | GitHub/GitLab Workflows: PRs, Issues, Actions intro | 176–200 |

**Written:** [Chapter 9](./part-03-git/chapter-09-git-internals.md), [Chapter 10](./part-03-git/chapter-10-branching-code-review.md), [Chapter 11](./part-03-git/chapter-11-github-gitlab-workflows.md)

---

## Part IV — Networking for DevOps (Pages 201–280)

| Ch | Title | Pages |
|----|-------|-------|
| 12 | OSI Model, TCP/IP, DNS Deep Dive | 201–225 |
| 13 | HTTP/HTTPS, TLS, and Certificates | 226–245 |
| 14 | Load Balancing, Proxies, and CDN Concepts | 246–265 |
| 15 | Cloud Networking Patterns (VPC overview) | 266–280 |

**Written:** [Chapter 12](./part-04-networking/chapter-12-osi-tcpip-dns.md) through [Chapter 15](./part-04-networking/chapter-15-cloud-networking-vpc.md)

---

## Part V — Scripting & Programming (Pages 281–360)

| Ch | Title | Pages |
|----|-------|-------|
| 16 | Python for DevOps: boto3, requests, pathlib | 281–305 |
| 17 | Go for CLI Tools and Operators | 306–325 |
| 18 | JSON/YAML, Jinja2, and Templating | 326–345 |
| 19 | Testing Automation Scripts | 346–360 |

**Written:** [Chapter 16](./part-05-scripting/chapter-16-python-devops.md) through [Chapter 19](./part-05-scripting/chapter-19-testing-automation.md)

---

## Part VI — Infrastructure as Code (Pages 361–480)

| Ch | Title | Pages |
|----|-------|-------|
| 20 | IaC Principles: State, Idempotency, Drift | 361–380 |
| 21 | Terraform: HCL, Providers, Modules | 381–410 |
| 22 | Terraform: Workspaces, Backends, CI Integration | 411–430 |
| 23 | Ansible: Playbooks, Roles, Inventories | 431–450 |
| 24 | Packer & Golden Images | 451–465 |
| 25 | Policy as Code: OPA, Checkov, Sentinel | 466–480 |

---

## Part VII — Containers (Pages 481–580)

| Ch | Title | Pages |
|----|-------|-------|
| 26 | Docker: Images, Dockerfile, Multi-stage Builds | 481–505 |
| 27 | Container Networking, Volumes, and Security | 506–525 |
| 28 | Docker Compose and Local Dev Environments | 526–540 |
| 29 | Container Registries and Image Signing | 541–560 |
| 30 | Rootless Containers and Alternatives (Podman) | 561–580 |

---

## Part VIII — Kubernetes (Pages 581–720)

| Ch | Title | Pages |
|----|-------|-------|
| 31 | K8s Architecture: Control Plane & Node Components | 581–605 |
| 32 | Workloads: Pod, Deployment, StatefulSet, DaemonSet | 606–630 |
| 33 | Services, Ingress, and Network Policies | 631–655 |
| 34 | ConfigMaps, Secrets, and Storage (PV/PVC) | 656–675 |
| 35 | Helm, Kustomize, and GitOps (Argo CD) | 676–700 |
| 36 | RBAC, Pod Security, and Hardening | 701–720 |

---

## Part IX — CI/CD (Pages 721–840)

| Ch | Title | Pages |
|----|-------|-------|
| 37 | CI/CD Concepts and Pipeline Design | 721–745 |
| 38 | GitHub Actions: Workflows, Secrets, Runners | 746–770 |
| 39 | Jenkins: Pipelines as Code (Declarative) | 771–790 |
| 40 | GitLab CI and Multi-platform Comparison | 791–810 |
| 41 | Deployment Strategies: Blue/Green, Canary, Feature Flags | 811–825 |
| 42 | DORA Metrics and Continuous Improvement | 826–840 |

---

## Part X — Observability & SRE (Pages 841–960)

| Ch | Title | Pages |
|----|-------|-------|
| 43 | Monitoring Fundamentals: Metrics, Logs, Traces | 841–865 |
| 44 | Prometheus & Grafana Stack | 866–890 |
| 45 | ELK/EFK and Log Aggregation | 891–910 |
| 46 | OpenTelemetry and Distributed Tracing | 911–930 |
| 47 | SLOs, Error Budgets, and Incident Response | 931–945 |
| 48 | Chaos Engineering and Game Days | 946–960 |

---

## Part XI — Security (DevSecOps) (Pages 961–1080)

| Ch | Title | Pages |
|----|-------|-------|
| 49 | Shift-Left Security in the Pipeline | 961–980 |
| 50 | SAST, DAST, SCA, and Container Scanning | 981–1000 |
| 51 | Secrets Management: Vault, SOPS, External Secrets | 1001–1020 |
| 52 | Supply Chain: SBOM, Sigstore, SLSA | 1021–1040 |
| 53 | Runtime Security: Falco, OPA Gatekeeper | 1041–1060 |
| 54 | Compliance Automation and Audit Trails | 1061–1080 |

---

## Part XII — Advanced Topics (Pages 1081–1200)

| Ch | Title | Pages |
|----|-------|-------|
| 55 | Platform Engineering & Internal Developer Platforms | 1081–1100 |
| 56 | Multi-Cloud and Hybrid Patterns | 1101–1115 |
| 57 | FinOps and Cost-Aware Engineering | 1116–1130 |
| 58 | MLOps Overview for DevOps Engineers | 1131–1145 |
| 59 | Capstone: End-to-End Production System Design | 1146–1180 |
| 60 | Appendix: Command Cheatsheets, Glossary, Index | 1181–1200 |

---

## Expansion status

| Part | Status |
|------|--------|
| I | ✅ Ch 1–4 complete |
| II | ✅ Ch 5–8 complete |
| III | ✅ Ch 9–11 complete |
| IV | ✅ Ch 12–15 complete |
| V | ✅ Ch 16–19 complete |
| VI | ✅ Ch 20–25 complete |
| VII | ✅ Ch 26–30 complete |
| VIII | ✅ Ch 31–36 complete |
| IX | ✅ Ch 37–42 complete |
| X | ✅ Ch 43–48 complete |
| XI | ✅ Ch 49–54 complete |
| XII | ✅ Ch 55–60 complete |

**All 60 chapters written with in-depth content.**
