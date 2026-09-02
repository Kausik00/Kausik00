# Chapter 45: Lambda Event Patterns

*AWS Handbook — Pages 239–245 of this PDF edition*

AWS Lambda is a compute primitive that runs your function in response to events. This workbook is about *those events*: how they arrive, how they retry, how they poison a queue, how concurrency turns into throttling, and how Terraform should express the wiring so you do not debug mappings in the console at 03:00. Chapter 17 covered the runtime. Here you design the system around the function.

---

## 45.1 Choose Lambda when the event is the product

Lambda fits work that is:

- Triggered by a discrete event (object created, API call, schedule, stream record)
- Able to finish within the timeout (max 15 minutes)
- Comfortable with ephemeral disk (`/tmp`) and no inbound long-lived TCP server of your own
- Scaled to zero or to thousands of parallel invocations

It is a poor fit for:

- Sticky in-memory caches you cannot rebuild
- Multi-hour batch without chunking (use Step Functions, ECS, or Batch)
- Hard real-time sub-millisecond loops
- Workloads that need dedicated GPUs in a custom topology (look at specialized services)

| Pattern | Typical source | Success look |
|---------|----------------|--------------|
| Synchronous request/response | API Gateway, ALB, Function URL, SDK `Invoke` | Caller sees result or mapped HTTP error |
| Asynchronous | S3, SNS, EventBridge, `InvocationType=Event` | Event is accepted; Lambda retries then DLQ/on-failure |
| Stream/poller | SQS, Kinesis, DynamoDB Streams, MSK, MQ | Event source mapping owns the cursor |
| Orchestrated | Step Functions | State machine retries and compensation |

These four have *different* retry semantics. Mixing them in your head is how you double-charge a customer or lose a file notification.

---

## 45.2 Anatomy of an event source mapping (ESM)

For SQS, Kinesis, DynamoDB Streams, and similar, Lambda *polls*. You configure batch size, batching window, filters, starting position, and failure destination.

```bash
aws lambda create-event-source-mapping \
  --function-name orders-worker \
  --event-source-arn arn:aws:sqs:us-east-1:111122223333:orders \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5 \
  --function-response-types ReportBatchItemFailures
```

**ReportBatchItemFailures** is required for partial batch success on SQS. Without it, one bad record retries the whole batch and you amplify poison.

**Filters** reduce invocations:

```json
{
  "Filters": [{
    "Pattern": "{ \"body\": { \"type\": [ \"OrderPlaced\" ] } }"
  }]
}
```

Filter patterns use EventBridge-style matching. Invalid JSON in SQS bodies will not match; design producers to emit structured JSON.

---

## 45.3 Pattern: S3 → Lambda (async)

Use when an object landing should kick work (thumbnail, virus scan, metadata extract).

Pitfalls:

- Recursion: the function writes back to the same prefix that triggers it. Always write to a different prefix or bucket.
- Partial failures: S3 event notifications are not a durable work queue. For business-critical ingest, fan the S3 event into SQS first.
- Overwrite vs create: configure event types explicitly (`s3:ObjectCreated:*` includes multipart completion).

```hcl
resource "aws_s3_bucket_notification" "ingest" {
  bucket = aws_s3_bucket.landing.id
  queue {
    queue_arn = aws_sqs_queue.ingest.arn
    events    = ["s3:ObjectCreated:*"]
  }
}
```

Then ESM from SQS to Lambda. You gain visibility, delay, and a DLQ.

---

## 45.4 Pattern: API Gateway HTTP API → Lambda (sync)

Synchronous invoke. Timeout of the API (29 seconds classic REST; HTTP API similar order of magnitude) is lower than Lambda’s 15 minutes. Your function timeout must be less than the API timeout or the caller gets 503 while Lambda continues.

Map errors deliberately:

| Lambda behavior | API result if unmapped |
|-----------------|------------------------|
| Unhandled exception | 500 |
| Timeout | 503 / 502 depending on integration |
| `statusCode` in payload (proxy) | That HTTP status |

Use provisioned concurrency only when cold starts violate a latency SLO. Measure first. SnapStart (Java) is another lever.

IAM: the API needs `lambda:InvokeFunction` on the function alias, not `$LATEST` in production.

---

## 45.5 Pattern: SQS worker

Standard queue: at-least-once, best-effort order. FIFO: order per message group, lower throughput.

Visibility timeout must exceed the function timeout (AWS recommends at least six times the function timeout for retries, but the precise multiple depends on maxReceiveCount). If visibility expires while the function still runs, another invocation gets the same message — classic double processing. Make handlers **idempotent** (conditional writes, idempotency keys in DynamoDB).

```hcl
resource "aws_sqs_queue" "dlq" {
  name                      = "orders-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "orders" {
  name                       = "orders"
  visibility_timeout_seconds = 90
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}
```

Lambda timeout 15s, visibility 90s, maxReceiveCount 5 is a starting point, not a law. Alarm on DLQ `ApproximateNumberOfMessagesVisible`.

---

## 45.6 Pattern: EventBridge → Lambda

EventBridge is the routing layer: content-based filters, archive/replay, SaaS partners, scheduler.

```json
{
  "source": ["orders.api"],
  "detail-type": ["OrderPlaced"],
  "detail": {
    "amount": [{ "numeric": [">", 1000] }]
  }
}
```

Put an SQS queue between EventBridge and Lambda when you need a buffer or when multiple consumers must share the event. EventBridge to Lambda is async invoke with Lambda’s async retry (twice) unless you configure a destination.

**Destinations:** on failure, send to SQS, SNS, EventBridge, or another Lambda. Prefer SQS for operations.

---

## 45.7 Pattern: DynamoDB Streams / Kinesis

Shard iterator semantics: `TRIM_HORIZON` vs `LATEST` vs `AT_TIMESTAMP`. Production replays need `StartingPosition` and sometimes a new ESM.

Bisect on function error (Kinesis/DynamoDB) splits the batch to isolate a poison record. Combine with a failure destination.

Parallelization factor and the number of shards cap throughput. Lambda concurrency can stall a stream if the function is slow; watch `IteratorAge`.

---

## 45.8 Concurrency, throttling, and reserved capacity

Account concurrency is shared. One runaway function can starve others.

- **Reserved concurrency** guarantees a cap *and* a floor of capacity for that function (it also *limits* the function to that number).
- **Provisioned concurrency** keeps execution environments warm.
- **Per-function maximum** is how you protect downstream RDS from 1,000 parallel opens.

```bash
aws lambda put-function-concurrency --function-name orders-worker --reserved-concurrent-executions 25
```

Throttles appear as `429` to sync callers and as retries for async/ESM. CloudWatch `Throttles` and `ConcurrentExecutions` belong on every production dashboard.

VPC-attached functions no longer require a unique ENI per invocation (Hyperplane), but they still need subnet IP headroom and NAT or endpoints for AWS APIs. Cold starts can still include VPC overhead. Put Lambda in VPC only if it must reach private RFC1918 resources.

---

## 45.9 Versions, aliases, and weighted traffic

Publish versions. Point alias `live` at a version. Shift 10% of traffic to a new version:

```bash
aws lambda update-alias --function-name orders-worker --name live \
  --routing-config AdditionalVersionWeights='{"42":0.1}'
```

Provisioned concurrency attaches to an alias, not to `$LATEST`. CI should never invoke `$LATEST` in production.

---

## 45.10 Observability

- Structured JSON logs; one event per log line; include `correlationId` from the payload.
- Embedded Metric Format or Powertools for metrics (`ColdStart`, `BatchSize`, business counters).
- AWS X-Ray or OpenTelemetry: trace from API Gateway through Lambda to DynamoDB.
- Lambda Insights for memory and network when you are guessing at sizing.

Memory setting also scales CPU. A function that is “CPU bound at 128 MB” often becomes cheaper at 512 MB because it finishes faster. Use AWS Lambda Power Tuning.

---

## 45.11 IAM for functions

Execution role: logs, plus only the data plane it needs. Resource-based policy on the function allows the *source* to invoke:

```json
{
  "Effect": "Allow",
  "Principal": { "Service": "s3.amazonaws.com" },
  "Action": "lambda:InvokeFunction",
  "Resource": "arn:aws:lambda:us-east-1:111122223333:function:thumb",
  "Condition": {
    "ArnLike": { "AWS:SourceArn": "arn:aws:s3:::landing-prod" }
  }
}
```

Omit the condition and any bucket in your account (or worse patterns) can invoke you.

---

## 45.12 Terraform: queue worker

```hcl
resource "aws_lambda_function" "worker" {
  function_name = "orders-worker"
  role          = aws_iam_role.worker.arn
  runtime       = "python3.12"
  handler       = "app.handler"
  filename      = "worker.zip"
  timeout       = 15
  memory_size   = 512
  architectures = ["arm64"]
  tracing_config { mode = "Active" }
  dead_letter_config { target_arn = aws_sqs_queue.fn_dlq.arn } # async only; ESM uses ESM destinations
  environment { variables = { TABLE = aws_dynamodb_table.orders.name } }
}

resource "aws_lambda_event_source_mapping" "orders" {
  event_source_arn = aws_sqs_queue.orders.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 10
  function_response_types = ["ReportBatchItemFailures"]
}
```

Note: SQS event source mappings do not use the function-level `dead_letter_config`. That field is for asynchronous invokes. DLQ for SQS is on the *queue*.

---

## 45.13 Idempotency and poison pills

Store `Idempotency-Key` (or hash of the payload) in DynamoDB with a TTL. On replay, return the stored result.

Poison: a record that always throws. For SQS, `maxReceiveCount` plus DLQ. For streams, bisect plus on-failure destination plus a metric. Never infinite-retry a JSON parse error.

---

## 45.14 Lab 1 — S3 to SQS to Lambda

1. Create landing and processed buckets.
2. S3 notification to SQS; Lambda reads the object, writes a marker to processed, deletes nothing in landing.
3. Upload a file. Confirm one processed marker.
4. Intentionally throw on a specific key. Confirm DLQ after maxReceiveCount.
5. Fix the handler; replay from DLQ with a small script (`aws sqs receive-message` / `send-message` back to main).

---

## 45.15 Lab 2 — Concurrency vs RDS

1. Lambda opens a new RDS connection per invoke (the anti-pattern).
2. Burst 200 concurrent invokes. Watch RDS `DatabaseConnections`.
3. Add reserved concurrency = 10 and an RDS Proxy. Repeat.
4. Write the graph into your notes: this is why “serverless” still needs connection pooling.

---

## 45.16 Lab 3 — Alias canary

1. Publish v1 that returns `{ok: true, v: 1}`.
2. Alias `live` → v1. HTTP API integration uses the alias ARN.
3. Publish v2. Shift 10% traffic. Compare logs.
4. Complete the shift or roll back by pointing the alias to v1 with zero extra weights.

---

## 45.17 Failure catalog

| Symptom | Cause |
|---------|--------|
| Duplicate side effects | At-least-once + non-idempotent handler |
| Stuck SQS messages | Visibility < timeout; exception after side effect |
| IteratorAge climbing | Slow function, throttling, or downstream latency |
| Recursive billing spike | S3 trigger writes to same prefix |
| 503 from API | Function longer than API timeout |
| Cold start SLO miss | VPC + large package + tiny memory + Java without SnapStart |

---

## 45.18 Review questions

1. Why put SQS between S3 and Lambda for critical ingest?
2. What does `ReportBatchItemFailures` change?
3. Why must SQS visibility timeout exceed the function timeout?
4. Function `dead_letter_config` vs SQS redrive: which applies to ESM?
5. How does reserved concurrency both protect and starve a function?
6. Why must production invoke an alias rather than `$LATEST`?
7. What EventBridge feature lets you replay a bad hour after a bugfix?
8. How do you stop an S3→Lambda recursion loop?
9. Why is a 15-minute Lambda a bad API Gateway integration?
10. What metric tells you a Kinesis consumer is falling behind?

**Answers (brief):** (1) Durability, DLQ, fan-out, and control of retries. (2) Only failed item identifiers are retried, not the whole batch. (3) Otherwise another worker receives the in-flight message. (4) Redrive on the queue; function DLQ is async. (5) It caps the function and reserves that capacity from the account pool. (6) Versions are immutable; `$LATEST` mutates under you. (7) Archive and replay. (8) Different destination prefix/bucket and careful event types. (9) API timeout is ~29s; the caller is gone. (10) `IteratorAge`.

---

## 45.19 Packages, layers, and runtimes

Keep deployment packages small. A 250 MB zip that unpacks scientific libraries on every cold start is an ECS task pretending to be Lambda. Prefer container images on Lambda (up to the published image size limit) when the dependency set is large, or move the work to Fargate.

Layers are for shared instrumentation (OpenTelemetry, Powertools), not for dumping your entire `node_modules`. Layer versioning is independent of function versions; pin layer ARNs in Terraform.

**Runtime deprecation** is a calendar item. CloudWatch and Health events announce it. A workbook habit: quarterly `list-functions` grouped by runtime (Chapter 51 recipe 77 plus a query).

```bash
aws lambda list-functions --query 'Functions[].{Name:FunctionName,Runtime:Runtime,LastMod:LastModified}' --output table
```

**Ephemeral storage** (`/tmp`, configurable up to a large size) is useful for unzipping, not for durable files. **EFS** mounts work; they add VPC and burst-credit considerations. **RDS inside Lambda** without Proxy remains the most common self-inflicted outage.

**Powertools idempotency** (Python/Java/TypeScript) stores hashes in DynamoDB. Use it for payment and ticket APIs.

**Event source maximum concurrency** (SQS ESM) is another throttle besides reserved concurrency. Set it when the downstream is a database of 50 connections.

Worked retry story:

| Source | Default retry | Where to attach DLQ |
|--------|---------------|---------------------|
| Async invoke | 2 retries | Function destination or DLQ |
| SQS ESM | Until maxReceiveCount | Queue redrive |
| Kinesis ESM | Until record expires or you bisect/drop | On-failure destination |
| Sync API | None (caller retries) | Caller and API 5xx mapping |

Write this table in the service README. On-call should not guess.

---

**Cold start budget:** measure p99 INIT_DURATION from REPORT lines in CloudWatch Logs. If p99 cold start exceeds half your latency SLO, consider provisioned concurrency on the alias, SnapStart for Java, a smaller package, more memory, or not using Lambda for that path. Do not buy provisioned concurrency because a dashboard “looked spiky” once. Re-measure after every dependency bump.

---

---

## 45.20 What to do next

If the unit of deploy is a container with many processes, Chapter 46 takes the same event-driven discipline onto EKS: still think in health, IAM (IRSA), and backpressure, but the scheduler is Kubernetes.
