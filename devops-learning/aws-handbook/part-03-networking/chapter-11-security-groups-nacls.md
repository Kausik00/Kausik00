# Chapter 11: Security Groups vs Network ACLs

*AWS Handbook — Part III, Pages 206–220*

---

## 11.1 Two layers of VPC security

Amazon VPC provides **two complementary firewall mechanisms** for controlling traffic:

1. **Security Groups (SGs)** — Stateful, instance-level (or ENI-level) firewalls.
2. **Network Access Control Lists (NACLs)** — Stateless, subnet-level firewalls.

Understanding when and how to use each is essential for designing secure, compliant network architectures. Most day-to-day rules are security groups; NACLs add a subnet-wide safety net.

---

## 11.2 Security groups in depth

A **security group** acts as a virtual firewall for EC2 instances, RDS databases, Lambda functions in a VPC, ELBs, and other resources. It controls **inbound** and **outbound** traffic at the **elastic network interface (ENI)** level.

### Key characteristics

| Property | Security Group |
|----------|----------------|
| **State** | **Stateful** — return traffic automatically allowed |
| **Scope** | ENI / resource level |
| **Rules** | Allow only (no Deny rules) |
| **Evaluation** | All rules evaluated before decision |
| **Default** | Deny all inbound; allow all outbound |
| **Attachment** | One or more SGs per ENI |

### Stateful behavior example

If you allow inbound TCP 443, the response traffic on ephemeral ports is **automatically permitted** without an explicit outbound rule. This simplifies rule management significantly.

### Security group rules

Each rule specifies:

| Field | Example |
|-------|---------|
| **Type** | HTTP, HTTPS, SSH, Custom TCP |
| **Protocol** | TCP, UDP, ICMP, all |
| **Port range** | 443, 22, 1024-65535 |
| **Source (inbound)** | CIDR, another SG, prefix list |
| **Destination (outbound)** | CIDR, another SG, prefix list |

### Referencing security groups

Instead of IP addresses, reference another security group:

```
Inbound: TCP 3306 from sg-0abc123 (app-tier SG)
```

This allows any instance in the app-tier SG to reach the database, regardless of IP address. When instances scale, rules remain valid.

### CLI example

```bash
# Create a web tier security group
aws ec2 create-security-group \
  --group-name web-tier-sg \
  --description "Allow HTTP/HTTPS from ALB" \
  --vpc-id vpc-0abc123

# Allow HTTPS from ALB security group
aws ec2 authorize-security-group-ingress \
  --group-id sg-0web123 \
  --protocol tcp \
  --port 443 \
  --source-group sg-0alb456

# Allow SSH from bastion only
aws ec2 authorize-security-group-ingress \
  --group-id sg-0web123 \
  --protocol tcp \
  --port 22 \
  --source-group sg-0bastion789
```

### Terraform example

```hcl
resource "aws_security_group" "web" {
  name        = "web-tier"
  description = "Web server security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTPS from ALB"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "web-tier-sg" }
}
```

---

## 11.3 Network ACLs in depth

A **Network ACL (NACL)** is an optional layer of security that acts as a firewall for **subnets**. Each subnet is associated with exactly one NACL; a NACL can be associated with multiple subnets.

### Key characteristics

| Property | NACL |
|----------|------|
| **State** | **Stateless** — must allow both directions explicitly |
| **Scope** | Subnet level |
| **Rules** | Allow **and** Deny |
| **Evaluation** | Lowest rule number first; first match wins |
| **Default** | Allow all inbound and outbound |
| **Attachment** | One NACL per subnet |

### Stateless behavior

If you allow inbound TCP 443, you must **also** allow outbound traffic on ephemeral ports (1024–65535) for the response to return. Forgetting the outbound rule is the most common NACL mistake.

### Rule numbering

NACL rules are numbered (e.g., 100, 200, 300). Lower numbers are evaluated first. A `*` rule at the end denies everything not explicitly allowed (in custom NACLs).

### Example: Restrict SSH to corporate IP

| Rule # | Type | Protocol | Port | Source | Allow/Deny |
|--------|------|----------|------|--------|------------|
| 100 | Inbound | TCP | 22 | 203.0.113.0/24 | ALLOW |
| 110 | Inbound | TCP | 22 | 0.0.0.0/0 | DENY |
| 100 | Outbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |

### CLI example

```bash
aws ec2 create-network-acl --vpc-id vpc-0abc123

aws ec2 create-network-acl-entry \
  --network-acl-id acl-0abc123 \
  --rule-number 100 \
  --protocol tcp \
  --port-range From=22,To=22 \
  --cidr-block 203.0.113.0/24 \
  --rule-action allow \
  --ingress

aws ec2 replace-network-acl-association \
  --association-id aclassoc-0abc123 \
  --network-acl-id acl-0abc123
```

---

## 11.4 Security groups vs NACLs — comparison

| Feature | Security Group | NACL |
|---------|----------------|------|
| Level | Instance/ENI | Subnet |
| Stateful | Yes | No |
| Deny rules | No | Yes |
| Rule evaluation | All rules | Ordered (first match) |
| Default action | Deny inbound | Allow all |
| Affects | Resources with ENI | All traffic to/from subnet |
| Use case | Primary access control | Subnet-wide guardrails |

### When to use which

| Scenario | Use |
|----------|-----|
| Allow app → database on port 3306 | Security group referencing app SG |
| Block a known malicious IP range | NACL Deny rule |
| Allow ALB → web tier on 443 | Security group |
| Block all inbound except specific CIDRs at subnet level | NACL |
| Lambda in VPC accessing RDS | Security group on both |

---

## 11.5 Defense in depth pattern

Production architectures typically use **both**:

```
Internet → NACL (subnet) → Security Group (ALB) → Security Group (web) → NACL (private subnet) → Security Group (DB)
```

1. **Public subnet NACL** — Deny known bad IPs, allow 80/443 from internet.
2. **ALB security group** — Allow 80/443 from 0.0.0.0/0.
3. **Web tier SG** — Allow 443 only from ALB SG.
4. **Private subnet NACL** — Deny all inbound from internet CIDRs.
5. **Database SG** — Allow 3306 only from web tier SG.

---

## 11.6 Common mistakes and troubleshooting

| Mistake | Symptom | Fix |
|---------|---------|-----|
| NACL missing outbound ephemeral rule | Connection hangs after SYN | Add outbound allow for 1024-65535 |
| SG allows wrong source CIDR | Unexpected access or blocked access | Use SG references instead of CIDRs |
| Default SG used in production | Overly permissive (same-SG traffic allowed) | Create dedicated SGs per tier |
| NACL deny blocks health checks | ALB marks targets unhealthy | Allow health check IPs/CIDRs |
| Forgot IPv6 rules | IPv6 traffic blocked | Add ::/0 rules where needed |

### Connectivity troubleshooting order

1. Check **security group** inbound rules on the target.
2. Check **security group** outbound rules on the source.
3. Check **NACL** inbound on the target subnet.
4. Check **NACL** outbound on the source subnet.
5. Check **route tables** (covered in Chapter 10).
6. Use **VPC Reachability Analyzer** for automated path analysis.

```bash
aws ec2 describe-security-groups --group-ids sg-0abc123
aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=subnet-0abc123"
```

---

## 11.7 Security group limits and quotas

| Resource | Default limit |
|----------|---------------|
| Security groups per VPC | 2,500 |
| Rules per security group | 60 inbound + 60 outbound |
| Security groups per ENI | 5 (can request increase) |
| Referenced security groups per rule | 1 |

Use **prefix lists** to reduce rule count when allowing access from many CIDRs.

---

## 11.8 Chapter summary

- **Security groups** are stateful, instance-level, allow-only firewalls—the primary access control mechanism.
- **NACLs** are stateless, subnet-level, support deny rules—a secondary guardrail.
- Reference security groups instead of IP addresses for scalable architectures.
- Always allow **return traffic** in NACLs (ephemeral ports outbound).
- Use both layers for defense in depth; troubleshoot connectivity systematically.

---

## 🧪 Lab 11.1 — Security group tiers

1. Create three security groups in your VPC: `alb-sg`, `web-sg`, `db-sg`.
2. Configure: ALB allows 80/443 from internet; web allows 443 from ALB SG; db allows 3306 from web SG.
3. Launch a test EC2 in a private subnet with `web-sg`.
4. Verify you cannot SSH directly from the internet.
5. Verify web tier can reach a test database port using `nc` or `telnet`.

## 🧪 Lab 11.2 — NACL deny rule

1. Create a custom NACL for a public subnet.
2. Add a Deny rule for a specific IP (your test IP).
3. Verify HTTP access is blocked from that IP but works from another.
4. Remove the deny rule and confirm access is restored.

---

## Review questions

1. Why are security groups called "stateful" and NACLs "stateless"?
2. Can you create a Deny rule in a security group?
3. If a security group allows inbound TCP 80, is an outbound rule needed for the response?
4. What happens when NACL rule 100 allows traffic but rule 110 denies it?
5. Why should you reference security groups instead of IP addresses between tiers?

---

*Next: [Chapter 12 — Load Balancers](./chapter-12-load-balancers.md)*
