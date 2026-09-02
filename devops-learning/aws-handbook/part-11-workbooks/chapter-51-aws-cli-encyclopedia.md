# Chapter 51: AWS CLI Encyclopedia

This chapter is a field manual of **100+ AWS CLI recipes** grouped by service. Commands assume AWS CLI v2, a configured profile, and that you replace placeholders (`111122223333`, `us-east-1`, resource IDs). Prefer `--output table` or `--query` when learning; use JSON in scripts.

Set these once per shell:

```bash
export AWS_PROFILE=prod
export AWS_REGION=us-east-1
export AWS_PAGER=""
aws sts get-caller-identity
```

Terraform is shown only where a recipe is about *wiring* rather than a one-shot inspect. The labs at the end are “muscle memory” drills, not a second copy of earlier chapters.

---

## 51.1 Global: identity, regions, pricing sanity

| # | Intent | Command |
|---|--------|---------|
| 1 | Who am I | `aws sts get-caller-identity` |
| 2 | Session remaining (SSO) | `aws sts get-session-token` (long-lived keys only; SSO uses login) |
| 3 | Assume a role | `aws sts assume-role --role-arn arn:aws:iam::111122223333:role/Breakglass --role-session-name ir-$(date +%s)` |
| 4 | List regions | `aws ec2 describe-regions --query 'Regions[].RegionName' --output text` |
| 5 | Enabled regions | `aws account list-regions --region-opt-status-contains ENABLED` |
| 6 | Caller account aliases | `aws iam list-account-aliases` |
| 7 | CLI version | `aws --version` |
| 8 | Dry-run EC2 | `aws ec2 run-instances --dry-run ...` |
| 9 | Waiters | `aws ec2 wait instance-running --instance-ids i-...` |
| 10 | Debug signing | `aws s3 ls --debug 2>&1 \| tail` |

Assume-role helper:

```bash
creds=$(aws sts assume-role --role-arn "$ARN" --role-session-name cli --query 'Credentials' --output json)
export AWS_ACCESS_KEY_ID=$(echo "$creds" | jq -r .AccessKeyId)
export AWS_SECRET_ACCESS_KEY=$(echo "$creds" | jq -r .SecretAccessKey)
export AWS_SESSION_TOKEN=$(echo "$creds" | jq -r .SessionToken)
```

---

## 51.2 IAM and Organizations

| # | Intent | Command |
|---|--------|---------|
| 11 | Credential report | `aws iam generate-credential-report && aws iam get-credential-report --output text --query Content \| base64 -d` |
| 12 | List users | `aws iam list-users --query 'Users[].UserName'` |
| 13 | Access keys | `aws iam list-access-keys --user-name jdoe` |
| 14 | Disable key | `aws iam update-access-key --user-name jdoe --access-key-id AKIA... --status Inactive` |
| 15 | List roles | `aws iam list-roles --query 'Roles[].RoleName'` |
| 16 | Role trust | `aws iam get-role --role-name app-orders --query 'Role.AssumeRolePolicyDocument'` |
| 17 | Inline policies | `aws iam list-role-policies --role-name app-orders` |
| 18 | Attached managed | `aws iam list-attached-role-policies --role-name app-orders` |
| 19 | Get policy version | `aws iam get-policy-version --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess --version-id v1` |
| 20 | Simulate | `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::111122223333:role/app-orders --action-names s3:GetObject --resource-arns arn:aws:s3:::bkt/key` |
| 21 | Last accessed job | `aws iam generate-service-last-accessed-details --arn arn:aws:iam::111122223333:role/app-orders` |
| 22 | Password policy | `aws iam get-account-password-policy` |
| 23 | Virtual MFA devices | `aws iam list-virtual-mfa-devices` |
| 24 | Server certs (legacy) | `aws iam list-server-certificates` |
| 25 | Org accounts | `aws organizations list-accounts --query 'Accounts[].{Id:Id,Name:Name,Email:Email}'` |
| 26 | SCPs | `aws organizations list-policies --filter SERVICE_CONTROL_POLICY` |
| 27 | Attach SCP | `aws organizations attach-policy --policy-id p-... --target-id ou-...` |
| 28 | Identity Center instances | `aws sso-admin list-instances` |
| 29 | Access Analyzer | `aws accessanalyzer list-analyzers` |
| 30 | Validate policy | `aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document file://p.json` |

---

## 51.3 VPC, EC2, ELB, Auto Scaling

| # | Intent | Command |
|---|--------|---------|
| 31 | List VPCs | `aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Cidr:CidrBlock,Name:Tags[?Key==\`Name\`].Value\|[0]}'` |
| 32 | Subnets | `aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-...` |
| 33 | Routes | `aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-...` |
| 34 | NAT | `aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=vpc-...` |
| 35 | IGW | `aws ec2 describe-internet-gateways` |
| 36 | Endpoints | `aws ec2 describe-vpc-endpoints` |
| 37 | Flow logs | `aws ec2 describe-flow-logs` |
| 38 | SGs | `aws ec2 describe-security-groups --filters Name=vpc-id,Values=vpc-...` |
| 39 | Authorize SG | `aws ec2 authorize-security-group-ingress --group-id sg-... --protocol tcp --port 443 --source-group sg-alb` |
| 40 | NACLs | `aws ec2 describe-network-acls` |
| 41 | EIPs | `aws ec2 describe-addresses` |
| 42 | Release EIP | `aws ec2 release-address --allocation-id eipalloc-...` |
| 43 | Instances | `aws ec2 describe-instances --filters Name=instance-state-name,Values=running --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,AZ:Placement.AvailabilityZone}'` |
| 44 | Console screenshot | `aws ec2 get-console-screenshot --instance-id i-...` |
| 45 | Console output | `aws ec2 get-console-output --instance-id i-... --latest` |
| 46 | Stop / start | `aws ec2 stop-instances --instance-ids i-...` / `start-instances` |
| 47 | Replace SG | `aws ec2 modify-instance-attribute --instance-id i-... --groups sg-isolate` |
| 48 | Volumes unused | `aws ec2 describe-volumes --filters Name=status,Values=available` |
| 49 | Snapshots | `aws ec2 describe-snapshots --owner-ids self --query 'Snapshots[?StartTime>=\`2026-01-01\`]`'` |
| 50 | AMIs you own | `aws ec2 describe-images --owners self` |
| 51 | Launch templates | `aws ec2 describe-launch-templates` |
| 52 | LT versions | `aws ec2 describe-launch-template-versions --launch-template-name web-prod` |
| 53 | IMDSv2 enforce | `aws ec2 modify-instance-metadata-options --instance-id i-... --http-tokens required` |
| 54 | ASGs | `aws autoscaling describe-auto-scaling-groups` |
| 55 | Set desired | `aws autoscaling set-desired-capacity --auto-scaling-group-name web-prod --desired-capacity 6` |
| 56 | Instance refresh | `aws autoscaling start-instance-refresh --auto-scaling-group-name web-prod --preferences MinHealthyPercentage=90` |
| 57 | Lifecycle complete | `aws autoscaling complete-lifecycle-action --auto-scaling-group-name web-prod --lifecycle-hook-name drain --instance-id i-... --lifecycle-action-result CONTINUE` |
| 58 | ALBs | `aws elbv2 describe-load-balancers` |
| 59 | Target health | `aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:...` |
| 60 | Listener certs | `aws elbv2 describe-listeners --load-balancer-arn arn:...` |

Create a gateway endpoint (S3):

```bash
aws ec2 create-vpc-endpoint --vpc-id vpc-... --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-...
```

---

## 51.4 S3, EBS extras, Backup

| # | Intent | Command |
|---|--------|---------|
| 61 | List buckets | `aws s3 ls` |
| 62 | ls prefix | `aws s3 ls s3://bucket/prefix/ --recursive --human-readable --summarize` |
| 63 | cp | `aws s3 cp file s3://bucket/key --sse aws:kms --sse-kms-key-id alias/data` |
| 64 | sync | `aws s3 sync ./out s3://bucket/out --delete --dryrun` |
| 65 | presign | `aws s3 presign s3://bucket/key --expires-in 300` |
| 66 | BPA get | `aws s3api get-public-access-block --bucket bucket` |
| 67 | BPA put | `aws s3api put-public-access-block --bucket bucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true` |
| 68 | Versioning | `aws s3api get-bucket-versioning --bucket bucket` |
| 69 | Encryption | `aws s3api get-bucket-encryption --bucket bucket` |
| 70 | Policy | `aws s3api get-bucket-policy --bucket bucket` |
| 71 | Inventory / lifecycle | `aws s3api get-bucket-lifecycle-configuration --bucket bucket` |
| 72 | Object lock | `aws s3api get-object-lock-configuration --bucket bucket` |
| 73 | Delete unmarked versions (careful) | `aws s3api list-object-versions --bucket bucket --prefix tmp/` |
| 74 | Restore Glacier | `aws s3api restore-object --bucket bucket --key k --restore-request Days=3,GlacierJobParameters={Tier=Standard}` |
| 75 | Backup plans | `aws backup list-backup-plans` |
| 76 | Backup jobs | `aws backup list-backup-jobs --by-state COMPLETED --max-results 20` |

---

## 51.5 Lambda, API Gateway, EventBridge, SQS, SNS, Step Functions

| # | Intent | Command |
|---|--------|---------|
| 77 | List functions | `aws lambda list-functions --query 'Functions[].FunctionName'` |
| 78 | Get config | `aws lambda get-function-configuration --function-name orders-worker` |
| 79 | Invoke | `aws lambda invoke --function-name orders-worker --payload '{"id":"1"}' --cli-binary-format raw-in-base64-out out.json` |
| 80 | Logs tail | `aws logs tail /aws/lambda/orders-worker --follow` |
| 81 | Publish version | `aws lambda publish-version --function-name orders-worker` |
| 82 | Alias | `aws lambda update-alias --function-name orders-worker --name live --function-version 12` |
| 83 | Reserved concurrency | `aws lambda put-function-concurrency --function-name orders-worker --reserved-concurrent-executions 25` |
| 84 | ESM list | `aws lambda list-event-source-mappings --function-name orders-worker` |
| 85 | HTTP APIs | `aws apigatewayv2 get-apis` |
| 86 | REST APIs | `aws apigateway get-rest-apis` |
| 87 | Event buses | `aws events list-event-buses` |
| 88 | Put events | `aws events put-events --entries '[{"Source":"orders.api","DetailType":"OrderPlaced","Detail":"{\"id\":\"1\"}"}]'` |
| 89 | Rules | `aws events list-rules --event-bus-name default` |
| 90 | SQS send | `aws sqs send-message --queue-url https://sqs.us-east-1.amazonaws.com/111122223333/orders --message-body '{"t":"OrderPlaced"}'` |
| 91 | SQS receive | `aws sqs receive-message --queue-url ... --max-number-of-messages 10 --wait-time-seconds 10` |
| 92 | SQS purge (dev) | `aws sqs purge-queue --queue-url ...` |
| 93 | SNS publish | `aws sns publish --topic-arn arn:aws:sns:us-east-1:111122223333:ops --message 'hello'` |
| 94 | SF list | `aws stepfunctions list-state-machines` |
| 95 | SF start | `aws stepfunctions start-execution --state-machine-arn arn:... --input '{}'` |
| 96 | SF history | `aws stepfunctions get-execution-history --execution-arn arn:...` |

---

## 51.6 ECS, EKS, ECR

| # | Intent | Command |
|---|--------|---------|
| 97 | ECS clusters | `aws ecs list-clusters` |
| 98 | Services | `aws ecs list-services --cluster prod` |
| 99 | Force deploy | `aws ecs update-service --cluster prod --service web --force-new-deployment` |
| 100 | Task exec | `aws ecs execute-command --cluster prod --task TASK --container web --interactive --command /bin/sh` |
| 101 | EKS clusters | `aws eks list-clusters` |
| 102 | kubeconfig | `aws eks update-kubeconfig --name prod --alias prod` |
| 103 | Node groups | `aws eks list-nodegroups --cluster-name prod` |
| 104 | Add-ons | `aws eks list-addons --cluster-name prod` |
| 105 | Access entries | `aws eks list-access-entries --cluster-name prod` |
| 106 | ECR repos | `aws ecr describe-repositories` |
| 107 | ECR login | `aws ecr get-login-password \| docker login --username AWS --password-stdin 111122223333.dkr.ecr.us-east-1.amazonaws.com` |
| 108 | Image scan | `aws ecr describe-image-scan-findings --repository-name web --image-id imageTag=1.2.3` |

---

## 51.7 RDS, Aurora, DynamoDB, ElastiCache

| # | Intent | Command |
|---|--------|---------|
| 109 | DB instances | `aws rds describe-db-instances --query 'DBInstances[].{Id:DBInstanceIdentifier,Class:DBInstanceClass,MultiAZ:MultiAZ}'` |
| 110 | Clusters | `aws rds describe-db-clusters` |
| 111 | Failover Aurora | `aws rds failover-db-cluster --db-cluster-identifier orders` |
| 112 | Stop RDS (limits apply) | `aws rds stop-db-instance --db-instance-identifier dev-pg` |
| 113 | Snapshots | `aws rds describe-db-snapshots --db-instance-identifier orders-pg` |
| 114 | PITR restore | `aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier orders-pg --target-db-instance-identifier orders-pitr --use-latest-restorable-time` |
| 115 | Proxy | `aws rds describe-db-proxies` |
| 116 | DDB tables | `aws dynamodb list-tables` |
| 117 | Describe table | `aws dynamodb describe-table --table-name orders` |
| 118 | Get item | `aws dynamodb get-item --table-name orders --key '{"pk":{"S":"CUSTOMER#1"},"sk":{"S":"ORDER#1"}}'` |
| 119 | Query | `aws dynamodb query --table-name orders --key-condition-expression 'pk = :p' --expression-attribute-values '{":p":{"S":"CUSTOMER#1"}}'` |
| 120 | PITR flag | `aws dynamodb describe-continuous-backups --table-name orders` |
| 121 | TTL | `aws dynamodb describe-time-to-live --table-name sessions` |
| 122 | ElastiCache groups | `aws elasticache describe-replication-groups` |
| 123 | Failover cache | `aws elasticache test-failover --replication-group-id sessions --node-group-id 0001` |

---

## 51.8 CloudWatch, X-Ray, CloudTrail, Config

| # | Intent | Command |
|---|--------|---------|
| 124 | Alarms | `aws cloudwatch describe-alarms --state-value ALARM` |
| 125 | Put metric | `aws cloudwatch put-metric-data --namespace App/Orders --metric-name Checkout --value 1` |
| 126 | Log groups | `aws logs describe-log-groups` |
| 127 | Insights start | `aws logs start-query --log-group-name /aws/lambda/orders-worker --start-time $(date -d '1 hour ago' +%s) --end-time $(date +%s) --query-string 'fields @message \| limit 20'` |
| 128 | Metrics list | `aws cloudwatch list-metrics --namespace AWS/Lambda --dimensions Name=FunctionName,Value=orders-worker` |
| 129 | X-Ray groups | `aws xray get-groups` |
| 130 | Trails | `aws cloudtrail describe-trails` |
| 131 | Lookup events | `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=ConsoleLogin --max-results 20` |
| 132 | Config recorders | `aws configservice describe-configuration-recorders` |
| 133 | Compliance | `aws configservice describe-compliance-by-config-rule` |

---

## 51.9 KMS, Secrets, ACM, SSM

| # | Intent | Command |
|---|--------|---------|
| 134 | List keys | `aws kms list-keys` |
| 135 | Key rotation | `aws kms get-key-rotation-status --key-id alias/data` |
| 136 | Encrypt | `aws kms encrypt --key-id alias/data --plaintext fileb://plain.txt --output text --query CiphertextBlob \| base64 -d > c.bin` |
| 137 | Secrets list | `aws secretsmanager list-secrets` |
| 138 | Get secret | `aws secretsmanager get-secret-value --secret-id prod/orders/db` |
| 139 | Rotate | `aws secretsmanager rotate-secret --secret-id prod/orders/db` |
| 140 | ACM certs | `aws acm list-certificates --certificate-statuses ISSUED` |
| 141 | SSM params | `aws ssm get-parameters-by-path --path /prod/orders --recursive --with-decryption` |
| 142 | SSM put | `aws ssm put-parameter --name /prod/orders/log_level --type String --value INFO --overwrite` |
| 143 | Session | `aws ssm start-session --target i-...` |
| 144 | Inventory | `aws ssm describe-instance-information` |
| 145 | Patch baseline | `aws ssm describe-patch-baselines` |

---

## 51.10 Security Hub, GuardDuty, WAF, Inspector

| # | Intent | Command |
|---|--------|---------|
| 146 | GD detectors | `aws guardduty list-detectors` |
| 147 | GD findings | `aws guardduty list-findings --detector-id 12abc --finding-criteria file://crit.json` |
| 148 | Sample findings | `aws guardduty create-sample-findings --detector-id 12abc` |
| 149 | Hub enable | `aws securityhub enable-security-hub` |
| 150 | Hub findings | `aws securityhub get-findings --max-results 10` |
| 151 | Standards | `aws securityhub get-enabled-standards` |
| 152 | WAF ACLs | `aws wafv2 list-web-acls --scope REGIONAL` |
| 153 | Inspector2 coverage | `aws inspector2 list-coverage --max-results 20` |
| 154 | Macie | `aws macie2 get-macie-session` |

Example finding filter file `crit.json`:

```json
{ "Criterion": { "severity": { "Gte": 7 } } }
```

---

## 51.11 Route 53, CloudFront, ACM DNS

| # | Intent | Command |
|---|--------|---------|
| 155 | Hosted zones | `aws route53 list-hosted-zones` |
| 156 | Records | `aws route53 list-resource-record-sets --hosted-zone-id Z...` |
| 157 | Change batch | `aws route53 change-resource-record-sets --hosted-zone-id Z... --change-batch file://chg.json` |
| 158 | Health checks | `aws route53 list-health-checks` |
| 159 | CloudFront distros | `aws cloudfront list-distributions --query 'DistributionList.Items[].{Id:Id,Domain:DomainName,Enabled:Enabled}'` |
| 160 | Invalidate | `aws cloudfront create-invalidation --distribution-id E... --paths '/*'` |

---

## 51.12 Billing, Cost Explorer, Budgets, Compute Optimizer

| # | Intent | Command |
|---|--------|---------|
| 161 | Services this month | `aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE` |
| 162 | By tag | `aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity MONTHLY --metrics UnblendedCost --group-by Type=TAG,Key=CostCenter` |
| 163 | Forecast | `aws ce get-cost-forecast --time-period Start=2026-09-02,End=2026-10-01 --metric UNBLENDED_COST --granularity MONTHLY` |
| 164 | Budgets | `aws budgets describe-budgets --account-id 111122223333` |
| 165 | Optimizer | `aws compute-optimizer get-ec2-instance-recommendations` |
| 166 | Trusted Advisor (Support) | `aws support describe-trusted-advisor-checks --language en` (Business+ support) |
| 167 | Service quotas EC2 | `aws service-quotas list-service-quotas --service-code ec2` |
| 168 | Request quota | `aws service-quotas request-service-quota-increase --service-code vpc --quota-code L-... --desired-value 10` |

---

## 51.13 Organizations networking extras: TGW, Direct Connect, RAM

| # | Intent | Command |
|---|--------|---------|
| 169 | TGW list | `aws ec2 describe-transit-gateways` |
| 170 | TGW routes | `aws ec2 search-transit-gateway-routes --transit-gateway-route-table-id tgw-rtb-... --filters Name=type,Values=static,propagated` |
| 171 | RAM shares | `aws ram get-resource-shares --resource-owner SELF` |
| 172 | VPC peering | `aws ec2 describe-vpc-peering-connections` |
| 173 | PrivateLink services | `aws ec2 describe-vpc-endpoint-services --query 'ServiceNames[?contains(@, \`s3\`)]'` |

---

## 51.14 One-liners worth scripting

**Untagged EC2:**

```bash
aws ec2 describe-instances --query 'Reservations[].Instances[?!Tags].[InstanceId,InstanceType]' --output table
```

**Public NACL / SG SSH (heuristic):**

```bash
aws ec2 describe-security-groups --query 'SecurityGroups[?IpPermissions[?FromPort==`22` && IpRanges[?CidrIp==`0.0.0.0/0`]]].[GroupId,GroupName]'
```

**Lambda runtimes:**

```bash
aws lambda list-functions --query 'Functions[].{Name:FunctionName,Runtime:Runtime,Timeout:Timeout}' --output table
```

**Expired ACM (issued, not imported expiry hunt):**

```bash
aws acm list-certificates --query 'CertificateSummaryList[].{Arn:CertificateArn,Domain:DomainName}'
```

Terraform data source companion (inventory in code):

```hcl
data "aws_caller_identity" "me" {}
data "aws_region" "current" {}
output "who" { value = { account = data.aws_caller_identity.me.account_id, region = data.aws_region.current.name } }
```

---

## 51.15 Recipe count index

Recipes **1–173** are listed above (tables plus the assume-role and S3 endpoint blocks as operational recipes). That is more than 100 distinct CLI invocations you will actually use. Do not memorize flags; memorize *which service answers which question*, then `--generate-cli-skeleton` when stuck:

```bash
aws ec2 run-instances --generate-cli-skeleton yaml-input
aws lambda invoke --generate-cli-skeleton
```

---

## 51.16 Labs

### Lab A — Identity and blast radius (recipes 1, 3, 15–20)

1. `get-caller-identity`.
2. Simulate `s3:DeleteBucket` on your role (expect deny).
3. List the role policy that would have allowed it if it were over-permissioned.

### Lab B — Network evidence (31–37, 43)

1. Pick a running instance. Note subnet, SG, route table.
2. Confirm or deny a default route to NAT vs IGW.
3. Check for an S3 gateway endpoint.

### Lab C — Data plane (109–122)

1. Describe whether Multi-AZ is true.
2. Describe DynamoDB PITR.
3. List ElastiCache failover settings.

### Lab D — Detect (146–151, 130–131)

1. List GuardDuty detectors in this region.
2. List CloudTrail trails.
3. If allowed, create sample GuardDuty findings in a sandbox only.

### Lab E — Cost (161–165)

1. Group last month’s cost by SERVICE.
2. List Compute Optimizer recommendations (enable the service first if empty).

---

## 51.17 Production habits

| Habit | Why |
|-------|-----|
| Named profiles, never keys in Git | Credential hygiene |
| `--cli-read-timeout` in slow regions | Scripts |
| Pagination: CLI auto-paginates most list calls | Do not assume one page in custom SDK code |
| `--no-cli-pager` in CI | Hanging pipes |
| CloudShell for break-glass | No local keys |
| Prefer SSM over SSH | No inbound 22 |

```bash
aws configure set cli_follow_urlparam false
# ~/.aws/config
# [profile prod]
# sso_start_url = https://example.awsapps.com/start
# sso_region = us-east-1
# sso_account_id = 111122223333
# sso_role_name = ProdReadOnly
# region = us-east-1
```

---

## 51.18 Review questions

1. Why export `AWS_PAGER=""` in scripts?
2. How do you pass JSON to `lambda invoke` without base64 surprises in CLI v2?
3. Which command shows whether an RDS instance is Multi-AZ?
4. How do you confirm a target group has healthy hosts?
5. What is the difference between `s3 ls` and `s3api list-objects-v2`?
6. How do you attach an SCP with the CLI?
7. Which command tails Lambda logs without visiting the console?
8. How do you force IMDSv2 on a running instance?
9. How do you start an ASG instance refresh with 90% healthy?
10. Why is `purge-queue` dangerous?
11. How do you get kubeconfig for EKS?
12. Which CE call groups cost by tag key `CostCenter`?
13. How do you list Security Hub findings from CLI?
14. What waiter waits for EC2 running?
15. How do you generate an IAM credential report?

**Answers (brief):** (1) Prevent the client from opening `less`. (2) `--cli-binary-format raw-in-base64-out` plus a JSON payload file. (3) `rds describe-db-instances` → `MultiAZ`. (4) `elbv2 describe-target-health`. (5) High-level recursive UX vs API pagination/details. (6) `organizations attach-policy`. (7) `logs tail --follow`. (8) `ec2 modify-instance-metadata-options --http-tokens required`. (9) `autoscaling start-instance-refresh --preferences MinHealthyPercentage=90`. (10) Deletes all messages in a queue. (11) `eks update-kubeconfig`. (12) `ce get-cost-and-usage --group-by Type=TAG,Key=CostCenter`. (13) `securityhub get-findings`. (14) `ec2 wait instance-running`. (15) `iam generate-credential-report` then `get-credential-report`.

---

## 51.19 Closing the handbook workbooks

You now have design cookbooks (VPC, IAM, data), production compute (EC2/ASG, Lambda, EKS), operations (security, cost, Well-Architected), and this CLI index. The next skill is not another service: it is repeating the labs until the commands are boring. Boring operations are the point.
