# Chapter 58: Serverless Reference — API Gateway, Lambda, DynamoDB, EventBridge, SAM

This chapter is a single-stop **serverless reference** for architects who already met the services in Parts IV, VI, and VII. It emphasizes integration contracts, failure modes, SAM/CDK packaging, and labs that produce a working API with events — not another "Hello World" that ignores IAM and retries.

Serverless on AWS in production is rarely "just Lambda." It is an **event topology**: API Gateway or Function URLs in front, DynamoDB or Aurora as state, EventBridge/SQS/SNS as glue, IAM as the real network, and observability as the only way to debug a system with no SSH.

---

## 58.1 When serverless is the right default

| Fit | Not a fit |
|-----|-----------|
| Spiky traffic, idle majority | Steady 24/7 high CPU with custom kernels |
| Event-driven glue | Hard real-time <1 ms on-box |
| Team wants no patching | Stateful WebSockets at huge scale without API GW experience |
| Pay per request | Always-on GPU training (use Batch/SageMaker) |

Lambda timeout (15 minutes), payload sizes, and cold starts are constraints, not moral failures. If you fight them daily, use Fargate.

---

## 58.2 Lambda runtime contract

### Handler, identity, and config

- **Execution role:** what AWS APIs the function may call.
- **Resource policy:** what may invoke the function (API GW, S3, EventBridge).
- **VPC:** ENI/Hyperplane in subnets; you then need endpoints or NAT for AWS APIs.
- **Env vars:** non-secrets; secrets from SM/SSM at init or via extension.
- **Layers:** shared code; version them; don't put secrets in layers.
- **Ephemeral `/tmp`:** 512 MB–10 GB; not durable.
- **Arch:** x86 vs arm64 (Graviton) for cost.

### Concurrency

| Knob | Meaning |
|------|---------|
| Unreserved account concurrency | Shared pool (default 1000, quota) |
| Reserved | Guarantees and **caps** that function |
| Provisioned | Pre-warmed execution environments (cost) |
| SQS batch vs concurrent Lambdas | Scaling from queue |

A noisy neighbor function without a reserve can starve a payment function. **Reserve** the critical path.

**Throttle behavior:** invoke returns 429 to sync callers; async retries with DLQ/on-failure destination.

### Cold starts

Mitigations: smaller package, arm64, provisioned concurrency, snapstart (Java), stay out of VPC if you do not need it (or accept Hyperplane improvements). Do not "fix" cold start by keeping a busy loop — that is an expensive EC2.

### Versions and aliases

Publish versions; `prod` alias weighted to `2` and `1` for canary. CodeDeploy for Lambda automates alias traffic.

```bash
aws lambda update-alias --function-name checkout --name prod \
  --routing-config AdditionalVersionWeights={"2"=0.1}
```

---

## 58.3 API Gateway modes

| Mode | Use | Auth common |
|------|-----|-------------|
| HTTP API | Cheaper, JWT, Lambda proxy, WebSocket no (use REST/WebSocket APIs) | JWT, IAM, Lambda authorizer |
| REST API | Usage plans, API keys, WAF association classic, request validation | IAM, Cognito, Lambda auth, API keys |
| WebSocket API | Push | Same family |
| Private REST | NLB/VPC endpoint | Resource policy |

**Lambda proxy integration** is the default: API GW passes a well-known JSON event; your function returns `{statusCode, headers, body}`.

**Payload limits:** REST ~10 MB, HTTP API similar order; huge uploads belong on S3 presign (Chapter 55 Q5).

**Timeouts:** API Gateway timeout is shorter than Lambda max (HTTP API configurable up to 30s typically). Long jobs: accept 202 + SQS + poll/status.

### Auth patterns

```
Client --JWT--> HTTP API JWT authorizer --> Lambda
Client --IAM SigV4--> execute-api --> Lambda
Client --token--> Lambda authorizer (cache TTL) --> Lambda
```

Cache authorizer results; a 0-second TTL DDOS your authorizer Lambda.

Resource policy for private API:

```json
{
  "Effect": "Allow",
  "Principal": "*",
  "Action": "execute-api:Invoke",
  "Resource": "arn:aws:execute-api:us-east-1:222222222222:abc123/*",
  "Condition": {
    "StringEquals": { "aws:SourceVpce": "vpce-0123" }
  }
}
```

### Stages, canaries, custom domains

REST canary deployments percentage-split. Custom domain + ACM in us-east-1 for edge-optimized; regional ACM in the API Region. Base path mapping for `/v1` vs `/v2`.

WAF on REST/HTTP (HTTP API WAF support — verify current). Shield for DDoS.

---

## 58.4 DynamoDB for serverless APIs

### Keys and access patterns first

You do not "create a table and see." You list queries:

| Access pattern | Key design |
|----------------|------------|
| Get order by id | PK `ORDER#id` |
| Orders for user | PK `USER#id` SK `ORDER#ts` |
| Status index | GSI on `status` + `ts` — watch fan-out |

**Hot partitions:** one popular PK. Mitigate with sharding suffixes or redesign.

### Capacity

On-demand for spiky APIs. Provisioned + auto scaling for steady. **Max on-demand** account quotas still exist.

**Transactions:** `TransactWrite` up to 100 items; extra cost; use for payment+inventory pairing.

**TTL:** expire sessions; DynamoDB does not guarantee immediate delete — do not use TTL as a license expiry to the second.

**Streams:** async integrations (EventBridge pipes, Lambda). At-least-once; idempotent consumers.

**Global tables:** multi-Region last-writer-wins. Idempotent writes; no cross-item transactions across Regions.

### DAX

Microsecond reads for cached gets. Does not cache queries the way people hope; not a write buffer. Another failure domain and VPC requirement.

### Single-table vs multi-table

Single-table is a valid advanced pattern, not a religion. For teams new to DynamoDB, **one table per aggregate** with GSIs is operable. Serverless still loves DynamoDB because IAM + AWS SDK + no connection pool in Lambda.

RDS Proxy + Aurora is valid when SQL is required; connection storms are the Lambda+RDS classic outage — **always Proxy or Data API**.

---

## 58.5 EventBridge, SQS, SNS — who does what

| Service | Semantics | Serverless role |
|---------|-----------|-----------------|
| EventBridge | Bus, rules, schema, archive/replay, Pipes | Default enterprise event router |
| SQS | Buffer, delay, DLQ, FIFO | Absorb Lambda concurrency; backpressure |
| SNS | Fan-out, filter | Broadcast |

**Never** have Lambda call Lambda synchronously as your architecture. Use events.

### EventBridge Pipes

Source (SQS, Kinesis, DDB stream) → optional enrichment → EventBridge or another target. Reduces "glue Lambdas."

### Archive and replay

Turn on archive for the bus you will need to replay after a bad consumer deploy. Replay is not a backup of DynamoDB.

### Schema registry

Optional; useful for org-wide events. Don't block delivery on schema police on day one; add when you have more than three teams.

---

## 58.6 SAM and the programming model

**AWS SAM** is CloudFormation with the `AWS::Serverless` transform. Fastest path from laptop to API.

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: checkout-api

Globals:
  Function:
    Runtime: python3.12
    Timeout: 10
    Architectures: [arm64]
    Tracing: Active
    Environment:
      Variables:
        TABLE: !Ref Orders

Resources:
  Orders:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: pk, AttributeType: S }
        - { AttributeName: sk, AttributeType: S }
      KeySchema:
        - { AttributeName: pk, KeyType: HASH }
        - { AttributeName: sk, KeyType: RANGE }
      StreamSpecification:
        StreamViewType: NEW_IMAGE

  Api:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ["https://app.example.com"]
        AllowMethods: ["GET", "POST"]
        AllowHeaders: ["Authorization"]

  PutOrder:
    Type: AWS::Serverless::Function
    Properties:
      Handler: app.put_order
      Policies:
        - DynamoDBWritePolicy:
            TableName: !Ref Orders
      Events:
        Post:
          Type: HttpApi
          Properties:
            ApiId: !Ref Api
            Path: /orders
            Method: POST

  OnOrderStream:
    Type: AWS::Serverless::Function
    Properties:
      Handler: app.on_stream
      Policies:
        - EventBridgePutEventsPolicy:
            EventBusName: default
      Events:
        Stream:
          Type: DynamoDB
          Properties:
            Stream: !GetAtt Orders.StreamArn
            StartingPosition: LATEST
            BisectBatchOnFunctionError: true
            DestinationConfig:
              OnFailure:
                Type: SQS
                Destination: !GetAtt StreamDLQ.Arn

  StreamDLQ:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600
```

`sam local start-api` for laptop. `sam pipeline bootstrap` for CI. Prefer **SAM Policy Templates** over `AdministratorAccess`.

CDK equivalent: `lambda.Function` + `apigwv2` + `table.grantWriteData(fn)`. Use the catalog constructs from Chapter 52.

---

## 58.7 Idempotency, retries, and DLQs

| Invocation | Retry | You must |
|------------|-------|----------|
| Sync (API) | Client retries | Idempotency key on writes |
| Async Lambda | 2 retries then DLQ/destination | Idempotent handler |
| SQS | Until max receive | Partial batch failure reporting |
| Streams | Whole batch retry | Bisect + DLQ |

```python
# partial batch for SQS
def handler(event, context):
    failures = []
    for rec in event["Records"]:
        try:
            process(rec)
        except Exception:
            failures.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": failures}
```

Enable `ReportBatchItemFailures` on the event source mapping.

Idempotency: Powertools for AWS Lambda `Idempotency` table, or put `Idempotency-Key` as DynamoDB PK with a condition `attribute_not_exists`.

---

## 58.8 Observability for serverless

- **JSON logs**, one object per line, `correlation_id` from API GW request id.
- **EMF** (embedded metric format) for custom metrics without a PutMetricData storm.
- **X-Ray** or Powertools tracing; sample 1%–10% in prod, 100% in staging.
- **Alarms:** errors, throttles, duration p99, iterator age (streams), DLQ depth, API 5xx, API latency.
- **Lambda Insights** for memory/CPU.

Iterator age growing means the stream consumer cannot keep up — scale, optimize, or shard.

---

## 58.9 Cold path: Step Functions

When the API must kick a 20-minute workflow: API returns 202 with `executionArn`; client polls or WebSocket. Express workflows for high-volume short; Standard for long/wait/human.

Do not orchestrate with nested Lambda waits.

---

## 58.10 Networking extras for Lambda

- **Hyperplane ENIs** are reused; still pick **private subnets** with endpoints: `execute-api` (if calling APIs), `logs`, `kms`, `secretsmanager`, `dynamodb` (gateway), `s3` (gateway).
- **RDS:** RDS Proxy mandatory.
- **IPv6:** dual-stack Lambda in VPC is available in many Regions — prefer it to NAT for egress if your path supports it.
- Function URLs: Auth `AWS_IAM` or `NONE` (only with CloudFront + WAF in front if public). Prefer API Gateway for JWT and stages.

---

## 58.11 SAM vs CDK vs Terraform vs Console

| Tool | Serverless fit |
|------|----------------|
| SAM | Fast Lambda+API, local, pipeline |
| CDK | Strong when mixed with VPC/ECS |
| Terraform | Multi-cloud teams |
| Console | Learning only; no PR |

---

## 58.12 Lab A — HTTP API + DynamoDB + stream to EventBridge

**Goal:** `POST /orders` stores an item; stream function emits `OrderPlaced` on the default bus; a rule logs to CloudWatch.

1. `sam init` (hello-world Python) then replace with the template skeleton above.
2. Implement `put_order` with `PutItem` and idempotency key header.
3. `sam build && sam deploy --guided` in sandbox.
4. `curl -X POST $API/orders -d '{"id":"o1"}'`.
5. Check DynamoDB item, stream Lambda logs, EventBridge rule target (CloudWatch log group).
6. Force a poison stream record (bad JSON) and confirm DLQ.

**Success criteria:** One order produces one event; retries do not create duplicate customer emails (use idempotency on the notification side).

---

## 58.13 Lab B — reserved concurrency starvation

**Goal:** Feel 429s.

1. Two functions, account concurrency small if you can (don't change prod quotas).
2. Function A reserved = 2, Function B unreserved floods.
3. Sync invoke A in a loop; then flood B; observe whether A is protected.
4. Remove reserve from A; flood B; A throttles.

**Success criteria:** You can explain reserved concurrency as both a floor and a ceiling.

---

## 58.14 Lab C — API Gateway JWT

1. Stand up a Cognito user pool or use a test JWT issuer.
2. HTTP API JWT authorizer with issuer and audience.
3. Call without token → 401; with token → 200.
4. Enable access logging to CloudWatch; confirm `$context.authorizer` fields.

---

## 58.15 Cost knobs

| Knob | Effect |
|------|--------|
| Arm64 | Often cheaper |
| Memory (which also scales CPU) | Tune with Lambda Power Tuning |
| HTTP API vs REST | HTTP cheaper |
| Provisioned concurrency | Always-on tax |
| On-demand DynamoDB | Fine until steady high RPS — then provisioned |
| NAT vs endpoints | Endpoints often cheaper at volume |
| Log retention 3 days vs forever | Real money |

---

## 58.16 Security checklist

- [ ] Least privilege policy templates
- [ ] No `*` on `dynamodb:PutItem` across all tables
- [ ] Encryption at rest CMK if required
- [ ] PII not in logs
- [ ] WAF on public APIs
- [ ] Resource policy on functions (no `lambda:InvokeFunction` from `*`)
- [ ] Secrets not in env
- [ ] CORS not `*` if credentials

---

## 58.17 Comparison: AppSync vs API Gateway

| | AppSync | API GW + Lambda |
|--|---------|-----------------|
| GraphQL | Native | DIY |
| Subscriptions | Built-in | WebSocket API work |
| DynamoDB resolvers | VTL/JS resolvers without Lambda | Lambda |
| Team skill | GraphQL | REST |

Pick AppSync when GraphQL is the product. Don't use it as "magic DynamoDB" if the team only knows REST.

---

## 58.18 Failure injection

Use FIS or simply:

- PutItem throttle: consume capacity on purpose.
- Kill the stream function: watch iterator age.
- EventBridge rule disabled: archive still fills if configured.
- Authorizer timeout: API 500s.

Write the alarms **before** the demo to leadership.

---

## 58.19 Interview talking points

"We front Lambda with HTTP API, JWT from Cognito, DynamoDB single-key gets, EventBridge for domain events, SQS for burst, SAM in CI with policy templates, X-Ray + Insights, reserved concurrency on checkout, DLQ on every async path, and no Lambda-to-Lambda."

That sentence scores well if you can defend each clause.

---

## 58.19.1 Powertools and structured handlers

Use [Powertools for AWS Lambda](https://docs.powertools.aws.dev/) (or equivalent) rather than ad-hoc logging wrappers. The Tracer, Logger, Metrics, and Idempotency utilities encode the operational contracts in this chapter. A typical Python handler:

```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer, idempotent_function,
)

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayHttpResolver()
persistence = DynamoDBPersistenceLayer(table_name="idempotency")

@app.post("/orders")
@idempotent_function(persistence_store=persistence, data_keyword_argument="body")
def put_order(body: dict):
    logger.append_keys(order_id=body["id"])
    # write DynamoDB
    metrics.add_metric(name="OrderPlaced", unit="Count", value=1)
    return {"id": body["id"]}, 201

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event, context):
    return app.resolve(event, context)
```

Idempotency keys should come from the client (`Idempotency-Key` header) or from a natural business key. Do not hash the entire body if optional fields change between retries.

---

## 58.20 Chapter checklist

- [ ] Can draw sync vs async vs stream paths.
- [ ] Know API GW timeout vs Lambda timeout.
- [ ] DynamoDB access patterns written before table.
- [ ] DLQ and idempotency on writes.
- [ ] SAM template reviewed for IAM.
- [ ] Labs A and B done.

Chapter 59 is the troubleshooting cookbook that starts when this architecture returns 5xx at 02:00.
