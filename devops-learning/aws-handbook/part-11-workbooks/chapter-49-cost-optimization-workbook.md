# Chapter 49: Cost Optimization Workbook

Cost on AWS is an architecture property, not a monthly surprise. This workbook is a FinOps loop you can run: see, attribute, reduce unit cost, reduce waste, negotiate commitment, and prevent regression with budgets and governance. It complements Chapter 3 and the Well-Architected cost pillar. Every lab should be done in an account where you are allowed to look at bills.

---

## 49.1 The loop

1. **Allocate** — tags, Cost Categories, linked accounts that match teams.
2. **Observe** — Cost Explorer, CUR + Athena, Budgets, anomaly detection, unit metrics (cost per order).
3. **Optimize** — delete waste, rightsize, storage class, data transfer, idle NAT, logs.
4. **Commit** — Savings Plans and Reserved Instances only after usage is stable.
5. **Govern** — SCPs, budgets actions, pipeline checks, showback.

If you skip allocation, every optimization argument becomes a fight.

---

## 49.2 Account and tag strategy

| Dimension | Mechanism |
|-----------|-----------|
| Team / product | Account in Organizations *or* mandatory `CostCenter` tag |
| Environment | Separate accounts (prod / non-prod) beat tags alone |
| Shared platform | Cost Categories split networking and observability |
| Unallocated | A budget named “untagged” that should shrink |

Activate cost allocation tags in Billing. Terraform default tags on the provider:

```hcl
provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Owner       = "platform"
      Environment = "prod"
      Application = "orders"
      CostCenter  = "cc-1040"
    }
  }
}
```

Tags that exist only on EC2 but not on EBS, snapshots, and ALBs produce ghost spend. Use Config rules to require tags on new resources.

---

## 49.3 The Cost and Usage Report (CUR) is the source of truth

Cost Explorer is interactive. CUR is auditable.

1. Enable CUR to S3 (Parquet, hourly, resource IDs).
2. Use AWS Glue + Athena or a vendor.
3. Query `line_item_product_code`, `line_item_usage_type`, `resource_id`, `line_item_unblended_cost`.

Example questions:

- Top 20 `resource_id` by unblended cost last 7 days
- NAT Gateway `Bytes` vs hourly charge
- Data transfer `USE1-USE2` vs `CloudFront`
- Idle Elastic IPs
- gp2 vs gp3 remaining

```sql
SELECT
  line_item_resource_id,
  product_product_name,
  SUM(line_item_unblended_cost) AS cost
FROM cur
WHERE year = '2026' AND month = '08'
GROUP BY 1, 2
ORDER BY cost DESC
LIMIT 20;
```

---

## 49.4 Waste catalog (hunt this first)

| Waste | How you see it | Fix |
|-------|----------------|-----|
| Unattached EBS | CUR `EBS:VolumeUsage` on volumes not attached | Snapshot if needed, delete |
| Old snapshots / AMIs | Snapshot age report | Lifecycle policies |
| Elastic IPs not on running instances | Hourly EIP waste | Release |
| Idle load balancers | ALB `RequestCount` ≈ 0 | Delete |
| Idle NAT | Bytes low, hourly high | Endpoints; consolidate |
| `gp2` volumes | Usage type | Migrate gp3 |
| CloudWatch Logs never-expiring | Ingestion + storage | Retention 14–90 days unless compliance |
| Unused Transit Gateway attachments | Hourly TGW | Detach |
| Oversize RDS Multi-AZ in dev | Hours × class | Stop (where supported), smaller, Aurora clone |
| Lambda never invoked but provisioned concurrency | ProvisionedConcurrency | Drop |
| S3 Intelligent-Tiering vs many tiny objects | Overhead vs benefit | Measure |
| Duplicate GuardDuty in unused patterns | — | Keep GuardDuty; cut real waste elsewhere |

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-08-01,End=2026-09-01 \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

```bash
aws ec2 describe-volumes --filters Name=status,Values=available \
  --query 'Volumes[].{Id:VolumeId,Size:Size,Type:VolumeType,Created:CreateTime}'
```

---

## 49.5 Compute rightsizing

Compute Optimizer and the EC2 “CPU 4% for 14 days” graph are starting points. Rightsizing a latency-sensitive fleet from `m7g.xlarge` to `m7g.large` needs p99 latency, not only CPU.

| Lever | When |
|-------|------|
| Smaller instance | Headroom unused |
| Graviton | Compatible AMI and deps |
| Spot | Fault-tolerant ASG/EKS/EMR |
| Savings Plans (Compute) | Flexible across EC2/Fargate/Lambda |
| EC2 Instance SP / RI | Stable instance family |
| Fargate vs EC2 | Ops vs density trade |
| Lambda memory tune | CPU scales with memory; may reduce duration cost |
| ASG scheduled scaling | Nights and weekends |

```bash
aws compute-optimizer get-ec2-instance-recommendations --max-results 20
```

Turn on Compute Optimizer at org level.

---

## 49.6 Storage and databases

**S3:** lifecycle to IA/Glacier; abort incomplete multipart; Intelligent-Tiering for unknown access; compress; CloudFront in front of hot public objects to cut transfer.

**EBS:** gp3 baseline 3000 IOPS is often enough; provisioned IOPS only when measured; delete unused volumes.

**RDS/Aurora:** stop non-prod overnight (RDS stop limits apply); Aurora Serverless v2 min ACU = 0.5 (or current minimum) in dev; reserved instances for prod steady state; look at I/O-Optimized Aurora if I/O is the bill.

**DynamoDB:** on-demand vs provisioned; Standard-IA table class for cold tables; avoid storing blobs.

**Backups:** overlapping AWS Backup + native snapshots + EBS snapshots of the same data. Pick one system of record.

---

## 49.7 Data transfer: the silent line item

| Path | Typical charge | Mitigation |
|------|----------------|------------|
| AZ to AZ | Cross-AZ | Keep chatty tiers together; but do not sacrifice HA |
| NAT processing | Per GB + hourly | VPC endpoints |
| Public IPv4 | Hourly per address | Dual-stack; reduce EIPs |
| Internet egress | Per GB | CloudFront, compression, regionalize |
| Inter-region | Per GB | Stay regional; replicate only what DR needs |
| TGW | Per GB + attachment hour | Summarize; avoid hairpin |

Draw the packet path (Chapter 42) with dollar signs on each hop.

---

## 49.8 Logging and security cost (do not “save” by going blind)

Flow Logs, CloudTrail data events, GuardDuty, and Security Hub cost money. The wrong save is disabling them in prod. The right save is:

- REJECT-only or sampled Flow Logs where full logs are unused
- CloudTrail data events only on sensitive buckets
- Log retention
- Security Hub standards scoped; disable irrelevant product integrations
- CloudWatch Logs Infrequent Access class where appropriate

Document these as **accepted security spend**.

---

## 49.9 Budgets, anomaly detection, and actions

```bash
aws budgets create-budget --account-id 111122223333 --budget file://budget.json --notifications-with-subscribers file://notify.json
aws ce create-anomaly-monitor --anomaly-monitor '{
  "MonitorName": "services",
  "MonitorType": "DIMENSIONAL",
  "MonitorDimension": "SERVICE"
}'
```

Budget **actions** can apply an SCP or stop instances. Use with care: an action that stops RDS during a traffic spike is an outage. Prefer notify first, auto-remediate only in sandbox OUs.

```hcl
resource "aws_budgets_budget" "monthly" {
  name         = "prod-monthly"
  budget_type  = "COST"
  limit_amount = "5000"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["finops@example.com"]
  }
}
```

---

## 49.10 Commitments without trapping yourself

Rules:

- Never buy a 3-year All Upfront RI on a service you might leave in 4 months.
- Compute Savings Plans cover EC2, Fargate, and Lambda — good default.
- SageMaker, RDS, ElastiCache, OpenSearch, Redshift have their own reservation story.
- Coverage reports: aim for high coverage of *stable* usage, not 100% of a spiky fleet (you will overpay).
- Review SP utilization monthly; unused commitment is waste with extra steps.

---

## 49.11 Unit economics

Finance wants cost per checkout, per tenant, per pipeline minute. Engineering must emit usage metrics (orders, GB processed) and join them to CUR in a warehouse.

Example: if NAT cost / order is rising, Chapter 42 endpoints are the fix. If Lambda cost / order is rising, Chapter 45 memory tuning and batching are the fix. Unit metrics connect workbooks.

---

## 49.12 Lab 1 — Tag gap and Cost Explorer

1. List untagged `Name` or `CostCenter` resources (`aws resourcegroupstaggingapi get-resources`).
2. Tag them.
3. In Cost Explorer, group by tag `CostCenter` for last 30 days.
4. Screenshot (or export CSV) the before/after unallocated slice.

---

## 49.13 Lab 2 — NAT vs endpoint dollars

1. From CUR or NAT CloudWatch `BytesOutToDestination`, estimate monthly GB.
2. Price NAT hourly × AZs + per-GB.
3. Price S3/DynamoDB gateway endpoints (data via endpoint is not NAT).
4. Implement gateway endpoints (Lab in Chapter 42). Recalculate.

---

## 49.14 Lab 3 — Rightsizing a noisy idle instance

1. Launch `m5.xlarge`, idle it for a period (or use historical data).
2. Pull CloudWatch CPU + Compute Optimizer.
3. Stop, change to `t3.small` or `m7g.large` as appropriate, restart.
4. Record that production needs a canary, not a blind resize.

---

## 49.15 Governance checklist

| Control | Where |
|---------|--------|
| Deny huge instance types in sandbox | SCP |
| Require encryption and tags | Config + SCP |
| Monthly budget per account | Budgets |
| Anomaly detection | Cost Explorer |
| Showback report | CUR + Athena |
| SP coverage review | FinOps calendar |
| Log retention | Org policy / Terraform |

---

## 49.16 Review questions

1. Why is Cost Explorer insufficient as the only source of truth?
2. What spend is invisible if you only tag EC2 instances?
3. When is a Compute Savings Plan better than an instance-family RI?
4. Why can 100% RI coverage be a bad goal?
5. Name three data-transfer anti-patterns.
6. Why is deleting GuardDuty a false economy?
7. What is showback vs chargeback?
8. How does `default_tags` in Terraform fail if modules create untagged supporting resources?
9. Why measure cost per order instead of only monthly total?
10. What is the risk of budget actions that stop compute?

**Answers (brief):** (1) CUR has resource-level line items and is queryable. (2) EBS, snapshots, IPs, data transfer, NAT. (3) When you move across families, Fargate, or Lambda. (4) You over-commit on usage that disappears. (5) NAT to S3, chatty cross-AZ without need, multi-region copies for convenience. (6) Breach cost dwarfs the detector. (7) Showback informs; chargeback bills teams. (8) Some resources need extra tag blocks; ASG propagate tags. (9) Totals hide growth vs inefficiency. (10) They can cause outages.

---

## 49.17 Worked example: monthly $12k orders stack

Numbers are illustrative so you can copy the *method*.

| Line | Monthly | Lever |
|------|---------|-------|
| ALB + WAF | $90 | One ALB, path routing; do not multiply ALBs without a reason |
| NAT × 3 AZ | $100 hourly + $400 data | Gateway endpoints; maybe NAT only in two AZs if you accept the reliability trade-off (usually you should not) |
| ECS/EC2 m7g.large × 6 | $450 | Graviton already; SP at 70% coverage |
| Aurora r7g.large × 2 | $700 | Reserved; I/O-Optimized if I/O dominates |
| DynamoDB on-demand | $200 | Watch Scan; table class IA for audit table |
| ElastiCache r7g.large × 4 | $800 | Maybe three nodes; reserved |
| S3 + CloudFront | $150 | Lifecycle |
| CloudWatch + logs | $250 | Retention 30 days app, 365 audit |
| GuardDuty + Hub | $80 | Keep |
| Inter-AZ and NAT remainder | $400 | Placement groups? usually just less chatty apps |
| **Total** | **~$3.6k compute/data + transfer** | The $12k version is the same architecture in a larger size plus unused UAT Multi-AZ copies |

The point of the table is **attribution**. Without CUR resource IDs you cannot tell NAT data from instance hours.

**EKS cost:** control plane hourly plus nodes plus LB plus unused local zones. Karpenter often beats a static node group that is 40% empty, but it can also launch expensive GPU types if a developer’s pod requests them — use NodePools with allowed instance families.

**Marketplace AMIs** with hidden hourly software charges show up as separate product codes. Read them.

**Savings plan purchase CLI (read-only first):**

```bash
aws ce get-savings-plans-utilization --time-period Start=2026-08-01,End=2026-09-01
aws savingsplans describe-savings-plans
```

Buy in the console or via API only with FinOps approval. This workbook will not tell you to purchase a 3-year All Upfront plan from muscle memory.

**Non-prod calendar:** EventBridge Scheduler → Lambda → `rds stop-db-instance` at 19:00 local, start at 07:00 weekdays. Skip when integration tests need nights. Document the exception.

---

**Architecture decision records:** every new always-on regional service (OpenSearch, MSK, NAT, TGW) gets a one-page ADR with monthly cost at expected scale and at 10×. If the author cannot fill the 10× line, the service is not ready for prod. Revisit ADRs when CUR shows a line item that was not in the ADR.

---

**Weekly 30-minute FinOps standup:** (1) anomaly detection exceptions, (2) top 10 resource IDs that moved more than 20%, (3) one waste item deleted live (unused LT, idle ALB, leftover volume), (4) SP coverage vs target. Minutes go in the same repo as Terraform so architecture and money stay in one history.

If the meeting only reviews Cost Explorer pie charts by service, you will never find the NAT Gateway named `tmp-debug`.

---

Record the deleted resource IDs in the meeting notes so you can prove the loop runs when someone asks why the bill flattened. Repeat until waste tickets are boring.

---

---

## 49.18 What to do next

Chapter 50 turns cost, security, reliability, and the rest into Well-Architected checklists you can run as a review, not as a slogan on a slide.
