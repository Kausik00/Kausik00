# Chapter 38: CloudTrail & AWS Config

*AWS Handbook — Pages 191–195 of this PDF edition*
---

## 38.1 Audit and compliance foundations

Two services form the backbone of AWS governance and compliance:

| Service | Purpose | Question answered |
|---------|---------|-------------------|
| **CloudTrail** | API activity logging | Who did what, when, and from where? |
| **AWS Config** | Resource configuration tracking | What is the current/desired state of resources? |

Together, they provide the audit trail and configuration baseline required for SOC 2, PCI DSS, HIPAA, and internal security policies.

---

## 38.2 AWS CloudTrail

**CloudTrail** records AWS API calls and delivers log files to S3 (and optionally CloudWatch Logs):

### Event types

| Type | Description | Example |
|------|-------------|---------|
| **Management events** | Control plane operations | CreateVpc, RunInstances, DeleteBucket |
| **Data events** | Data plane operations (opt-in) | S3 GetObject, Lambda Invoke, DynamoDB GetItem |
| **Insights events** | Unusual API activity | Spike in DeleteSecurityGroup calls |

### Trail types

| Type | Scope |
|------|-------|
| **Organization trail** | All accounts in the organization (deploy from management account) |
| **Account trail** | Single account |

**Best practice:** One organization trail in the management account, logging to a centralized S3 bucket in the log archive account.

### Terraform organization trail

```hcl
resource "aws_cloudtrail" "org" {
  name                          = "organization-trail"
  s3_bucket_name                = aws_s3_bucket.trail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  is_organization_trail         = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.trail.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::sensitive-bucket/"]
    }
  }

  insight_selector {
    insight_type = "ApiCallRateInsight"
  }
}
```

### CloudTrail log entry structure

```json
{
  "eventTime": "2024-06-15T10:30:00Z",
  "eventName": "RunInstances",
  "eventSource": "ec2.amazonaws.com",
  "awsRegion": "us-east-1",
  "sourceIPAddress": "203.0.113.50",
  "userAgent": "aws-cli/2.15.0",
  "userIdentity": {
    "type": "AssumedRole",
    "principalId": "AROA123:session-name",
    "arn": "arn:aws:sts::123456789012:assumed-role/AdminRole/session-name"
  },
  "requestParameters": {
    "instanceType": "t3.micro",
    "minCount": 1,
    "maxCount": 1
  },
  "responseElements": {
    "instancesSet": { "items": [{ "instanceId": "i-0abc123" }] }
  }
}
```

### Querying CloudTrail

```bash
# Recent events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBucket \
  --max-results 10

# CloudTrail Lake (SQL queries)
aws cloudtrail create-event-data-store \
  --name security-events \
  --retention-period 365

# Athena (S3-based trail logs)
# Create Athena table on trail S3 bucket and run SQL queries
```

---

## 38.3 CloudTrail security

| Control | Purpose |
|---------|---------|
| **Log file validation** | Detect tampering with digest files |
| **S3 bucket policy** | Restrict access to security team |
| **KMS encryption** | Encrypt trail logs at rest |
| **S3 Object Lock** | Prevent deletion (WORM compliance) |
| **Organization trail** | Ensure all accounts are logged (cannot be disabled by members) |

### Protecting the trail bucket

```json
{
  "Sid": "DenyTrailDeletion",
  "Effect": "Deny",
  "Principal": "*",
  "Action": ["s3:DeleteObject", "s3:DeleteBucket"],
  "Resource": [
    "arn:aws:s3:::org-cloudtrail-logs",
    "arn:aws:s3:::org-cloudtrail-logs/*"
  ],
  "Condition": {
    "StringNotEquals": {
      "aws:PrincipalArn": "arn:aws:iam::LOG_ACCOUNT:role/CloudTrailAdmin"
    }
  }
}
```

---

## 38.4 AWS Config

**AWS Config** continuously records resource configuration changes and evaluates compliance against rules:

### How Config works

```
Resource change → Config records configuration item → Rules evaluate → Compliance status
                                                          ↓
                                                    Non-compliant → SNS/SSM remediation
```

### Configuration items

Each CI includes:
- Resource type, ID, and ARN.
- Current configuration (JSON).
- Relationships to other resources.
- Configuration change timeline.

### Config rules

| Type | Example |
|------|---------|
| **AWS managed** | `s3-bucket-public-read-prohibited`, `encrypted-volumes` |
| **Custom (Lambda)** | Company-specific policies |
| **Custom (Guard)** | Policy-as-code (Cedar language) |

```hcl
resource "aws_config_config_rule" "s3_public_read" {
  name = "s3-bucket-public-read-prohibited"

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_PUBLIC_READ_PROHIBITED"
  }
}

resource "aws_config_config_rule" "encrypted_volumes" {
  name = "encrypted-volumes"

  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }

  scope {
    compliance_resource_types = ["AWS::EC2::Volume"]
  }
}
```

### Remediation

Automatically fix non-compliant resources:

```hcl
resource "aws_config_remediation_configuration" "encrypt_volume" {
  config_rule_name = aws_config_config_rule.encrypted_volumes.name
  target_type      = "SSM_DOCUMENT"
  target_identifier = "AWS-EnableEBSEncryption"
  automatic                  = true
  maximum_automatic_attempts = 3

  parameter {
    name         = "AutomationAssumeRole"
    static_value = aws_iam_role.remediation.arn
  }
}
```

---

## 38.5 Config aggregators

For multi-account environments, **Config aggregators** collect configuration and compliance data from multiple accounts and regions:

```hcl
resource "aws_config_configuration_aggregator" "org" {
  name = "organization-aggregator"

  organization_aggregation_source {
    all_regions = true
    role_arn    = aws_iam_role.config_aggregator.arn
  }
}
```

Deploy the aggregator in the security/audit account for centralized compliance dashboards.

---

## 38.6 CloudTrail vs Config

| Aspect | CloudTrail | Config |
|--------|-----------|--------|
| Records | API calls (actions) | Resource configurations (state) |
| Question | Who deleted the bucket? | Is the bucket encrypted? |
| Trigger | Every API call | Configuration change |
| Retention | S3 lifecycle policies | Config retention period |
| Compliance rules | No (use CloudTrail Lake + Athena) | Yes (managed and custom rules) |

**Use both:** CloudTrail for "who did it" and Config for "is it compliant."

---

## 38.7 Compliance reporting

| Tool | Output |
|------|--------|
| **Config conformance packs** | Pre-built rule collections (PCI, CIS, NIST) |
| **Config compliance timeline** | Historical compliance status |
| **Security Hub** | Aggregates Config, GuardDuty, Inspector findings |
| **Athena on CloudTrail** | Custom compliance queries |

```hcl
resource "aws_config_conformance_pack" "cis" {
  name = "CIS-AWS-Foundations-Benchmark"
  template_body = file("cis-conformance-pack.yaml")
}
```

---

## 38.8 Chapter summary

- **CloudTrail** logs all API activity; deploy an **organization trail** to a centralized, protected S3 bucket.
- **AWS Config** tracks resource configurations and evaluates **compliance rules**.
- Use **Config aggregators** for multi-account compliance visibility.
- Enable **log file validation**, **KMS encryption**, and **Object Lock** on trail buckets.
- Combine CloudTrail (who) and Config (what state) for complete governance.

---

## 🧪 Lab 38.1 — CloudTrail investigation

1. Enable a multi-region CloudTrail with S3 and CloudWatch Logs delivery.
2. Perform several API actions (create/delete security group).
3. Use `lookup-events` and CloudWatch Logs Insights to find the events.
4. Identify the IAM principal that performed each action.

## 🧪 Lab 38.2 — Config compliance

1. Enable AWS Config with the `s3-bucket-public-read-prohibited` managed rule.
2. Create a bucket with public read access.
3. Verify the rule reports non-compliance.
4. Fix the bucket and confirm compliance is restored.

---

## Review questions

1. What is the difference between CloudTrail management events and data events?
2. Why should organization trails be deployed from the management account?
3. How does AWS Config differ from CloudTrail?
4. What is a Config conformance pack?
5. How do you protect CloudTrail logs from tampering?

---

*Next: [Chapter 39 — KMS, Secrets Manager, ACM](../part-10-security/chapter-39-kms-secrets-acm.md)*
