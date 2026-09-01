# Chapter 40: GuardDuty, Security Hub, WAF, and Shield

*AWS Handbook — Part X, Pages 776–790*

---

## 40.1 AWS security services landscape

AWS provides a layered security stack for threat detection, compliance aggregation, and attack mitigation:

| Layer | Service | Function |
|-------|---------|----------|
| **Detection** | GuardDuty | ML-based threat detection |
| **Aggregation** | Security Hub | Centralized findings dashboard |
| **Prevention** | WAF | Application-layer firewall |
| **DDoS protection** | Shield | Network/transport layer DDoS mitigation |
| **Vulnerability** | Inspector | Software vulnerability scanning |
| **Network firewall** | Network Firewall | VPC-level stateful firewall |

This chapter focuses on the four most critical services for production workloads.

---

## 40.2 Amazon GuardDuty

**GuardDuty** is a threat detection service that continuously monitors for malicious activity using machine learning, anomaly detection, and threat intelligence feeds.

### Data sources

| Source | Detects |
|--------|---------|
| **CloudTrail** | Unusual API calls, credential exfiltration |
| **VPC Flow Logs** | Malicious IPs, anomalous traffic patterns |
| **DNS Logs** | Compromised instances, crypto-mining domains |
| **S3 Data Events** | Unusual data access patterns |
| **EKS Audit Logs** | Kubernetes-specific threats |
| **Malware Protection** | Malicious files on EC2 and EBS |

### Finding types (examples)

| Severity | Finding | Description |
|----------|---------|-------------|
| High | `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration` | Credentials used from unusual IP |
| High | `CryptoCurrency:EC2/BitcoinTool` | Instance communicating with mining pool |
| Medium | `Recon:EC2/PortProbeUnprotectedPort` | Port scanning detected |
| Low | `Policy:IAMUser/RootCredentialUsage` | Root account API usage |

### Enabling GuardDuty

```bash
# Enable in a single account
aws guardduty create-detector --enable

# Organization-wide (from delegated admin account)
aws guardduty enable-organization-admin-account \
  --admin-account-id 111111111111

aws organizations enable-aws-service-access \
  --service-principal guardduty.amazonaws.com

aws guardduty create-members \
  --detector-id abc123 \
  --account-details AccountId=222222222222,Email=team@example.com
```

### Terraform

```hcl
resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs { enable = true }
    kubernetes {
      audit_logs { enable = true }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes { enable = true }
      }
    }
  }
}
```

### Response workflow

```
GuardDuty finding → EventBridge rule → Lambda (auto-remediate) / SNS (alert SOC)
                                              ├── Isolate instance (modify SG)
                                              ├── Snapshot EBS for forensics
                                              └── Disable compromised IAM credentials
```

---

## 40.3 AWS Security Hub

**Security Hub** aggregates, organizes, and prioritizes security findings from multiple AWS services and third-party tools:

### Integrated services

| Service | Findings |
|---------|----------|
| GuardDuty | Threat detections |
| Inspector | Vulnerability findings |
| Config | Compliance violations |
| IAM Access Analyzer | External access findings |
| Macie | Sensitive data exposure |
| Firewall Manager | WAF rule violations |
| Third-party | CrowdStrike, Palo Alto, Trend Micro |

### Security standards

| Standard | Framework |
|----------|-----------|
| **AWS Foundational Security Best Practices** | AWS-recommended controls |
| **CIS AWS Foundations Benchmark** | CIS critical controls |
| **PCI DSS** | Payment card industry |
| **NIST 800-53** | US government framework |

```hcl
resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_standards_subscription" "fsbp" {
  standards_arn = "arn:aws:securityhub:us-east-1::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0"
  depends_on    = [aws_securityhub_account.main]
}
```

### Finding workflow

| Status | Meaning |
|--------|---------|
| **NEW** | Just received |
| **NOTIFIED** | Sent to integration |
| **SUPPRESSED** | Acknowledged/accepted risk |
| **RESOLVED** | Remediated |

### Cross-account aggregation

Designate a **delegated administrator** account to aggregate findings from all organization accounts into a single dashboard.

---

## 40.4 AWS WAF

**AWS WAF** is a web application firewall that protects HTTP/HTTPS applications from common exploits:

### Attach points

| Resource | Use case |
|----------|----------|
| **CloudFront** | Global edge protection |
| **ALB** | Regional application protection |
| **API Gateway** | API-specific rules |
| **App Runner** | Containerized app protection |

### Rule types

| Type | Description |
|------|-------------|
| **Regular rule** | Custom conditions (IP, headers, body, URI) |
| **Managed rule group** | AWS or marketplace pre-built rules |
| **Rate-based rule** | Block IPs exceeding request rate |

### AWS managed rule groups

| Group | Protects against |
|-------|-----------------|
| `AWSManagedRulesCommonRuleSet` | OWASP Top 10 (SQLi, XSS) |
| `AWSManagedRulesKnownBadInputs` | Log4j, Spring4Shell |
| `AWSManagedRulesSQLiRuleSet` | SQL injection |
| `AWSManagedRulesBotControlRuleSet` | Bot traffic |
| `AWSManagedRulesAmazonIpReputationList` | Known malicious IPs |

### Terraform WAF

```hcl
resource "aws_wafv2_web_acl" "main" {
  name  = "app-waf"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "RateLimit"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesCommon"
    priority = 2
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "AppWAF"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}
```

### WAF logging

Send WAF logs to S3, CloudWatch Logs, or Kinesis Firehose for analysis:

```bash
aws wafv2 put-logging-configuration \
  --logging-configuration '{
    "ResourceArn": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/app-waf/abc123",
    "LogDestinationConfigs": ["arn:aws:firehose:us-east-1:123456789012:deliverystream/waf-logs"]
  }'
```

---

## 40.5 AWS Shield

**Shield** provides DDoS protection for AWS resources:

| Tier | Cost | Protection |
|------|------|------------|
| **Shield Standard** | Free (automatic) | Network/transport layer (L3/L4) for all AWS customers |
| **Shield Advanced** | $3,000/month + data transfer | Enhanced L3/L4 + L7 protection, 24/7 DDoS Response Team, cost protection |

### Shield Standard (automatic)

- Protects CloudFront, Route 53, ALB, NLB, Global Accelerator.
- No configuration required.
- Mitigates common SYN/UDP floods, reflection attacks.

### Shield Advanced

| Feature | Benefit |
|---------|---------|
| **Advanced detection** | More sophisticated attack detection |
| **DDoS Response Team (DRT)** | 24/7 access to AWS DDoS experts |
| **Cost protection** | Credits for scaling costs during attacks |
| **WAF included** | WAF fees waived for protected resources |
| **Real-time metrics** | Enhanced CloudWatch metrics and attack notifications |

### DDoS mitigation architecture

```
Attacker → Shield Standard/Advanced → CloudFront (WAF) → ALB → Application
              ↓
         Automatic mitigation
         (SYN flood, UDP reflection, etc.)
```

---

## 40.6 Defense-in-depth architecture

```
Internet
  │
  ▼
Route 53 (Shield)
  │
  ▼
CloudFront + WAF (Shield + managed rules)
  │
  ▼
ALB + WAF (regional rules)
  │
  ▼
ECS/EC2 (Security Groups + GuardDuty monitoring)
  │
  ▼
RDS (encrypted, private subnet, Security Hub compliance)
```

| Layer | Service | Protects against |
|-------|---------|-----------------|
| DNS | Shield | DNS amplification |
| Edge | CloudFront + WAF + Shield | DDoS, OWASP Top 10 |
| Network | Security Groups, NACLs | Unauthorized access |
| Detection | GuardDuty | Compromised instances, credential theft |
| Compliance | Security Hub, Config | Misconfigurations |
| Data | KMS, Macie | Encryption, data exposure |

---

## 40.7 Incident response integration

```hcl
resource "aws_cloudwatch_event_rule" "guardduty" {
  name = "guardduty-findings"
  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [7, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9,
                  8, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9]
    }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule      = aws_cloudwatch_event_rule.guardduty.name
  target_id = "SendToSOC"
  arn       = aws_sns_topic.security_alerts.arn
}
```

---

## 40.8 Chapter summary

- **GuardDuty** detects threats using ML across CloudTrail, VPC Flow Logs, and DNS logs.
- **Security Hub** aggregates findings and maps to compliance standards (CIS, PCI, NIST).
- **WAF** protects web applications with managed and custom rules at CloudFront and ALB.
- **Shield Standard** is free and automatic; **Shield Advanced** adds DRT and cost protection.
- Integrate findings with **EventBridge** for automated incident response.

---

## 🧪 Lab 40.1 — GuardDuty and Security Hub

1. Enable GuardDuty and Security Hub with the AWS Foundational standard.
2. Generate a test finding (e.g., unusual API call from a new IP).
3. Review the finding in GuardDuty and Security Hub.
4. Create an EventBridge rule to alert on high-severity findings.

## 🧪 Lab 40.2 — WAF protection

1. Create a WAF Web ACL with rate limiting and AWS managed rules.
2. Associate it with an ALB.
3. Test with a rate-exceeding script and verify blocking.
4. Review WAF sampled requests in the console.

---

## Review questions

1. What data sources does GuardDuty analyze?
2. How does Security Hub differ from GuardDuty?
3. Where can AWS WAF be attached?
4. What is the difference between Shield Standard and Advanced?
5. How would you automate response to a high-severity GuardDuty finding?

---

*Next: [Chapter 41 — Well-Architected Review & Capstone](./chapter-41-well-architected-capstone.md)*
