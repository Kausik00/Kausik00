# Chapter 17: Lambda — Events, Concurrency, and Layers

*AWS Handbook — Pages 77–82 of this PDF edition*
---

## 17.1 What is AWS Lambda?

**AWS Lambda** is a serverless compute service that runs code in response to events without provisioning or managing servers. You upload your function code, configure triggers, and AWS handles scaling, patching, and availability. You pay only for compute time consumed (per millisecond) and number of requests.

Lambda is ideal for event-driven workloads: API backends, data processing, scheduled tasks, and microservices glue.

---

## 17.2 Lambda fundamentals

| Concept | Description |
|---------|-------------|
| **Function** | Your code + runtime + configuration |
| **Handler** | Entry point (e.g., `index.handler`) |
| **Runtime** | Language environment (Python 3.12, Node.js 20, etc.) |
| **Trigger** | Event source that invokes the function |
| **Execution role** | IAM role granting AWS service permissions |
| **Deployment package** | .zip or container image (up to 10 GB for containers) |

### Limits (selected)

| Resource | Limit |
|----------|-------|
| Memory | 128 MB – 10,240 MB (CPU scales with memory) |
| Timeout | 900 seconds (15 minutes) |
| Deployment package (zip) | 50 MB (direct upload), 250 MB (S3) |
| Environment variables | 4 KB total |
| /tmp storage | 512 MB – 10,240 MB |
| Concurrent executions (default) | 1,000 per region (can increase) |

---

## 17.3 Creating a Lambda function

### AWS CLI

```bash
# Create execution role
aws iam create-role \
  --role-name lambda-basic-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name lambda-basic-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create function
aws lambda create-function \
  --function-name hello-world \
  --runtime python3.12 \
  --handler index.handler \
  --role arn:aws:iam::123456789012:role/lambda-basic-role \
  --zip-file fileb://function.zip
```

### Python handler example

```python
import json

def handler(event, context):
    name = event.get("name", "World")
    return {
        "statusCode": 200,
        "body": json.dumps(f"Hello, {name}!"),
    }
```

### Terraform

```hcl
resource "aws_lambda_function" "api" {
  function_name = "api-handler"
  runtime       = "python3.12"
  handler       = "app.handler"
  role          = aws_iam_role.lambda.arn
  filename      = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")

  memory_size = 256
  timeout     = 30

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.items.name
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
}
```

---

## 17.4 Event sources and triggers

Lambda integrates with 200+ AWS services and custom applications:

| Trigger | Pattern |
|---------|---------|
| **API Gateway** | HTTP API requests |
| **S3** | Object created/deleted events |
| **SQS** | Message queue processing |
| **SNS** | Pub/sub notifications |
| **EventBridge** | Event bus rules |
| **DynamoDB Streams** | Change data capture |
| **Kinesis** | Stream record processing |
| **CloudWatch Events** | Scheduled (cron) execution |
| **ALB** | HTTP requests to Lambda targets |

### S3 trigger example

```hcl
resource "aws_s3_bucket_notification" "trigger" {
  bucket = aws_s3_bucket.uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ".csv"
  }
}
```

### Scheduled execution

```hcl
resource "aws_cloudwatch_event_rule" "daily" {
  name                = "daily-cleanup"
  schedule_expression = "cron(0 6 * * ? *)"  # 6 AM UTC daily
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "cleanup"
  arn       = aws_lambda_function.cleanup.arn
}
```

---

## 17.5 Concurrency

**Concurrency** is the number of simultaneous executions of your function.

### Types

| Type | Description |
|------|-------------|
| **Unreserved** | Shared pool; competes with other functions |
| **Reserved** | Guaranteed concurrency for a specific function |
| **Provisioned** | Pre-warmed execution environments (no cold start) |

### Concurrency formula

```
Account concurrency limit = 1,000 (default, per region)
Reserved concurrency for function X = 100
Unreserved pool = 1,000 - sum(all reserved)
```

### Reserved concurrency

```bash
aws lambda put-function-concurrency \
  --function-name api-handler \
  --reserved-concurrent-executions 50
```

**Use reserved concurrency to:**
- Guarantee capacity for critical functions.
- Limit maximum concurrency (acts as a throttle).
- Prevent one function from consuming all account concurrency.

### Provisioned concurrency

Eliminates cold starts by keeping execution environments warm:

```bash
aws lambda put-provisioned-concurrency-config \
  --function-name api-handler \
  --provisioned-concurrent-executions 10 \
  --qualifier live
```

Costs: provisioned concurrency is billed even when idle. Use for latency-sensitive APIs.

---

## 17.6 Cold starts and performance

A **cold start** occurs when Lambda creates a new execution environment:

| Factor | Impact |
|--------|--------|
| Runtime | Java/.NET slower than Python/Node.js |
| Package size | Larger = slower init |
| VPC | Adds ENI creation time (improved with Hyperplane) |
| Provisioned concurrency | Eliminates cold starts |

### Optimization tips

- Keep deployment packages small; use **Lambda layers** for dependencies.
- Initialize SDK clients **outside** the handler (reused across invocations).
- Use **ARM64 (Graviton2)** for 20% better price-performance.
- Choose the right memory (more memory = more CPU = potentially faster).
- Use **SnapStart** for Java functions.

---

## 17.7 Lambda layers

**Layers** package libraries, custom runtimes, or other dependencies separately from your function code:

```
Function code (handler.py) + Layer (boto3, pandas, numpy) = Deployment
```

### Benefits

- Share dependencies across multiple functions.
- Keep deployment packages small.
- Separate dependency updates from function code changes.

### Creating a layer

```bash
mkdir -p python/lib/python3.12/site-packages
pip install requests -t python/lib/python3.12/site-packages/
zip -r layer.zip python

aws lambda publish-layer-version \
  --layer-name python-requests \
  --zip-file fileb://layer.zip \
  --compatible-runtimes python3.12
```

### Attaching a layer

```hcl
resource "aws_lambda_function" "api" {
  # ...
  layers = [
    aws_lambda_layer_version.deps.arn,
    "arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-requests:1"  # public layer
  ]
}
```

---

## 17.8 Lambda in a VPC

Place Lambda in a VPC to access private resources (RDS, ElastiCache, internal APIs):

```hcl
vpc_config {
  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.lambda.id]
}
```

**Requirements:**
- Subnets must have routes to the resource (not necessarily NAT for VPC-internal traffic).
- Security groups on Lambda and target must allow communication.
- Hyperplane ENIs reduce cold start penalty but still add some latency.

---

## 17.9 Error handling and retries

| Trigger type | Retry behavior |
|--------------|----------------|
| Synchronous (API GW, ALB) | Caller handles retry |
| Asynchronous (S3, SNS, EventBridge) | 2 automatic retries, then DLQ |
| Stream (Kinesis, DynamoDB) | Retry until data expires; bisect on failure |
| SQS | Retry based on visibility timeout; DLQ after max receives |

### Dead letter queue (DLQ)

```hcl
resource "aws_lambda_function_event_invoke_config" "api" {
  function_name = aws_lambda_function.api.function_name

  destination_config {
    on_failure {
      destination = aws_sqs_queue.dlq.arn
    }
  }
}
```

---

## 17.10 Monitoring

| Tool | Purpose |
|------|---------|
| **CloudWatch Metrics** | Invocations, Duration, Errors, Throttles, ConcurrentExecutions |
| **CloudWatch Logs** | Function stdout/stderr (auto-created log group) |
| **X-Ray** | Distributed tracing (enable active tracing) |
| **Lambda Insights** | Enhanced metrics (init duration, memory usage) |

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/api-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s000)
```

---

## 17.11 Chapter summary

- **Lambda** runs event-driven code without server management; pay per invocation and duration.
- **Triggers** connect Lambda to 200+ event sources (API Gateway, S3, SQS, schedules).
- **Concurrency** controls — reserved (guarantee/limit), provisioned (no cold start).
- **Layers** separate dependencies from function code for reuse and smaller packages.
- Configure **DLQs**, **VPC access**, and **monitoring** for production reliability.

---

## 🧪 Lab 17.1 — S3-triggered processor

1. Create a Lambda function that processes CSV files uploaded to S3.
2. Configure an S3 event trigger for `uploads/*.csv`.
3. Upload a test CSV and verify the function logs and processes it.
4. Add error handling and a DLQ for failures.

## 🧪 Lab 17.2 — API with provisioned concurrency

1. Create a Lambda function behind API Gateway HTTP API.
2. Measure cold start latency with `curl -w "%{time_total}"`.
3. Enable provisioned concurrency (5) and measure again.
4. Compare p50 and p99 latency.

---

## Review questions

1. What is the maximum Lambda timeout, and when would you need it?
2. How does reserved concurrency differ from provisioned concurrency?
3. Why should SDK clients be initialized outside the handler function?
4. What happens to failed asynchronous invocations after retries are exhausted?
5. What are the trade-offs of running Lambda in a VPC?

---

*Next: [Chapter 18 — ECS & Fargate](./chapter-18-ecs-fargate.md)*
