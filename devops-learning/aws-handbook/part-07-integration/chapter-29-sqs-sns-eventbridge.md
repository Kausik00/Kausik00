# Chapter 29: SQS, SNS, and EventBridge

*AWS Handbook — Pages 143–148 of this PDF edition*
---

## 29.1 Event-driven architecture on AWS

Modern applications decouple components using asynchronous messaging. AWS provides three core services for event-driven patterns:

| Service | Pattern | Delivery |
|---------|---------|----------|
| **SQS** | Message queuing | Pull-based; consumer polls |
| **SNS** | Pub/sub fan-out | Push-based; subscribers receive |
| **EventBridge** | Event bus routing | Push-based; rules route events |

Understanding when to use each—and how to combine them—is fundamental to building scalable, resilient systems.

---

## 29.2 Amazon SQS

**Simple Queue Service (SQS)** is a fully managed message queue. Producers send messages; consumers poll and process them.

### Queue types

| Type | Throughput | Delivery | Use case |
|------|------------|----------|----------|
| **Standard** | Unlimited | At-least-once; best-effort ordering | Most workloads |
| **FIFO** | 3,000 msg/s (with batching: 30,000) | Exactly-once; strict ordering | Order processing, financial transactions |

### Key concepts

| Concept | Description |
|---------|-------------|
| **Message** | Up to 256 KB (larger via S3 pointer) |
| **Visibility timeout** | Message hidden after receive; must delete or it reappears |
| **Retention** | 1 minute to 14 days (default 4 days) |
| **Dead letter queue (DLQ)** | Captures messages that fail processing repeatedly |
| **Long polling** | Wait up to 20 seconds for messages (reduces empty receives) |

### Standard queue workflow

```
Producer → SQS Queue → Consumer polls → Process → Delete message
                              │
                    (fail after N retries)
                              ▼
                           DLQ
```

### Terraform

```hcl
resource "aws_sqs_queue" "dlq" {
  name = "orders-dlq"
}

resource "aws_sqs_queue" "orders" {
  name                       = "orders-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600  # 14 days
  receive_wait_time_seconds  = 20       # long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}
```

### Lambda + SQS integration

```hcl
resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn = aws_sqs_queue.orders.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
  maximum_batching_window_in_seconds = 5

  scaling_config {
    maximum_concurrency = 50
  }
}
```

### CLI

```bash
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders-queue \
  --message-body '{"orderId": "12345", "action": "process"}'

aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders-queue \
  --wait-time-seconds 20 \
  --max-number-of-messages 10
```

---

## 29.3 Amazon SNS

**Simple Notification Service (SNS)** is a pub/sub messaging service. Publishers send messages to a **topic**; subscribers (SQS, Lambda, HTTP, email, SMS) receive copies.

### SNS + SQS fan-out pattern

```
                    ┌── SQS Queue A → Lambda (process orders)
Publisher → SNS Topic ├── SQS Queue B → Lambda (send email)
                    └── SQS Queue C → Lambda (update analytics)
```

Benefits:
- Decouple publisher from consumers.
- Each consumer processes at its own pace.
- Add/remove consumers without changing the publisher.

```hcl
resource "aws_sns_topic" "orders" {
  name = "order-events"
}

resource "aws_sns_topic_subscription" "email_queue" {
  topic_arn = aws_sns_topic.orders.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.email.arn
}

resource "aws_sqs_queue_policy" "email" {
  queue_url = aws_sqs_queue.email.id
  policy = jsonencode({
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.email.arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_sns_topic.orders.arn }
      }
    }]
  })
}
```

### Message filtering

SNS subscription filter policies route only matching messages:

```json
{
  "eventType": ["order.created", "order.updated"],
  "amount": [{ "numeric": [">", 100] }]
}
```

---

## 29.4 Amazon EventBridge

**EventBridge** is a serverless event bus that routes events from AWS services, SaaS applications, and custom applications.

### Event buses

| Bus | Events |
|-----|--------|
| **Default** | All AWS service events in the account |
| **Custom** | Application-specific events |
| **Partner** | SaaS events (Zendesk, Auth0, etc.) |

### Rules and targets

```
Event source → Rule (pattern match) → Target(s)
                                        ├── Lambda
                                        ├── SQS
                                        ├── SNS
                                        ├── Step Functions
                                        ├── API Gateway
                                        └── 20+ other targets
```

### Event pattern example

```json
{
  "source": ["aws.ec2"],
  "detail-type": ["EC2 Instance State-change Notification"],
  "detail": {
    "state": ["stopped", "terminated"]
  }
}
```

### Terraform

```hcl
resource "aws_cloudwatch_event_rule" "ec2_state" {
  name        = "ec2-state-change"
  description = "Capture EC2 state changes"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
    detail = {
      state = ["stopped", "terminated"]
    }
  })
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.ec2_state.name
  target_id = "notify-slack"
  arn       = aws_lambda_function.notify.arn
}

resource "aws_cloudwatch_event_bus" "app" {
  name = "app-events"
}

resource "aws_cloudwatch_event_rule" "order_created" {
  name           = "order-created"
  event_bus_name = aws_cloudwatch_event_bus.app.name

  event_pattern = jsonencode({
    source      = ["app.orders"]
    detail-type = ["OrderCreated"]
  })
}
```

### Custom events

```python
import boto3, json

events = boto3.client("events")
events.put_events(Entries=[{
    "Source": "app.orders",
    "DetailType": "OrderCreated",
    "Detail": json.dumps({"orderId": "12345", "amount": 99.99}),
    "EventBusName": "app-events",
}])
```

---

## 29.5 Choosing the right service

| Scenario | Service |
|----------|---------|
| Decouple two services; consumer polls | SQS |
| Fan-out to multiple consumers | SNS (+ SQS for each) |
| React to AWS service events | EventBridge |
| Custom application events with routing rules | EventBridge |
| Guaranteed ordering | SQS FIFO |
| Exactly-once processing | SQS FIFO |
| Cross-account event routing | EventBridge |
| Real-time push to HTTP endpoints | SNS (HTTP subscription) |
| Scheduled events | EventBridge Scheduler |

### EventBridge vs SNS

| Feature | EventBridge | SNS |
|---------|-------------|-----|
| Event filtering | Content-based rules | Subscription filter policies |
| Targets per rule | 5 (default) | Many subscribers per topic |
| Schema registry | Yes | No |
| Archive and replay | Yes | No |
| Cross-account | Native | Via topic policy |
| Delivery | At-least-once | At-least-once |

---

## 29.6 Error handling patterns

### SQS retry with DLQ

```
Receive → Process (fail) → Visibility timeout expires → Re-deliver
  → Fail 3 times → Move to DLQ → Alert + manual review
```

### SNS retry

SNS retries failed deliveries to HTTP/Lambda targets with exponential backoff. Configure DLQ on the subscription for persistent failures.

### EventBridge retry

EventBridge retries failed target invocations for 24 hours with exponential backoff. Configure DLQ or retry policy per target.

---

## 29.7 Monitoring

| Service | Key metrics |
|---------|-------------|
| **SQS** | `ApproximateNumberOfMessagesVisible`, `ApproximateAgeOfOldestMessage` |
| **SNS** | `NumberOfMessagesPublished`, `NumberOfNotificationsFailed` |
| **EventBridge** | `FailedInvocations`, `Invocations`, `ThrottledRules` |

Alarm on DLQ message count > 0 and `ApproximateAgeOfOldestMessage` > threshold (processing lag).

---

## 29.8 Chapter summary

- **SQS** provides reliable message queuing with standard and FIFO options.
- **SNS** enables pub/sub fan-out to multiple subscribers.
- **EventBridge** routes events from AWS services and custom applications with content-based filtering.
- Combine **SNS + SQS** for fan-out with independent consumer scaling.
- Configure **DLQs** and monitor queue depth and message age.

---

## 🧪 Lab 29.1 — Order processing pipeline

1. Create an SNS topic for order events.
2. Subscribe two SQS queues (email notifications, inventory update).
3. Publish order events and verify both queues receive messages.
4. Process messages with Lambda and configure DLQs.

## 🧪 Lab 29.2 — EventBridge automation

1. Create a rule that triggers on S3 `ObjectCreated` events.
2. Route matching events to a Lambda that processes uploaded files.
3. Create a custom event bus and publish application events.
4. Archive events and replay from a specific timestamp.

---

## Review questions

1. What is the difference between SQS standard and FIFO queues?
2. How does the SNS + SQS fan-out pattern work?
3. When would you use EventBridge instead of SNS?
4. What is a dead letter queue and when should you configure one?
5. What does the SQS visibility timeout control?

---

*Next: [Chapter 30 — Step Functions](./chapter-30-step-functions.md)*
