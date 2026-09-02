# Chapter 48: Security Operations on AWS (GuardDuty, Security Hub, Findings, IR)

*AWS Handbook — Pages 260–265 of this PDF edition*

Detection without response is a dashboard. This workbook is how a small cloud team runs security operations on AWS: enable the right detectors, normalize findings in Security Hub, route them, investigate with CloudTrail and VPC Flow Logs, contain with IAM and network controls, and write the incident timeline. Pair with Chapters 38–41. You will not become a 24×7 SOC in one lab, but you will stop treating GuardDuty as a green check mark you enabled once in 2022.

---

## 48.1 Operating model

| Function | AWS building block | Human output |
|----------|-------------------|--------------|
| Prevent | IAM, SCPs, WAF, Security Groups, KMS, private subnets | Fewer findings |
| Detect | GuardDuty, Security Hub, Config, CloudTrail, Inspector, Macie | Signal |
| Respond | SSM, IAM surgery, isolate ENI/SG, disable keys, ticket | Containment |
| Recover | Backups, known-good AMIs, pipeline redeploy | Restore |
| Learn | IR report, new Config rule, new SCP | Hardening |

Shared Responsibility still applies: AWS detects threats in the *service* telemetry they can see. You must instrument *your* application logs and on-host (or EKS runtime) signals.

---

## 48.2 GuardDuty: what it actually looks at

GuardDuty consumes CloudTrail management events, some data events (S3, etc., depending on protection plans), VPC Flow Logs, DNS logs (when using AWS DNS), Kubernetes audit logs (EKS protection), RDS login activity, Lambda network activity, Malware Protection for S3/EBS, and Runtime Monitoring agents.

Findings have a **severity**, **type** (e.g. `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.InsideAWS`), **resource**, and **actor**. Read the type; it is a taxonomy, not a random string.

| Plan / feature | Enable when |
|----------------|-------------|
| Foundational | Always, all regions you use (and maybe unused regions too) |
| S3 protection | Data lakes, sensitive buckets |
| EKS protection | Any EKS |
| Runtime Monitoring | EC2/ECS/EKS where you can run the agent |
| Malware Protection | EBS snapshots / S3 object scanning as required |
| RDS protection | Production databases |
| Lambda protection | Significant Lambda estate |

```bash
aws guardduty create-detector --enable --finding-publishing-frequency FIFTEEN_MINUTES
aws guardduty list-detectors
aws guardduty update-detector --detector-id 12abc --features \
  '[{"Name":"S3_DATA_EVENTS","Status":"ENABLED"},{"Name":"EKS_AUDIT_LOGS","Status":"ENABLED"}]'
```

**Delegated administrator** in AWS Organizations: one Security account owns detectors in members. Do not leave 40 standalone detectors with 40 forgotten emails.

**Suppression rules** hide known benign findings (a vulnerability scanner that looks like port probes). Suppress by filter, not by ignoring the mailbox.

---

## 48.3 Security Hub: the aggregation and scoreboard

Security Hub ingests GuardDuty, Inspector, Macie, IAM Access Analyzer, AWS Health, partner products, and its own **security standards** (AWS Foundational Security Best Practices, CIS, PCI, NIST). Each control is a Config-backed or service-backed check.

```bash
aws securityhub enable-security-hub --enable-default-standards
aws securityhub batch-enable-standards --standards-subscription-requests \
  '[{"StandardsArn":"arn:aws:securityhub:us-east-1::standards/aws-foundational-security-best-practices/v/1.0.0"}]'
```

**Findings** vs **insights** vs **controls**:

- A finding is an instance of an issue on a resource.
- A control is a check that can be passed/failed with related findings.
- An insight is a saved filter (e.g. “IAM findings, severity ≥ HIGH, last 7 days”).

**Automation rules** (or EventBridge) should route:

| Severity / type | Destination |
|-----------------|-------------|
| CRITICAL / HIGH GuardDuty IAM | Pager / incident channel immediately |
| FAILED FSBP controls on public S3 | Ticket + Slack, 1 business day |
| Informational | Weekly digest |

Do not page humans on every CIS failed control in a sandbox account. Do page on `CredentialExfiltration`.

Cross-Region aggregation and Organizations central configuration belong in the Security account. Application teams get **member** view or tickets, not root in the Security account.

---

## 48.4 Finding → investigation playbook (generic)

1. **Triage:** Is it a known lab? A suppression candidate? A duplicate of an open incident?
2. **Scope:** Account, region, principal ARN, IP, user agent, resource ARN, time window.
3. **Enrich:** CloudTrail `LookupEvents` around the time; VPC Flow Logs for the ENI; GuardDuty finding JSON `service.action`; Config timeline; IAM Access Advisor.
4. **Hypotheses:** Stolen key vs misconfigured app vs attacker in a workload vs compromised dependency.
5. **Contain:** Disable access key; revoke session (`aws iam revoke-session` / apply deny-all boundary / delete role credentials by changing trust); isolate instance SG (no ingress/egress except forensic); stop instance if memory capture is not needed; block S3 public; rotate KMS? usually disable key grants carefully.
6. **Eradicate & recover:** Redeploy from known-good; rotate all possibly exposed secrets; patch; rotate IAM.
7. **Lessons:** New SCP, new alert, new IMDS hop limit, new IRSA.

```bash
# CloudTrail around a principal
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=admin \
  --start-time 2026-09-02T00:00:00Z \
  --end-time 2026-09-02T04:00:00Z

# GuardDuty finding
aws guardduty get-findings --detector-id 12abc --finding-ids abc-finding-id
```

For organization trails, use Athena on the Log Archive bucket rather than `lookup-events` (which is limited).

---

## 48.5 Playbook: IAM credential theft

**Signals:** GuardDuty `UnauthorizedAccess:IAMUser/*`, `Stealth:IAMUser/CloudTrailLoggingDisabled`, console login from unexpected geo, Access Key used from an EC2 IP that is not yours.

**Contain immediately:**

```bash
aws iam update-access-key --user-name broken --access-key-id AKIA... --status Inactive
aws iam delete-access-key --user-name broken --access-key-id AKIA...
# For assumed roles: attach an explicit deny session policy or delete/replace the role
aws iam put-role-policy --role-name app-orders --policy-name deny-all --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"*","Resource":"*"}]}'
```

Revoking a role is disruptive; in true IR, disruption is cheaper than an attacker’s `CreateUser`.

Hunt CloudTrail for `CreateAccessKey`, `AttachUserPolicy`, `PassRole`, `UpdateAssumeRolePolicy`, `PutBucketPolicy`, `DisableAlarmActions`.

---

## 48.6 Playbook: EC2 cryptomining / C2

**Signals:** GuardDuty `CryptoCurrency:EC2/BitcoinTool.*`, unusual DNS to mining pools, security group opened 22 to the world plus a new user.

**Contain:** Snapshot the volume for forensics (`create-snapshot`), then isolate:

```bash
aws ec2 create-network-acl --vpc-id vpc-...  # forensic: isolate subnet if needed
aws ec2 modify-instance-attribute --instance-id i-... --groups sg-forensic-only
aws ssm start-session --target i-...   # only if you trust the box; often you do not
```

Prefer **isolate and replace** from a clean AMI over “cleaning” a mined instance. Capture memory only if you have a trained forensic path (and legal hold).

---

## 48.7 Playbook: S3 public or ransomware-like deletes

**Signals:** Security Hub control S3.1/S3.8 fail, CloudTrail `PutBucketAcl`, GuardDuty `PenTest:IAMUser/KaliLinux`, mass `DeleteObject`.

**Contain:** Block public access at account level (should already be on); bucket policy deny; enable Object Lock on *new* buckets before you need it (you cannot magically Object-Lock yesterday’s bucket without versioning design). Restore from versioning or AWS Backup. Rotate keys that performed deletes.

```bash
aws s3api put-public-access-block --bucket prod-data \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket prod-data --versioning-configuration Status=Enabled
```

---

## 48.8 EventBridge routing Terraform

```hcl
resource "aws_cloudwatch_event_rule" "gd_high" {
  name = "guardduty-high"
  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 7] }]
    }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule = aws_cloudwatch_event_rule.gd_high.name
  arn  = aws_sns_topic.secops.arn
}
```

Security Hub custom actions can send selected findings to Jira. Ticketing is part of IR, not a substitute for paging on exfiltration types.

---

## 48.9 Evidence and legal hygiene

- Do not power off if you need RAM, but also do not leave an attacker running; this is a judgment call — default to isolate network first.
- Snapshots and CloudTrail files are evidence: copy to a dedicated forensic account with restricted IAM.
- Write a timeline in UTC. Include finding IDs.
- Preserve GuardDuty findings (they expire from the API after a retention window unless exported to S3/EventBridge archive).

```bash
aws guardduty create-publishing-destination \
  --detector-id 12abc \
  --destination-type S3 \
  --destination-properties DestinationArn=arn:aws:s3:::sec-findings,KmsKeyArn=arn:aws:kms:...
```

---

## 48.10 Lab 1 — Enable, generate, route (safe)

Use a **dedicated sandbox**. Do not attack AWS services. Use GuardDuty sample findings.

```bash
aws guardduty create-sample-findings --detector-id 12abc \
  --finding-types UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.InsideAWS
```

1. Enable GuardDuty and Security Hub in the sandbox.
2. Generate sample findings.
3. Confirm they appear in Security Hub.
4. Wire EventBridge to email/SNS.
5. Write a one-page runbook: “If this finding were real, we would…”

---

## 48.11 Lab 2 — CloudTrail hunt

1. Enable a trail to S3 + CloudWatch Logs.
2. Perform benign actions: `sts get-caller-identity`, `s3 ls`, `iam list-roles`.
3. Query CloudWatch Logs Insights or Athena for your principal.
4. Practice extracting IP, userAgent, and `errorCode`.

This is the muscle memory IR needs.

---

## 48.12 Lab 3 — Isolate an instance

1. Launch a throwaway instance with a web SG.
2. Create `sg-isolate` with no ingress and egress only to a logging endpoint (or none).
3. Swap SGs. Confirm you can no longer curl the instance, and the instance cannot reach the internet.
4. Snapshot the volume. Stop the instance.

Document why this is better than `terminate` when you might need disk forensics.

---

## 48.13 Metrics for the security program

| Metric | Intent |
|--------|--------|
| Mean time to acknowledge HIGH GuardDuty | On-call health |
| % FSBP controls passed in prod OUs | Hygiene |
| Age of oldest CRITICAL finding | Backlog |
| Public S3 count | Should be near zero |
| IAM users with access keys | Should trend to zero |
| Unused IAM roles | Attack surface |

Security Hub **security score** is a conversation starter, not a compensation metric. Gaming controls with suppressions without risk acceptance is fraud against yourself.

---

## 48.14 Review questions

1. Why enable GuardDuty in unused regions?
2. What is a delegated administrator for GuardDuty?
3. Why are sample findings useful, and why are they dangerous if mixed with prod?
4. What is the first containment step for a leaked IAM access key?
5. Why export GuardDuty findings to S3?
6. How does Security Hub relate to AWS Config?
7. When should a failed CIS control *not* page the on-call?
8. Why isolate with security groups before terminate?
9. What CloudTrail events suggest privilege escalation?
10. How do SCPs help *after* an incident, not only before?

**Answers (brief):** (1) Attackers use quiet regions; credentials work globally for many APIs. (2) A central account that manages member detectors. (3) They test routing; they can train people to ignore real findings if unlabeled. (4) Deactivate/delete the key; hunt; rotate everything it could have touched. (5) API retention is limited; IR and SIEM need history. (6) Many Hub controls are implemented as Config rules. (7) Low-severity hygiene in non-prod; use tickets. (8) Preserve disk and stop lateral movement. (9) `AttachUserPolicy`, `CreateAccessKey`, `UpdateAssumeRolePolicy`, `PassRole`. (10) You can deny the abused APIs org-wide while you clean accounts.

---

## 48.15 Detective, Inspector, Macie, and when to add them

GuardDuty and Security Hub are the backbone. Adjacent services fill gaps:

| Service | Question it answers |
|---------|---------------------|
| Amazon Inspector | Are these EC2/ECR/Lambda artifacts full of CVEs? |
| Macie | Is there PII in S3 I forgot about? |
| Detective | How do I graph this IAM principal’s API activity without writing Athena first? |
| IAM Access Analyzer | What is shared outside the account or org? |
| Config | What *was* the SG yesterday? |
| CloudTrail Lake or Athena | Full-fidelity query |

```bash
aws inspector2 list-findings --filter-criteria '{"severity":{"comparison":"EQUALS","value":"CRITICAL"}}' --max-results 5
aws macie2 list-classification-jobs
aws detective list-graphs
```

Turn on Inspector for ECR in prod accounts that ship containers. Macie is priced on data classified; start with sensitive buckets, not the entire log archive.

**Finding quality:** tune Inspector to suppress OS packages you cannot patch until AMI rebuild, but track them as risk. Do not suppress CVE-critical on internet-facing instances.

**IR roles:** a dedicated `SecurityBreakglass` role, SCP-exempt in a documented way or in a separate OU, MFA, logged, ticket required after the fact. Test it twice a year. An IR role that nobody can assume because of a broken IdP is a paperweight.

**Communications:** status page owner, legal, and customer comms are not GuardDuty’s job. Your IR doc names them. AWS Abuse reports for your IPs should have an alias that reaches on-call.

**Tabletop:** twice a year, pick a finding type and walk the playbook without changing prod. Time how long it takes to answer “what data could they see.”

---

**After-action report template:** UTC timeline, finding IDs, principals, resources, containment commands (paste actual CLI), remaining risk, tickets for permanent fixes (SCP, IMDS, IRSA), and whether customer notification was required. Store reports in a bucket the attacker could not have deleted (log archive account, SCP deny `s3:DeleteBucket`).

---

**Containment decision tree (short):** If credentials leak → disable keys and deny-all on the role before you snapshot anything. If a host is mining → isolate SG, snapshot EBS, replace from AMI; do not “apt remove miner” and return to the ASG. If S3 objects vanish → stop the principal, enable versioning if off (helps only future objects), restore versions, rotate. If EKS token leaks → delete the ServiceAccount token bindings, rotate IRSA role trust, cordon nodes if node IAM was overly broad.

Map each GuardDuty type you enable to one of those three buckets so 03:00 does not become a debate club.

---

Keep the decision tree on a wiki page next to the EventBridge rule that pages you. If the page and the pager disagree, the pager wins until the doc is updated in the same change window.

---

## 48.16 What to do next

Security operations that ignore cost will be turned off by finance. Chapter 49 is the workbook that keeps detection enabled *and* the bill explainable — including GuardDuty, Flow Logs, and Security Hub themselves as line items you chose on purpose.
