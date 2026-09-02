# Chapter 8: AWS Organizations & Service Control Policies

*AWS Handbook — Pages 33–37 of this PDF edition*
---

## 8.1 Why AWS Organizations?

A single AWS account works for small teams, but enterprises need **multiple accounts** for security isolation, blast-radius containment, billing separation, and compliance boundaries. **AWS Organizations** is a free service that centrally manages a hierarchy of accounts under one **organization**.

Without Organizations, you cannot use Service Control Policies, consolidated billing, or automated account vending.

---

## 8.2 Organization structure

```
Organization (o-xxxxxxxxxx)
├── Management account (formerly "master")
├── Organizational Units (OUs)
│   ├── Security OU
│   │   ├── Log Archive account
│   │   └── Audit account
│   ├── Infrastructure OU
│   │   ├── Network account
│   │   └── Shared Services account
│   └── Workloads OU
│       ├── Dev OU
│       │   ├── Team-A-Dev
│       │   └── Team-B-Dev
│       └── Prod OU
│           ├── Team-A-Prod
│           └── Team-B-Prod
└── (member accounts)
```

### Key concepts

| Concept | Description |
|---------|-------------|
| **Management account** | Pays for all member accounts; hosts Organizations, Identity Center |
| **Member account** | Standard AWS account within the organization |
| **Organizational Unit (OU)** | Grouping of accounts for policy application |
| **Root** | Top of the hierarchy; contains all OUs and accounts |

---

## 8.3 Consolidated billing

Organizations provides a **single bill** for all accounts:

- **Volume discounts** aggregate across accounts (e.g., S3, Data Transfer).
- **Cost allocation tags** propagate for chargeback.
- **AWS Budgets** and **Cost Explorer** work across the organization.
- **Reserved Instances and Savings Plans** can be shared within the org.

```bash
# List all accounts in the organization
aws organizations list-accounts \
  --query 'Accounts[].{Id:Id,Name:Name,Status:Status}' \
  --output table
```

---

## 8.4 Service Control Policies (SCPs)

**SCPs** are guardrails that set the **maximum permissions** for accounts or OUs. They do not grant permissions—they **filter** what identity-based policies can allow.

### SCP evaluation

```
Effective permissions = Identity policies ∩ SCPs (and permission boundaries)
```

- **Explicit Deny** in an SCP always wins.
- If no SCP allows an action, it is implicitly denied (for SCP scope).
- SCPs affect all principals **except** the management account root user and certain service-linked roles.

### Example: Deny leaving the organization

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyLeaveOrganization",
      "Effect": "Deny",
      "Action": "organizations:LeaveOrganization",
      "Resource": "*"
    }
  ]
}
```

### Example: Restrict regions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnapprovedRegions",
      "Effect": "Deny",
      "NotAction": [
        "iam:*",
        "organizations:*",
        "route53:*",
        "support:*",
        "cloudfront:*",
        "globalaccelerator:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
        }
      }
    }
  ]
}
```

### Example: Deny root user actions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyRootUser",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "aws:PrincipalArn": "arn:aws:iam::*:root"
        }
      }
    }
  ]
}
```

---

## 8.5 Common SCP strategies

| SCP purpose | Approach |
|-------------|----------|
| **Region lock** | Deny all actions outside approved regions |
| **Prevent privilege escalation** | Deny `iam:CreateUser`, `iam:AttachUserPolicy` in workload accounts |
| **Require encryption** | Deny S3 `PutObject` without `s3:x-amz-server-side-encryption` |
| **Block expensive services** | Deny `ec2:RunInstances` for large instance types in dev |
| **Protect security services** | Deny disabling GuardDuty, CloudTrail, Config |

### Terraform SCP attachment

```hcl
resource "aws_organizations_policy" "deny_root" {
  name    = "DenyRootUser"
  type    = "SERVICE_CONTROL_POLICY"
  content = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "DenyRootUser"
      Effect   = "Deny"
      Action   = "*"
      Resource = "*"
      Condition = {
        StringLike = {
          "aws:PrincipalArn" = "arn:aws:iam::*:root"
        }
      }
    }]
  })
}

resource "aws_organizations_policy_attachment" "workloads" {
  policy_id = aws_organizations_policy.deny_root.id
  target_id = aws_organizations_organizational_unit.workloads.id
}
```

---

## 8.6 Account vending with Control Tower

**AWS Control Tower** builds on Organizations to provide:

- **Account Factory** — Automated account creation with baseline guardrails.
- **Guardrails** — Pre-built SCPs (mandatory and elective).
- **Account Factory for Terraform (AFT)** — Terraform-based account vending.

Typical landing zone accounts:

| Account | Purpose |
|---------|---------|
| Management | Organizations, Identity Center, billing |
| Log Archive | Centralized CloudTrail, Config logs |
| Audit | Security tooling (GuardDuty admin, Security Hub) |
| Network | Transit Gateway, VPN, Direct Connect |
| Shared Services | CI/CD, artifact repos, DNS |

---

## 8.7 Delegated administration

Certain security services can be administered from a **delegated admin account** instead of the management account:

| Service | Delegated admin use |
|---------|---------------------|
| GuardDuty | Central threat detection |
| Security Hub | Aggregated findings |
| AWS Config | Aggregator for compliance |
| CloudTrail | Organization trail management |
| Firewall Manager | WAF rules across accounts |

```bash
aws organizations enable-aws-service-access \
  --service-principal guardduty.amazonaws.com

aws guardduty enable-organization-admin-account \
  --admin-account-id 111111111111
```

---

## 8.8 SCP troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `AccessDeniedException` for allowed IAM policy | SCP denies the action |
| Works in management account, fails in member | SCP attached to member OU |
| Service-linked role fails | SCP may need exception for that role |
| Cannot enable a service | SCP blocks the enable API |

### Testing SCP impact

```bash
# Use IAM Policy Simulator with Organizations context
# Or: create a test role in a sandbox account with the SCP attached
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/TestRole \
  --action-names ec2:RunInstances \
  --resource-arns "*"
```

---

## 8.9 Chapter summary

- **AWS Organizations** manages multi-account hierarchies with consolidated billing.
- **OUs** group accounts for policy application.
- **SCPs** set permission guardrails; they filter but do not grant access.
- **Control Tower** provides a landing zone with automated account vending.
- **Delegated administration** centralizes security services in a dedicated account.

---

## 🧪 Lab 8.1 — Explore your organization

1. Run `aws organizations describe-organization` and note the organization ID.
2. List all accounts: `aws organizations list-accounts`.
3. Identify which OUs exist and which accounts belong to each.
4. List SCPs: `aws organizations list-policies --filter SERVICE_CONTROL_POLICY`.

## 🧪 Lab 8.2 — Create a sandbox SCP

1. In a **sandbox OU** (never production first), create an SCP that denies `ec2:RunInstances` for instance types larger than `xlarge`.
2. Attach the SCP to the sandbox OU.
3. Attempt to launch a `m5.2xlarge` — verify denial.
4. Launch a `t3.micro` — verify success.
5. Detach and delete the SCP when done.

---

## Review questions

1. Do SCPs grant permissions or restrict them?
2. Which account is exempt from SCP restrictions?
3. How do consolidated billing volume discounts work across accounts?
4. What is the difference between an OU and an AWS account?
5. Why should you test SCPs in a sandbox before applying to production OUs?

---

*Next: [Chapter 9 — VPC Fundamentals](../part-03-networking/chapter-09-vpc-fundamentals.md)*
