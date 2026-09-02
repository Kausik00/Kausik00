# Chapter 2: AWS Global Infrastructure — Regions, AZs, and Edge

*AWS Handbook — Pages 9–11 of this PDF edition*
---

## 2.1 Global infrastructure overview

AWS operates a worldwide network of data centers organized into:

```
Region (e.g., us-east-1)
 ├── Availability Zone A (us-east-1a)
 ├── Availability Zone B (us-east-1b)
 ├── Availability Zone C (us-east-1c)
 └── ... (typically 3+ AZs per region)

Edge Locations (200+) — CloudFront, Route 53, etc.
```

---

## 2.2 Regions

A **Region** is a separate geographic area. Each region is **fully isolated** from others for most services.

### Choosing a region

| Factor | Guidance |
|--------|----------|
| **Latency** | Place resources near users |
| **Compliance** | Data residency (GDPR, etc.) may require EU regions |
| **Service availability** | New services launch in select regions first |
| **Cost** | Pricing varies by region (`us-east-1` often cheapest) |
| **Disaster recovery** | Use a second region for critical workloads |

**Naming:** `us-east-1` (N. Virginia), `eu-west-1` (Ireland), `ap-southeast-1` (Singapore).

### Regional vs global services

| Regional (must specify region) | Global (single endpoint) |
|-------------------------------|--------------------------|
| EC2, RDS, VPC, Lambda | IAM, Route 53, CloudFront |
| S3 (bucket tied to region) | AWS Organizations |

---

## 2.3 Availability Zones (AZs)

An **AZ** is one or more discrete data centers with independent power, networking, and cooling within a region. AZs are connected by **low-latency private fiber**.

- Deploy across **multiple AZs** for high availability.
- AZ names like `us-east-1a` are **account-specific mappings**—`1a` in your account may not be the same physical DC as `1a` in another account.

### Multi-AZ patterns

| Pattern | Use case |
|---------|----------|
| **Active-passive** | RDS Multi-AZ failover |
| **Active-active** | ALB spanning AZs with EC2 in each |
| **Stretch cluster** | EKS node groups per AZ |

---

## 2.4 Local Zones, Wavelength, and Outposts

| Type | Purpose |
|------|---------|
| **Local Zones** | Extend region closer to metro areas (ultra-low latency) |
| **Wavelength** | 5G edge at carrier locations |
| **Outposts** | AWS hardware on-premises; hybrid cloud |

These are specialized; start with standard regions + AZs.

---

## 2.5 Edge locations and CloudFront

**Edge locations** cache content close to users via **Amazon CloudFront** (CDN). Route 53 and AWS Shield also use the edge network.

Benefits:
- Lower latency for static assets
- Reduced origin load
- DDoS protection at edge (with Shield)

---

## 2.6 Fault isolation design principles

1. **Never rely on a single AZ** for production.
2. **Design for regional failure** for mission-critical systems (multi-region active-active or pilot light).
3. **Use managed services** that handle AZ redundancy (RDS Multi-AZ, S3 cross-AZ durability).
4. **Test failover** regularly.

### S3 durability vs availability

- **S3 Standard** — 99.999999999% (11 nines) durability across AZs in a region.
- **Availability** — Different metric; rare regional outages can still occur.

---

## 2.7 Service quotas (limits)

Each account has **default quotas** per region (e.g., EC2 vCPUs, VPCs per region). Request increases via **Service Quotas** console. Plan capacity before large deployments.

---

## 2.8 Chapter summary

- **Regions** are geographic; **AZs** are isolated DCs within a region.
- Deploy production workloads across **multiple AZs**.
- **Edge locations** power CloudFront and global services.
- Know **regional vs global** services when designing architecture.

---

## 🧪 Lab 2.1 — Explore regions in CLI

```bash
aws configure                    # Set default region
aws ec2 describe-availability-zones --region us-east-1
aws ec2 describe-regions --output table
```

Document which region you will use for labs and why.

---

## Review questions

1. How many AZs should a highly available web app use at minimum?
2. Is IAM a regional or global service?
3. What AWS service uses edge locations for caching?
4. Why might you choose `eu-central-1` over `us-east-1`?

---

*Next: Part II — [Chapter 5: IAM Fundamentals](../part-02-iam/chapter-05-iam-fundamentals.md)*
