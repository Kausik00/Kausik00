# Chapter 7: IAM Identity Center (SSO) & Federation

*AWS Handbook — Pages 28–32 of this PDF edition*
---

## 7.1 The problem with IAM users at scale

Managing hundreds of **IAM users** across dozens of AWS accounts does not scale. Each user needs credentials, MFA enrollment, password rotation, and offboarding when they leave. **IAM Identity Center** (formerly AWS Single Sign-On) centralizes workforce access: users authenticate once through your corporate identity provider and receive temporary credentials to AWS accounts and applications.

For organizations with multiple accounts, Identity Center is the **recommended** human access pattern, replacing per-account IAM users.

---

## 7.2 IAM Identity Center architecture

```
┌──────────────┐     SAML/OIDC      ┌─────────────────────┐
│  IdP         │ ─────────────────► │  IAM Identity       │
│  (Okta, AD,  │                    │  Center             │
│   Google)    │                    │  (management acct)  │
└──────────────┘                    └──────────┬──────────┘
                                               │
                    Permission sets + account assignments
                                               │
              ┌────────────────┬─────────────────┼────────────────┐
              ▼                ▼                 ▼                ▼
         Account A        Account B        Account C        SaaS apps
         (Dev)            (Staging)        (Prod)           (optional)
```

### Key components

| Component | Description |
|-----------|-------------|
| **Identity Center instance** | Deployed in a home region; one per organization |
| **Identity source** | Built-in directory, or federation with external IdP |
| **Permission set** | Template of IAM policies assigned to users/groups |
| **Account assignment** | Maps user/group + permission set → AWS account |
| **Access portal** | `https://d-xxxxxxxxxx.awsapps.com/start` |

---

## 7.3 Permission sets

A **permission set** is a collection of IAM policies that define what a user can do in a target account. When assigned, Identity Center creates an **IAM role** in the target account (prefixed `AWSReservedSSO_`).

### Common permission sets

| Permission set | Typical use |
|----------------|-------------|
| `AdministratorAccess` | Platform team, break-glass |
| `PowerUserAccess` | Developers (no IAM changes) |
| `ReadOnlyAccess` | Auditors, observers |
| Custom (least privilege) | Application-specific access |

### Custom permission set example (Terraform)

```hcl
resource "aws_ssoadmin_permission_set" "developer" {
  name             = "DeveloperAccess"
  instance_arn     = tolist(data.aws_ssoadmin_instances.main.arns)[0]
  session_duration = "PT4H"  # ISO 8601 duration: 4 hours
}

resource "aws_ssoadmin_managed_policy_attachment" "developer_poweruser" {
  instance_arn       = tolist(data.aws_ssoadmin_instances.main.arns)[0]
  permission_set_arn = aws_ssoadmin_permission_set.developer.arn
  managed_policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_ssoadmin_account_assignment" "dev_team" {
  instance_arn       = tolist(data.aws_ssoadmin_instances.main.arns)[0]
  permission_set_arn = aws_ssoadmin_permission_set.developer.arn
  principal_id       = aws_identitystore_group.developers.group_id
  principal_type     = "GROUP"
  target_id          = "123456789012"  # Dev account ID
  target_type        = "AWS_ACCOUNT"
}
```

---

## 7.4 Federation with external identity providers

### SAML 2.0 federation

Most common for enterprise IdPs (Okta, Azure AD, PingFederate):

1. Configure SAML application in your IdP.
2. In Identity Center, set identity source to **External identity provider**.
3. Exchange metadata (IdP → AWS and AWS → IdP).
4. Map IdP attributes to Identity Center users and groups.

### Attribute mapping

| IdP attribute | Identity Center field |
|---------------|----------------------|
| `email` | Username |
| `givenName` | First name |
| `sn` | Last name |
| `memberOf` | Group membership (via SCIM or manual) |

### SCIM provisioning

**System for Cross-domain Identity Management (SCIM)** automates user and group lifecycle:

- User created in Okta → automatically appears in Identity Center
- User deactivated in Okta → access revoked in AWS
- Group membership changes → permission set assignments update

Enable SCIM in Identity Center settings and configure your IdP's provisioning connector.

---

## 7.5 Accessing AWS with Identity Center

### AWS access portal

Users visit the portal URL, authenticate via IdP, and see assigned accounts and roles. Clicking an account/role opens the console or provides CLI credentials.

### CLI access

```bash
aws configure sso
# SSO start URL: https://d-xxxxxxxxxx.awsapps.com/start
# SSO region: us-east-1
# Account: 123456789012
# Role: DeveloperAccess

aws sso login --profile dev
aws sts get-caller-identity --profile dev
```

### Programmatic access from CI/CD

CI/CD should **not** use human SSO sessions. Instead:

- Use **IAM roles** with OIDC federation (GitHub Actions → AWS)
- Use **IAM roles** for EC2/ECS/Lambda
- Use short-lived credentials via `sts:AssumeRole`

---

## 7.6 IAM federation without Identity Center

For single-account or legacy setups, you can federate directly:

| Method | Use case |
|--------|----------|
| **SAML 2.0** | Enterprise IdP → IAM role |
| **Web Identity (OIDC)** | Google, Facebook, Amazon login |
| **Cognito Identity Pools** | Mobile/web apps with federated identities |

### SAML role trust policy example

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:saml-provider/MyCorp"
      },
      "Action": "sts:AssumeRoleWithSAML",
      "Condition": {
        "StringEquals": {
          "SAML:aud": "https://signin.aws.amazon.com/saml"
        }
      }
    }
  ]
}
```

---

## 7.7 Multi-account access patterns

| Pattern | Description |
|---------|-------------|
| **Account per environment** | dev, staging, prod as separate accounts |
| **Account per team** | Team A owns accounts for their services |
| **Account per workload** | PCI workloads isolated from general workloads |
| **Management account** | Identity Center, Organizations, billing only |

### Session duration

Permission sets support session duration from **1 hour to 12 hours**. Shorter sessions reduce risk; longer sessions improve developer experience. Production admin access should use shorter durations (1–2 hours).

---

## 7.8 Security best practices

| Practice | Why |
|----------|-----|
| Use Identity Center for all human access | Centralized audit, MFA, offboarding |
| Assign permissions via groups, not individuals | Easier lifecycle management |
| Enable SCIM provisioning | Automatic deprovisioning |
| Use least-privilege permission sets | Limit blast radius per account |
| Require MFA at the IdP level | Defense in depth |
| Audit assignments regularly | Remove stale access |
| Separate break-glass admin | Emergency access with extra logging |

### Auditing SSO access

```bash
# CloudTrail logs AssumeRoleWithSAML and SSO portal logins
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithSAML \
  --max-results 10
```

---

## 7.9 Chapter summary

- **IAM Identity Center** replaces per-account IAM users with centralized SSO across accounts.
- **Permission sets** define what users can do; **account assignments** map them to specific accounts.
- **SAML/OIDC federation** connects corporate IdPs; **SCIM** automates user lifecycle.
- CLI access via `aws configure sso` and `aws sso login`.
- CI/CD and services should use **IAM roles**, not SSO sessions.

---

## 🧪 Lab 7.1 — Identity Center setup

1. In the management account, enable **IAM Identity Center** (if not already enabled).
2. Create a permission set `LabReadOnly` with the `ViewOnlyAccess` AWS managed policy.
3. Create a user (or use your IdP) and assign them to a dev account with `LabReadOnly`.
4. Log in via the access portal and verify you can view but not modify resources.
5. Configure CLI SSO: `aws configure sso` and run `aws s3 ls` with the new profile.

## 🧪 Lab 7.2 — Audit permission assignments

1. List all account assignments in Identity Center (console or CLI).
2. Identify any assignments with `AdministratorAccess` to production accounts.
3. Document a plan to replace them with least-privilege permission sets.

---

## Review questions

1. What is the difference between a permission set and an account assignment?
2. How does SCIM improve security compared to manual user management?
3. Why should CI/CD pipelines not use Identity Center SSO sessions?
4. What IAM role prefix does Identity Center create in target accounts?
5. Where should MFA be enforced: the IdP, Identity Center, or both?

---

*Next: [Chapter 8 — AWS Organizations & SCPs](./chapter-08-organizations-scps.md)*
