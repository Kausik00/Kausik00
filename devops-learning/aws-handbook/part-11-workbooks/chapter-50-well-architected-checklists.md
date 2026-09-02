# Chapter 50: Well-Architected Checklists

*AWS Handbook — Pages 273–281 of this PDF edition*

The AWS Well-Architected Framework is six pillars plus a set of questions that force specifics. Chapter 41 walked a capstone design. This workbook is the review kit: checklists you can run on a real workload, evidence to collect, scoring notes, and review questions. There are no planned PDF page numbers here — use the checklists, not a page index.

A review is successful when it produces **work items with owners**, not a color-coded slide. Use the AWS Well-Architected Tool to store answers if your organization requires it; the checklists below work with a spreadsheet equally well.

---

## 50.1 How to run a review

| Step | Practice |
|------|----------|
| Scope | One workload (orders API), not “all of AWS” |
| People | Engineer who operates it, security, FinOps, product (for criticality) |
| Evidence | Console is weak; prefer Terraform state, pipelines, tickets, dashboards, incident history |
| Cadence | Before major launches; after incidents; quarterly for revenue systems |
| Output | Risks (high/medium) with pillar, recommendation, ticket ID |

**Scoring:** High risk means a realistic failure or breach path exists. Medium means toil or incomplete testing. Do not mark “best effort” as high if the business accepted the risk in writing.

CLI helpers while you review:

```bash
aws wellarchitected list-workloads --region us-east-1
# If you use the WA Tool API:
# aws wellarchitected get-lens-review --workload-id ... --lens-alias wellarchitected
```

Terraform does not “implement Well-Architected,” but a module that forces encryption, tags, and multi-AZ is evidence for several questions at once.

---

## 50.2 Operational Excellence checklist

Operational Excellence is deploy, observe, respond, and improve.

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| OE-1 | Workload has an owner and runbook location | Wiki link, CODEOWNERS | “Ask in Slack” |
| OE-2 | Changes go through pipeline; no click-ops in prod | Pipeline definitions, CloudTrail | Console edits on SG |
| OE-3 | You can deploy off-hours with one command | Runbook | Hero engineer laptop |
| OE-4 | Rollback is tested | Last rollback ticket | Forward-only migrations |
| OE-5 | Telemetry: metrics, logs, traces with example dashboards | Screenshot + IaC | Logs only |
| OE-6 | Alerts route to a human who can act; no infinite SNS to nowhere | On-call rotation | 400 noisy alarms |
| OE-7 | Incident process: severity, comms, post-incident review | IR doc | Outages vanish |
| OE-8 | Game days or failure tests exist | Calendar | First failover is production |
| OE-9 | Config and secrets are code; parameters documented | Terraform + Secrets Manager | Shared `.env` on a bastion |
| OE-10 | Limit blast radius of deploys (canary, instance refresh, alias) | Config | All-at-once `$LATEST` |

**Ops questions to ask aloud:**

1. What happens if the primary engineer is unreachable for 72 hours?
2. Show the last production rollback.
3. Show an alert that fired and was useful in the last month.
4. Where is the dependency map (managed services this app needs)?

```bash
aws ssm get-document --name "AWS-RunPatchBaseline" # example of documented ops automation
aws logs describe-log-groups --query 'logGroups[].{Name:logGroupName,Retention:retentionInDays}'
```

**Lab OE:** Pick one microservice. Write a one-page runbook: deploy, rollback, “disk full,” “error rate > 2%.” Fill every blank with a real command. If you cannot, that is the finding.

---

## 50.3 Security checklist

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| SEC-1 | No long-lived IAM users for humans | Identity Center | IAM users + access keys |
| SEC-2 | Root unused, MFA, no access keys | Credential report | Root used for daily |
| SEC-3 | Least privilege; no `Action:*` on `Resource:*` in app roles | IAM Access Analyzer, last-accessed | Administrator on ECS task |
| SEC-4 | Permission boundaries or SCPs constrain builders | Org policies | Sandbox can create IAM users |
| SEC-5 | Encryption at rest with recorded key owners | KMS key policies | Default keys everywhere, no rotation story |
| SEC-6 | TLS in transit for user and service traffic | ALB listeners, RDS force SSL | HTTP to ALB “temporarily” |
| SEC-7 | Public access blocked (S3 account BPA, no public SG 22/3389) | Config, Security Hub | One “debug” SG |
| SEC-8 | Secrets not in Git or user data | Scanning, Secrets Manager | Password in launch template |
| SEC-9 | GuardDuty + Security Hub + CloudTrail org trail | Detectors, trail ARN | Trail in one region only |
| SEC-10 | IMDS hop / IMDSv2; IRSA not node roles for apps | Launch templates, SA annotations | Node role `s3:*` |
| SEC-11 | WAF on public HTTP; Shield as required | Web ACL association | Naked ALB |
| SEC-12 | IR playbooks exist (Chapter 48) | Doc + EventBridge | GuardDuty email unread |

**Security questions:**

1. Show CloudTrail for this account for yesterday. Who deployed?
2. What data classification does this workload handle?
3. If this IAM role leaked, what could an attacker read?

```bash
aws iam generate-credential-report
aws iam get-credential-report --query 'Content' --output text | base64 -d | head
aws accessanalyzer list-analyzers
aws guardduty list-detectors
```

**Lab SEC:** Run Security Hub FSBP against the workload account. File tickets for every FAILED control that maps to this app. Accept risk in writing for the rest.

---

## 50.4 Reliability checklist

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| REL-1 | Multi-AZ for compute and data that must survive AZ loss | Subnet maps, RDS Multi-AZ | Single-AZ RDS “to save money” |
| REL-2 | Defined RTO/RPO and a tested restore | Restore ticket | Backups never restored |
| REL-3 | Health checks match user success | Target group `/ready` | `/` always 200 |
| REL-4 | Autoscaling or sufficient static headroom | ASG policies | Desired=1 |
| REL-5 | Throttling and backoff to dependencies | Code + dashboards | Retry storms |
| REL-6 | Change management does not require downtime | Instance refresh, blue/green | Manual AMI swap SSH |
| REL-7 | Quota monitoring (service quotas) | Alarms on usage | Silent `LimitExceeded` |
| REL-8 | DR: backup, pilot light, or active-active as required | Runbook | “We will figure it out” |
| REL-9 | Stateless compute; state in DynamoDB/Aurora/S3 | Architecture | Unique snowflake instance |
| REL-10 | Chaos or fault injection at least annually for tier-1 | FIS experiment | None |

```bash
aws service-quotas list-service-quotas --service-code ec2 --query 'Quotas[?QuotaName!=`null`].[QuotaName,Value]' --output table
aws rds describe-db-instances --query 'DBInstances[].{Id:DBInstanceIdentifier,MultiAZ:MultiAZ,Status:DBInstanceStatus}'
```

**Reliability questions:**

1. What is the blast radius of losing us-east-1a?
2. Show the last backup restore test date.
3. What is the client behavior when DynamoDB returns 500?

**Lab REL:** Terminate one AZ’s app instances (lab) or simulate with FIS. Confirm ALB remaining healthy hosts ≥ min. If the group is in two AZs with min=2, you may still pass — then fail the NAT in one AZ (Chapter 42) and watch egress.

---

## 50.5 Performance Efficiency checklist

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| PERF-1 | Architecture matches access patterns (SQL vs key-value vs cache) | Chapter 47 review | Scan-heavy DynamoDB |
| PERF-2 | Right compute: Graviton, size, Lambda memory tuned | Benchmarks | Copy-paste m5.xlarge |
| PERF-3 | CDN for static and cacheable API | CloudFront | Origin in one region for global users |
| PERF-4 | Database indexes and slow-query process | PI, slow logs | “Add more RDS” |
| PERF-5 | Load tests exist at expected peak + burst | Report | Prod is the load test |
| PERF-6 | Streaming/async for heavy work | SQS/Kinesis | Synchronous 60s HTTP |
| PERF-7 | Storage: gp3, EFS vs EBS vs S3 chosen on purpose | Tickets | Everything on io2 |
| PERF-8 | Review new instance families yearly | Notes | 2018 instance types |

```bash
aws ec2 describe-instance-types --filters Name=instance-type,Values=m7g.large --query 'InstanceTypes[].{vCPU:VCpuInfo.DefaultVCpus,Mem:MemoryInfo.SizeInMiB}'
aws elasticache describe-replication-groups --query 'ReplicationGroups[].{Id:ReplicationGroupId,Status:Status}'
```

**Lab PERF:** Run a 10-minute load test against a non-prod ALB. Capture p50/p99, error rate, CPU, RDS connections. Write one sentence on the bottleneck.

---

## 50.6 Cost Optimization checklist

Reuse Chapter 49; this is the WA-shaped version.

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| COST-1 | Tags + accounts allow showback | CUR query | 40% unallocated |
| COST-2 | Budgets and anomaly detection | Budget ARNs | Bill shock |
| COST-3 | Waste hunt in last 90 days | Ticket list | Unattached EBS for a year |
| COST-4 | Commitments match stable usage | SP coverage | 3-year RI on a prototype |
| COST-5 | Data transfer designed | NAT vs endpoints | S3 via NAT |
| COST-6 | Non-prod scheduled off or scaled to zero | ASG schedules | Dev RDS 24×7 Multi-AZ |
| COST-7 | Logs and metrics retention | Log groups | Never expire |
| COST-8 | Unit metric (cost / business event) | Dashboard | Only monthly total |

```bash
aws ce get-cost-forecast --time-period Start=2026-09-01,End=2026-10-01 --metric UNBLENDED_COST --granularity MONTHLY
```

**Lab COST:** Export top five services by cost. For each, name one architectural lever (not “be more careful”).

---

## 50.7 Sustainability checklist

Sustainability on AWS is mostly utilization, Region choice, and hardware generation.

| ID | Check | Evidence | Typical fail |
|----|-------|----------|--------------|
| SUS-1 | High utilization or scale-to-zero | ASG/Lambda graphs | Always-on idle fleets |
| SUS-2 | Graviton or newer efficient families | Instance types | Old x86 only by habit |
| SUS-3 | Lifecycle cold data to infrequent storage | S3 analytics | Hot storage forever |
| SUS-4 | Right Region for users (fewer network hops) | Architecture | Dual-region without users |
| SUS-5 | Efficient software (batch, compression) | Design notes | Chatty chatty chatty |

Sustainability findings often duplicate cost and performance. That is acceptable; record them once and tag both pillars.

---

## 50.8 Cross-pillar trade-offs (the real review)

Write these explicitly:

| Trade-off | Example |
|-----------|---------|
| Cost vs Reliability | Single NAT vs NAT per AZ |
| Security vs Ops | Private API endpoint vs engineer VPN toil |
| Performance vs Cost | Provisioned concurrency |
| Reliability vs Cost | Multi-region active-active |
| Ops vs Security | SSM vs inbound SSH (this one should not be a debate) |

If a team “passed” every pillar without a trade-off table, they did not review.

---

## 50.9 Workload review scorecard (copy this)

| Pillar | High risks | Medium risks | Notes |
|--------|------------|--------------|-------|
| Operational Excellence | | | |
| Security | | | |
| Reliability | | | |
| Performance Efficiency | | | |
| Cost Optimization | | | |
| Sustainability | | | |

**Top 5 actions this quarter:** (must have owners)

1.
2.
3.
4.
5.

Terraform stub to document the workload in tags:

```hcl
variable "wa_workload_id" { type = string } # optional WA Tool id
locals {
  wa_tags = {
    WellArchitectedWorkload = var.wa_workload_id
    Criticality             = "high"
    RPOHours                = "1"
    RTOHours                = "4"
  }
}
```

---

## 50.10 Full review question bank

Answer in writing for your workload. Prefer short factual answers.

### Operational Excellence

1. How is software delivered from commit to production?
2. How are schema migrations rolled back?
3. What is the on-call escalation path?
4. Which runbooks were used in the last incident?
5. How do you add a new alarm without a console click?
6. How is playbook drift prevented?
7. What is the change freeze policy?
8. How are feature flags operated?
9. Where do you track toil?
10. What is the environment promotion path (dev/stage/prod)?

### Security

11. Who can assume the production deploy role?
12. How are secrets rotated?
13. What is the data classification and residency story?
14. How is S3 public access prevented org-wide?
15. What GuardDuty findings fired this quarter, and what did you do?
16. How is tenant isolation implemented (if multi-tenant)?
17. How do you revoke a compromised role session?
18. Is CloudTrail immutable (log archive account, SCP deny delete)?
19. How are container images scanned and signed?
20. What is the WAF rule review cadence?

### Reliability

21. What is RTO and RPO numerically?
22. When was the last restore test?
23. How many AZs does each tier use?
24. What happens at service quota limits?
25. How does the app handle partial AZ failure?
26. Are queues bounded? What is the overflow behavior?
27. How do you drain a node or instance?
28. Is there a poison-message path?
29. What is the dependency timeout budget?
30. How is DNS failover tested?

### Performance

31. What is the SLO for latency and error rate?
32. What was the last load-test peak versus production peak?
33. Where is the bottleneck at 5× traffic?
34. Why this database engine?
35. What is cached, and what is the stampede plan?
36. Are we on current generation hardware?
37. How are N+1 queries prevented?
38. What is the pagination strategy?
39. How is payload size controlled?
40. When do we use async vs sync APIs?

### Cost

41. What is monthly fully loaded cost of this workload?
42. What is cost per business transaction?
43. What percent is untagged?
44. What waste was removed last quarter?
45. What commitments cover this workload?
46. What is the non-prod spend ratio?
47. Which logs are we over-retaining?
48. What is the NAT and transfer bill?
49. Who approves architecture that adds a new always-on service?
50. How do budgets fire?

### Sustainability

51. What is average CPU of the fleet?
52. Can any tier scale to zero?
53. Are we using Graviton where feasible?
54. Is cold data on cold storage?
55. Do we run idle GPU or large analytics 24×7?

---

## 50.11 Sample answers style (for training)

**Bad:** “We are secure because we use AWS.”  
**Good:** “Humans use Identity Center permission set `ProdReadOnly` and `ProdDeploy` with MFA; app uses IRSA `orders-sa`; GuardDuty delegated admin is `111122223333`; last HIGH finding 2026-07-12, contained in 18 minutes (ticket SEC-441).”

That specificity is the standard for this workbook.

---

## 50.12 Lab: 90-minute mini review

1. Pick a workload.
2. Fill the scorecard with at least one evidence link per pillar.
3. Identify three high or medium risks.
4. Open three tickets with pillar IDs (e.g. `REL-2`).
5. Schedule the restore test or the IAM last-accessed shrink — the first ticket that is not “document more.”

---

## 50.13 Review questions (meta)

1. Why is “all green” on Security Hub not the same as a Well-Architected review?
2. Name a cost vs reliability trade-off you would accept for a sandbox.
3. Why must a review produce owners?
4. Which pillar owns GuardDuty enablement? Which owns *response time*?
5. How does RPO differ from backup frequency?
6. Why is a single-AZ NAT a reliability *and* cost discussion?
7. What evidence proves least privilege better than a screenshot of a policy?
8. Why include sustainability if cost already covers utilization?
9. How does Chapter 44 instance refresh support Operational Excellence and Reliability together?
10. When should you re-run this checklist besides “quarterly”?

**Answers (brief):** (1) Hub is mostly config hygiene; WA includes ops, DR tests, and trade-offs. (2) Single NAT, no Multi-AZ RDS. (3) Otherwise nothing changes. (4) Security enablement; Operational Excellence (and Security) for IR SLAs. (5) RPO is max tolerable data loss; backups must meet it including lag. (6) Cheaper hourly, worse AZ failure and maybe transfer. (7) Last-accessed, Access Analyzer, simulate-principal-policy. (8) Carbon and hardware efficiency; also a forcing function for idle resources. (9) Safe change and replacement of bad nodes. (10) After incidents, new data class, new region, architecture changes.

---

## 50.14 What to do next

Chapter 51 is a CLI encyclopedia: the commands behind the evidence column. Use it during reviews so “we think Multi-AZ is on” becomes `describe-db-instances` output pasted into the ticket.
