# Chapter 13: Route 53 — DNS Records and Routing Policies

*AWS Handbook — Part III, Pages 246–265*

---

## 13.1 What is Amazon Route 53?

**Amazon Route 53** is AWS's highly available and scalable **Domain Name System (DNS)** web service. It translates human-readable domain names (e.g., `www.example.com`) into IP addresses and provides advanced routing policies for traffic management, failover, and latency optimization.

Route 53 also offers **domain registration**, **health checks**, and **traffic flow** visual policies.

---

## 13.2 Core DNS concepts

| Term | Definition |
|------|------------|
| **Hosted zone** | Container for DNS records for a domain |
| **Record** | Maps a name to a value (A, CNAME, MX, etc.) |
| **TTL** | Time-to-live; how long resolvers cache the answer |
| **Name server (NS)** | Authoritative DNS servers for the zone |
| **Resolver** | Client-side DNS lookup (Route 53 Resolver in VPC) |

### Hosted zone types

| Type | Cost | Use case |
|------|------|----------|
| **Public hosted zone** | $0.50/month + queries | Internet-facing domains |
| **Private hosted zone** | $0.50/month + queries | Internal VPC DNS (associated with VPCs) |

---

## 13.3 DNS record types

| Type | Purpose | Example value |
|------|---------|---------------|
| **A** | IPv4 address | `203.0.113.10` |
| **AAAA** | IPv6 address | `2001:db8::1` |
| **CNAME** | Alias to another name | `app.example.com` → `d123.cloudfront.net` |
| **MX** | Mail server | `10 mail.example.com` |
| **TXT** | Text (SPF, DKIM, verification) | `"v=spf1 include:..."` |
| **NS** | Name servers | `ns-123.awsdns-45.com` |
| **SOA** | Start of authority | Zone metadata |
| **SRV** | Service location | `_http._tcp.example.com` |
| **Alias** | Route 53-specific; maps to AWS resource | ALB, CloudFront, S3, API Gateway |

### Alias records (Route 53 specific)

**Alias records** are Route 53's extension of CNAME with advantages:

- Can be used at the **zone apex** (`example.com` — CNAME cannot).
- No charge for alias queries to AWS resources.
- Automatically tracks IP changes of the target resource.

Supported alias targets: ALB, CloudFront, S3 website, API Gateway, Elastic Beanstalk, VPC interface endpoints, another Route 53 record.

---

## 13.4 Routing policies

Route 53 supports multiple routing policies beyond simple DNS:

### Simple routing

One record with one or more values. Route 53 returns **all** values in random order (client picks one).

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "www.example.com",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "203.0.113.10"}]
      }
    }]
  }'
```

### Weighted routing

Distribute traffic by **weight** (percentage). Useful for A/B testing and blue/green deployments.

| Record | Weight | Traffic share |
|--------|--------|---------------|
| blue.example.com → 1.2.3.4 | 90 | 90% |
| green.example.com → 5.6.7.8 | 10 | 10% |

```hcl
resource "aws_route53_record" "blue" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"
  ttl     = 60
  records = ["203.0.113.10"]

  set_identifier = "blue"
  weighted_routing_policy {
    weight = 90
  }
}

resource "aws_route53_record" "green" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "app.example.com"
  type    = "A"
  ttl     = 60
  records = ["203.0.113.20"]

  set_identifier = "green"
  weighted_routing_policy {
    weight = 10
  }
}
```

### Latency-based routing

Route traffic to the region with the **lowest latency** for the user. Requires one record per region with a `region` identifier.

| Region | Record | Latency |
|--------|--------|---------|
| us-east-1 | 203.0.113.10 | ~20ms (US East users) |
| eu-west-1 | 198.51.100.10 | ~15ms (EU users) |

### Failover routing

**Active-passive** failover. Pair a primary record with a secondary; Route 53 health checks determine which is active.

```
Primary (active)  → ALB in us-east-1 (health check: /health)
Secondary (passive) → S3 static failover page (no health check needed)
```

### Geolocation routing

Route based on the user's **geographic location** (continent, country, or US state). Useful for content localization and compliance (e.g., EU data stays in EU).

### Geoproximity routing

Route based on **geographic location and bias**. Unlike geolocation, you can shift traffic by applying a **bias** value to expand or shrink a region's coverage area. Requires Route 53 Traffic Flow.

### Multi-value answer routing

Return **multiple healthy** IP addresses. Similar to simple routing but only returns values that pass health checks. Up to 8 healthy records.

---

## 13.5 Health checks

Route 53 health checks monitor endpoint health and integrate with routing policies (failover, weighted, multi-value).

| Type | Monitors |
|------|----------|
| **Endpoint** | HTTP, HTTPS, or TCP to an IP/hostname |
| **CloudWatch alarm** | Any CloudWatch metric (e.g., DynamoDB throttling) |
| **Calculated** | Combination of child health checks (AND/OR) |

### Health check settings

| Setting | Typical value |
|---------|---------------|
| Protocol | HTTPS |
| Path | `/health` |
| Interval | 30 seconds (10 seconds for fast) |
| Failure threshold | 3 |
| Regions | Minimum 3 for reliable failover |

```bash
aws route53 create-health-check \
  --health-check-config '{
    "IPAddress": "203.0.113.10",
    "Port": 443,
    "Type": "HTTPS",
    "ResourcePath": "/health",
    "FullyQualifiedDomainName": "app.example.com",
    "RequestInterval": 30,
    "FailureThreshold": 3
  }'
```

### Health check billing note

Health checks cost $0.50/month each (first 50 AWS-endpoint checks free). Fast interval checks cost more.

---

## 13.6 Private DNS and hybrid resolution

### Private hosted zones

Associate a hosted zone with one or more VPCs. Internal names (e.g., `db.internal.example.com`) resolve only within those VPCs.

### Route 53 Resolver

For hybrid cloud (on-premises + AWS):

| Feature | Purpose |
|---------|---------|
| **Inbound endpoints** | On-premises resolves AWS private DNS |
| **Outbound endpoints** | AWS VPC resolves on-premises DNS |
| **Resolver rules** | Forward specific domains to on-premises |

```
On-premises DNS → Inbound Resolver Endpoint → Private hosted zone (db.internal)
VPC instances → Outbound Resolver Endpoint → On-premises DNS (corp.example.com)
```

---

## 13.7 Route 53 with other AWS services

| Integration | Pattern |
|-------------|---------|
| **ALB/NLB** | Alias A record → load balancer DNS name |
| **CloudFront** | Alias A/AAAA → CloudFront distribution |
| **S3 static site** | Alias A → S3 website endpoint |
| **API Gateway** | Alias A → API Gateway custom domain |
| **Global Accelerator** | Alias A → accelerator DNS name |
| **ACM** | DNS validation via CNAME records |

---

## 13.8 DNS security

| Feature | Purpose |
|---------|---------|
| **DNSSEC** | Cryptographic signing of DNS responses |
| **Route 53 Resolver DNS Firewall** | Block malicious domains |
| **Query logging** | Log all DNS queries to CloudWatch Logs |

---

## 13.9 Chapter summary

- **Route 53** provides DNS hosting, domain registration, and advanced routing policies.
- **Alias records** map to AWS resources without CNAME limitations at the zone apex.
- **Routing policies** — simple, weighted, latency, failover, geolocation, geoproximity, multi-value.
- **Health checks** enable automatic failover and traffic shifting.
- **Private hosted zones** and **Resolver** support hybrid DNS architectures.

---

## 🧪 Lab 13.1 — Public hosted zone

1. Create a public hosted zone for a domain you control.
2. Update your registrar's NS records to point to Route 53 name servers.
3. Create an A record (alias) pointing to an ALB or CloudFront distribution.
4. Verify resolution: `dig www.yourdomain.com`.

## 🧪 Lab 13.2 — Weighted routing

1. Create two EC2 instances in different AZs with simple web pages ("Server A" / "Server B").
2. Create weighted A records (50/50) for the same hostname.
3. Run `dig` or `curl` multiple times and observe distribution.
4. Shift weight to 90/10 and verify the change.

## 🧪 Lab 13.3 — Failover routing

1. Set up a primary record with a health check on a healthy endpoint.
2. Create a secondary record pointing to an S3 static failover page.
3. Stop the primary endpoint and verify DNS failover within 1–2 minutes.

---

## Review questions

1. What is the advantage of an alias record over a CNAME at the zone apex?
2. How does weighted routing differ from latency-based routing?
3. What happens when a failover primary record's health check fails?
4. How do private hosted zones differ from public hosted zones?
5. Why should health checks use at least three AWS regions?

---

*Next: [Chapter 14 — VPC Peering, Transit Gateway, PrivateLink](./chapter-14-vpc-peering-tgw.md)*
