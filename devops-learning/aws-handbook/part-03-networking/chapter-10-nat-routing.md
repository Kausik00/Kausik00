# Chapter 10: Internet Gateway, NAT Gateway, and Routing

*AWS Handbook — Part III, Pages 186–205*

---

## 10.1 Internet Gateway (IGW)

An **Internet Gateway** is a horizontally scaled, redundant VPC component that allows:

- Instances with public IPs to communicate with the internet
- Internet to initiate connections to instances with public IPs

Attach one IGW per VPC (for internet-connected VPCs).

```bash
aws ec2 create-internet-gateway
aws ec2 attach-internet-gateway --internet-gateway-id igw-xxx --vpc-id vpc-xxx
```

Public subnet route table:

```
Destination     Target
0.0.0.0/0       igw-xxxxxxxx
10.0.0.0/16     local
```

---

## 10.2 NAT Gateway

Private subnet instances should **not** have public IPs. They reach the internet (for updates, API calls) via a **NAT Gateway** in a public subnet.

```
Private subnet instance (10.0.10.5)
    → NAT Gateway (public subnet, elastic IP)
    → Internet Gateway
    → Internet
```

### NAT Gateway facts

- **Managed** by AWS (no patching)
- **Charged** per hour + per GB processed
- **AZ-specific** — deploy one NAT per AZ for HA, or accept cross-AZ failover tradeoffs
- **Alternative:** NAT instances (self-managed, not recommended)

Private subnet route table:

```
Destination     Target
0.0.0.0/0       nat-xxxxxxxx
10.0.0.0/16     local
```

---

## 10.3 VPC Endpoints — avoid NAT costs

For AWS service traffic (S3, DynamoDB, etc.), use **VPC endpoints** to keep traffic on the AWS network—no NAT charges.

| Type | Services | Cost |
|------|----------|------|
| **Gateway** | S3, DynamoDB | Free |
| **Interface** | Most other services | Per hour + data |

```hcl
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.us-east-1.s3"
  route_table_ids = [aws_route_table.private.id]
}
```

---

## 10.4 Elastic IP (EIP)

A **static public IPv4** address. Required for NAT Gateway.

- **Charge** applies if EIP is allocated but not attached to a running instance
- Release unused EIPs to avoid fees

---

## 10.5 Troubleshooting connectivity

| Problem | Check |
|---------|-------|
| Can't SSH to public instance | SG allows 22; has public IP; IGW attached; correct route |
| Private instance can't reach internet | NAT in public subnet; private RT has 0.0.0.0/0 → NAT |
| Can't reach S3 from private subnet | VPC endpoint or NAT route |
| Inter-subnet blocked | NACL rules; SG rules |

### Useful commands

```bash
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=vpc-xxx"
aws ec2 describe-network-interfaces --filters "Name=subnet-id,Values=subnet-xxx"
# From instance:
curl -s https://checkip.amazonaws.com   # Public IP test
```

---

## 10.6 High availability networking

Production checklist:

- [ ] Multi-AZ subnets
- [ ] NAT Gateway per AZ (or accept risk)
- [ ] ALB spans multiple AZs
- [ ] VPC endpoints for S3/DynamoDB/ECR/API
- [ ] No single-AZ dependencies for critical paths

---

## 10.7 Chapter summary

- **IGW** enables public internet for public subnets.
- **NAT Gateway** provides outbound-only internet for private subnets.
- Use **VPC endpoints** to reduce NAT costs and improve security for AWS APIs.

---

## 🧪 Lab 10.1

1. Deploy NAT Gateway in public subnet with EIP.
2. Configure private subnet route table.
3. Launch EC2 in private subnet; `curl` an external API successfully.
4. Add S3 gateway endpoint; verify S3 access without NAT.

---

*Next: [Chapter 15 — EC2](../part-04-compute/chapter-15-ec2-fundamentals.md)*
