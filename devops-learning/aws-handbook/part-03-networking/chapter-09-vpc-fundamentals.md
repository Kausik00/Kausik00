# Chapter 9: VPC Fundamentals — CIDR, Subnets, and Route Tables

*AWS Handbook — Pages 37–39 of this PDF edition*
---

## 9.1 What is a VPC?

A **Virtual Private Cloud (VPC)** is your isolated network in AWS. You control IP ranges, subnets, routing, and firewalls.

Every AWS account has a **default VPC** per region (with public subnets). Production workloads use **custom VPCs** with explicit design.

---

## 9.2 CIDR and IP planning

**CIDR** (Classless Inter-Domain Routing) defines IP ranges:

| CIDR | Addresses | Usable (AWS reserves 5) |
|------|-----------|-------------------------|
| `10.0.0.0/16` | 65,536 | ~65,531 |
| `10.0.1.0/24` | 256 | ~251 |
| `10.0.1.0/28` | 16 | ~11 |

### Example VPC design

```
VPC: 10.0.0.0/16

Public subnets (ALB, NAT Gateway):
  10.0.1.0/24  — us-east-1a
  10.0.2.0/24  — us-east-1b

Private subnets (app servers, ECS, Lambda):
  10.0.10.0/24 — us-east-1a
  10.0.11.0/24 — us-east-1b

Database subnets (RDS, no internet):
  10.0.20.0/24 — us-east-1a
  10.0.21.0/24 — us-east-1b
```

**Tip:** Plan for growth; changing VPC CIDR later is painful. Use `/16` for VPC, `/24` for subnets.

---

## 9.3 Subnets

Subnets live in **one Availability Zone**. Types:

| Type | Route to IGW | Typical workloads |
|------|--------------|-------------------|
| **Public** | Yes (via route table) | ALB, NAT Gateway, bastion |
| **Private** | No direct IGW | App servers, workers |
| **Isolated** | No NAT either | Databases |

`map_public_ip_on_launch = true` assigns public IPs to instances in public subnets.

---

## 9.4 Route tables

A **route table** defines where traffic goes:

| Destination | Target | Meaning |
|-------------|--------|---------|
| `10.0.0.0/16` | local | Traffic within VPC |
| `0.0.0.0/0` | igw-xxxxx | Internet via Internet Gateway |
| `0.0.0.0/0` | nat-xxxxx | Internet via NAT Gateway (private subnet) |
| `pl-xxxxx` | VPC Endpoint | Private AWS service access |

Each subnet associates with **one** route table.

---

## 9.5 Internet Gateway and NAT (preview)

- **Internet Gateway (IGW)** — VPC component for bidirectional internet access
- **NAT Gateway** — Allows private subnet instances to reach internet (outbound only); place in public subnet

```
Internet
    │
    ▼
┌─────────┐     ┌──────────────────┐
│   IGW   │────►│ Public subnet    │
└─────────┘     │ (ALB, NAT GW)    │
                └────────┬─────────┘
                         │
                ┌────────▼─────────┐
                │ Private subnet   │
                │ (app servers)    │
                └──────────────────┘
```

---

## 9.6 Security Groups vs NACLs

| | Security Group | NACL |
|---|----------------|------|
| Level | Instance/ENI | Subnet |
| State | Stateful | Stateless |
| Rules | Allow only | Allow and deny |
| Default | Deny all inbound | Allow all |

**Best practice:** Use security groups as primary firewall; NACLs for subnet-level deny rules if needed.

Example security group for web tier:

- Inbound: 443 from ALB security group
- Outbound: 5432 to database security group

---

## 9.7 Terraform VPC snippet

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "prod-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true
}
```

---

## 9.8 Chapter summary

- Design VPCs with **public**, **private**, and **database** subnet tiers across **multiple AZs**.
- **Route tables** control internet and local routing.
- **Security groups** are stateful instance firewalls; default deny inbound.

---

## 🧪 Lab 9.1

1. Create a custom VPC with 2 public and 2 private subnets in different AZs.
2. Attach an Internet Gateway and configure route tables.
3. Launch an EC2 in a private subnet (no public IP) and verify no direct internet access.

---

*Next: [Chapter 10 — NAT and Routing](../part-03-networking/chapter-10-nat-routing.md)*
