# Chapter 42: VPC Design Cookbook

*AWS Handbook — Pages 216–222 of this PDF edition*

This workbook is a production-oriented companion to the networking chapters in Parts III. It is not a recap of “what a VPC is.” It is a design cookbook: CIDR strategies that survive mergers, subnet layouts that keep NAT bills under control, route-table patterns that do not surprise on-call, and Terraform you can paste into a landing-zone module. Work through the labs in a throwaway account. Tear everything down when you finish.

---

## 42.1 Design goals before you pick a CIDR

A VPC is cheap to create and expensive to live with. The wrong prefix collides with on-premises RFC1918 space, partner VPCs, or a future Transit Gateway attachment. The wrong subnet split forces you to run NAT Gateways in every AZ forever, or to dual-home databases in public subnets because private space ran out.

Write the following down before you open the console:

| Decision | Why it is hard to change later |
|----------|--------------------------------|
| VPC CIDR (and secondary CIDRs) | ENIs, routes, TGW associations, and security-group references all bake in the prefix |
| Number of Availability Zones | Subnet counts, NLB target groups, RDS subnet groups, and EKS node groups assume the AZ set |
| Public vs private vs isolated tiers | Moving a workload across tiers means new ENIs, new routes, and often new security groups |
| Egress model (NAT, egress-only IGW, proxy, central inspection) | Billing and packet path change together |
| DNS (AmazonProvidedDNS vs Route 53 Resolver) | Hybrid name resolution is a program, not a checkbox |

**Rule of thumb:** design for three AZs even if you only use two on day one. Reserve the third AZ’s subnets so you never have to carve leftovers from a `/24` that is already half full.

---

## 42.2 CIDR cookbook

### RFC1918 inventory

Most enterprises already occupy `10.0.0.0/8`. Treat AWS as one more site in that plan, not as a second internet.

| Environment | Example allocation | Notes |
|-------------|--------------------|-------|
| Production region A | `10.64.0.0/16` | `/16` is the default production size |
| Production region B | `10.65.0.0/16` | Adjacent prefixes simplify summarization on TGW |
| Non-prod shared | `10.80.0.0/16` | Split further by account if needed |
| Sandbox | `10.90.0.0/16` | Expect overlap; never peer sandbox to prod |
| On-premises summary | `10.0.0.0/12` | Document the hole you will not use in AWS |

Avoid `172.17.0.0/16` (Docker default bridge) and `169.254.0.0/16` (link-local, including the instance metadata path). Avoid `100.64.0.0/10` unless you fully understand CGNAT and AWS PrivateLink implications.

### How many addresses do you actually need?

AWS reserves five addresses in every subnet (network, VPC router, DNS, future, broadcast). A `/24` yields 251 usable IPs. That sounds large until you run:

- An Application Load Balancer (ENIs grow with traffic and IP targets)
- VPC endpoints (one ENI per AZ per interface endpoint)
- EKS or ECS tasks with `awsvpc` networking (one IP per task or pod)
- Lambda in VPC (ENIs, even with Hyperplane, still consume subnet IPs during scale)

| Workload class | Suggested subnet mask per AZ | Rationale |
|----------------|------------------------------|-----------|
| Isolated data (RDS, ElastiCache) | `/24` or `/26` | Few ENIs; isolation matters more than density |
| Application private | `/22` or `/23` | Containers and Lambda eat IPs |
| Public (ALB, NAT, bastion) | `/24` | Small, predictable |
| TGW / inspection | `/28` | Tiny; dedicated |

### Secondary CIDRs

If you must grow without replacing the VPC, add a secondary IPv4 CIDR and new subnets. Do not assume every service supports secondary CIDRs equally. Document which workloads may land in the new range. Prefer secondary CIDRs that still summarize cleanly on Transit Gateway.

IPv6 dual-stack is the right long-term answer for public-facing and container-dense VPCs. Assign Amazon-provided `/56` to the VPC and `/64` per subnet. Egress-only internet gateways handle IPv6 out without NAT.

---

## 42.3 Three reference topologies

### Topology A — Three-tier regional VPC (most web apps)

```
VPC 10.64.0.0/16

AZ-a                          AZ-b                          AZ-c
10.64.0.0/24  public          10.64.1.0/24  public          10.64.2.0/24  public
10.64.16.0/22 app             10.64.20.0/22 app             10.64.24.0/22 app
10.64.32.0/24 data            10.64.33.0/24 data            10.64.34.0/24 data
```

Route tables:

- **Public:** `0.0.0.0/0` → Internet Gateway; local `10.64.0.0/16`
- **App:** `0.0.0.0/0` → NAT Gateway in the same AZ (avoid cross-AZ NAT data charges and a single NAT as a blast radius)
- **Data:** no `0.0.0.0/0`; only VPC local plus specific prefixes to interface endpoints or TGW if required

This is the default you should be able to draw from memory.

### Topology B — Hub-and-spoke with inspection

Workloads live in spoke VPCs. A network account owns a Transit Gateway and an inspection VPC with Gateway Load Balancer or Gateway Load Balancer endpoints plus firewall appliances (or AWS Network Firewall).

| Path | Typical route |
|------|----------------|
| Spoke → internet | Spoke `0.0.0.0/0` → TGW → inspection VPC → NAT or firewall → IGW |
| Spoke → spoke | TGW route table with associations and optional appliance mode |
| Spoke → on-prem | TGW attachment to VPN or Direct Connect gateway |

**Appliance mode** on the TGW attachment is required when a stateful firewall must see both directions of a flow. Forgetting it produces “it works for a few packets then dies” tickets.

### Topology C — Isolated data VPC with PrivateLink

A data platform VPC has no internet route. Producers reach it through interface VPC endpoints (PrivateLink) or through TGW with tightly scoped prefixes. This is the pattern for PCI cardholder data, healthcare, or a shared Kafka cluster.

---

## 42.4 Gateways, endpoints, and egress cost

NAT Gateways are billed hourly per AZ plus per-gigabyte processing. A chatty microservice estate can spend more on NAT than on compute.

| Egress need | Prefer | Avoid |
|-------------|--------|--------|
| AWS APIs (S3, ECR, Logs, STS) | Gateway endpoints (S3, DynamoDB) and interface endpoints | Hairpinning through NAT to the public AWS endpoint |
| Third-party SaaS | Interface endpoints if the vendor offers PrivateLink; otherwise NAT | Public IPs on app instances |
| Software updates | Centralized HTTP proxy or VPC endpoints for Amazon Linux repos via S3 | Every account with its own NAT farm |
| IPv6 dual-stack | Egress-only IGW | NAT64 unless you have a measured need |

Gateway VPC endpoints for S3 and DynamoDB are free of hourly ENI charges and belong in every production route table that talks to those services. Interface endpoints cost money; create them once in a shared-services VPC and expose them with PrivateLink if you have dozens of spokes.

---

## 42.5 Security groups and NACLs in a designed VPC

Security groups are stateful and should be the primary control. Network ACLs are stateless and useful as a coarse subnet-level guardrail (deny known-bad prefixes, restrict data subnets to RFC1918 sources).

Cookbook rules:

1. One security group per role (ALB, app, data), not per instance name.
2. Reference other security groups as sources, not `/16` CIDRs, for east-west traffic.
3. Do not open `0.0.0.0/0` on port 22 or 3389. Use SSM Session Manager and skip bastions unless a vendor requires SSH.
4. Data-tier security groups accept only the app-tier security group on the database port.
5. If you use NACLs on data subnets, remember ephemeral return ports (1024–65535) or you will break TCP.

---

## 42.6 AWS CLI: inspect a live VPC like an auditor

```bash
REGION=us-east-1
VPC_ID=vpc-0123456789abcdef0

aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --region "$REGION"
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION" \
  --query 'Subnets[].{Id:SubnetId,Az:AvailabilityZone,Cidr:CidrBlock,Public:MapPublicIpOnLaunch}'
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION"
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" --region "$REGION"
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC_ID" --region "$REGION"
aws ec2 describe-flow-logs --filter "Name=resource-id,Values=$VPC_ID" --region "$REGION"
```

Enable VPC Flow Logs to CloudWatch Logs or S3 before you need them. Reject-only logs are cheaper and still catch mis-aimed traffic.

```bash
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids "$VPC_ID" \
  --traffic-type REJECT \
  --log-destination-type cloud-watch-logs \
  --log-group-name /vpc/flow-logs \
  --deliver-logs-permission-arn arn:aws:iam::111122223333:role/vpc-flow-logs
```

---

## 42.7 Terraform: three-AZ VPC module sketch

The following is a teaching module, not a full registry module. It shows the relationships you must get right: one IGW, NAT per AZ, three route table classes, and gateway endpoints.

```hcl
variable "cidr" { default = "10.64.0.0/16" }
variable "azs"  { default = ["us-east-1a", "us-east-1b", "us-east-1c"] }

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "prod-app" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "public" {
  count                   = length(var.azs)
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.azs[count.index]
  cidr_block              = cidrsubnet(var.cidr, 8, count.index)
  map_public_ip_on_launch = true
  tags                    = { Tier = "public", Name = "public-${var.azs[count.index]}" }
}

resource "aws_subnet" "app" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = cidrsubnet(var.cidr, 6, count.index + 4)
  tags              = { Tier = "app", Name = "app-${var.azs[count.index]}" }
}

resource "aws_subnet" "data" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = cidrsubnet(var.cidr, 8, count.index + 32)
  tags              = { Tier = "data", Name = "data-${var.azs[count.index]}" }
}

resource "aws_eip" "nat" {
  count  = length(var.azs)
  domain = "vpc"
}

resource "aws_nat_gateway" "this" {
  count         = length(var.azs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
}

resource "aws_route_table" "app" {
  count  = length(var.azs)
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.us-east-1.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], aws_route_table.app[*].id)
}
```

Associate public subnets to the public table and each app subnet to its AZ-local app table. Leave data subnets on a table with no default route. Add an RDS subnet group that lists only data subnets.

---

## 42.8 Hybrid connectivity without painting yourself into a corner

| Mechanism | When to use | Failure mode |
|-----------|-------------|--------------|
| VPC peering | Two VPCs, no transitive routing needed | Does not transit; CIDR overlap is fatal |
| Transit Gateway | Many VPCs, on-prem, shared services | Route table spaghetti if you do not diagram associations vs propagations |
| PrivateLink | Expose a service without sharing the whole VPC | Throughput and zonal endpoint placement |
| Site-to-Site VPN | Fast hybrid, backup to Direct Connect | MTU, asymmetric routing, BGP vs static |
| Direct Connect | Steady high volume | Attachment design (private VIF vs TGW vs DX gateway) |

**CIDR overlap** is the number-one hybrid blocker. If you cannot guarantee uniqueness, do not peer. Use PrivateLink or a proxy. NAT between overlapping networks is a last resort and a debugging nightmare.

Route 53 Resolver inbound and outbound endpoints belong in a dedicated shared-services subnet pair (two AZs). Forward `corp.example` to on-premises DNS; forward `amazonaws.com` queries from on-premises to inbound endpoints so private hosted zones resolve.

---

## 42.9 Lab 1 — Build Topology A and prove isolation

**Goal:** Create a three-tier VPC, launch a throwaway instance in the app tier, and confirm the data tier has no internet path.

1. Create the VPC, subnets, IGW, NAT, and route tables from the Terraform sketch or equivalent CLI.
2. Launch Amazon Linux in an app subnet with no public IP. Attach a security group that allows only HTTPS egress and SSM (or use the default outbound and lock it after you confirm SSM).
3. Confirm you can reach `https://checkip.amazonaws.com` from the instance (NAT works).
4. Launch a second instance in a data subnet with no public IP and no default route. Confirm it cannot reach the internet.
5. From the app instance, attempt TCP to the data instance on port 5432 with security groups that only allow the app SG. Confirm CONNECT vs timeout.
6. Enable REJECT flow logs and generate a denied attempt. Find the line in CloudWatch Logs Insights.

**Cleanup:** Destroy the Terraform workspace. NAT Gateways and EIPs will otherwise idle-charge overnight.

---

## 42.10 Lab 2 — Cut NAT spend with endpoints

1. From the app instance, time an `aws s3 ls` against a bucket in the same region with only NAT (no S3 gateway endpoint).
2. Add the S3 gateway endpoint and the prefix list routes.
3. Repeat the listing. Packet path should no longer show NAT in VPC Flow Logs for the S3 prefix list.
4. Optionally add `com.amazonaws.region.ecr.api` and `ecr.dkr` interface endpoints if you pull images from private subnets.

Measure NAT `BytesOutToDestination` in CloudWatch before and after. This is the conversation you take to FinOps.

---

## 42.11 Lab 3 — Break and fix a route table

1. Point an app subnet’s `0.0.0.0/0` at a NAT Gateway in a different AZ.
2. Stop that NAT’s AZ with a simulated failure (delete the NAT or the EIP association in a lab only).
3. Observe cross-AZ failure and extra data transfer.
4. Restore same-AZ NAT.

Write a one-page runbook: “How we route egress” with a table of route table IDs.

---

## 42.12 Production checklist

| Check | Pass criteria |
|-------|----------------|
| DNS | `enable_dns_hostnames` and `enable_dns_support` true |
| Flow logs | Enabled, retention set, IAM role least-privilege |
| Public IPs | Only on NAT, ALB, and explicitly public services |
| Subnet space | Documented headroom for EKS/Lambda ENIs |
| Endpoints | S3 and DynamoDB gateway endpoints present |
| Tags | `Name`, `Tier`, `Environment`, `Owner` on every subnet and route table |
| IPv6 | Decision recorded even if “not yet” |
| TGW | No `0.0.0.0/0` propagated into a VPC that should be isolated |

---

## 42.13 Anti-patterns

- One NAT Gateway for three AZs “to save money,” then a zonal outage takes out all egress.
- Default VPC in production.
- `/28` public subnets and then an ALB that cannot scale ENIs.
- Peering every VPC to every other VPC until you have a full mesh you cannot explain.
- Security groups that allow `10.0.0.0/8` on all ports because “we are private.”
- Disabling the VPC router’s DNS and then wondering why `sts.amazonaws.com` resolution differs from on-premises.

---

## 42.14 Review questions

1. AWS reserves how many addresses per subnet, and what are they used for?
2. Why does this cookbook put a NAT Gateway in each AZ instead of one shared NAT?
3. When is VPC peering the wrong tool compared with Transit Gateway or PrivateLink?
4. What is appliance mode on a Transit Gateway attachment, and what breaks if you omit it?
5. Why do S3 gateway endpoints belong on app-tier route tables even when you already have NAT?
6. A data subnet has a NACL that allows inbound 5432 from the app CIDR but forgets ephemeral ports on the outbound rule. What do you observe?
7. You need to grow a VPC that is out of IPv4 space. Compare secondary CIDR, a new VPC plus TGW, and IPv6 dual-stack.
8. Why is `172.17.0.0/16` a poor choice for a VPC CIDR on container hosts?
9. How do Route 53 Resolver inbound endpoints differ from AmazonProvidedDNS inside the VPC?
10. Write the three default routes (public, app, data) for Topology A in one table from memory.

**Answers (brief):** (1) Five: network, router, DNS, future, broadcast. (2) Zonal isolation and to avoid cross-AZ NAT charges. (3) When you need transitive routing, many VPCs, or to expose a service without sharing CIDRs. (4) Symmetric flow pinning through a stateful appliance; without it, return traffic may bypass the firewall. (5) They remove NAT data processing and keep S3 traffic on the Amazon network. (6) SYN might arrive; ACK/data return is dropped — connections hang. (7) Secondary CIDR is fastest; new VPC is cleaner isolation; IPv6 avoids IPv4 exhaustion. (8) Collides with Docker’s default bridge. (9) Inbound endpoints are ENIs that on-premises DNS can query; AmazonProvidedDNS is the VPC `.2` resolver. (10) IGW, same-AZ NAT, and no default route respectively.

---

## 42.15 What to do next

Re-read Chapter 9–14 with this cookbook in hand. For every application you own, draw the packet path from a pod or instance to S3, to RDS, and to the public internet. If you cannot draw it, you do not operate it. The IAM cookbook in Chapter 43 assumes you can already point to the ENI and the route that a denied API call actually used.
