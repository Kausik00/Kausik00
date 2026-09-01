# Chapter 15: Cloud Networking Patterns — VPC Overview

*DevOps Handbook — Part IV, Pages 266–280*

---

## 15.1 VPC: your private network in the cloud

A **Virtual Private Cloud (VPC)** is an isolated virtual network in AWS, GCP (**VPC**), or Azure (**VNet**). You define IP ranges, subnets, routing, firewalls, and attachments to on-prem or other clouds.

DevOps engineers provision VPCs via Terraform, deploy workloads into **private subnets**, and expose services through **controlled ingress**—not public IPs on every VM.

Conceptual map (AWS-centric; others analogous):

| AWS | GCP | Azure |
|-----|-----|-------|
| VPC | VPC | Virtual Network |
| Subnet | Subnet | Subnet |
| Security Group | Firewall rule (VPC) | NSG |
| NACL | — (less common pattern) | NACL (optional) |
| Internet Gateway | — | Internet Gateway |
| NAT Gateway | Cloud NAT | NAT Gateway |
| Route 53 private zone | Cloud DNS private | Private DNS zone |

---

## 15.2 CIDR design fundamentals

Plan **non-overlapping** CIDR blocks before peering or VPN:

```
VPC: 10.0.0.0/16
├── public-a:   10.0.0.0/24   (AZ a) — LB, NAT
├── public-b:   10.0.1.0/24   (AZ b)
├── private-a:  10.0.10.0/24  (AZ a) — apps, workers
├── private-b:  10.0.11.0/24  (AZ b)
└── data-a/b:   10.0.20.0/24, 10.0.21.0/24 — databases
```

Rules of thumb:

- Leave **spare capacity** in VPC CIDR for growth.
- **Multi-AZ** subnets for HA—one failure domain per AZ.
- Put **internet-facing LBs** in public subnets; **instances** in private subnets without public IPs.

---

## 15.3 Public vs private subnets

| Subnet type | Default route | Typical resources |
|-------------|---------------|-------------------|
| **Public** | `0.0.0.0/0 → Internet Gateway` | NAT GW, public ALB, bastion (legacy) |
| **Private** | `0.0.0.0/0 → NAT Gateway` (optional) | App servers, EKS nodes, RDS |

Private subnets **without NAT** cannot reach the internet—ideal for data layers with VPC endpoints only.

```
Internet
    ↓
Internet Gateway
    ↓
Public subnet (ALB, NAT)
    ↓
Private subnet (application tier)
    ↓
Private subnet (database, no NAT)
```

---

## 15.4 Security groups vs NACLs

### Security groups (stateful)

- Instance/network interface level.
- **Allow rules only**; implicit deny.
- **Stateful**—return traffic automatically allowed.
- Example: allow 443 from `0.0.0.0/0` to ALB SG; allow 8080 from ALB SG to app SG.

### Network ACLs (stateless, AWS)

- Subnet level; optional deny rules.
- **Stateless**—must allow ephemeral return ports explicitly if used.
- Less common in day-to-day DevOps than SGs.

**Defense in depth:** SG for fine-grained app rules; NACL for coarse subnet blocks if compliance requires.

---

## 15.5 NAT, egress, and VPC endpoints

**NAT Gateway** lets private instances initiate outbound internet (package updates, external APIs) without inbound exposure. Costs and bandwidth add up—monitor NAT metrics.

**VPC endpoints** (AWS **Interface** and **Gateway** endpoints) keep traffic on AWS backbone:

| Endpoint type | Example | Avoids |
|---------------|---------|--------|
| Gateway | S3, DynamoDB | Internet for AWS API |
| Interface | ECR, Secrets Manager, STS | Public NAT egress |

For EKS pulling images from ECR, **interface endpoints** reduce NAT dependency and improve security posture.

---

## 15.6 Hybrid and multi-VPC connectivity

| Pattern | Use case |
|---------|----------|
| **VPC peering** | Connect two VPCs (non-transitive) |
| **Transit Gateway** | Hub-and-spoke many VPCs |
| **VPN / Direct Connect** | On-prem to cloud |
| **PrivateLink** | Consumer access to service without full peering |

Peering requires **non-overlapping CIDRs**. Transitive routing pitfalls break naive "peer everything" designs—document a **network topology diagram**.

---

## 15.7 Kubernetes networking in VPC

Managed Kubernetes (EKS, GKE, AKS) integrates CNI plugins assigning pod IPs from VPC or overlay ranges.

DevOps concerns:

- **Pod CIDR vs VPC CIDR**—must not overlap peered networks.
- **Security groups for pods** (where supported) replace blanket node SG rules.
- **LoadBalancer Service** provisions cloud LB into public/private subnets per annotation.
- **Internal-only services** use internal LB annotations and private DNS.

---

## 15.8 IaC example (Terraform sketch)

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "us-east-1a"
}

resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Store network diagrams alongside Terraform for reviewers who don't read HCL daily.

---

## 15.9 Operational checklist

Before production launch:

1. **No 0.0.0.0/0 SSH** on app SGs—use SSM Session Manager or bastion with MFA.
2. **Flow logs** enabled on VPC or key subnets for forensics.
3. **Route tables** verified per subnet—accidental IGW on DB subnet is a data breach.
4. **DNS** private zones linked to VPC; resolver rules for hybrid.
5. **Quota limits** checked (EIPs, NAT GW per AZ, LB limits).

---

## 15.10 Chapter summary

- **VPC** isolates cloud resources with subnets, routes, and firewalls.
- **Public subnets** expose ingress paths; **private subnets** protect workloads.
- **Security groups** are stateful primary filters; know when **NACLs** apply.
- **NAT** vs **VPC endpoints** trade cost, security, and simplicity for egress.
- Plan **CIDR and peering** early; overlaps are painful to fix later.

---

## 🧪 Lab 15.1 — Paper VPC design

1. Design a VPC for a three-tier app (web, app, DB) in two AZs.
2. Assign CIDR blocks and list route table entries for each subnet type.
3. Document SG rules as a matrix: source → destination → port.
4. Identify which traffic uses IGW, NAT, and VPC endpoints.

---

## 🧪 Lab 15.2 — Terraform mini-VPC (optional cloud)

1. Apply a module creating VPC + one public + one private subnet.
2. Launch a test instance in private subnet without public IP.
3. Verify outbound via NAT with `curl` and inbound denial from internet.
4. Tear down to avoid charges.

---

## Review questions

1. What is the difference between public and private subnets at the routing layer?
2. Why are security groups described as stateful?
3. When would you use a VPC endpoint instead of NAT for S3 access?
4. What problem does non-overlapping CIDR solve in peering?
5. Where should an internet-facing ALB sit in a well-designed VPC?

---

*Next: [Chapter 16 — Python for DevOps](../part-05-scripting/chapter-16-python-devops.md)*
