# Chapter 61: AWS Interview Questions (80 Q&A)

*AWS Handbook — Pages 379–385 of this PDF edition*

This chapter is **80 interview questions** with answers you can speak in 60–120 seconds, then deepen if the interviewer asks. They mix SAA, DOP, networking, security, and architecture. There are no trick "gotcha only" items without an explanation.

**How to practice:** cover the answer, speak aloud, then read. Interviews reward structure: **requirement → options → pick → trade-off → failure mode.**

---

## Identity, accounts, and IAM (1–12)

**1. What is the shared responsibility model?**  
AWS secures the cloud (hardware, Regions, hypervisor, managed service plumbing). You secure in the cloud (IAM, data, OS on EC2, SG, encryption choices). SaaS-like services (S3, Lambda) shift more OS work to AWS; EC2 shifts less. Always state the service type.

**2. IAM user vs role vs group?**  
User: long-lived identity (avoid for humans). Role: assumable, temporary creds, the default for EC2/Lambda/IdP. Group: permission bundle for users. Prefer Identity Center federation over IAM users.

**3. What does an IAM policy evaluation actually do?**  
Implicit deny by default. All applicable identity, resource, boundary, session, SCP, RCP layers: **any explicit deny wins**; else need an **allow**. Conditions must match. Resource policies and identity policies both matter for S3/KMS.

**4. Permission boundary vs SCP?**  
Boundary: max permissions for a principal **in an account** (delegation). SCP: org-level guard on **member accounts**, does not grant. Management account is not constrained by SCPs.

**5. How do you give GitHub Actions AWS access without access keys?**  
OIDC IdP in IAM; role trust on `token.actions.githubusercontent.com` with `sub` limited to repo/branch; workflow `AssumeRoleWithWebIdentity`.

**6. Instance metadata SSRF — what do you do?**  
Require IMDSv2 (`HttpTokens=required`), hop limit 1, block instance IMDS from pods if using IRSA (IMDSv2 + iptables/AWS recommendations), never put creds in user data.

**7. Cross-account S3 access?**  
Bucket policy allow the role ARN in account B + IAM allow on that role; or assume a role in the bucket account. KMS CMK policy must allow the same principal if SSE-KMS.

**8. What is IRSA?**  
IAM Roles for Service Accounts: EKS OIDC provider, annotate ServiceAccount with role ARN, pods get projected JWT, `AssumeRoleWithWebIdentity`. Apps must not fall back silently to the node role.

**9. Break-glass root?**  
Hardware MFA, sealed credentials, logged, SCP cannot save you in the management account, use Organizations management only for org tasks, monitor root usage with CloudTrail metric filters.

**10. Cognito user pool vs identity pool?**  
User pool: authentication (users, tokens). Identity pool: federation to **AWS credentials** for access to AWS APIs. They combine for mobile apps that put objects in S3.

**11. STS GetSessionToken vs AssumeRole?**  
GetSessionToken: MFA-protect a user. AssumeRole: change identity/account, optional MFA, ExternalId for partners.

**12. How do you prevent IAM access keys in prod?**  
SCP Deny `CreateAccessKey`, Identity Center, detector (Access Analyzer / Config), culture of roles.

---

## Networking (13–24)

**13. Security group vs NACL?**  
SG: stateful, ENI, allow-only. NACL: stateless, subnet, allow/deny, ephemeral ports. Default NACL allow vs custom deny-all until rules added.

**14. Why isn't VPC peering transitive?**  
By design. Use TGW (or Cloud WAN) for transitive hub-and-spoke.

**15. When PrivateLink over peering?**  
Expose a **service** without sharing CIDRs/routes; overlapping CIDRs; SaaS to many customers; reduce blast radius.

**16. NAT Gateway vs NAT instance vs Egress-Only IGW?**  
NAT GW: managed IPv4 egress. NAT instance: DIY, cheaper/smaller, more ops. Egress-Only: IPv6 private egress.

**17. Gateway vs interface VPC endpoint?**  
Gateway: S3/DynamoDB, route prefix list, no extra ENI hourly. Interface: PrivateLink ENIs, most AWS APIs, hourly + data.

**18. ALB vs NLB vs GWLB?**  
ALB L7 HTTP. NLB L4 TCP/UDP, static IP, PrivateLink. GWLB GENEVE to appliances.

**19. What is TGW appliance mode?**  
Pins a flow to the same AZ attachment so stateful firewalls see both directions.

**20. Direct Connect VIF types?**  
Private (VGW), Transit (DX GW + TGW), Public (AWS public prefixes).

**21. Hybrid DNS?**  
Route 53 Resolver inbound/outbound + forwarding rules, share with RAM.

**22. Route 53 alias vs CNAME?**  
Alias: apex, AWS targets, health with some aliases. CNAME: not at apex, extra lookup.

**23. Geolocation routing pitfall?**  
Must have a **default** record or some clients get no answer.

**24. How do you debug "it times out in the VPC"?**  
DNS vs TCP vs TLS; SG both sides; NACL ephemerals; routes; flow logs REJECT; Reachability Analyzer; endpoints for AWS APIs from private Lambdas.

---

## Compute (25–34)

**25. ASG + ALB pattern?**  
ASG spans AZs, registers with target group, health checks replace instances, ELB health vs EC2 health.

**26. Spot vs On-Demand vs Reserved/Savings Plans?**  
Spot: interruptible discount. On-Demand: flexible. SP/RI: commit for steady state. Mix: checkout On-Demand, batch Spot.

**27. Lambda in VPC implications?**  
Hyperplane ENIs, no internet without NAT/egress, need endpoints for AWS APIs, extra cold start historically (improved).

**28. Reserved vs provisioned Lambda concurrency?**  
Reserved: cap+guarantee from pool. Provisioned: warm environments, cost even idle.

**29. ECS on EC2 vs Fargate vs EKS?**  
EC2: control instances. Fargate: no servers. EKS: Kubernetes API, portability, more moving parts. Choose based on skill and features (Karpenter, CRDs).

**30. Why images by digest?**  
`latest` moves; prod must run the artifact that passed staging.

**31. What does EKS control plane HA mean?**  
AWS runs etcd/API in the Region (multi-AZ). You still need multi-AZ **nodes** and apps.

**32. Cluster autoscaler vs Karpenter?**  
CA: scales ASGs. Karpenter: provisions right-sized nodes faster, fewer ASG pre-defs. Both need disruption safety for checkouts.

**33. User data vs golden AMI vs SSM?**  
User data: late, slow, drift. AMI: immutable. SSM: patch/operate running systems. Prefer AMI for boots, SSM for emergencies.

**34. Placement groups?**  
Cluster: low latency one AZ. Spread: distinct hardware. Partition: Hadoop-style. Not a substitute for Multi-AZ HA.

---

## Storage and data (35–48)

**35. S3 consistency?**  
Strong read-after-write for PUTs of new and overwrites (current S3). Still design for retries/idempotency.

**36. S3 encryption options?**  
SSE-S3, SSE-KMS (audit/CMK), SSE-C, client-side. Bucket keys to reduce KMS cost.

**37. Versioning + MFA delete + Object Lock?**  
Versioning: recover overwrite. MFA delete: extra protect versioning state. Object Lock WORM for compliance/ransomware.

**38. EBS vs EFS vs FSx vs S3?**  
Block vs NFS vs managed Windows/Lustre vs object. Don't mount S3 as POSIX for databases.

**39. RDS Multi-AZ vs read replica vs Aurora Global?**  
Multi-AZ: HA same Region. Replica: scale reads / DR promote. Aurora Global: low RTO cross-Region.

**40. When DynamoDB over RDS?**  
Known access patterns, extreme scale, serverless, global tables. RDS when ad-hoc SQL, relations, transactions across many rows.

**41. Hot partition?**  
One PK gets most traffic. Shard keys, cache, or redesign.

**42. DAX vs ElastiCache?**  
DAX: DynamoDB-specific microsecond cache. ElastiCache: general Redis/Memcached for any app.

**43. RDS Proxy why?**  
Connection pooling for Lambda/thousands of clients; failover handling.

**44. DMS use case?**  
Minimal-downtime migration, CDC to lake. Not a forever dual-write bus unless designed.

**45. Athena vs Redshift vs OpenSearch?**  
Athena: ad-hoc S3 SQL. Redshift: warehouse, concurrent BI. OpenSearch: full text, logs, search.

**46. S3 Glacier vs RTO 15 minutes?**  
Restore can exceed 15 minutes (especially Deep Archive). Wrong tier for that RTO.

**47. Backup vs HA?**  
Multi-AZ is HA. Snapshots/PITR/global copies are backup/DR. You need both.

**48. DynamoDB transactions limits?**  
Item count/size limits; extra WCUs; not cross-table in the SQL sense beyond TransactWrite items; not multi-Region.

---

## Integration, serverless, IaC (49–60)

**49. SQS vs SNS vs EventBridge vs Kinesis?**  
Queue buffer; pub/sub fan-out; event bus/rules/archive; streaming shards/order/replay.

**50. SQS at-least-once?**  
Duplicates happen. Idempotent consumers. FIFO + dedup if needed (throughput limits).

**51. API Gateway Lambda 502?**  
Bad proxy response shape, crash, timeout, VPC link.

**52. Why not Lambda calling Lambda sync?**  
Coupling, timeout stacks, retries explode. Use SQS/EventBridge/Step Functions.

**53. Step Functions Standard vs Express?**  
Standard: long, exactly-once-ish, visual, expensive per transition. Express: high volume, short, at-least-once.

**54. CloudFormation nested vs StackSets?**  
Nested: compose one account. StackSets: many accounts/Regions.

**55. Change sets why?**  
Preview replacements before you drop a database.

**56. Drift detection?**  
Finds console edits. Not a backup. Remediate or import.

**57. CDK Aspects?**  
Visit constructs to apply tags/nag/encryption org-wide.

**58. SAM?**  
CloudFormation transform for serverless: APIs, functions, events, local.

**59. Blue/green vs canary vs rolling?**  
BG: two environments, flip. Canary: % traffic. Rolling: replace batches. Pair with automatic rollback alarms.

**60. Immutable infrastructure?**  
Replace AMIs/containers rather than patch in place. Faster rollback, less drift. Still patch the pipeline's builders.

---

## Observability, security services, DR, cost (61–72)

**61. Golden signals?**  
Latency, traffic, errors, saturation. Map to ALB 5xx, p99, CPU, queue depth, connections.

**62. X-Ray vs logs vs metrics?**  
Traces for path; logs for detail; metrics for alarms. You need all three.

**63. GuardDuty vs Security Hub vs Inspector vs Macie vs WAF vs Shield?**  
Threat intel findings; aggregator; vuln scanning; sensitive data S3; L7 rules; DDoS.

**64. CloudTrail vs Config vs CloudWatch?**  
API history; resource configuration/compliance; operational metrics/logs.

**65. KMS key policy vs IAM?**  
Both required typically: key policy must trust the account/principal; IAM must allow kms actions. Cross-account always key policy.

**66. RPO vs RTO?**  
Data loss vs downtime. Measure with drills, not slides.

**67. Four DR patterns?**  
Backup/restore, pilot light, warm standby, active/active. Cost vs RTO.

**68. Why cross-account backups?**  
Ransomware/compromise in the workload account shouldn't delete the only copies. Vault lock.

**69. NAT Gateway bill shock?**  
Interface endpoints for S3, avoid hairpin, flow logs, many NATs vs centralized egress trade-off.

**70. Cost allocation?**  
Tags, Cost Categories, accounts/OUs, CUR in Athena. Tag at catalog launch.

**71. How do you page humans?**  
Alarm → SNS → PagerDuty; composite to reduce noise; runbook link; not a dashboard someone might glance at.

**72. 429 vs 5xx vs 403?**  
Throttle/quota; server/target failure; authz/WAF/IAM. Different runbooks (Chapter 59).

---

## Architecture and behavioral (73–80)

**73. Design a URL shortener on AWS.**  
API Gateway + Lambda + DynamoDB (PK=code), CloudFront, 301 cache carefully, unique ID (nanoid + retry), analytics async SQS, custom domain ACM.

**74. Design multi-tenant SaaS isolation.**  
Pool (shared tables with tenant key + IAM conditions) vs silo (account per tenant). Enterprise: silo or strong pool with noisy-neighbor limits. Landing zone vending for silo.

**75. How would you migrate a monolith?**  
Strangle: ALB path routing to new services, DMS for data, dual-write carefully or CDC, feature flags, don't big-bang DB and app together.

**76. Biggest AWS outage you handled / would handle?**  
Use Chapter 54: detect, don't split-brain, lag gate, comms, failback. If no story, walk AZ loss vs Region loss vs bad deploy.

**77. How do you know a design is Well-Architected?**  
Six pillars, questions, workload review, risks recorded, not a logo on a slide. Capstone Chapter 60 as an example.

**78. Terraform vs CloudFormation vs CDK?**  
TF: multi-cloud, ecosystem. CFN: AWS-native, StackSets, no extra state server. CDK: languages, constructs, still CFN. Pick one platform standard.

**79. Tell me about a time you reduced cost.**  
Structure: metric (NAT GB, idle ASG, unattached EBS), action (endpoints, schedules, gp3), result (%, $), guardrail so it didn't return.

**80. What would you improve in our architecture (whiteboard)?**  
Start with SLOs and data stores. Ask blast radius (accounts). Ask deploy/rollback. Ask packet path. Propose one high-value change, not twenty. Reference NWR capstone patterns: isolate PCI, queues in front of inventory, digest-pinned images, DR data-first.

---

## Lab — mock interview

1. Pick 10 numbers from a hat.
2. 45 minutes, spoken answers, no notes.
3. Record yourself; count filler.
4. For each answer, add one **failure mode** sentence.
5. Repeat weekly until Chapter 60 can be told in 8 minutes.

---

## Interview anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| Listing 15 services | Pick 3 and defend |
| "We would use Kubernetes" with no why | EKS vs Fargate vs Lambda |
| Ignoring cost | Always add a cheaper alternative |
| Ignoring IAM | Who is the principal? |
| RPO 0 for everything | Show you can prioritize |
| "AWS is secure by default" | Shared responsibility |
| Blaming the interviewer for a vague Q | Ask one clarifying constraint |

---

## Mapping to handbook parts

| Q range | Parts |
|---------|-------|
| 1–12 | I–II, 53 |
| 13–24 | III, 57 |
| 25–34 | IV |
| 35–48 | V–VI |
| 49–60 | VII–VIII, 52, 58 |
| 61–72 | IX–X, 54, 59 |
| 73–80 | 41, 60 |

---

## One-page cheat sheet (memorize verbs)

- Isolate with **accounts**.
- Constrain with **SCP**.
- Assume **roles**.
- Route packets with **TGW/PrivateLink**, not hope.
- Store money in **Aurora**, sessions/carts in **DynamoDB** if access patterns fit.
- Decouple with **SQS**.
- Observe with **metrics + traces + logs**.
- Recover with **tested runbooks**.
- Deploy **digests** with **rollback**.
- Encrypt with **CMK** when you need control.

If you can expand each verb into a design, you are hireable as an AWS engineer. If you can only recite service names, keep building the labs in Chapters 52–60.

---

## STAR stories you should pre-write (not counted as extra questions)

Interviews often pivot from trivia to **behavioral**. Prepare four stories using Situation, Task, Action, Result. Map each to AWS artifacts so you do not freeze.

**Reliability:** A Multi-AZ RDS failover where the app kept stale DNS. You lowered JVM TTL, added RDS Proxy, and created a CloudWatch alarm on `DatabaseConnections` drop. Result: MTTR from 40 minutes to 8.

**Security:** An S3 bucket policy with `Principal: "*"` in nonprod. You enabled Block Public Access at account level, Access Analyzer, and an SCP. Result: zero public buckets in the OU; one legitimate static site moved to CloudFront OAC.

**Cost:** NAT Gateway $12k/month. Flow logs showed S3. You added gateway endpoints and moved ECR pulls to interface endpoints. Result: 60% NAT data reduction without a firewall project.

**Delivery:** Friday all-at-once ECS deploy. You moved to CodeDeploy canary with 5xx rollback. Result: failed canary auto-rolled twice in a month with no customer incident.

Do not invent metrics in a real interview. If you lack a story, do Chapters 52–60 labs and then you have one.

---

## Deepening prompts interviewers use after Q73–80

When you answer "design a URL shortener," expect follow-ups. Practice these out loud:

- How do you guarantee uniqueness without a central Oracle sequence? (conditional PutItem, contact-hash, or Snowflake IDs)
- What if a celebrity link is 1M RPS? (CloudFront cache 301s, but cache TTL vs update-on-delete; DDB on-demand; partition key is the code — entropy in codes)
- How do you GDPR-delete a mapping? (soft delete + TTL; invalidate CDN)
- How do you audit who created links? (CloudTrail is not enough; app table + who from JWT)

When you answer EKS vs Lambda: "What if the team has no Kubernetes?" Honest answer: Fargate or Lambda until the platform team exists. Hero clusters without operators fail interviews **and** production.

When you answer multi-account: "Won't that slow developers?" Account Factory + Identity Center + catalog (Chapters 52–53) is how you keep speed. Clicking 40 accounts by hand is how you lose speed.

---

## Closing

This handbook's reference part (52–61) does not replace running the console and breaking sandbox accounts. Interviews detect that gap in two questions. Schedule lab time on your calendar the same way you schedule drills in Chapter 54. Speak in requirements, options, trade-offs, and failure modes — that is the entire skill.
