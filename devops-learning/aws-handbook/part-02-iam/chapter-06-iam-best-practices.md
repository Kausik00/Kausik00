# Chapter 6: IAM Best Practices and Permission Boundaries

*AWS Handbook — Pages 24–26 of this PDF edition*
---

## 6.1 The IAM security baseline

Follow these rules in every AWS account:

1. **Root account** — MFA only; no access keys; break-glass use only
2. **No long-lived access keys** for humans — use SSO + temporary credentials
3. **Least privilege** — Grant minimum permissions required
4. **MFA** — Required for console access and sensitive API calls
5. **Rotate keys** — If keys must exist, rotate every 90 days max
6. **Audit** — CloudTrail enabled in all regions; review Access Analyzer findings

---

## 6.2 Prefer roles over users for applications

| Identity | Use for |
|----------|---------|
| IAM user + keys | Legacy; avoid for new projects |
| IAM role | EC2, Lambda, ECS, cross-account, CI/CD |
| IAM Identity Center | Human workforce access |

### CI/CD role pattern

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:myorg/myrepo:*"
      }
    }
  }]
}
```

GitHub Actions assumes this role—no static AWS keys in GitHub Secrets.

---

## 6.3 Permission boundaries

A **permissions boundary** sets the **maximum** permissions an identity can have—even if policies grant more.

Use for:

- Delegating IAM admin to developers without full account access
- Sandbox accounts with caps

```bash
aws iam put-user-permissions-boundary \
  --user-name developer \
  --permissions-boundary arn:aws:iam::aws:policy/PowerUserAccess
```

---

## 6.4 Policy writing tips

### Start with AWS managed, refine to customer managed

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DeployToSpecificBucket",
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject"],
    "Resource": "arn:aws:s3:::my-app-artifacts-prod/*"
  }]
}
```

### Use IAM Policy Simulator

Test policies before deploying: AWS Console → IAM → Policy Simulator.

### Avoid these anti-patterns

- `"Action": "*"` on production roles
- `"Resource": "*"` when ARNs are known
- Attaching `AdministratorAccess` to CI roles
- Sharing one IAM user across a team

---

## 6.5 Service-linked roles

AWS creates **service-linked roles** for services (e.g., AWSServiceRoleForElasticLoadBalancing). Do not delete these unless AWS docs say it's safe.

---

## 6.6 Cross-account access

**Pattern:** Account A (workload) trusts Account B (CI/CD) via role assumption.

```bash
# From CI in account B
aws sts assume-role \
  --role-arn arn:aws:iam::WORKLOAD_ACCOUNT:role/DeployRole \
  --role-session-name github-deploy
```

Use **AWS Organizations** SCPs to prevent privilege escalation across accounts.

---

## 6.7 Chapter summary

- Humans: **SSO + MFA**. Apps: **roles**. CI: **OIDC federation**.
- Write **scoped customer-managed policies**; test with Policy Simulator.
- Use **permission boundaries** and **SCPs** for guardrails.

---

## 🧪 Lab 6.1

1. Create a CI/CD role trust policy for GitHub OIDC (or a second AWS account).
2. Attach a least-privilege policy for S3 deploy only.
3. Run Access Analyzer and remediate any `Public` findings.

---

*Next: [Chapter 9 — VPC Fundamentals](../part-03-networking/chapter-09-vpc-fundamentals.md)*
