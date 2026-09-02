# Chapter 55: Practice Exam — AWS Solutions Architect Associate (SAA)

*AWS Handbook — Pages 325–335 of this PDF edition*

This chapter contains **50 original practice questions** in the style of the AWS Certified Solutions Architect – Associate exam. They are not dumps of live exam items. Use them to test design judgment: pick the **cheapest sufficiently correct** option unless the stem demands otherwise.

How to use: sit a 90-minute timed pass without notes, then read every explanation — including items you got right. SAA punishes "the service I like" when the stem specified on-premises NFS, millisecond session state, or a 1-hour RTO.

Legend: **(Correct)** marks the best answer. Distractors include a short why-not.

---

## Exam strategy (read before Q1)

| Stem keyword | Often points to |
|--------------|-----------------|
| Lowest cost, infrequently accessed | S3 IA / Glacier / Aurora Serverless pause |
| Millisecond, millions of users | DynamoDB, ElastiCache, CloudFront |
| NFS, concurrent POSIX | EFS (or FSx) |
| SMB / Windows | FSx for Windows |
| Hybrid, consistent network | Direct Connect, then Site-to-Site VPN backup |
| Decrypt in app, manage keys | KMS CMK + grants |
| Block public, accidental | S3 Block Public Access, SCP |
| Multi-AZ automatic failover | RDS Multi-AZ, ALB, Aurora |
| Global users, static | CloudFront |
| Fan-out notifications | SNS |
| Decouple, at-least-once | SQS |
| Ordered, exactly one consumer group | SQS FIFO |
| On-premises VMware | AWS Backup / Storage Gateway / Migration Hub as stem dictates |

Eliminate answers that violate an explicit constraint (must stay in VPC, must be real-time, cannot change the application). Then eliminate operational heroes ("manually copy snapshots") when a managed feature exists.

---

## Questions 1–10 — compute and scaling

**1.** A web fleet on EC2 behind an ALB must scale with CPU and keep at least two instances in different AZs. Which combination meets this with the least operational work?

A. Launch two instances by cron in two AZs  
B. **(Correct)** Application Auto Scaling / EC2 Auto Scaling group spanning two AZs, min=2, target tracking on CPU, ALB target group  
C. Lambda instead of EC2  
D. Placement group cluster in one AZ  

**Explanation:** ASG + ALB is the textbook SAA pattern. Cron is not HA. Lambda changes the compute model (not asked). Cluster placement groups are for low latency in one AZ — opposite of HA.

**2.** An application needs to run a 4-hour video encode. It can retry. Cost must be minimized. Instances may be interrupted.

A. Dedicated Hosts  
B. On-Demand p-family  
C. **(Correct)** Spot Instances (or Spot Fleet / ASG with Spot) with checkpointing to S3  
D. Lightsail  

**Explanation:** Interruptible + cost → Spot. Dedicated Hosts are for licenses. Lightsail is not the encode farm pattern.

**3.** You need to run containers without managing servers. Burst to 500 tasks, pay per vCPU-second.

A. ECS on EC2  
B. **(Correct)** ECS on Fargate (or EKS Fargate)  
C. Elastic Beanstalk with t3.micro  
D. Batch with default CE on On-Demand only if Fargate is not listed — here Fargate is listed  

**Explanation:** Serverless containers = Fargate. Beanstalk still has instances. ECS on EC2 manages servers.

**4.** A Lambda function times out at 15 minutes processing 2 GB files from S3. What is the most architecturally sound fix?

A. Increase timeout to 30 minutes  
B. **(Correct)** Offload to ECS/Batch/Step Functions + smaller chunks; Lambda max is 15 minutes  
C. Use SQS visibility 12 hours only  
D. Enable Lambda provisioned concurrency  

**Explanation:** You cannot exceed 15 minutes. Provisioned concurrency does not extend duration. Chunk + Step Functions or a container job is the SAA answer.

**5.** Users upload objects up to 5 GB through a browser. You want to avoid proxying bytes through EC2.

A. Multipart through a NAT instance  
B. **(Correct)** S3 presigned URLs (or POST policy) from a lightweight auth API  
C. FTP on EC2  
D. Snowball Edge for each user  

**Explanation:** Presigned URLs are the classic pattern. Snowball is physical migration.

**6.** You must boot instances from a golden image with a specific agent version. Updates weekly.

A. Copy-paste AMI IDs in a wiki  
B. **(Correct)** EC2 Image Builder (or Packer) pipeline producing AMIs; launch templates reference latest via SSM parameter  
C. User data `yum update` at every boot as the only control  
D. Store AMIs on EFS  

**Explanation:** Image Builder + launch templates. User data updates are slow and drift. AMIs are not stored on EFS.

**7.** An ASG scales on SQS ApproximateNumberOfMessagesVisible. Sometimes it does not scale in. Why might that be, and what should you check first?

A. SQS is eventually consistent so ASG never works  
B. **(Correct)** Scale-in protection, stuck messages (visibility), or metric period/cooldown; ASG + SQS is valid  
C. You must use Kinesis  
D. ALB health checks replace SQS metrics  

**Explanation:** The pattern is valid. Operationally, poison messages keep the queue depth high. SAA may ask the pattern; interviews ask the stuck-message case.

**8.** You need GPU inference for 2 hours a day. Lowest cost.

A. Always-on p3  
B. **(Correct)** Start/stop or ASG scheduled + Spot if interruption OK; or SageMaker serverless/async if in scope — for EC2, scheduled ASG / Spot  
C. Fargate (no GPU in the usual SAA options)  
D. CloudFront  

**Explanation:** Don't leave GPUs on. Fargate GPU is not the associate default. Scheduled scaling or Spot batch.

**9.** A stateful WebSocket service needs sticky sessions at L7.

A. NLB with UDP  
B. **(Correct)** ALB with sticky sessions (or better: store state in DynamoDB/ElastiCache and stay stateless)  
C. Classic CLB only in 2014  
D. Global Accelerator stickiness as the only layer  

**Explanation:** ALB supports stickiness. The better architecture is externalize state — if the stem allows, pick DynamoDB. If it says "cannot change app," stickiness.

**10.** IMDSv2 must be required on all new instances in an account.

A. Security group egress deny  
B. **(Correct)** Account-level IMDS defaults / launch template HttpTokens=required / SCP on RunInstances  
C. NACL deny 80  
D. Disable the metadata service entirely for all apps that use IAM roles  

**Explanation:** Requiring IMDSv2 is a launch/account setting. Killing metadata breaks instance roles.

---

## Questions 11–20 — storage and databases

**11.** 200 EC2 Linux instances need a shared POSIX file system, concurrent writes, bursty throughput.

A. EBS io2 attached to all (impossible)  
B. **(Correct)** EFS  
C. S3 mount via s3fs as first choice  
D. Instance store RAID  

**Explanation:** EFS is shared POSIX. EBS is single-AZ attach (io2 Block Express multi-attach is special and not general POSIX NAS).

**12.** Windows file shares with Active Directory, SMB, and user quotas, lifted from on-premises.

A. EFS  
B. **(Correct)** FSx for Windows File Server  
C. S3  
D. EBS  

**Explanation:** FSx Windows. EFS is NFS/Linux.

**13.** Analytics team queries historical objects rarely. Cost first. Retrieval in hours is OK.

A. S3 Standard  
B. S3 Intelligent-Tiering only  
C. **(Correct)** S3 Glacier Deep Archive (or Glacier Flexible if hours and cheaper fit)  
D. EBS snapshots of a file server  

**Explanation:** Deep Archive is the cost floor for rarely accessed archives with hour-scale restore.

**14.** DynamoDB single-digit millisecond at 40K writes/sec, unpredictable spikes.

A. Provisioned 40K 24/7  
B. **(Correct)** On-demand capacity (PAY_PER_REQUEST) or provisioned + auto scaling; on-demand for unpredictable  
C. RDS with bigger instance  
D. DAX only (DAX is read cache)  

**Explanation:** Unpredictable → on-demand. DAX does not absorb write spikes.

**15.** RDS MySQL reports storage full. Fastest mitigation with least downtime?

A. Switch to DynamoDB immediately  
B. **(Correct)** Enable allocated storage autoscaling / increase allocated storage (gp3); short disruption vs migration  
C. Delete binlogs by hand as the long-term design  
D. Nightly mysqldump to S3 as the fix  

**Explanation:** Storage autoscaling is the managed feature. Migration is not "fastest."

**16.** You need a graph of friends-of-friends queries. Not a trick SQL join.

A. DynamoDB adjacency list always  
B. **(Correct)** Amazon Neptune (graph) when the stem says graph database  
C. OpenSearch  
D. QLDB  

**Explanation:** Neptune is the AWS graph service. Adjacency lists in DynamoDB appear in advanced design questions if Neptune is absent.

**17.** Cache session data with sub-millisecond reads, eviction LRU, from ElastiCache. App can tolerate cache loss.

A. RDS Multi-AZ  
B. **(Correct)** ElastiCache Redis or Memcached (Redis if persistence/replication asked; Memcached if simple and hinted)  
C. CloudFront  
D. Glacier  

**Explanation:** ElastiCache. If Multi-AZ Redis is mentioned, Redis replication group.

**18.** A bucket must remain private but a CloudFront distribution serves the objects.

A. Bucket ACL public-read  
B. **(Correct)** Origin access control (OAC) / OAI legacy, bucket policy allow CloudFront service principal  
C. Website hosting with no policy  
D. Make the bucket public and use WAF only  

**Explanation:** OAC is current SAA. Public bucket is wrong.

**19.** You must query S3 JSON in place with SQL occasionally.

A. Athena always on provisioned cluster  
B. **(Correct)** Amazon Athena (serverless)  
C. Redshift Spectrum only  
D. EMR always  

**Explanation:** Athena. Redshift Spectrum is valid if they already have Redshift — stem says occasionally, serverless.

**20.** Database migration from on-premises Oracle to Aurora PostgreSQL with minimal downtime.

A. mysqldump over the internet  
B. **(Correct)** AWS DMS (plus SCT for schema conversion)  
C. Snowball for the database only as first choice  
D. Datasync on the data files while Oracle is live without DMS  

**Explanation:** DMS + SCT is the SAA pair for heterogeneous migration.

---

## Questions 21–30 — networking and hybrid

**21.** Two VPCs in the same Region need private connectivity. Overlapping CIDRs are **not** present. Fewest moving parts.

A. Transit Gateway always  
B. **(Correct)** VPC peering  
C. VPN via the internet for each VPC  
D. Direct Connect  

**Explanation:** Simple two-VPC, no overlap → peering. TGW for hub-and-spoke / many VPCs / overlapping via TGW+NAT patterns.

**22.** 40 VPCs, shared internet egress inspection, on-premises via DX. Central routing.

A. Full mesh peering  
B. **(Correct)** Transit Gateway + DX Gateway; inspection VPC  
C. Classic ELB  
D. Only PrivateLink for all RFC1918 routing  

**Explanation:** TGW is the hub. PrivateLink is service endpoints, not a full mesh replacement.

**23.** Consume a partner's service privately without VPC peering or route sharing.

A. Peering anyway  
B. **(Correct)** PrivateLink (endpoint service + interface endpoint)  
C. Public API + security group  
D. ClassicLink  

**Explanation:** PrivateLink is designed for this.

**24.** On-premises 2 Gbps steady to AWS, predictable, not encrypted at L3 by default requirement in stem "private dedicated."

A. Site-to-Site VPN only  
B. **(Correct)** Direct Connect  
C. CloudFront  
D. API Gateway  

**Explanation:** DX for dedicated consistent bandwidth. VPN is IPsec over internet, variable.

**25.** Users worldwide resolve `api.example.com` to the lowest-latency Regional API.

A. Failover routing only  
B. **(Correct)** Route 53 latency-based routing  
C. Simple routing to one ALB  
D. Geolocation if the stem said "compliance: EU users must stay in EU" — then geolocation/geoproximity with a legal twist  

**Explanation:** Latency routing matches the stem. Geolocation is policy/jurisdiction.

**26.** A VPC needs S3 access without traversing the internet, from private subnets.

A. NAT Gateway as the only answer  
B. **(Correct)** S3 gateway VPC endpoint  
C. Interface endpoint for S3 only if gateway is not listed — gateway is preferred for S3  
D. Internet Gateway on private subnets  

**Explanation:** Gateway endpoint for S3/DynamoDB. NAT works but costs and is not "without internet."

**27.** You must prevent SSH from the internet to all instances, even if a security group is mis-set, at subnet boundary.

A. Security group deny (SGs are stateful allow-lists, no deny)  
B. **(Correct)** Network ACL inbound deny 22 from 0.0.0.0/0 on public subnets (plus don't assign public IPs)  
C. WAF  
D. Shield Advanced  

**Explanation:** NACLs can deny. SGs cannot deny. Still prefer no public IPs + SSM Session Manager.

**28.** Hybrid DNS: on-premises BIND should resolve `ec2.internal` and AWS should resolve `corp.local`.

A. Public hosted zone only  
B. **(Correct)** Route 53 Resolver inbound/outbound endpoints + forwarding rules  
C. Edit every instance `/etc/hosts`  
D. Cloud Map only  

**Explanation:** Resolver endpoints are the hybrid DNS pattern.

**29.** An NLB is required because the app uses a custom TCP protocol, not HTTP.

A. ALB  
B. **(Correct)** Network Load Balancer  
C. Gateway Load Balancer  
D. CloudFront  

**Explanation:** NLB = L4 TCP/UDP. GWLB is for appliances. ALB is HTTP/HTTPS/gRPC.

**30.** You need IPv6-only public connectivity for a dual-stack ALB.

A. NAT Gateway for IPv6  
B. **(Correct)** Internet Gateway + IPv6, or Egress-Only IGW for private IPv6 egress; dual-stack ALB as specified  
C. Classic ELB  
D. Direct Connect always  

**Explanation:** IPv6 does not use NAT GW the same way; Egress-Only IGW is the trick fact.

---

## Questions 31–40 — security, identity, architecture

**31.** Developers need temporary AWS access from an existing Okta org. Least long-lived IAM users.

A. IAM users with passwords  
B. **(Correct)** IAM Identity Center (SSO) SAML/OIDC federation to Okta  
C. Root user for each developer  
D. Embedded access keys in laptops  

**Explanation:** Identity Center / SAML federation.

**32.** An EC2 app must call S3 and DynamoDB. Best identity?

A. Access keys on the instance  
B. **(Correct)** IAM role instance profile (IRSA on EKS analog)  
C. Root keys  
D. Cognito user pool for the server  

**Explanation:** Roles, not keys.

**33.** Encrypt RDS using a key the security team can revoke.

A. Default AWS owned key only  
B. **(Correct)** Customer managed KMS key (CMK)  
C. SSL in transit only  
D. Client-side XOR  

**Explanation:** CMK for revoke/audit. In-transit SSL is complementary.

**34.** GuardDuty should monitor all accounts with one security team.

A. Per-account console hopping  
B. **(Correct)** GuardDuty administrator / Organizations auto-enable  
C. Macie only  
D. Inspector only  

**Explanation:** Delegated administrator.

**35.** WAF to block SQL injection at CloudFront.

A. NACL regex  
B. **(Correct)** AWS WAF web ACL associated with CloudFront  
C. Security group string match  
D. Shield Standard only (DDoS, not SQLi)  

**Explanation:** WAF. Shield is DDoS.

**36.** A company wants isolation between prod and dev, centralized bill, and the ability to deny `LeaveOrganization`.

A. Separate standalone accounts, no org  
B. **(Correct)** AWS Organizations, OUs, consolidated billing, SCP Deny leave  
C. IAM groups only  
D. VPC peering only  

**Explanation:** Organizations + SCP.

**37.** Store a database password rotated every 30 days, accessed by Lambda.

A. Plaintext env var  
B. **(Correct)** Secrets Manager (rotation) or SSM SecureString + custom rotation; Secrets Manager if rotation highlighted  
C. Git  
D. S3 public  

**Explanation:** Secrets Manager for native RDS rotation.

**38.** Need a service mesh mTLS between ECS services? (If too advanced, think certificates.)

A. Security groups only  
B. **(Correct)** AWS App Mesh / ECS Service Connect / ACM certificates on ALB depending on options; pick ACM+ALB if mesh not listed  
C. NACL  
D. CloudFront  

**Explanation:** Associate exam often uses ALB + ACM. If App Mesh is an option for mTLS mesh, that can be correct.

**39.** Prevent accidental S3 public from any principal in member accounts.

A. Trust developers  
B. **(Correct)** Account BPA + SCP deny public ACL + IAM Access Analyzer / Block Public Access  
C. Disable S3  
D. CloudTrail only (detect, not prevent)  

**Explanation:** Preventive + detective. CloudTrail alone is detective.

**40.** Server-side encryption with a key in another account for S3.

A. Impossible  
B. **(Correct)** SSE-KMS with CMK policy granting the bucket role in the app account  
C. SSE-S3 only  
D. Client-side only  

**Explanation:** Cross-account KMS is a standard policy pattern.

---

## Questions 41–50 — integration, DR, cost, mixed

**41.** Decouple upload processing; workers scale; at-least-once; order not required.

A. SNS only (no buffer)  
B. **(Correct)** SQS standard queue + workers (Lambda or EC2)  
C. Step Functions Express for 1 MB video  
D. EventBridge bus with no queue when backlog expected  

**Explanation:** SQS is the buffer. SNS is pub/sub. EventBridge can target SQS.

**42.** Same message must go to email, Lambda, and SQS.

A. Three polling loops on SQS  
B. **(Correct)** SNS fan-out to email, Lambda, SQS  
C. SES only  
D. CloudWatch Logs subscription only  

**Explanation:** SNS fan-out.

**43.** Orchestrate 12 Lambda steps with retries and a human approval.

A. Nested Lambda calls  
B. **(Correct)** Step Functions Standard workflow (wait for callback)  
C. Cron on EC2  
D. SQS delay 15 min loops  

**Explanation:** Step Functions.

**44.** RTO of a few minutes for a Regional RDS outage, RPO seconds.

A. Nightly dump  
B. **(Correct)** Aurora Global Database or cross-Region replica with promotion  
C. EBS snapshot weekly  
D. S3 CRR of the datadir  

**Explanation:** Global DB / replica. Weekly snapshots miss RPO/RTO.

**45.** Static website, global, HTTPS, lowest ops.

A. EC2 + nginx  
B. **(Correct)** S3 + CloudFront + ACM  
C. Elastic Beanstalk  
D. Lightsail VM  

**Explanation:** S3 website or OAC + CloudFront.

**46.** Cost: unpredictable test accounts launching huge instances.

A. Trust  
B. **(Correct)** Budgets + SCP deny large instance types in Sandbox OU  
C. Dedicated Instances  
D. Savings Plans on sandbox GPUs  

**Explanation:** SCP + budgets. Don't buy SPs for abuse.

**47.** IoT / clickstream ingest, ordered per device, replay.

A. SQS standard  
B. **(Correct)** Kinesis Data Streams (or Kafka MSK if listed for that pattern)  
C. SNS  
D. S3 PUT per click without buffer  

**Explanation:** Kinesis for streaming ordered shards.

**48.** Need SQL join-heavy BI on terabytes, predictable.

A. DynamoDB scans  
B. **(Correct)** Redshift (or Athena on data lake if "ad hoc / cost" — stem says predictable TB SQL → Redshift)  
C. ElastiCache  
D. QLDB  

**Explanation:** Redshift for warehouse. Athena if serverless lake.

**49.** Multi-AZ high availability for ALB targets.

A. All instances in us-east-1a  
B. **(Correct)** Subnets in at least two AZs, ASG spanning them  
C. Cluster placement group  
D. One huge instance  

**Explanation:** Two AZs minimum.

**50.** A solution must work if the application **cannot be modified** and needs SMB on AWS.

A. Rewrite to S3  
B. **(Correct)** FSx for Windows or SMB-capable gateway (Storage Gateway file gateway) as options dictate  
C. EFS NFS only  
D. DynamoDB  

**Explanation:** Cannot modify + SMB → FSx or file gateway. EFS is NFS.

---

## Score interpretation

| Score | Meaning |
|-------|---------|
| 45–50 | Architecture reflexes are solid; drill Well-Architected trade-offs |
| 35–44 | Review the domains you missed; re-read handbook parts III–VI |
| Below 35 | Study service **selection tables**, not only tutorials |

---

## Lab — exam simulator

1. Put these 50 items in a spreadsheet. Randomize order.
2. 90 minutes, no AWS console.
3. Mark confidence (high/low). Review all low-confidence even if correct.
4. For each miss, write **one sentence** of the constraint you ignored.
5. Re-sit only the missed domain (networking vs data) 48 hours later.

---

## Common SAA traps (memorize)

| Trap | Reality |
|------|---------|
| "HA" with one AZ | Not HA |
| Glacier for RTO 5 minutes | Restore is too slow |
| SQS exactly-once | Standard is at-least-once; FIFO + dedup is closer |
| Security group deny | No deny rules |
| IAM `Allow *` plus SCP | SCP deny still wins |
| CloudFront for dynamic WebSockets | Possible with caveats; NLB/ALB may be cleaner |
| Multi-AZ RDS is a backup | It is HA, not a Regional DR copy |
| NAT instance as default 2026 | NAT Gateway is the managed default |
| Public RDS "just for a minute" | Exam always says no |

---

## Mapping misses to handbook chapters

| If you missed | Read |
|---------------|------|
| VPC, NACL, TGW | Chapters 9–14, 57 |
| IAM, Organizations | Chapters 5–8, 53 |
| S3/EBS/EFS | Chapters 20–23 |
| RDS/DynamoDB | Chapters 24–27 |
| Lambda/API | Chapters 17, 28, 58 |
| DR | Chapters 23, 27, 54 |
| Well-Architected | Chapter 41, 60 |

---

## Additional worked example (not scored)

A company has 3-tier web, 10K users, MySQL, session in local disk, requirement: 99.99% in one Region, cost-aware.

Walkthrough: ALB + ASG across 3 AZs; move sessions to ElastiCache or DynamoDB (local disk fails ASG); RDS Multi-AZ; private subnets + NAT or VPC endpoints; WAF on ALB; backups with PITR; no second Region unless stem says DR. That single paragraph is a large fraction of SAA.

---

## Closing

The associate exam rewards **boring, managed, Well-Architected** designs. If two answers work, the one that uses a managed feature, spans two AZs, and costs less usually wins. Chapter 56 raises the difficulty to DevOps Professional: pipelines, CloudFormation, governance, and operational metrics.
