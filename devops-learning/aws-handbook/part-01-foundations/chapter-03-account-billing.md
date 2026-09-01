# Chapter 3: AWS Account Setup, Billing, and Cost Basics

*AWS Handbook — Part I, Pages 36–55*

---

## 3.1 Creating a secure AWS account

### Step-by-step

1. **Sign up** at https://aws.amazon.com with a dedicated email (not personal if possible for work).
2. **Root account** — Full admin access. Enable **MFA immediately**.
3. **Do not use root** for daily tasks.
4. Create an **IAM admin user** or use **IAM Identity Center** for workforce access.
5. Set up **billing alerts** before launching resources.

### Root account checklist

- [ ] MFA enabled (hardware key preferred)
- [ ] Strong unique password in password manager
- [ ] No access keys on root
- [ ] Contact info and alternate contacts set
- [ ] AWS Budgets alert configured

---

## 3.2 AWS Free Tier

| Type | Examples |
|------|----------|
| **12-month free** | 750 hrs/month t2/t3.micro EC2, 5 GB S3, RDS limits |
| **Always free** | Lambda 1M requests/month, DynamoDB 25 GB |
| **Short trials** | Some services have limited trials |

**Warning:** Free tier expires; resources left running can incur charges. Always set billing alarms.

---

## 3.3 Billing and Cost Management

| Tool | Purpose |
|------|---------|
| **Billing Dashboard** | Current month spend |
| **Cost Explorer** | Historical analysis, forecasts, filters |
| **AWS Budgets** | Email/SNS alerts at thresholds |
| **Cost & Usage Report (CUR)** | Granular export to S3 for analysis |
| **Pricing Calculator** | Estimate architecture costs before building |

### Budget example

Create a monthly budget of $20 with alerts at 50%, 80%, and 100%:

```bash
aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

---

## 3.4 Cost optimization fundamentals

1. **Tag everything** — `Environment`, `Project`, `Owner`, `CostCenter`
2. **Right-size** — Use Compute Optimizer recommendations
3. **Stop dev resources** — Schedule EC2/RDS shutdown nights/weekends
4. **Use Spot** for fault-tolerant batch workloads
5. **S3 lifecycle** — Move old data to IA/Glacier
6. **Reserved capacity** — 1–3 year Savings Plans for steady workloads
7. **Delete unused** — EBS volumes, Elastic IPs, old snapshots

---

## 3.4 Consolidated billing with Organizations

**AWS Organizations** lets you manage multiple accounts under one payer account:

- **Consolidated billing** — Single invoice, volume discounts
- **SCPs** — Guardrails on what accounts can do
- **Separate accounts** per environment (dev/staging/prod) or per team

Recommended for any serious AWS usage.

---

## 3.5 Support plans (overview)

| Plan | Best for |
|------|----------|
| **Basic** | Free; account and billing support |
| **Developer** | Business hours email support |
| **Business** | 24/7 phone, < 1 hr response for production down |
| **Enterprise** | TAM, < 15 min critical response |

---

## 3.6 Chapter summary

- Secure the **root account** with MFA; use IAM for daily work.
- Set **budgets and alerts** on day one.
- **Tag** resources and review Cost Explorer weekly during learning.

---

## 🧪 Lab 3.1

1. Enable MFA on root.
2. Create IAM admin user `admin-yourname`.
3. Create a $10 monthly budget with email alert.
4. Enable Cost Explorer (may take 24h for data).

---

*Next: [Chapter 6 — IAM Best Practices](../part-02-iam/chapter-06-iam-best-practices.md)*
