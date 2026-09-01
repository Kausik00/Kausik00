# DevOps Curriculum: Tools & Concepts (Beginner → Advanced)

Complete reference of what to learn, in recommended order. Items marked **(adv)** are advanced topics.

---

## Level 0 — Prerequisites (before DevOps)

### Concepts
- Software development lifecycle (SDLC)
- Agile, Scrum, Kanban
- Waterfall vs iterative delivery
- Client–server architecture
- APIs (REST, GraphQL basics)
- Databases (SQL vs NoSQL overview)
- Environment tiers: dev, staging, production

### Tools & Skills
| Category | Tools / Skills |
|----------|----------------|
| Operating systems | Linux (Ubuntu, RHEL), Windows Server basics |
| Shell | Bash, Zsh, PowerShell basics |
| Text editing | Vim, Nano, VS Code |
| Networking | TCP/IP, DNS, HTTP/HTTPS, TLS, ports, firewalls |
| Version control | Git (clone, branch, merge, rebase, cherry-pick) |
| Scripting | Python, Bash, Go (pick one primary) |
| Documentation | Markdown, diagrams (draw.io, Mermaid) |

---

## Level 1 — DevOps Foundations

### Concepts
- What is DevOps? Culture, CALMS (Culture, Automation, Lean, Measurement, Sharing)
- DevOps vs SysAdmin vs SRE vs Platform Engineering
- Continuous Integration (CI) vs Continuous Delivery (CD) vs Continuous Deployment
- Build artifacts, immutable infrastructure
- Configuration vs secrets
- The Twelve-Factor App
- DevSecOps introduction
- GitOps introduction

### Tools
| Category | Tools |
|----------|-------|
| Git hosting | GitHub, GitLab, Bitbucket, Azure DevOps Repos |
| SSH & keys | OpenSSH, ssh-agent, key pairs |
| Package managers | apt, yum/dnf, Homebrew |
| Build tools | Make, Maven, Gradle, npm/yarn/pnpm |
| Virtualization | VirtualBox, VMware, Hyper-V |
| Cloud CLI basics | AWS CLI, gcloud, az |

---

## Level 2 — Infrastructure & Automation

### Concepts
- Infrastructure as Code (IaC) principles
- Idempotency, declarative vs imperative
- Server provisioning & bootstrapping
- Configuration management
- Immutable vs mutable infrastructure
- Golden images / AMIs
- Inventory & state management

### Tools
| Category | Tools |
|----------|-------|
| IaC — Terraform | Terraform, OpenTofu, Terragrunt |
| IaC — Cloud-native | AWS CloudFormation, Azure Bicep/ARM, Google Deployment Manager, Pulumi, CDK (AWS/Azure/GCP) |
| Configuration mgmt | Ansible, Chef, Puppet, SaltStack |
| Image building | Packer |
| Secrets (intro) | HashiCorp Vault, AWS Secrets Manager, SOPS |
| Cloud VMs | EC2, Azure VMs, GCE |

---

## Level 3 — Containers & Orchestration

### Concepts
- Containers vs VMs
- Images, layers, registries
- Dockerfile best practices
- Container networking & storage
- Orchestration primitives (Pod, Service, Deployment)
- Service mesh concepts
- Sidecar pattern
- Helm charts & package management

### Tools
| Category | Tools |
|----------|-------|
| Runtime | Docker, containerd, CRI-O, Podman |
| Compose / local | Docker Compose, Dev Containers |
| Registries | Docker Hub, ECR, GCR, ACR, Harbor, Artifactory |
| Orchestration | Kubernetes (K8s), Amazon ECS, Amazon EKS, GKE, AKS |
| K8s tooling | kubectl, k9s, Lens, Helm, Kustomize |
| Service mesh | Istio, Linkerd, Consul Connect |
| Local K8s | minikube, kind, k3s, Docker Desktop K8s |

---

## Level 4 — CI/CD Pipelines

### Concepts
- Pipeline stages: source → build → test → scan → deploy
- Branching strategies (GitFlow, trunk-based)
- Artifact versioning & promotion
- Blue/green, canary, rolling deployments
- Feature flags
- Pipeline as Code
- DORA metrics (deployment frequency, lead time, MTTR, change failure rate)

### Tools
| Category | Tools |
|----------|-------|
| CI/CD platforms | Jenkins, GitHub Actions, GitLab CI, CircleCI, Travis CI, Azure Pipelines, AWS CodePipeline, Tekton, Argo CD (GitOps) |
| Build agents | Jenkins agents, GitHub-hosted/self-hosted runners |
| Artifact repos | Nexus, Artifactory, GitHub Packages |
| GitOps | Argo CD, Flux, Fleet |
| Deployment | Spinnaker, Harness, Octopus Deploy |

---

## Level 5 — Cloud Platforms (cross-cutting)

### Concepts
- Shared responsibility model
- Regions, AZs, edge locations
- IAM (users, roles, policies, least privilege)
- VPC networking (subnets, routing, NAT, peering)
- Load balancing (L4 vs L7)
- Object storage vs block vs file
- Managed vs self-managed services
- Well-Architected Framework pillars
- Cost optimization & tagging
- Multi-account / landing zone strategy

### Tools (by provider)
| Provider | Core services to learn |
|----------|------------------------|
| AWS | See [curriculum-aws.md](./curriculum-aws.md) |
| Azure | Resource Manager, AAD, VNet, AKS, App Service |
| GCP | IAM, VPC, GKE, Cloud Run, Cloud Build |

---

## Level 6 — Observability & Reliability

### Concepts
- Monitoring vs observability (metrics, logs, traces)
- SLI, SLO, SLA, error budgets
- Alerting philosophy (symptom vs cause)
- On-call, incident management, postmortems
- Chaos engineering
- Capacity planning
- Distributed tracing

### Tools
| Category | Tools |
|----------|-------|
| Metrics | Prometheus, Grafana, Datadog, New Relic, CloudWatch, Azure Monitor |
| Logging | ELK/EFK (Elasticsearch, Logstash/Fluentd, Kibana), Loki, Splunk, CloudWatch Logs |
| Tracing | Jaeger, Zipkin, OpenTelemetry, AWS X-Ray, Honeycomb |
| APM | Datadog APM, Dynatrace, AppDynamics |
| Incident mgmt | PagerDuty, Opsgenie, incident.io |
| Status | Statuspage |
| Chaos | Chaos Monkey, LitmusChaos, Gremlin |

---

## Level 7 — Security (DevSecOps)

### Concepts
- Shift-left security
- OWASP Top 10
- Supply chain security (SBOM, signing)
- Zero trust networking
- CIS benchmarks
- Compliance frameworks (SOC 2, PCI-DSS, HIPAA overview)
- Threat modeling
- Principle of least privilege

### Tools
| Category | Tools |
|----------|-------|
| SAST | SonarQube, Semgrep, CodeQL, Checkmarx |
| DAST | OWASP ZAP, Burp Suite |
| Container scan | Trivy, Grype, Snyk, Clair |
| IaC scan | Checkov, tfsec, KICS, cfn-lint |
| Secrets scan | git-secrets, TruffleHog, Gitleaks |
| Policy as code | OPA, Gatekeeper, Kyverno, Sentinel |
| WAF / edge | AWS WAF, Cloudflare, ModSecurity |
| PKI / certs | cert-manager, Let's Encrypt, ACM |
| SIEM | Splunk, Elastic Security, AWS Security Hub |

---

## Level 8 — Data, Messaging & Databases (Ops view)

### Concepts
- Backup & restore strategies (RPO/RTO)
- Replication, failover, DR
- Connection pooling
- Caching layers
- Message queues & event-driven architecture
- Database migrations in CI/CD

### Tools
| Category | Tools |
|----------|-------|
| RDBMS | PostgreSQL, MySQL, MariaDB, SQL Server |
| NoSQL | MongoDB, DynamoDB, Redis, Cassandra |
| Messaging | Kafka, RabbitMQ, SQS, SNS, Pub/Sub |
| Streaming | Kinesis, Flink, Spark Streaming |
| Backup | Velero (K8s), AWS Backup, pg_dump, Percona XtraBackup |
| Migrations | Flyway, Liquibase, Alembic |

---

## Level 9 — Platform Engineering & Internal Developer Platforms (adv)

### Concepts
- Platform as a product
- Developer experience (DevEx)
- Self-service portals
- Golden paths & paved roads
- Service catalogs
- Backstage software templates

### Tools
| Category | Tools |
|----------|-------|
| IDP | Backstage, Port, Cortex |
| API gateways | Kong, Apigee, AWS API Gateway, Ambassador |
| Service discovery | Consul, Eureka, CoreDNS |
| Feature flags | LaunchDarkly, Unleash, Flagsmith |

---

## Level 10 — Advanced & Specialized (adv)

### Concepts
- Site Reliability Engineering (SRE) — toil reduction, automation
- FinOps & cloud cost governance
- Multi-cloud & hybrid cloud
- Edge computing & CDN strategy
- WebAssembly in ops (adv)
- eBPF for observability (adv)
- ML/LLM ops (MLOps) pipelines

### Tools
| Category | Tools |
|----------|-------|
| FinOps | Kubecost, CloudHealth, AWS Cost Explorer, Infracost |
| CDN | CloudFront, Cloudflare, Fastly, Akamai |
| DNS | Route 53, Cloudflare DNS, ExternalDNS |
| Workflow | Airflow, Temporal, Step Functions |
| MLOps | MLflow, Kubeflow, SageMaker (AWS) |
| eBPF | Cilium, Pixie, Falco |

---

## Certifications (optional milestones)

| Track | Certifications |
|-------|----------------|
| Linux | LPIC, RHCSA/RHCE |
| Cloud | AWS SAA, AWS DVA, AWS SOA, AWS DOP, AWS SAP; Azure AZ-104, AZ-400; GCP PCA |
| Kubernetes | CKA, CKAD, CKS |
| Terraform | HashiCorp Terraform Associate |
| Security | CISSP (broad), AWS Security Specialty |
| SRE | Google SRE book + practice (no single cert) |

---

## Learning project ideas (apply everything)

1. **Static site pipeline** — S3 + CloudFront + GitHub Actions + Terraform
2. **Microservices on EKS** — Helm, Prometheus, Argo CD
3. **Full observability stack** — app + OpenTelemetry + Grafana stack
4. **Secure CI/CD** — SAST/DAST/SCA in pipeline, signed images
5. **Multi-env IaC** — dev/stage/prod with Terragrunt or Terraform workspaces
6. **Incident simulation** — chaos tests + runbooks + PagerDuty
7. **Internal developer portal** — Backstage with one golden-path service
