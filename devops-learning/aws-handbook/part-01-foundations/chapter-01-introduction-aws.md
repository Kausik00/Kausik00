# Chapter 1: Introduction to AWS & the Shared Responsibility Model

*AWS Handbook — Pages 5–7 of this PDF edition*
---

## 1.1 What is Amazon Web Services (AWS)?

**Amazon Web Services (AWS)** is a comprehensive **cloud computing platform** offering on-demand compute, storage, databases, networking, machine learning, and 200+ other services. Instead of buying physical servers, you provision resources in minutes and pay primarily for what you use.

### Why AWS matters for DevOps

- **API-driven** — Every service is controllable via CLI, SDK, and IaC.
- **Global scale** — Deploy in multiple regions for resilience and latency.
- **Managed services** — Offload undifferentiated heavy lifting (RDS, EKS, Lambda).
- **Ecosystem** — Largest cloud market share; extensive documentation and community.

---

## 1.2 Cloud service models

| Model | You manage | Provider manages | AWS examples |
|-------|------------|------------------|--------------|
| **IaaS** | OS, apps, data | Hardware, network, hypervisor | EC2, VPC, EBS |
| **PaaS** | Apps, data | Runtime, OS, infra | Elastic Beanstalk, App Runner |
| **SaaS** | Configuration, data | Everything else | WorkSpaces, Chime |
| **FaaS** | Function code | Everything else | Lambda |

**Containers** blur lines: ECS/EKS give you orchestration (between IaaS and PaaS).

---

## 1.3 The Shared Responsibility Model

Security and compliance are **shared** between AWS and the customer. The boundary shifts by service type.

### AWS is responsible for **Security OF the Cloud**

- Physical data centers
- Hardware and global network
- Virtualization layer
- Managed service patching (for fully managed services)

### You are responsible for **Security IN the Cloud**

- Data classification and encryption choices
- IAM users, roles, and policies
- Operating system patches (on EC2)
- Network configuration (security groups, NACLs)
- Application code security

```
┌─────────────────────────────────────────────────────────┐
│  CUSTOMER RESPONSIBILITY                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Data · Application · IAM · OS (EC2) · Network    │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  AWS RESPONSIBILITY                         │  │  │
│  │  │  Compute · Storage · Database · Networking  │  │  │
│  │  │  (managed service scope varies)             │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Example: RDS vs EC2 MySQL

| Task | EC2 + self-managed MySQL | Amazon RDS |
|------|--------------------------|------------|
| Patch MySQL | **You** | **AWS** |
| Patch OS | **You** | **AWS** |
| Configure security groups | **You** | **You** |
| Encrypt data at rest | **You** (configure) | **You** (enable) |
| Physical security | **AWS** | **AWS** |

---

## 1.4 Core AWS concepts

| Concept | Definition |
|---------|------------|
| **Region** | Geographic area (e.g., `us-east-1`, `eu-west-1`) |
| **Availability Zone (AZ)** | Isolated data center within a region |
| **Account** | Billing and security boundary (12-digit ID) |
| **Resource** | Any AWS entity (EC2 instance, S3 bucket, etc.) |
| **ARN** | Amazon Resource Name — unique identifier |
| **Tag** | Key-value metadata on resources |

Example ARN:
```
arn:aws:s3:::my-bucket
arn:aws:ec2:us-east-1:123456789012:instance/i-0abcd1234
```

---

## 1.5 AWS console, CLI, and IaC

Three ways to interact with AWS:

1. **Management Console** — Web UI; great for learning and ad-hoc tasks.
2. **AWS CLI** — Scriptable; essential for automation.
3. **Infrastructure as Code** — CloudFormation, CDK, Terraform for reproducible environments.

DevOps engineers spend most time in **CLI + IaC**, using the console for debugging.

---

## 1.6 Pricing fundamentals

- **On-Demand** — Pay per hour/second; no commitment.
- **Reserved Instances / Savings Plans** — 1–3 year commitment; lower cost.
- **Spot Instances** — Unused capacity; cheap but can be interrupted.
- **Free Tier** — Limited free usage for 12 months (and some always-free services).

**Always set billing alarms** (AWS Budgets) on new accounts.

---

## 1.7 Well-Architected Framework (preview)

AWS defines six pillars for good architecture (covered throughout this handbook):

1. Operational Excellence
2. Security
3. Reliability
4. Performance Efficiency
5. Cost Optimization
6. Sustainability

---

## 1.8 Chapter summary

- AWS provides on-demand cloud infrastructure and managed services.
- **Shared responsibility** splits security between AWS and you—know your side.
- Learn **regions, accounts, ARNs, and tags** early.
- Use CLI and IaC for production; console for exploration.

---

## 🧪 Lab 1.1 — Create your AWS account

1. Sign up at https://aws.amazon.com (use a dedicated email).
2. Enable **MFA** on the root account; do not use root daily.
3. Create an **IAM admin user** for daily work.
4. Set a **billing budget** alert at $10 or your comfort threshold.
5. Explore the console: EC2, S3, IAM dashboards.

---

## Review questions

1. What is the difference between IaaS and PaaS? Give one AWS example of each.
2. Who patches the OS on an EC2 instance?
3. What is an ARN used for?
4. Name two AWS pricing models.

---

*Next: [Chapter 2 — Global Infrastructure](./chapter-02-global-infrastructure.md)*
