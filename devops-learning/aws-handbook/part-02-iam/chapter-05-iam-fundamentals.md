# Chapter 5: IAM Users, Groups, Roles, and Policies

*AWS Handbook — Pages 20–23 of this PDF edition*
---

## 5.1 What is IAM?

**AWS Identity and Access Management (IAM)** controls **who** can access **which** AWS resources and **how**. Every API call to AWS is authenticated and authorized through IAM (except public resources like anonymous S3 access).

IAM is **global**—users and roles exist at the account level, not per region.

---

## 5.2 IAM identity types

| Identity | Use case |
|----------|----------|
| **Root user** | Account owner; created at signup. **Avoid for daily use.** |
| **IAM user** | Long-term credentials for humans or legacy apps |
| **IAM role** | Temporary credentials; assumed by users, services, or other accounts |
| **IAM group** | Collection of users with shared permissions |

**Best practice:** Humans use **IAM Identity Center (SSO)** or roles with MFA. Applications and EC2/Lambda use **roles**, not access keys on users.

---

## 5.3 Policies — the core of permissions

A **policy** is a JSON document defining **Allow** or **Deny** for **actions** on **resources** under **conditions**.

### Policy structure

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3Read",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-app-bucket",
        "arn:aws:s3:::my-app-bucket/*"
      ],
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": "203.0.113.0/24"
        }
      }
    }
  ]
}
```

### Policy types

| Type | Attached to |
|------|-------------|
| **Identity-based** | Users, groups, roles |
| **Resource-based** | S3 buckets, SNS topics, etc. |
| **Permission boundaries** | Max permissions for identity |
| **SCP** | AWS Organizations — account ceiling |
| **Session policies** | Limit role session scope |

**Evaluation logic:** Explicit **Deny** always wins. Default is implicit deny until Allow.

---

## 5.4 Users and groups

### Create a developer group (example workflow)

1. Create group `Developers`.
2. Attach policy `PowerUserAccess` (or custom least-privilege policy).
3. Create users; add to group.
4. Enable **MFA** for console access.
5. Provide **programmatic access** only if needed (prefer roles).

```bash
aws iam create-group --group-name Developers
aws iam attach-group-policy --group-name Developers \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
aws iam create-user --user-name alice
aws iam add-user-to-group --user-name alice --group-name Developers
```

---

## 5.5 Roles and trust policies

A **role** has two policies:

1. **Trust policy** — Who can assume the role
2. **Permission policy** — What the role can do

### EC2 instance role example

Trust policy (allows EC2 service to assume):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach permission policy allowing `s3:GetObject` on a specific bucket. The EC2 instance receives **temporary credentials** via instance metadata—no hardcoded keys.

### Assume role (cross-account or CLI)

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/DeployRole \
  --role-session-name deploy-session
```

---

## 5.6 AWS managed vs customer managed policies

| Type | Description |
|------|-------------|
| **AWS managed** | Maintained by AWS (`ReadOnlyAccess`, `AdministratorAccess`) |
| **Customer managed** | You create and reuse across identities |
| **Inline** | Embedded in single user/group/role; harder to reuse |

Prefer **customer managed** policies for team standards; avoid `AdministratorAccess` except break-glass accounts.

---

## 5.7 Least privilege in practice

1. Start with **read-only** access; add permissions as needed.
2. Use **IAM Access Analyzer** to find overly broad access.
3. Scope resources with ARNs, not `"Resource": "*"`.
4. Use **conditions** (MFA present, source IP, tag-based).
5. Rotate or eliminate **access keys**; prefer roles.

### Tag-based access (ABAC)

```json
"Condition": {
  "StringEquals": {
    "aws:PrincipalTag/Department": "${aws:ResourceTag/Department}"
  }
}
```

Users tagged `Department=Engineering` access only resources tagged the same.

---

## 5.8 Common IAM actions for DevOps

| Action prefix | Service |
|---------------|---------|
| `ec2:*` | EC2 |
| `s3:*` | S3 |
| `iam:PassRole` | Allow attaching roles to services |
| `sts:AssumeRole` | Switch roles |
| `cloudformation:*` | Stack operations |

`iam:PassRole` is often required when CI/CD deploys resources that need an instance/task role.

---

## 5.9 IAM Access Analyzer & CloudTrail

- **Access Analyzer** — Identifies resources shared externally.
- **CloudTrail** — Logs every IAM API call for audit.

Enable CloudTrail in all regions for security accounts.

---

## 5.10 Chapter summary

- IAM controls authentication and authorization globally.
- Use **groups** for humans, **roles** for services and temporary access.
- Policies are JSON with Effect, Action, Resource, Condition.
- Apply **least privilege**; avoid root and long-lived access keys.

---

## 🧪 Lab 5.1 — IAM hands-on

1. Create IAM user `lab-user` with MFA.
2. Create customer managed policy allowing `s3:ListBucket` and `s3:GetObject` on one bucket.
3. Create role `EC2-S3-ReadRole` with trust for EC2 and the S3 read policy.
4. Launch EC2 with the role; verify `aws s3 ls` works without configured keys.
5. Review effective permissions in **IAM Policy Simulator**.

---

## Review questions

1. What is the difference between an IAM user and an IAM role?
2. What happens when Allow and Deny conflict?
3. Why should EC2 instances use roles instead of access keys?
4. What does `sts:AssumeRole` do?

---

*Continue: Chapter 6 — IAM Best Practices (outline in TOC)*
