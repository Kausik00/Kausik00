# Chapter 43: IAM Policy Cookbook

*AWS Handbook — Pages 223–230 of this PDF edition*

Identity and Access Management is the control plane of AWS. This workbook is a policy-writing studio: JSON you can reason about, Terraform that keeps humans from clicking in the console, and labs that prove a statement is deny-by-default rather than “it worked for the admin.” Pair it with Chapters 5–8. If you cannot explain the difference between an identity policy, a resource policy, a permission boundary, and an SCP, stop and reread those chapters first.

---

## 43.1 The evaluation order you must memorize

AWS authorization is not “first matching allow.” It is a documented algorithm. For day-to-day engineering, hold this compressed version:

1. **Explicit deny** anywhere (SCP, session policy, permission boundary, identity policy, resource policy, VPC endpoint policy) wins.
2. **Organization SCPs** must allow the action in every SCP that applies to the account.
3. **Permission boundaries** and **session policies** (if present) must allow the action.
4. **Identity-based policy** must allow the action, *unless* a resource-based policy grants the calling principal access (the classic S3/KMS/SQS cross-account pattern).
5. Default is **implicit deny**.

Cross-account access requires *both* an identity allow in the caller account *and* a resource policy allow in the target account (with the usual KMS and S3 exceptions you already studied).

| Policy type | Attached to | Typical use |
|-------------|-------------|-------------|
| Identity | User, group, role | What this principal can do |
| Resource | Bucket, queue, topic, key, vault, … | Who can use this object |
| SCP | OU or account | Ceiling for an account |
| Permission boundary | User or role | Ceiling for a delegated admin |
| Session | Assumed-role session | Further shrink a role for one session |
| VPC endpoint | Endpoint | What principals may call through this ENI |

---

## 43.2 Policy elements that actually matter

A statement is `Sid`, `Effect`, `Action`/`NotAction`, `Resource`/`NotResource`, `Principal` (resource policies), and `Condition`.

**Action:** prefer service-specific actions (`s3:GetObject`) over wildcards. `iam:*` in production is a finding, not a convenience.

**Resource:** many actions are ARN-shaped (`arn:aws:s3:::bucket/key`). Some are `*` only (many IAM and CloudWatch actions). If the console or Access Analyzer says the resource is invalid, you used an ARN on an action that does not take one.

**Condition operators** you will use weekly:

| Operator | Example | Intent |
|----------|---------|--------|
| `StringEquals` | `aws:RequestedRegion` | Region lock |
| `StringLike` | `s3:prefix` | Prefix confinement |
| `ArnEquals` | `aws:PrincipalArn` | Named caller |
| `Bool` | `aws:SecureTransport` | TLS only |
| `DateGreaterThan` | `aws:CurrentTime` | Break-glass expiry |
| `IpAddress` | `aws:SourceIp` | Corporate egress (brittle with NAT) |
| `Null` | `aws:MultiFactorAuthPresent` | Require MFA (careful with federation) |
| `ForAllValues:StringEquals` | `s3:RequestObjectTagKeys` | Tag constraints |
| `ForAnyValue:StringLike` | `kms:EncryptionContextKeys` | KMS context |

**NotAction** and **NotResource** are easy to invert wrongly. Prefer positive allows plus a separate explicit deny.

---

## 43.3 Recipe: least-privilege S3 application role

The application reads and writes one prefix in one bucket and lists only that prefix.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListOnlyOurPrefix",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::app-artifacts-prod",
      "Condition": {
        "StringLike": { "s3:prefix": ["releases/*", "releases"] }
      }
    },
    {
      "Sid": "ReadWritePrefix",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::app-artifacts-prod/releases/*"
    },
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::app-artifacts-prod",
        "arn:aws:s3:::app-artifacts-prod/*"
      ],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    }
  ]
}
```

Attach the deny-insecure statement on the *bucket policy* as well so even other principals cannot use HTTP.

---

## 43.4 Recipe: KMS via encryption context

Granting `kms:Decrypt` on a key ARN without conditions is how backups leak into analytics accounts.

```json
{
  "Sid": "DecryptOnlyWithContext",
  "Effect": "Allow",
  "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
  "Resource": "arn:aws:kms:us-east-1:111122223333:key/KEY-ID",
  "Condition": {
    "StringEquals": {
      "kms:EncryptionContext:Service": "orders",
      "kms:EncryptionContext:Env": "prod"
    }
  }
}
```

The key policy must allow the same principal. Encryption context is not secret; it is integrity metadata. Put non-secret identifiers there, not passwords.

---

## 43.5 Recipe: assume-role with external ID and session tags

Cross-account vendor access:

**Trust policy (your account):**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::999988887777:root" },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": { "sts:ExternalId": "vendor-contract-7741" },
      "ArnEquals": { "aws:PrincipalArn": "arn:aws:iam::999988887777:role/VendorScanner" }
    }
  }]
}
```

External ID stops the confused-deputy problem when the vendor is a multi-tenant SaaS. It is not an authentication secret on its own; combine it with a specific role ARN, not the vendor account root if you can avoid it.

---

## 43.6 Recipe: permission boundary for a platform team

A DevOps role may create application roles but must not create roles more powerful than a boundary.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "NoIamEscalation",
      "Effect": "Deny",
      "Action": [
        "iam:CreateUser",
        "iam:CreateLoginProfile",
        "iam:AttachUserPolicy",
        "iam:PutUserPolicy",
        "iam:UpdateAssumeRolePolicy",
        "iam:PassRole"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "iam:PermissionsBoundary": "arn:aws:iam::111122223333:policy/AppRoleBoundary"
        }
      }
    }
  ]
}
```

`iam:PassRole` is the action that turns a compute service into a privilege-escalation gadget. Restrict `PassRole` resource to named application roles and require `iam:PassedToService` when the API supports it.

```json
{
  "Sid": "PassOnlyAppRolesToEc2",
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::111122223333:role/app-*",
  "Condition": {
    "StringEquals": { "iam:PassedToService": "ec2.amazonaws.com" }
  }
}
```

---

## 43.7 Recipe: SCP for a sandbox OU

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyLeaveOrg",
      "Effect": "Deny",
      "Action": ["organizations:LeaveOrganization"],
      "Resource": "*"
    },
    {
      "Sid": "DenyExpensiveDefaults",
      "Effect": "Deny",
      "Action": [
        "ec2:RunInstances"
      ],
      "Resource": [
        "arn:aws:ec2:*:*:instance/*"
      ],
      "Condition": {
        "StringNotEquals": {
          "ec2:InstanceType": ["t3.micro", "t3.small", "t4g.micro", "t4g.small"]
        }
      }
    },
    {
      "Sid": "DenyUnapprovedRegions",
      "Effect": "Deny",
      "NotAction": ["sts:*", "iam:*", "organizations:*", "support:*", "budgets:*"],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2"]
        }
      }
    }
  ]
}
```

SCPs do not grant anything. They only set the ceiling. The `NotAction` region lock must exclude global IAM and STS or you lock yourself out of identity operations.

---

## 43.8 Resource policies: S3, SQS, and VPC endpoints

**S3 bucket policy** that allows a CloudFront OAC and denies non-TLS:

Combine CloudFront’s service principal with a condition on `AWS:SourceArn` of the distribution. Never use a public `Principal: "*"` with an “AWS console said it was fine” ACL.

**SQS policy** for SNS:

SNS must be allowed `sqs:SendMessage` with `aws:SourceArn` equal to the topic. Without the condition, any SNS topic in the world that you accidentally subscribe could publish.

**VPC endpoint policy** default is full access. Tighten it so that only roles tagged `Project=payments` may call `s3:GetObject` through the endpoint. This is defense in depth when a stolen key is used from an unexpected network path.

---

## 43.9 Terraform: role, policies, and Access Analyzer

```hcl
data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name                 = "app-orders-task"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  permissions_boundary = aws_iam_policy.boundary.arn
}

data "aws_iam_policy_document" "app" {
  statement {
    sid     = "Logs"
    actions = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [
      "arn:aws:logs:us-east-1:111122223333:log-group:/ecs/orders:*"
    ]
  }
}

resource "aws_iam_role_policy" "app" {
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_accessanalyzer_analyzer" "account" {
  analyzer_name = "account"
  type          = "ACCOUNT"
}
```

Prefer `aws_iam_policy_document` over heredoc JSON. It is diffable and harder to ship invalid JSON.

---

## 43.10 AWS CLI: simulate before you attach

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::111122223333:role/app-orders-task \
  --action-names s3:GetObject kms:Decrypt \
  --resource-arns arn:aws:s3:::app-artifacts-prod/releases/v1.tgz

aws iam simulate-custom-policy \
  --policy-input-list file://app-policy.json \
  --action-names s3:DeleteBucket \
  --resource-arns arn:aws:s3:::app-artifacts-prod
```

Read `EvalDecision` (`allowed` vs `implicitDeny` vs `explicitDeny`). Simulation does not always model resource policies and SCPs completely; still use it as a unit test for identity statements.

```bash
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document file://app-policy.json
aws iam generate-service-last-accessed-details --arn arn:aws:iam::111122223333:role/app-orders-task
# wait, then
aws iam get-service-last-accessed-details --job-id JOBID
```

Last-accessed data is how you shrink `AdministratorAccess` that “temporarily” aged into a year.

---

## 43.11 ABAC with tags

Attribute-based access control scales when you have hundreds of similar roles.

Condition keys:

- `aws:ResourceTag/Owner`
- `aws:PrincipalTag/Team`
- `aws:RequestTag/Owner` (on create)
- `ec2:ResourceTag/Environment`

Pattern: principals from Identity Center get session tags `Team=payments`. Policies allow `dynamodb:*` only when `aws:ResourceTag/Team` equals `aws:PrincipalTag/Team`. Creating untagged tables is denied. This only works if tag write actions are themselves locked down (`dynamodb:TagResource` restricted).

Pitfall: people with `tag:TagResources` on `*` bypass ABAC. Treat tag mutation as privileged.

---

## 43.12 Federation notes that bite in production

- **IAM Identity Center** permission sets compile to IAM roles in each account. Do not also create long-lived IAM users “just in case.”
- **SAML** `RoleSessionName` and duration affect CloudTrail attribution. Keep sessions short; use `sts:TagSession` for ABAC.
- **OIDC** for GitHub Actions: trust `token.actions.githubusercontent.com` with `sub` conditions that pin org, repo, and environment. A trust policy of `sub` `repo:myorg/*` is how a fork PR steals deploy credentials if you are careless with workflow triggers.

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:myorg/orders:ref:refs/heads/main"
    }
  }
}
```

---

## 43.13 Lab 1 — Write, simulate, attach, break

1. Create a role with an EC2 or Lambda trust policy.
2. Attach a policy that allows `s3:GetObject` on a single object ARN.
3. Simulate `s3:GetObject` (allow) and `s3:PutObject` (implicit deny).
4. Add a bucket policy explicit deny for that role on `PutObject`. Simulate again if applicable; then test from a real session.
5. Add a permission boundary that omits S3. Confirm even the identity allow fails.

Record every JSON file in version control. Policies that exist only in the console will drift.

---

## 43.14 Lab 2 — Confused deputy

1. Create role A in account A that trusts account B root (bad) versus a specific role (good).
2. From a third role in account B, try to assume role A.
3. Add `sts:ExternalId` and retry with and without the ID.

Write two paragraphs: what confused deputy means in AWS, and how External ID plus a specific `Principal` ARN together close it.

---

## 43.15 Lab 3 — PassRole escalation

1. Create a privileged role `admin-breakglass` with a trust policy that allows `ec2.amazonaws.com`.
2. Give a developer `iam:PassRole` on `*` and `ec2:RunInstances`.
3. Show that they can launch an instance with `admin-breakglass` and retrieve instance-profile credentials.
4. Fix PassRole to `role/app-*` and `iam:PassedToService=ec2.amazonaws.com`.

This lab is the reason security reviews ask about PassRole first.

---

## 43.16 Production checklist

| Item | Standard |
|------|----------|
| Root | Hardware MFA; no daily use; no access keys |
| Users | None for humans; Identity Center only |
| Keys | None on IAM users; prefer roles |
| Wildcards | No `Action:*` on `Resource:*` in prod roles |
| Boundaries | Required on roles created by pipelines |
| Analyzer | Account or organization analyzer enabled |
| CloudTrail | Management events plus data events for S3/Lambda as needed |
| Reviews | Quarterly last-accessed and unused roles |

---

## 43.17 Review questions

1. Does an SCP grant permissions? What does it do instead?
2. Why might `iam:PassRole` on `*` be equivalent to administrator in an account that has any privileged instance profile?
3. When is a resource policy required in addition to an identity policy?
4. What is the difference between `ForAllValues` and `ForAnyValue`?
5. Why exclude `iam:*` and `sts:*` from a region-restriction SCP?
6. How does a permission boundary interact with an identity policy allow?
7. What condition key pins GitHub Actions OIDC to a single branch?
8. Why is `aws:SourceIp` a weak control for IAM users who work from home on residential NAT?
9. How do you force TLS for S3 regardless of which principal calls?
10. Access Analyzer reports a bucket as shared. What two questions do you ask before changing the policy?

**Answers (brief):** (1) No; it sets a permission ceiling. (2) The caller can attach the privileged role to a compute resource they control. (3) Cross-account, or services that evaluate resource policies (S3, KMS, SQS, SNS, Secrets Manager, …). (4) All vs any of a multi-valued key must match. (5) Those APIs are global; you would break login and role assumption. (6) The effective permission is the intersection; missing from the boundary means deny. (7) `token.actions.githubusercontent.com:sub` with `ref:refs/heads/...`. (8) IPs change; NAT is shared; it does not bind to identity. (9) Explicit deny on `aws:SecureTransport=false` on the bucket. (10) Who is the principal, and is the share intentional (CloudFront, Log Archive, a partner)?

---

## 43.18 Service control gotchas and CloudTrail for IAM

When a developer says “the policy allows it,” ask them to paste the CloudTrail `errorCode` and `errorMessage`. `AccessDenied` from IAM is different from `AccessDenied` from an S3 bucket policy, a KMS key policy, an SCP, a VPC endpoint policy, or an S3 Block Public Access setting that is not IAM at all.

CloudTrail fields to keep:

| Field | Why |
|-------|-----|
| `userIdentity.arn` | Who |
| `userIdentity.sessionContext.sessionIssuer` | Role chaining |
| `sourceIPAddress` | Often `eks.amazonaws.com` or `lambda.amazonaws.com` for service activity |
| `vpcEndpointId` | Proves the call came through PrivateLink |
| `requestParameters` | The resource they actually named |

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRole \
  --max-results 20
```

**Role chaining:** Role A assumes Role B. Session policies on A do not automatically follow unless you pass them. Duration cannot exceed the remaining time on the original session in some federation paths. Document maximum session duration on production roles (1 hour is a reasonable default; 12 hours is convenient and painful in IR).

**IAM Access Analyzer unused access** (where licensed) is stronger than last-accessed for large estates. Still treat 30-day unused as “candidate,” not “delete tonight,” because monthly jobs exist.

**Policy versioning:** Customer managed policies keep versions. Default version is what is attached. Rolling back is `set-default-policy-version`. Terraform `aws_iam_policy` rewrites in place — review diffs like application code.

---

## 43.19 What to do next

Take one production role, generate last-accessed, and cut unused actions. Then read Chapter 44 with IAM in mind: every Auto Scaling instance profile is a standing credential that VPC design and IAM policy must both constrain.
