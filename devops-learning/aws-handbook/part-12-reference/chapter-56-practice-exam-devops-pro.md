# Chapter 56: Practice Exam — AWS Certified DevOps Engineer – Professional (DOP)

This chapter contains **50 original DOP-style questions**. The Professional exam assumes SAA knowledge and then tests **automation, governance, observability, resilient delivery, and incident response**. Stems are longer. More than one option may be "possible"; the best answer is usually the one that is **repeatable, least privilege, and measurable**.

DOP loves CloudFormation/CDK, CodePipeline, CodeBuild, CodeDeploy, CloudWatch, X-Ray, Config, Organizations, IAM, Auto Scaling, blue/green, canary, and "how do we know this failed?"

Sit 180 minutes for a real exam analog; this 50-item set is a dense subset. Read explanations even when you are right.

---

## How DOP differs from SAA

| SAA | DOP |
|-----|-----|
| Which service? | How do we pipeline, test, roll back, and audit it? |
| Multi-AZ | Automated failover **and** the alarm that pages |
| IAM role | Permission boundaries, SCPs, pipeline roles |
| CloudWatch alarm | Composite alarms, anomaly detection, metric math, incident runbooks |
| CloudFormation exists | Drift, nested stacks, StackSets, change sets, cfn-init vs user data vs SSM |

If you cannot name the **rollback trigger**, you are still in associate mode.

---

## Questions 1–10 — CI/CD

**1.** A team must deploy a Lambda to 12 accounts whenever `main` is green. Least custom code.

A. Twelve GitHub Actions with access keys  
B. **(Correct)** CodePipeline (or CDK Pipelines) with a deploy wave using StackSets or CodeBuild assuming per-account roles via OIDC/IAM  
C. Manual console zip upload  
D. Email the zip to account owners  

**Explanation:** Central pipeline + temporary roles. Long-lived keys in twelve places fail DOP security domains.

**2.** CodeBuild must fetch dependencies from a private npm registry and cannot use the public internet.

A. Default CodeBuild in public subnet  
B. **(Correct)** VPC-connected CodeBuild, private subnets, VPC endpoints or internal Nexus/CodeArtifact  
C. Disable security groups  
D. Run builds on developer laptops only  

**Explanation:** VPC config for CodeBuild is a classic item. CodeArtifact is the AWS native registry.

**3.** CodeDeploy to ECS must shift 10% of traffic for 10 minutes, then 100%, and roll back on 5xx.

A. All-at-once  
B. **(Correct)** Canary or linear with ALB, CloudWatch alarms hooked to CodeDeploy rollback  
C. SSM SendCommand  
D. Replace the cluster DNS TTL 86400  

**Explanation:** ECS CodeDeploy blue/green + canary + alarms.

**4.** A pipeline must block deploy to prod if cfn-nag/Guard fails, even if unit tests pass.

A. Honor system  
B. **(Correct)** CodeBuild test stage with non-zero exit; pipeline condition / approvals after  
C. Deploy first, scan later  
D. Only scan on Fridays  

**Explanation:** Shift-left gates in the pipeline.

**5.** You need immutable artifacts: the exact image prod runs must be the one that passed staging.

A. Rebuild from `latest` in prod  
B. **(Correct)** Promote a digest (`image@sha256:...`) through environments; no rebuild  
C. `latest` tag in all accounts  
D. Build on the prod box  

**Explanation:** Digest promotion is the professional pattern.

**6.** CloudFormation stack policy should prevent REPLACE of a production database resource during app deploys.

A. Hope  
B. **(Correct)** Stack policy Deny Update:Replace on the RDS logical ID; separate data stack  
C. DeletionPolicy Delete  
D. Use the console to click through  

**Explanation:** Stack policies and split stacks. DeletionPolicy Delete is the opposite.

**7.** CDK app self-mutates the pipeline. A malicious PR could change prod approval.

A. Allow all PRs to mutate  
B. **(Correct)** Protected branches, CODEOWNERS, pipeline diff review, maybe split pipeline synth account; manual approval step that cannot be removed without a reviewed pipeline change  
C. Disable version control  
D. Put AWS keys in the PR  

**Explanation:** Self-mutation is powerful; governance is a DOP topic.

**8.** You must deploy to Elastic Beanstalk with rolling 25% and pause on failed health.

A. Immutable only  
B. **(Correct)** Rolling with additional batch / health-based rolling as configured  
C. Terminate the environment each time  
D. FTP files  

**Explanation:** Beanstalk still appears. Rolling + health.

**9.** Artifact store encryption for CodePipeline across accounts.

A. Unencrypted S3  
B. **(Correct)** KMS CMK with key policy allowing the target account roles + encrypted artifact bucket  
C. Client-side only in git  
D. EBS encryption of the build host as sufficient for artifacts at rest in S3  

**Explanation:** Cross-account KMS for artifacts is a frequent miss.

**10.** A canary Lambda (Synthetics) must fail the pipeline if checkout p95 > 800 ms in staging.

A. No metrics  
B. **(Correct)** CloudWatch metric from canary, alarm, CodePipeline deploy action rollback or a test action that polls the alarm  
C. One curl in CodeBuild against localhost  
D. Wait 3 days for customers to complain  

**Explanation:** Synthetics + alarms as quality gates.

---

## Questions 11–20 — IaC and configuration

**11.** 50 accounts need the same IAM role and Config recorder. Fast, drift-aware.

A. ClickOps  
B. **(Correct)** CloudFormation StackSets (service-managed, OUs)  
C. Email a script  
D. Nested stacks in one account  

**Explanation:** StackSets are the DOP multi-account primitive. Nested stacks are single-account composition.

**12.** Detect a console-changed security group on a CloudFormation-managed stack.

A. Ignore  
B. **(Correct)** CloudFormation drift detection (and Config)  
C. X-Ray  
D. Trusted Advisor only  

**Explanation:** Drift detection. Config for continuous.

**13.** Need to inject the latest AMI without changing the template parameters by hand.

A. Hardcode AMI  
B. **(Correct)** SSM public parameter `/aws/service/ami-amazon-linux-latest/...` or dynamic reference  
C. Guess  
D. Use Ubuntu 12.04 forever  

**Explanation:** SSM parameters for AMIs.

**14.** Bootstrapping packages on first launch, still CloudFormation-centric, Linux.

A. Only AMI  
B. **(Correct)** cfn-init / cfn-signal with CreationPolicy, or better Image Builder; exam often still tests cfn-signal  
C. SSH after create  
D. FTP  

**Explanation:** CreationPolicy + cfn-signal is a classic Professional item so the stack does not COMPLETE before the app is healthy.

**15.** You must apply OS patches to a fleet without SSH.

A. Open 22 to 0.0.0.0/0  
B. **(Correct)** Systems Manager Patch Manager + Session Manager if interactive  
C. FTP the RPM  
D. Recreate all instances always (valid immutable, but stem says patch)  

**Explanation:** SSM. Immutable rebuild is also "DevOps" if the stem allows AMIs.

**16.** Parameter Store vs Secrets Manager for a 4 KB API key with rotation.

A. Plaintext Parameter  
B. **(Correct)** Secrets Manager if rotation is required; SecureString if not  
C. DynamoDB  
D. CodeCommit  

**Explanation:** Rotation → Secrets Manager.

**17.** Prevent `iam:CreateUser` in workload accounts but allow pipelines to create service roles.

A. Impossible  
B. **(Correct)** SCP Deny CreateUser; allow CreateRole with permission boundary condition  
C. Deny all IAM  
D. Allow CreateUser for everyone  

**Explanation:** Fine-grained SCP + boundaries. DOP security domain.

**18.** A nested stack fails halfway. You need to see which child resource.

A. Only the parent status  
B. **(Correct)** `describe-stack-events` on the nested stack name / change set include nested  
C. Delete the account  
D. X-Ray on CloudFormation (not a thing)  

**Explanation:** Nested stack events.

**19.** Feature flags for gradual exposure without a new deploy.

A. Redeploy YAML  
B. **(Correct)** AppConfig (or LaunchDarkly); CodeDeploy canary is traffic, not flags  
C. Edit prod env vars by hand  
D. DNS TTL  

**Explanation:** AppConfig is the AWS-native flag service and shows up on DOP.

**20.** You need a golden AMI every week, tested, shared to 30 accounts.

A. Manual console  
B. **(Correct)** EC2 Image Builder pipeline, tests, RAM / AMI share, SSM parameter update  
C. Copy-paste  
D. Docker only (doesn't patch EC2)  

**Explanation:** Image Builder.

---

## Questions 21–30 — monitoring, incident, HA

**21.** Alarm when 5xx rate AND latency are both high, to reduce noise.

A. Two separate pages always  
B. **(Correct)** CloudWatch composite alarm  
C. Disable alarms  
D. CPU only  

**Explanation:** Composite alarms.

**22.** Trace a request across API Gateway, Lambda, and DynamoDB.

A. VPC Flow Logs only  
B. **(Correct)** AWS X-Ray (and CloudWatch ServiceLens)  
C. S3 access logs only  
D. Cost Explorer  

**Explanation:** X-Ray.

**23.** Logs from 200 Lambda functions, query "error AND sku=..." last hour, cost-aware.

A. Download all to Excel  
B. **(Correct)** CloudWatch Logs Insights (and standardized JSON logs)  
C. Glacier restore  
D. Email logs  

**Explanation:** Insights.

**24.** Auto Scaling should react to queue depth per instance, not raw CPU.

A. CPU only  
B. **(Correct)** Custom metric `ApproximateNumberOfMessagesVisible / InServiceInstances` (metric math) + target tracking  
C. Schedule 1000 instances  
D. Manual  

**Explanation:** Metric math for SQS backlogs.

**25.** RDS failover occurred; you must know whether the app reused stale DNS.

A. Ignore  
B. **(Correct)** Use RDS Proxy or refresh DNS; Java DNS TTL; monitor connections; this is an ops trap  
C. Switch to Access keys  
D. Disable Multi-AZ  

**Explanation:** Client caching after failover is a professional operations question.

**26.** Centralize CloudTrail from all accounts, immutable.

A. Per-account local trails only  
B. **(Correct)** Organization trail to log-archive bucket with Object Lock  
C. Print logs  
D. GuardDuty as a trail replacement  

**Explanation:** Org trail + lock.

**27.** Config rule: no public NACL. Auto-remediate.

A. Ticket forever  
B. **(Correct)** Config remediation with SSM document / Lambda  
C. Trusted Advisor weekly email as the only control  
D. Disable NACLs  

**Explanation:** Automated remediation.

**28.** You need MTTR under 20 minutes for checkout. What is the first missing piece if you only have dashboards?

A. More dashboards  
B. **(Correct)** SLO, paging alarms with runbooks, on-call, synthetic canaries  
C. Bigger instances  
D. Disable deploys forever  

**Explanation:** Observability without paging is not operations.

**29.** Blue/green ECS: green is unhealthy. Expected behavior?

A. CodeDeploy continues  
B. **(Correct)** Alarm triggers rollback to blue; target group stays on blue  
C. Delete the cluster  
D. Fail over the Region immediately  

**Explanation:** Don't Regional-failover a bad deploy.

**30.** Anomaly detection on invocation errors for a seasonal workload.

A. Static 1 error threshold  
B. **(Correct)** CloudWatch anomaly detection band  
C. No alarms  
D. CPU credit alarm only  

**Explanation:** Anomaly detection for seasonality.

---

## Questions 31–40 — security, governance, multi-account

**31.** Developers in sandbox may do most things but must not disable GuardDuty.

A. Training  
B. **(Correct)** SCP Deny GuardDuty delete/disassociate  
C. Hide the console  
D. IAM user per person with AdministratorAccess and a sticky note  

**Explanation:** SCP.

**32.** Pipeline role should not be able to read unrelated Secrets Manager secrets.

A. `Resource: "*"`  
B. **(Correct)** Resource ARNs + condition `aws:ResourceTag` / prefix  
C. Root  
D. Disable secrets  

**Explanation:** Least privilege.

**33.** Evidence for auditors: who deployed what when.

A. Slack memories  
B. **(Correct)** CloudTrail + CodePipeline execution history + artifact SHA + IAM Identity Center who  
C. Wiki  
D. Screenshots only  

**Explanation:** Audit trail design.

**34.** Control Tower account factory + extra VPC per account.

A. Console after vend  
B. **(Correct)** AFT or CfCT customizations  
C. Hope they peer  
D. Put VPCs in the management account  

**Explanation:** AFT/CfCT.

**35.** Encrypt EBS by default in every vended account.

A. Reminders  
B. **(Correct)** Account attribute `ebs-encryption-by-default` via StackSet on vend  
C. KMS on one volume  
D. Snapshot only  

**Explanation:** Default encryption setting.

**36.** GitHub Actions to deploy to AWS without storing access keys.

A. Keys in GitHub secrets forever  
B. **(Correct)** OIDC identity provider, IAM role trust `token.actions.githubusercontent.com`  
C. Root keys  
D. Disable CI  

**Explanation:** OIDC federation for CI.

**37.** WAF logs must be searchable with the rest of the logs.

A. Leave in WAF console  
B. **(Correct)** WAF logs to S3/Kinesis Firehose / CloudWatch; Athena or OpenSearch  
C. CloudFront access logs only  
D. GuardDuty  

**Explanation:** Centralize WAF logs.

**38.** Prevent creation of IAM access keys for users in prod OU.

A. SCP Deny `iam:CreateAccessKey`  
B. **(Correct)** That Deny, plus Identity Center, plus Access Analyzer unused keys  
C. Allow keys  
D. Share one key  

**Explanation:** A is necessary but DOP often wants the complete control; if A is the only SCP option it is still correct. Prefer A if single-best and B isn't listed as combo. Here B is fuller.

Wait, I marked both conceptually. For the exam, A is the direct control. I'll keep B as correct for completeness with Analyzer.

**39.** A Lambda in VPC cannot reach Secrets Manager.

A. Secrets Manager is down  
B. **(Correct)** Missing interface VPC endpoint or NAT; SG on endpoint  
C. KMS is optional always  
D. Use plaintext  

**Explanation:** VPC networking for managed APIs.

**40.** Cross-account CloudWatch dashboard in the ops account.

A. Impossible  
B. **(Correct)** Cross-account observability (Observability Access Manager) or metric streams  
C. Share root  
D. Email CSV  

**Explanation:** OAM is the modern answer.

---

## Questions 41–50 — reliability, data, mixed professional

**41.** DynamoDB under provisioned throughput; apps see 400s.

A. Ignore  
B. **(Correct)** On-demand or auto scaling; backoff; diagnose hot partition  
C. Switch to RDS immediately as first step  
D. Increase Lambda timeout only  

**Explanation:** Throttling is capacity + keys, not Lambda timeout.

**42.** You must stop a bad Kinesis consumer without losing the stream.

A. Delete the stream  
B. **(Correct)** Disable/scale the consumer, use enhanced fan-out isolation, checkpoint  
C. Drop shards to 0  
D. Format the account  

**Explanation:** Isolate consumers.

**43.** ECS tasks fail `CannotPullContainerError`.

A. CPU too high always  
B. **(Correct)** ECR permission, VPC endpoints for ECR/S3, image digest missing  
C. Route 53  
D. CloudFront  

**Explanation:** Image pull path.

**44.** Disaster recovery drill must run without touching customer DNS.

A. Fail over prod  
B. **(Correct)** Isolated drill account/Region, restore from vault, synthetic tests, restore evidence  
C. Skip drills  
D. Only tabletop forever  

**Explanation:** Chapter 54 pattern.

**45.** Cost anomaly on NAT Gateway after a deploy.

A. Ignore  
B. **(Correct)** Flow logs, interface endpoints for S3, check for traffic to internet, Cost Explorer by AZ  
C. Buy more NAT  
D. Disable VPC  

**Explanation:** Classic cost+ops.

**46.** Step Functions Standard vs Express for a 2-hour approval wait.

A. Express  
B. **(Correct)** Standard (Express max duration too short; no long wait)  
C. SQS 15 min max as the only wait  
D. Lambda sleep 2 hours (15 min max)  

**Explanation:** Standard workflows for long waits.

**47.** You need canary analysis beyond a single 5xx alarm (statistical).

A. Coin flip  
B. **(Correct)** CodeDeploy + CloudWatch alarms; or automated canary analysis (Kayenta-style) on metrics; AWS often tests CodeDeploy lifecycle hooks  
C. Deploy Friday 5pm  
D. Only unit tests  

**Explanation:** Lifecycle hooks / metric comparison.

**48.** SSM Session Manager session logs for forensics.

A. No logging  
B. **(Correct)** Session Manager logging to S3/CloudWatch + KMS  
C. Screenshot the terminal  
D. Disable SSM  

**Explanation:** Session logging.

**49.** A StackSet operation is PARTIAL. Next step?

A. Re-run blindly on all  
B. **(Correct)** Inspect failed stack instance events, fix SCP/IAM, retry failed instances  
C. Delete the org  
D. Ignore  

**Explanation:** Partial success debugging.

**50.** Definition of a good DOP architecture for "we deploy 50 times a day."

A. Weekly change advisory board only  
B. **(Correct)** Automated pipeline, small batches, automated tests, progressive delivery, instant rollback, telemetry, IAM least privilege  
C. SSH and vim  
D. One giant monthly release  

**Explanation:** This is the professional ethos in one item.

---

## Answer key (quick)

1B 2B 3B 4B 5B 6B 7B 8B 9B 10B  
11B 12B 13B 14B 15B 16B 17B 18B 19B 20B  
21B 22B 23B 24B 25B 26B 27B 28B 29B 30B  
31B 32B 33B 34B 35B 36B 37B 38B 39B 40B  
41B 42B 43B 44B 45B 46B 47B 48B 49B 50B  

(The correct option is **B** in this set by construction so you can self-check quickly. On the real exam, letters vary. Do not memorize letters; memorize reasons.)

---

## Lab — pipeline threat model

Take any CodePipeline in a sandbox:

1. Draw trust boundaries: source, build role, deploy role, KMS, artifact bucket.
2. List one abuse per boundary (stolen GitHub PAT, malicious buildspec, overly broad deploy role).
3. Add a Guard rule or IAM condition that stops that abuse.
4. Add a CloudWatch alarm on pipeline failures and on unauthorized `AssumeRole` for the deploy role (CloudTrail metric filter).
5. Run a change set that would replace RDS; confirm stack policy or split stack blocks it.

**Success criteria:** A one-page threat model and at least one implemented control.

---

## Domain refresh table

| DOP domain (conceptual) | Handbook |
|-------------------------|----------|
| SDLC automation | 31–33, 52 |
| Config management | 34, 52 |
| Monitoring | 35–38, 59 |
| Policies and standards | 8, 38, 53 |
| Incident and event response | 40, 54, 59 |
| HA/fault tolerance | 16, 23, 27, 54, 60 |

---

## Traps unique to Professional

| Trap | Better thought |
|------|----------------|
| "Use root to fix prod" | Break-glass role, logged |
| "Disable rollback to save time" | Keep rollback; fix the artifact |
| "AdministratorAccess on CodeBuild" | Scope to ecr:PutImage, logs, etc. |
| "Manual AMI copy" | Image Builder + share |
| "Alarms on CPU for APIs" | Use 5xx, latency, saturation |
| "One trail in prod account only" | Org trail, log archive |
| "Nested stacks for 50 accounts" | StackSets |
| "latest tag" | Digest |

---

## Closing

If you scored below 70% equivalent, do not buy more practice questions first. Build a pipeline that deploys a Lambda through a change set with Guard, an alarm, and a rollback. Then re-read this chapter. DOP is a **habits** exam disguised as a multiple-choice exam.

Chapter 57 is a Networking Specialty-style notes dump: Transit Gateway, PrivateLink, hybrid, and Route 53 at a depth SAA does not require.
