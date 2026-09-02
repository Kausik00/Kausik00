# Chapter 59: AWS Troubleshooting Cookbook

This cookbook is organized by **symptom**, not by service marketing name. When production is down, you do not need a reminder that CloudWatch exists. You need a sequence: freeze the blast radius, classify the failure, prove it with evidence, apply a reversible fix, then write the follow-up. Pair with Chapter 54 for Regional disasters and Chapter 57 for packet-level networking.

**Golden rules**

1. **One change at a time**, with a timestamp in the incident channel.
2. Prefer **evidence** (error code, request id, flow log REJECT) over vibes.
3. Distinguish **IAM Deny**, **SCP Deny**, **resource policy Deny**, **VPC path**, and **service throttle** — they all look like "AccessDenied" or timeout to a tired human.
4. Do not Regional-failover a bad deploy (Chapter 54 decision tree).
5. After mitigation, file the **missing alarm**.

---

## 59.1 Incident first five minutes

| Minute | Action |
|--------|--------|
| 0 | Name IC; copy the customer symptom (URL, error, time window, request id) |
| 1 | Check status.aws.amazon.com and your synthetic canaries |
| 2 | Check last deploy (CodePipeline, ECS deployment, Lambda alias) |
| 3 | Error rate vs latency vs saturation (the three golden signals) |
| 4 | If deploy-correlated: rollback. If AZ-correlated: shift away. If global AWS: communicate and wait/failover per runbook |
| 5 | Broader comms; stop random console clicking |

Keep a **scratch pad** of request IDs. AWS support and X-Ray are useless without them.

---

## 59.2 Symptom: timeouts and "connectivity"

Timeouts are not one disease. Split:

| Observation | Likely class |
|-------------|--------------|
| TCP SYN no SYN-ACK | Security group, NACL, route, NLB empty, wrong IP |
| TLS handshake fail | SNI, cert, TLS version, MTU |
| HTTP hang after headers | App deadlock, downstream, missing SG to DB |
| Intermittent | Cross-AZ, NAT port exhaustion, unhealthy targets flapping |
| Only from Lambda in VPC | Missing NAT/endpoint |
| Only from on-premises | TGW/DX/VPN routes, overlapping CIDR |

### Recipe — VPC path

1. From the client, `curl -v --max-time 5` (or Test-NetConnection). Note if failure is DNS (`could not resolve`) vs connect vs HTTP.
2. **DNS:** `dig` the name. Unexpected public IP for an internal service = split-horizon failure (Chapter 57).
3. **Reachability Analyzer** between ENIs. It is slower than instinct but catches NACL ephemeral holes.
4. **Flow logs** filtered by source/dest. `REJECT` at ENI vs at NACL.
5. **Routes:** subnet table has 0.0.0.0/0? To NAT or IGW or TGW? Wrong next hop blackholes.
6. **SGs:** stateful; if inbound 443 exists, outbound reply is OK unless you used **custom outbound deny** (rare). Check **the other side's inbound**.
7. **NACLs:** stateless; ephemeral 1024–65535.
8. **TGW:** search-transit-gateway-routes for the dest CIDR; appliance mode if firewalls.
9. **IPv6:** AAAA record to a host that has no IPv6 path.

### Recipe — Interface endpoint / PrivateLink

See Chapter 57 table. Confirm endpoint ENI SG, `enableDnsName`, and that the app is not still using the public AWS hostname from a peered network that does not have the endpoint.

### Recipe — NAT exhaustion

Symptom: random timeouts to the internet from private subnets at high connection rates.

- CloudWatch `IdleTimeoutCount`, `PacketsDropCount` on NAT Gateway.
- Fix: more NATs per AZ, more ports (scale), **VPC endpoints** so AWS API traffic skips NAT, connection reuse in the app.

### Lab — induce and see REJECT

1. Two instances; SG allows SSH from your IP only.
2. Enable flow logs.
3. `curl` instance A to B on 80 with no SG inbound 80.
4. Read flow logs `REJECT`.
5. Add SG; see `ACCEPT`.

This trains your eyes so you do not jump to "AWS is down."

---

## 59.3 Symptom: IAM deny / AccessDenied / UnauthorizedOperation

Read the **entire** error. CloudTrail `errorCode` + `errorMessage` often includes the **explicit deny** type.

### Decision tree

```
AccessDenied?
├─ CloudTrail event exists?
│   ├─ explicitDeny in message or "denied by SCP" → Organizations SCP / RCP / permissions boundary / session policy
│   ├─ implicit deny → missing Allow on identity or resource policy
│   └─ KMS AccessDenied → key policy + IAM kms:Decrypt
└─ No CloudTrail?
    └─ Wrong region, data event not logged, or not an AWS API (app 403)
```

### Layers that can deny (all must allow)

| Layer | Applies to |
|-------|------------|
| SCP | Member accounts, not management |
| Permission boundary | Max of the IAM principal |
| Session policy | Assumed role session |
| Identity policy | User/role |
| Resource policy | Bucket, key, queue, topic, SM secret |
| VPC endpoint policy | Calls through that endpoint |
| Service control via RCP | Resource policy shape |
| Condition keys | `aws:SourceIp`, `aws:ResourceTag`, `kms:ViaService` |

**Explicit deny anywhere wins.**

### Recipe

1. Reproduce with the **same role** (`aws sts get-caller-identity`).
2. CloudTrail Lake or Insights query on `userIdentity.arn` and `eventName`.
3. IAM Policy Simulator (limited with SCPs — simulator may not include org SCPs depending on setup).
4. Decode: `aws iam simulate-principal-policy` for identity; still check bucket policy separately.
5. KMS: `kms:Decrypt` on the **key**, plus `kms:ViaService` if required.
6. S3: bucket policy `Deny` with `NotPrincipal` is a classic lockout — use break-glass from a role listed in the policy.

### Common IAM gotchas

| Gotcha | Fix |
|--------|-----|
| `iam:PassRole` missing | Deploy roles cannot attach instance profiles |
| Confused deputy | `aws:SourceAccount` / `SourceArn` on resource policy |
| S3 `GetObject` without `ListBucket` | Different error for CLI vs console |
| `sts:AssumeRole` missing ExternalId | Third-party roles |
| Clock skew | Signature expired |
| Wrong partition | `aws-cn` vs `aws` ARNs |

### Lab — SCP vs IAM

In a canary OU (Chapter 53 Lab A), attach Deny `s3:CreateBucket`. With Admin role, create bucket. Capture the error string. Detach SCP, attach an IAM Deny on the role, compare messages. Teach the on-call the difference.

---

## 59.4 Symptom: throttling (429, 400, ProvisionedThroughputExceeded, Rate exceeded)

Throttling is **the service protecting itself** or **your quota**.

| API / service | Signal | Mitigation |
|---------------|--------|------------|
| DynamoDB | `ProvisionedThroughputExceeded`, `ThrottledRequests` | On-demand, auto scaling, fix hot key, DAX for reads |
| Lambda | `429 ConcurrentInvocationLimitExceeded` | Reserve concurrency, quota increase, SQS buffer |
| API Gateway | 429 | Usage plans, burst, WAF rate limit is different |
| STS | `Throttling` | Session cache, fewer AssumeRole |
| EC2 RunInstances | RequestLimitExceeded | Exponential backoff, fewer parallel ASGs |
| CloudWatch PutMetricData | 429 | EMF, batch |
| S3 | 503 Slow Down | Prefix entropy, retry |

**Always** implement exponential backoff with jitter in custom clients. AWS SDKs do this; **turned-off retries** in a "performance" refactor is a self-inflicted DDoS.

### Recipe — DynamoDB hot partition

1. CloudWatch `ThrottledRequests` by table; Contributor Insights for keys.
2. If one PK dominates, shard or cache.
3. If evenly hot, raise capacity.

### Recipe — Lambda vs API 429

If API Gateway 429 with `Limit Exceeded`, it may be **usage plan**, not Lambda. If Lambda 429, check **reserved** accidentally set to 5 in prod (Chapter 58 Lab B).

---

## 59.5 Symptom: HTTP 5xx

Classify **who generated the 5xx**.

| Source | Examples |
|--------|----------|
| ALB | `5XX` vs `ELB 5XX` (target vs load balancer) |
| API Gateway | `5XXError`, integration timeout, authorizer fail |
| CloudFront | `5xxErrorRate`, origin timeout, origin 5xx |
| App | Uncaught exception |
| AWS service | Rare; still check health dashboard |

ALB metrics: **HTTPCode_Target_5XX_Count** vs **HTTPCode_ELB_5XX_Count**. ELB 5xx includes **502** (unhealthy/reset), **503** (no healthy targets), **504** (target timeout).

### Recipe — ALB 502/504

1. Target group healthy host count → 0? Deploy, SG ALB→instance, failed health check path.
2. Keep-alive: target closes before ALB (idle timeout mismatch).
3. Response bigger than limits; HTTP/2 issues.
4. App crashed after accept — access logs `elb_status_code` vs `target_status_code`.

Enable **ALB access logs** to S3 **before** you need them. Same for CloudFront.

### Recipe — API Gateway 502/504

- Lambda crashed or malformed proxy response (must be JSON with `statusCode`).
- Timeout: integration timeout < Lambda duration.
- VPC link to NLB down.

Malformed Lambda proxy is the #1 beginner 502:

```python
# wrong: return "ok"
# right:
return {"statusCode": 200, "body": "{\"ok\": true}"}
```

### Recipe — CloudFront 504

Origin too slow; increase origin timeout (max limited); cache what you can; fix origin.

---

## 59.6 Symptom: 4xx that "used to work"

| Code | Typical AWS-ish cause |
|------|------------------------|
| 401 | JWT expired, Cognito, IAM SigV4 clock |
| 403 | WAF, S3, IAM, CloudFront geo, OAC |
| 404 | Wrong stage, wrong path, S3 no such key vs no such bucket |
| 409 | Conditional check DynamoDB, S3 name |
| 413 | Payload too large |
| 415 | Content-type |

WAF **403** with a labeled rule: check sampled requests / logs. A new managed rule group update can block a user-agent.

S3 403 vs 404: **without List permission**, missing keys may look like 403 (security). Don't leak existence.

---

## 59.7 Symptom: ECS/EKS cannot pull images or start

| Error | Check |
|-------|--------|
| `CannotPullContainerError` | ECR policy, `ecr:GetAuthorizationToken`, VPC endpoints `ecr.api`, `ecr.dkr`, `s3` |
| `ResourceInitializationError` | Exec role, secrets from SM, EFS mount SG |
| CrashLoop | Logs; don't scale yet |
| EKS `ImagePullBackOff` | Same plus IRSA vs node role confusion |
| Task stopped `OutOfMemory` | Memory limit vs Java heap |

**IRSA vs instance role:** the pod's ServiceAccount annotation must match; `aws sts get-caller-identity` inside the pod. If you see the **node** role, IRSA is not applied.

---

## 59.8 Symptom: "the database is slow"

1. Is it **CPU**, **IOPS**, **connections**, or **locks**?
2. RDS Performance Insights; wait events.
3. CloudWatch `DatabaseConnections` vs `max_connections`; RDS Proxy needed for Lambda.
4. Storage full (Chapter 55) — autoscaling.
5. Failover happened; DNS TTL (Chapter 56 Q25).
6. Noisy neighbor on burstable (`CPUCreditBalance` = 0 on T-class).

Do not "add read replicas" until you know the load is read-heavy and the app can use a reader endpoint.

---

## 59.9 Symptom: TLS/certificate problems

- ACM cert not **issued** (DNS validation CNAME missing).
- ALB listener cert in **wrong Region**.
- CloudFront cert must be in **us-east-1**.
- Client still has old cert (you didn't attach to the listener).
- SNI: client didn't send SNI; default cert served.
- Private PKI: trust bundle missing on clients.

---

## 59.10 Symptom: "KMS invalid ciphertext" / cannot decrypt

- Wrong key.
- Wrong account.
- Encryption context mismatch (S3/Secrets often set context).
- Role missing `kms:Decrypt`.
- Key pending deletion.

Never rotate CMKs by deleting. Use yearly rotation flag.

---

## 59.11 Logs, traces, and how to actually query

**CloudWatch Logs Insights** starter:

```
fields @timestamp, @message, @requestId
| filter @message like /ERROR/
| sort @timestamp desc
| limit 50
```

Correlate: ALB access log `trace_id` with X-Ray. Put **request id** in app logs.

**Metric filters** for `ERROR` on a log group → alarm. Without this, Insights is archaeology after the customer left.

---

## 59.12 Support, Health, and Personal Health Dashboard

- **PHD** events for your account: instance retirement, IAM changes, TLS deprecations.
- **AWS Health** org view in the audit account.
- When opening support: Region, resource IDs, request IDs, time UTC, "what changed," CloudTrail event names, **not** "it's slow."

---

## 59.13 Rollback catalog (quick)

| System | Rollback |
|--------|----------|
| Lambda alias | Point `prod` to previous version |
| ECS CodeDeploy | Automatic on alarm; else traffic back to blue |
| ECS rolling | `update-service --force-new-deployment` previous task def |
| CFN | Previous template change set; stack rollback |
| RDS | PITR to new instance (not "undo SQL" unless you have binlogs) |
| DynamoDB | Restore PITR to **new table**, then switch (disruptive) |
| S3 | Versioning restore object |

Practice these in sandbox. The worst time to learn PITR restore time is during RTO.

---

## 59.14 Lab A — ALB 503

1. ALB + target group, one instance, health `/health`.
2. Break health (stop nginx). Watch healthy host 0, ALB 503.
3. Access logs: `elb_status_code=503`.
4. Alarm `UnHealthyHostCount`.
5. Restore.

**Success criteria:** You can tell 503 (no targets) from 502 (bad response) from 504 (timeout).

---

## 59.15 Lab B — Lambda 502 from API Gateway

1. Function returns a Python `str`.
2. HTTP API or REST proxy. Observe 502.
3. Logs: Lambda succeeded, API failed mapping.
4. Fix return shape.

---

## 59.16 Lab C — throttle DynamoDB

1. Tiny table provisioned 1 WCU.
2. Burst writes. Capture `ProvisionedThroughputExceededException`.
3. Enable Contributor Insights. Switch to on-demand. Retry.

---

## 59.17 Checklist for a 5xx war room

- [ ] Request id / trace id
- [ ] Last deploy SHA and time
- [ ] ALB/API/CloudFront which layer 5xx
- [ ] Target health
- [ ] Throttles (Lambda, DDB, API)
- [ ] IAM/SCP (if 403 mixed in)
- [ ] Downstream DB connections
- [ ] AWS Health
- [ ] Rollback attempted if deploy-shaped
- [ ] Customer comms

---

## 59.18 Mapping symptoms to handbook

| Symptom | Chapters |
|---------|----------|
| Packets | 9–14, 57 |
| IAM | 5–8, 53 |
| Throttle | 17, 25, 58 |
| 5xx | 12, 16, 28 |
| DR | 54 |
| Pipeline | 33, 56 |

---

## 59.19 Anti-patterns during incidents

| Anti-pattern | Do this |
|--------------|---------|
| Ten people editing SG | One network driver |
| "Restart all the things" | Restart the saturated tier with a hypothesis |
| Disable WAF | Sample WAF logs first; disable one rule |
| Scale to 1000 tasks on a DB of 20 connections | Fix connections |
| ChatGPT the error without request id | Get evidence |
| Recreate the cluster | Last resort |

---

## 59.20 Chapter checklist

- [ ] Flow logs and ALB logs exist **before** the incident.
- [ ] On-call can distinguish SCP vs IAM vs SG.
- [ ] Dashboards separate ELB 5xx vs target 5xx.
- [ ] Backoff/jitter in custom clients.
- [ ] Labs A–C completed.

The capstone architecture in Chapter 60 expects you to apply this cookbook to a full multi-tier + EKS + data platform, not a single Lambda.
