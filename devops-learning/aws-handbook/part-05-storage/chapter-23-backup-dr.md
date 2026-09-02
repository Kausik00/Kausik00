# Chapter 23: AWS Backup & Disaster Recovery Patterns

*AWS Handbook — Pages 108–113 of this PDF edition*
---

## 23.1 Why backup and disaster recovery matter

Data loss—from accidental deletion, ransomware, regional outages, or application bugs—can destroy businesses. AWS provides native backup capabilities and architectural patterns to protect workloads with defined **Recovery Time Objective (RTO)** and **Recovery Point Objective (RPO)** targets.

| Metric | Definition | Example |
|--------|------------|---------|
| **RPO** | Maximum acceptable data loss (time) | 1 hour = lose at most 1 hour of data |
| **RTO** | Maximum acceptable downtime | 4 hours = back online within 4 hours |

---

## 23.2 AWS Backup

**AWS Backup** is a centralized backup service that automates and manages backups across AWS services:

| Supported resource | Backup method |
|--------------------|---------------|
| EC2 / EBS | EBS snapshots |
| RDS / Aurora | DB snapshots |
| DynamoDB | On-demand or continuous backup |
| EFS | EFS backup |
| FSx | FSx backup |
| S3 | S3 backup (newer) |
| Storage Gateway | Volume backup |

### Backup components

| Component | Description |
|-----------|-------------|
| **Backup vault** | Container for recovery points; encryption with KMS |
| **Backup plan** | Schedule, lifecycle, and rules |
| **Backup rule** | Frequency, retention, target vault, copy actions |
| **Recovery point** | A restorable backup at a point in time |
| **Backup selection** | Resources matched by tag or ID |

### Terraform backup plan

```hcl
resource "aws_backup_vault" "primary" {
  name        = "primary-vault"
  kms_key_arn = aws_kms_key.backup.arn
}

resource "aws_backup_plan" "daily" {
  name = "daily-backup-plan"

  rule {
    rule_name         = "daily-ec2-rds"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = "cron(0 5 * * ? *)"  # 5 AM UTC daily

    lifecycle {
      delete_after = 30  # days
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.dr.arn
      lifecycle {
        delete_after = 90
      }
    }
  }
}

resource "aws_backup_selection" "tagged" {
  name         = "production-resources"
  plan_id      = aws_backup_plan.daily.id
  iam_role_arn = aws_iam_role.backup.arn

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "Backup"
    value = "daily"
  }
}
```

### CLI

```bash
# Start on-demand backup
aws backup start-backup-job \
  --backup-vault-name primary-vault \
  --resource-arn arn:aws:ec2:us-east-1:123456789012:volume/vol-0abc123 \
  --iam-role-arn arn:aws:iam::123456789012:role/AWSBackupDefaultServiceRole

# List recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name primary-vault

# Restore
aws backup start-restore-job \
  --recovery-point-arn arn:aws:backup:us-east-1:123456789012:recovery-point:abc123 \
  --iam-role-arn arn:aws:iam::123456789012:role/AWSBackupDefaultServiceRole \
  --metadata file://restore-metadata.json
```

---

## 23.3 DR strategies

AWS defines four disaster recovery strategies, ordered by increasing RTO/RPO and cost:

```
Cost / Complexity ──────────────────────────────────────────►
Backup & Restore │ Pilot Light │ Warm Standby │ Multi-Site Active/Active
  (highest RTO)  │             │              │  (lowest RTO)
  (highest RPO)  │             │              │  (lowest RPO)
```

### Backup and Restore

- **RPO:** Hours to days | **RTO:** Hours to days
- Back up data to S3/EBS snapshots; restore in DR region when needed.
- Lowest cost; acceptable for non-critical workloads.

### Pilot Light

- **RPO:** Minutes to hours | **RTO:** Hours
- Core infrastructure (database replica, AMIs) running at minimal scale in DR region.
- Scale up on failover.

### Warm Standby

- **RPO:** Minutes | **RTO:** Minutes to hours
- Reduced-capacity version of production running in DR region.
- Scale up ASG/ECS on failover.

### Multi-Site Active/Active

- **RPO:** Near zero | **RTO:** Near zero
- Full production in multiple regions simultaneously.
- Route 53 health checks shift traffic on failure.
- Highest cost and complexity.

---

## 23.4 Cross-region and cross-account backup

### Cross-region copy

Protect against regional failures by copying backups to a DR region:

```hcl
copy_action {
  destination_vault_arn = aws_backup_vault.dr_region.arn
  lifecycle {
    cold_storage_after = 30
    delete_after       = 365
  }
}
```

### Cross-account backup

Protect against account compromise (ransomware, insider threat):

1. Create backup vault in a separate **log archive** or **security** account.
2. Configure cross-account copy in the backup plan.
3. Apply vault access policies restricting who can delete recovery points.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::PROD_ACCOUNT:root"},
    "Action": "backup:CopyIntoBackupVault",
    "Resource": "*"
  }]
}
```

---

## 23.5 Service-specific DR patterns

### RDS / Aurora

| Feature | RPO | Use case |
|---------|-----|----------|
| Automated backups | 5 minutes (transaction logs) | Point-in-time recovery |
| Read replica (cross-region) | Seconds | DR with promotion |
| Aurora Global Database | < 1 second | Multi-region with fast failover |
| Snapshot copy | Hours | Long-term retention |

```bash
# Create cross-region read replica
aws rds create-db-instance-read-replica \
  --db-instance-identifier prod-replica-dr \
  --source-db-instance-identifier arn:aws:rds:us-east-1:123456789012:db:prod \
  --region us-west-2
```

### S3

| Feature | Purpose |
|---------|---------|
| **Cross-Region Replication (CRR)** | Replicate objects to DR region |
| **S3 Versioning** | Recover from accidental overwrites/deletes |
| **MFA Delete** | Prevent deletion without MFA |
| **Object Lock** | WORM compliance; ransomware protection |

### DynamoDB

| Feature | RPO |
|---------|-----|
| On-demand backup | Point-in-time |
| Continuous backup (PITR) | 35 days, per-second recovery |
| Global Tables | Near-zero; multi-region active-active |

---

## 23.6 Failover automation

### Route 53 failover

Health checks on primary region; automatic DNS failover to DR region ALB/CloudFront.

### Database failover

```bash
# Promote Aurora Global Database secondary
aws rds failover-global-cluster \
  --global-cluster-identifier my-global-cluster \
  --target-db-cluster-identifier dr-cluster
```

### Application failover

- ASG/ECS desired count increase in DR region (via Lambda + CloudWatch alarm).
- Step Functions orchestrate multi-step failover runbooks.

---

## 23.7 Testing DR

**Untested backups are not backups.** Regular DR testing is required:

| Test type | Frequency | Scope |
|-----------|-----------|-------|
| **Backup verification** | Weekly (automated) | Restore random recovery point |
| **Tabletop exercise** | Quarterly | Walk through failover runbook |
| **Partial failover** | Semi-annually | Fail over one service to DR |
| **Full DR drill** | Annually | Complete regional failover |

Document RTO/RPO achieved during each test and update runbooks.

---

## 23.8 Compliance and retention

| Requirement | AWS feature |
|-------------|-------------|
| Immutable backups | S3 Object Lock, Backup Vault Lock |
| Long-term retention | Glacier via lifecycle; Backup cold storage |
| Audit trail | CloudTrail logs all backup API calls |
| Encryption | KMS keys per vault; separate keys per account |

### Backup Vault Lock

Prevent deletion of recovery points before their retention period expires—even by root account.

```bash
aws backup put-backup-vault-lock-configuration \
  --backup-vault-name compliance-vault \
  --min-retention-days 90 \
  --changeable-for-days 3
```

---

## 23.9 Chapter summary

- **AWS Backup** centralizes backup policies across EC2, RDS, EFS, DynamoDB, and more.
- DR strategies range from **backup & restore** (cheapest) to **active/active** (fastest recovery).
- Use **cross-region** and **cross-account** copies for comprehensive protection.
- Define **RPO** and **RTO** targets and test DR plans regularly.
- Enable **Vault Lock** and **Object Lock** for ransomware-resistant backups.

---

## 🧪 Lab 23.1 — AWS Backup plan

1. Create a backup vault with KMS encryption.
2. Create a backup plan with daily backups and 14-day retention.
3. Tag an EC2 instance with `Backup=daily` and verify it is included.
4. Trigger an on-demand backup and restore to a new volume.

## 🧪 Lab 23.2 — Cross-region replication

1. Enable S3 versioning and CRR on a production bucket.
2. Upload objects and verify replication to the DR region.
3. Simulate primary region failure by blocking access and reading from DR.

---

## Review questions

1. What is the difference between RPO and RTO?
2. Which DR strategy offers the lowest RTO and highest cost?
3. Why is cross-account backup important for ransomware protection?
4. How does Aurora Global Database achieve sub-second RPO?
5. Why should DR plans be tested regularly?

---

*Next: [Chapter 24 — RDS & Aurora](../part-06-databases/chapter-24-rds-aurora.md)*
