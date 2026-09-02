# Chapter 54: Disaster Recovery Runbooks

*AWS Handbook — Pages 316–324 of this PDF edition*

Disaster recovery (DR) is not a checkbox on a Well-Architected review. It is a set of **runbooks** that named humans (or fully automated pipelines) execute under time pressure, plus evidence from drills that those runbooks meet Recovery Point Objective (RPO) and Recovery Time Objective (RTO). Chapter 23 introduced backup primitives. Chapter 27 covered database-centric DR. This chapter is the operational catalog: backup design, failover patterns, communication, and RPO/RTO drills you can schedule like game days.

---

## 54.1 RPO and RTO without hand-waving

| Term | Meaning | How you measure |
|------|---------|-----------------|
| **RPO** | Maximum acceptable data loss, measured backward from the incident | Time between last good restore point and failure |
| **RTO** | Maximum acceptable downtime, measured forward from the incident | Time until service meets the defined success criteria |
| **RPO actual** | What backups/replication truly deliver | Drill restore timestamps |
| **RTO actual** | What operators plus automation truly deliver | Drill stopwatch, not architecture diagrams |

A system with 5-minute Aurora async replica lag does **not** have a 5-minute RPO if DNS TTL is 300 seconds and nobody is on-call. RTO includes detection, decision, execution, and validation.

Write objectives per **service**, not per company:

| Service | RPO | RTO | Pattern (pilot light / warm / hot) |
|---------|-----|-----|-------------------------------------|
| Public website (static) | 0 (immutable) | 15 min | Active-active CloudFront origins |
| Checkout API | 1 min | 30 min | Warm standby Region |
| Analytics warehouse | 24 h | 72 h | Backup and restore |
| Identity (IdP) | 0 | 15 min | Vendor SLA + cached sessions |

If everything is "RPO 0 / RTO 5 min," you are either spending like a global bank or you are lying. Cost scales roughly: backup/restore << pilot light << warm standby << multi-site active/active.

---

## 54.2 AWS DR patterns (reference table)

| Pattern | Infra in DR Region | Data | Typical RTO | Typical RTO cost |
|---------|--------------------|------|-------------|------------------|
| Backup and restore | Minimal (IAM, maybe VPC) | Snapshots, AWS Backup | Hours | Lowest |
| Pilot light | Core data + small compute | Replicated DBs | Tens of minutes–hours | Low |
| Warm standby | Scaled-down full stack | Sync/async replicas | Minutes | Medium |
| Multi-Region active/active | Full stack both | Global tables, Aurora global, CRDT-ish | Seconds–minutes | Highest |

**Pilot light** means the data plane is on (Aurora global secondary, DynamoDB global table, S3 replication) and the compute can scale from zero or from a tiny ASG. **Warm standby** means you already run a smaller copy of the app and can scale out on failover. Do not mix the terms in executive decks.

---

## 54.3 Backup architecture on AWS

### AWS Backup as the control plane

Central backup account (often Log Archive or a dedicated Backup account) with **AWS Backup delegated administrator**. Backup policies from Organizations assign plans to resource tags `org:backup=gold|silver|bronze`.

| Tier | Example resources | Vault | Retention |
|------|-------------------|-------|-----------|
| Gold | Aurora, DynamoDB, EFS prod | CMK, locked vault | Daily 35d, weekly 12w, monthly 7y |
| Silver | EBS, RDS nonprod | CMK | Daily 14d |
| Bronze | Sandbox EBS | Default | 7d |

Vault lock in **compliance mode** after a cooling-off period prevents ransomware-style deletion of recovery points. Governance mode is weaker; use it only while you still need to delete test recovery points.

### Cross-Region and cross-account copies

A backup that lives in the same account and Region as the workload is a **snapshot**, not a disaster recovery strategy, for Region-loss scenarios.

```yaml
# Conceptual backup plan copy action
CopyActions:
  - DestinationBackupVaultArn: arn:aws:backup:us-west-2:333333333333:backup-vault:dr-gold
    Lifecycle:
      DeleteAfterDays: 35
```

Cross-account copy requires vault policies allowing the source account. KMS: the destination vault CMK must allow the AWS Backup service principal and the copy role. Most "copy failed" tickets are KMS grants, not Backup service bugs.

### What AWS Backup does not cover well

- S3: use replication, versioning, Object Lock; Backup for S3 exists but test restore semantics.
- ECR images: enable replication or pull-through; disaster is "cannot deploy."
- Secrets Manager: replicate secrets; failover that cannot decrypt config is a failed failover.
- Route 53: it is global; still export hosted zone as IaC.
- Cognito: painful; treat as a DR bottleneck or use an external IdP.

---

## 54.4 Data-store specific runbooks

### S3

- Versioning on; lifecycle to Glacier only after you have tested restore times (Glacier RTO can blow a 30-minute objective).
- CRR (cross-Region replication) with RTC if RPO is minutes; RTC is not magic for existing objects — backfill separately.
- Failover: update application origin, CloudFront origin group, or Route 53 alias. Document which buckets are **authoritative** after failback to avoid split-brain writes.

### EBS and EC2

- Snapshot via AWS Backup, not ad-hoc cron, unless you like missing instances.
- AMIs for bake-time; do not rely on "we'll remember the packages."
- Failover: Launch templates in DR Region with the copied AMI. Instance store volumes are gone — if you needed them, you already lost RPO.

### EFS

- AWS Backup or EFS replication. Replication is easier for warm standby.
- Mount targets in DR VPC must exist before you claim RTO of 10 minutes.

### RDS / Aurora

- Automated backups + PITR for single-Region operational recovery.
- Aurora Global Database for low RTO Regional failover (`failover-global-cluster`).
- RDS cross-Region read replica promotion for engines that support it.
- **RPO** for async replicas is lag, not zero. Monitor `AuroraGlobalDBReplicationLag`.
- After promotion, applications must update endpoints. RDS Proxy and Secrets Manager rotation belong in the runbook, not as an exercise for the reader.

### DynamoDB

- Point-in-time recovery (35 days) for operational mistakes.
- Global tables for multi-Region. Conflict resolution is last-writer-wins per item — design keys accordingly.
- Streams consumers in DR must be deployed or RTO includes "oops, no Lambda."

### ElastiCache

- Redis OSS/Valkey: snapshots to S3; Global Datastore for cross-Region.
- Failover of cache is often **rebuild from DB** if RPO for cache is "all of it." Document whether cache is authoritative (usually no).

---

## 54.5 Traffic failover: DNS, anycast, and flags

| Mechanism | Failover style | Watchouts |
|-----------|----------------|-----------|
| Route 53 failover records | Health check, primary/secondary | TTL; health check identity; child health checks |
| Route 53 application recovery controller (ARC) | Gating, routing controls | Learn the readiness check model |
| CloudFront origin groups | HTTP origin failover | 4xx vs 5xx failover rules |
| Global Accelerator | Anycast to Regional ALBs | Client IPs; not a substitute for data failover |
| Feature flag (AppConfig) | Stop writes to primary | Must be in the runbook as step 0 |

**DNS TTL 60s** still means some clients cache 60s plus resolver cache. Do not promise 10-second RTO if DNS is the only switch.

ARC routing controls are preferable when you need **human or automated safety gates** ("do not failover while data replication lag > 30s"). Pair with a CloudWatch alarm on lag.

Example failover record (conceptual):

```
app.example.com
  Failover primary:   alias ALB-use1, health check HTTPS /healthz
  Failover secondary: alias ALB-usw2
```

Health checks must not require VPN. They must represent **user success**, not "ALB is up." An ALB that returns 200 from a static page while Aurora is down will not fail over.

---

## 54.6 The runbook format (use this template)

Every DR runbook in the catalog follows the same sections so on-call brains can pattern-match.

```markdown
# RUNBOOK: Checkout API Regional failover
## 0. Severity and decision
- SEV1 if error rate > 5% for 10 min OR Region AWS health dashboard red AND customers impacted
- Approver: Incident Commander (IC)
- Auto-failover: NO (replication lag gate)

## 1. Detection
- Alarm: `checkout-5xx` + `aurora-global-lag`
- Dashboard: ...
- Synthetic: CloudWatch Synthetics canary `checkout-buy`

## 2. Stop-the-bleeding (optional)
- AppConfig flag `checkout.write_primary=false` (queue orders)

## 3. Pre-flight checks
- [ ] Replication lag < 30s
- [ ] DR Aurora available
- [ ] DR ECS desired count > 0
- [ ] Secrets replicated
- [ ] Last game-day date < 90 days

## 4. Execution
- Commands (copy-paste)

## 5. Validation
- Synthetics green
- One real order in DR
- Error budget dashboard

## 6. Communications
- Status page template
- Customer email threshold

## 7. Failback
- Separate runbook ID DR-CHECKOUT-FAILBACK
```

If step 4 is "click around in the console until it works," you do not have a runbook. You have a hope.

---

## 54.7 Example runbook — Aurora Global failover (checkout)

**Scope:** Promote `us-west-2` secondary to writer. Switch Route 53.

**Commands (illustrative):**

```bash
# 1. Record lag (evidence for postmortem)
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name AuroraGlobalDBReplicationLag \
  --dimensions Name=GlobalClusterIdentifier,Value=shop-global \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 60 --statistics Average

# 2. Fail over global cluster (this is disruptive)
aws rds failover-global-cluster \
  --global-cluster-identifier shop-global \
  --target-db-cluster-identifier arn:aws:rds:us-west-2:222222222222:cluster:shop-usw2

# 3. Confirm writer endpoint
aws rds describe-global-clusters --global-cluster-identifier shop-global

# 4. Flip ARC routing control or Route 53
aws route53 change-resource-record-sets --hosted-zone-id ZXXXX --change-batch file://failover.json

# 5. Scale DR compute
aws ecs update-service --cluster shop-usw2 --service checkout --desired-count 8
```

**Validation:** `curl https://checkout.example.com/healthz` from a runner **outside** the failed Region. Place a synthetic SKU order. Confirm DynamoDB global table for carts is not split-brain (carts should already be global).

**Failback:** Do not fail back during peak. Schedule: reverse global cluster, drain, wait for lag ~0, flip DNS, watch 2× TTL.

---

## 54.8 Example runbook — ransomware / account compromise (backup restore)

Regional outage is only one disaster class. **Logical destruction** (bad deploy, ransomware encryption, malicious `s3 rm`) needs a different path.

1. Isolate: Suspended-style SCP on the affected account if compromise; or disable deploy pipeline.
2. Identify last known-good recovery point (Backup vault in **another account**).
3. Restore to a **clean account** in the same OU, not on top of malware.
4. Rotate all secrets, IAM keys, and KMS grants.
5. Point DNS only after forensics says so.

This is why backup copies must be **cross-account** with vault lock. Same-account backups are available to the same attacker principal.

---

## 54.9 Communications and legal

Runbooks that skip comms fail socially even when they succeed technically.

| Time | Action |
|------|--------|
| T+0 | IC named; channel `#inc-YYYYMMDD-checkout` |
| T+15 min | Internal status: impact, next update time |
| T+30 min | Customer status page if user-visible |
| T+RTO | "Mitigated" only after validation checklist |
| T+5 business days | Postmortem with RPO/RTO actuals |

Do not tweet root-cause speculation. Do not put customer PII in Slack screenshots of RDS query results.

---

## 54.10 Automation versus human gates

| Failover type | Automate? | Gate |
|---------------|-----------|------|
| AZ failure (Multi-AZ RDS, ALB) | Yes, native | None |
| Unhealthy deploy (canary) | Yes, pipeline rollback | Automated |
| Region failover | Often **gated** | Lag, IC approval |
| Account compromise | Human | Security |

Automating Regional failover without lag checks can **promote an empty or stale database**. That is a worse outage. Use Step Functions:

```json
{
  "Comment": "Regional failover with lag gate",
  "StartAt": "CheckLag",
  "States": {
    "CheckLag": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Next": "LagOk?"
    },
    "LagOk?": {
      "Type": "Choice",
      "Choices": [
        { "Variable": "$.lagMs", "NumericLessThan": 30000, "Next": "NotifyIC" }
      ],
      "Default": "AbortStaleData"
    },
    "NotifyIC": { "Type": "Task", "Resource": "arn:aws:states:::sns:publish", "Next": "WaitApprove" },
    "WaitApprove": { "Type": "Task", "Resource": "arn:aws:states:::aws-sdk:sfn.sendTaskSuccess", "Next": "Failover" },
    "Failover": { "Type": "Task", "Resource": "arn:aws:lambda:us-east-1:222222222222:function:failover-checkout" },
    "AbortStaleData": { "Type": "Fail", "Error": "RPOBreach" }
  }
}
```

(Replace the HTTP/SDK bits with a Lambda that reads CloudWatch and a callback for Slack approval.) The point is the **gate**, not the JSON art.

---

## 54.11 Observability required for DR

If you cannot see DR Region health, you cannot fail over.

Minimum:

- CloudWatch dashboards **per Region** with the same widget IDs.
- Synthetics from multiple Regions (a canary in us-east-1 cannot test us-east-1 DNS failover well if that Region is dark).
- Alarm actions in a **third** place: chat, incident tool, and a Lambda in another Region.
- CloudTrail in log archive still receiving events (or you lost forensics).

X-Ray and logs must not be the only copy of the truth in the failing Region. Metric streams or cross-Region dashboards help.

---

## 54.12 Lab A — measure actual RPO with a restore drill

**Goal:** Prove bronze/silver backup RPO for a toy RDS instance.

1. Create a small RDS PostgreSQL in sandbox, Multi-AZ off to save cost.
2. Enable automated backups, retention 7 days, and AWS Backup plan copying to a second Region vault.
3. Insert a row with timestamp `t1`. Wait for backup window or take an on-demand backup. Insert another row `t2` after the backup completes.
4. Simulate loss: delete the row or snapshot-restore to a new instance from the recovery point.
5. Query whether `t2` exists.

```sql
CREATE TABLE drill (id int primary key, note text, ts timestamptz);
INSERT INTO drill VALUES (1, 't1-before-backup', now());
-- take backup
INSERT INTO drill VALUES (2, 't2-after-backup', now());
```

6. Record: `RPO_actual ≈ t_failure - t_recovery_point`. Compare to the silver objective.

**Success criteria:** Written evidence (screenshot or query output in the drill ticket) of what was lost. If `t2` is gone, your RPO is at least the time since last backup, not "continuous."

---

## 54.13 Lab B — Route 53 failover game day

**Goal:** Fail HTTP from primary ALB to secondary without touching databases (static app or two identical S3 websites).

1. Two S3 website origins or two tiny ALBs in different Regions, each serving `{"region":"us-east-1"}` vs `us-west-2`.
2. Route 53 failover + health check on `/`.
3. Break primary: bucket policy deny, or security group deny, or stop the only instance.
4. Stopwatch from break to `dig` + `curl` showing secondary. Repeat with TTL 60 and TTL 300.

```bash
while true; do
  echo "$(date -u +%H:%M:%S) $(curl -s https://drill.example.com)"
  sleep 5
done
```

5. Restore primary; watch failback. Note flapping if health checks are too aggressive.

**Success criteria:** Measured RTO for **DNS-only** failover. Document resolver cache effects from your laptop vs from an EC2 in another Region.

---

## 54.14 Lab C — tabletop + partial automation

Not every drill needs a real failover. Quarterly **tabletop**: IC, DB, network, comms walk the checkout runbook with a injected "us-east-1 AZ1+AZ2 power event." Then annually a **partial real** failover of a non-customer-facing service.

Track metrics:

| Metric | Target |
|--------|--------|
| Drills per year per SEV1 service | ≥ 2 |
| Runbook step executed without improvisation | 100% or file a defect |
| RTO actual vs objective | ≤ objective |
| Secrets missing in DR | 0 |

---

## 54.15 Chaos and game days versus DR drills

Chaos engineering (fault injection on a single AZ, FIS experiments) tests **resilience** inside a Region. DR drills test **catastrophe** across Regions or accounts. You need both. FIS is not a substitute for restoring from a locked backup vault.

AWS FIS experiment example (AZ disruption) belongs in reliability engineering. Put a link from the DR runbook: "If only one AZ, do not Regional-failover; wait for Multi-AZ." Decision trees prevent well-meaning engineers from promoting the global database during a subnet-router blip.

---

## 54.16 Compliance mapping

| Framework | Typical evidence |
|-----------|------------------|
| SOC 2 | Drill tickets, backup reports, access to vaults |
| ISO 27001 | Defined RPO/RTO, tested |
| PCI | Segmented cardholder DR, encryption keys available |
| HIPAA | BAA, encryption, restore tests of ePHI |

Auditors want **dates and outcomes**, not architecture PDFs. Store drill records in the same ticket system as incidents.

---

## 54.17 Cost control for DR

Warm standby that nobody scales down after a drill is a silent 2× bill. Tag DR resources `org:dr-idle=true` and a budget alert. Use Aurora Serverless v2 or ECS desired=0 where RTO allows. S3 replication RTC and DynamoDB global tables are the expensive correctness tools — apply them only to gold data.

---

## 54.18 Failback, split-brain, and data repair

The hardest part is not failover. It is **failback**:

- Writes landed in DR. Primary comes back empty or old.
- Reverse replication. If you cannot reverse, you do an ETL of deltas.
- Clients still hitting primary due to DNS. Use ARC or low TTL plus connection draining.

Split-brain mitigation: **make primary read-only** (AppConfig or DB parameter) before DNS flip back. Have a reconciliation job for orders (idempotent order IDs).

---

## 54.19 Chapter checklist

- [ ] Per-service RPO/RTO written and cost-approved.
- [ ] AWS Backup org policies; cross-account locked vaults for gold.
- [ ] Runbooks in the template format with copy-paste commands.
- [ ] DNS/ARC health checks match user success.
- [ ] Secrets, IAM, and images exist in DR before the incident.
- [ ] Labs A and B measured actuals.
- [ ] Failback runbooks exist, not only failover.
- [ ] Drill calendar owned by SRE/platform.

The practice exams that follow will test whether you can choose backup versus global tables versus CloudFront origin groups under exam wording. The runbooks in this chapter are how you do it when the wording is a PagerDuty page.
