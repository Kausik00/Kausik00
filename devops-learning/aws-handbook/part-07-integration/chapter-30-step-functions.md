# Chapter 30: Step Functions Workflows

*AWS Handbook — Pages 150–155 of this PDF edition*
---

## 30.1 What are Step Functions?

**AWS Step Functions** is a serverless orchestration service that coordinates multiple AWS services into visual workflows. Instead of writing complex retry/error logic in application code, you define workflows as state machines that handle sequencing, parallel execution, error handling, and human approval steps.

Step Functions is ideal for order processing, ETL pipelines, ML workflows, and multi-step business processes.

---

## 30.2 Workflow types

| Type | Language | Use case |
|------|----------|----------|
| **Standard** | Amazon States Language (JSON/YAML) | Long-running (up to 1 year), exactly-once |
| **Express** | ASL | High-volume, short-duration (< 5 min), at-least-once |

### Standard vs Express

| Feature | Standard | Express |
|---------|----------|---------|
| Duration | Up to 1 year | Up to 5 minutes |
| Execution model | Exactly-once | At-least-once |
| Pricing | Per state transition | Per execution + duration |
| Use case | Business workflows, ETL | IoT, streaming, high-throughput |

---

## 30.3 State types

| State | Purpose |
|-------|---------|
| **Task** | Execute work (Lambda, ECS, DynamoDB, etc.) |
| **Choice** | Branch based on conditions |
| **Parallel** | Execute branches concurrently |
| **Map** | Iterate over array items (dynamic parallelism) |
| **Wait** | Delay for fixed time or until timestamp |
| **Pass** | Pass input to output (transform) |
| **Succeed** | Terminal success |
| **Fail** | Terminal failure |

---

## 30.4 Example: Order processing workflow

```
Start → ValidateOrder → Choice (valid?)
                           ├── Yes → ProcessPayment → Choice (paid?)
                           │                              ├── Yes → FulfillOrder → Succeed
                           │                              └── No → NotifyFailure → Fail
                           └── No → NotifyInvalid → Fail
```

### ASL definition

```json
{
  "Comment": "Order processing workflow",
  "StartAt": "ValidateOrder",
  "States": {
    "ValidateOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:validate-order",
      "Next": "IsOrderValid",
      "Retry": [{
        "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2
      }],
      "Catch": [{
        "ErrorEquals": ["ValidationError"],
        "Next": "NotifyInvalid"
      }]
    },
    "IsOrderValid": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.valid",
        "BooleanEquals": true,
        "Next": "ProcessPayment"
      }],
      "Default": "NotifyInvalid"
    },
    "ProcessPayment": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "process-payment",
        "Payload.$": "$"
      },
      "ResultPath": "$.payment",
      "Next": "IsPaymentSuccessful"
    },
    "IsPaymentSuccessful": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.payment.Payload.success",
        "BooleanEquals": true,
        "Next": "FulfillOrder"
      }],
      "Default": "NotifyFailure"
    },
    "FulfillOrder": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/fulfillment",
        "MessageBody": {
          "orderId.$": "$.orderId",
          "taskToken.$": "$$.Task.Token"
        }
      },
      "End": true
    },
    "NotifyInvalid": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:notify-invalid",
      "Next": "OrderFailed"
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:notify-failure",
      "Next": "OrderFailed"
    },
    "OrderFailed": {
      "Type": "Fail",
      "Error": "OrderProcessingFailed",
      "Cause": "Order could not be processed"
    }
  }
}
```

---

## 30.5 Service integrations

Step Functions integrates with 220+ AWS services via **optimized integrations** (no Lambda wrapper needed):

| Integration pattern | Example |
|--------------------|---------|
| **Request Response** | Invoke Lambda, call DynamoDB GetItem |
| **Run a Job** | Submit Batch job, start ECS task, start Glue job |
| **Wait for Callback** | Send SQS message with task token; resume when callback received |

### Direct DynamoDB integration

```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::dynamodb:putItem",
  "Parameters": {
    "TableName": "Orders",
    "Item": {
      "OrderId": { "S.$": "$.orderId" },
      "Status": { "S": "PROCESSING" },
      "Amount": { "N.$": "$.amount" }
    }
  },
  "Next": "ProcessPayment"
}
```

### ECS/Fargate task

```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::ecs:runTask.sync",
  "Parameters": {
    "LaunchType": "FARGATE",
    "Cluster": "processing-cluster",
    "TaskDefinition": "data-processor",
    "NetworkConfiguration": {
      "AwsvpcConfiguration": {
        "Subnets": ["subnet-aaa", "subnet-bbb"],
        "SecurityGroups": ["sg-processor"]
      }
    }
  },
  "Next": "CheckResults"
}
```

---

## 30.6 Error handling

### Retry

```json
"Retry": [{
  "ErrorEquals": ["States.TaskFailed"],
  "IntervalSeconds": 1,
  "MaxAttempts": 3,
  "BackoffRate": 2.0,
  "JitterStrategy": "FULL"
}]
```

### Catch

```json
"Catch": [{
  "ErrorEquals": ["PaymentDeclined"],
  "ResultPath": "$.error",
  "Next": "HandlePaymentFailure"
}]
```

### Error types

| Error | Source |
|-------|--------|
| `States.Timeout` | Task exceeded timeout |
| `States.TaskFailed` | Task returned error |
| `States.Permissions` | IAM permission denied |
| Custom errors | Application-defined (via `Fail` state or Lambda throw) |

---

## 30.7 Parallel and Map states

### Parallel

Execute multiple branches simultaneously:

```json
{
  "Type": "Parallel",
  "Branches": [
    { "StartAt": "SendEmail", "States": { "SendEmail": { "Type": "Task", "Resource": "...", "End": true } } },
    { "StartAt": "UpdateInventory", "States": { "UpdateInventory": { "Type": "Task", "Resource": "...", "End": true } } },
    { "StartAt": "LogAnalytics", "States": { "LogAnalytics": { "Type": "Task", "Resource": "...", "End": true } } }
  ],
  "Next": "OrderComplete"
}
```

### Map (dynamic parallelism)

Process each item in an array concurrently:

```json
{
  "Type": "Map",
  "ItemsPath": "$.orders",
  "MaxConcurrency": 10,
  "Iterator": {
    "StartAt": "ProcessSingleOrder",
    "States": {
      "ProcessSingleOrder": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:function:process-order",
        "End": true
      }
    }
  },
  "Next": "AllOrdersProcessed"
}
```

**Distributed Map** (newer) supports large-scale processing with S3 item sources and child executions.

---

## 30.8 Terraform

```hcl
resource "aws_sfn_state_machine" "order_processing" {
  name     = "order-processing"
  role_arn = aws_iam_role.step_functions.arn

  definition = templatefile("${path.module}/state-machine.json", {
    validate_lambda_arn = aws_lambda_function.validate.arn
    payment_lambda_arn  = aws_lambda_function.payment.arn
  })

  logging_configuration {
    level                  = "ALL"
    include_execution_data = true
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
  }

  tracing_configuration {
    enabled = true
  }
}
```

---

## 30.9 Monitoring and debugging

| Tool | Purpose |
|------|---------|
| **Execution history** | Visual trace of each state transition |
| **CloudWatch Logs** | Detailed execution data |
| **X-Ray** | Distributed tracing across services |
| **CloudWatch Metrics** | ExecutionsStarted, ExecutionsFailed, ExecutionTime |

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:order-processing \
  --input '{"orderId": "12345", "amount": 99.99}'

aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:123456789012:execution:order-processing:abc123
```

---

## 30.10 Chapter summary

- **Step Functions** orchestrates multi-step workflows with built-in error handling and retries.
- **Standard workflows** for long-running processes; **Express** for high-volume, short tasks.
- Use **service integrations** to call AWS services directly without Lambda wrappers.
- **Map** and **Parallel** states enable dynamic and static concurrency.
- Monitor with execution history, CloudWatch Logs, and X-Ray tracing.

---

## 🧪 Lab 30.1 — Order workflow

1. Create a Step Functions state machine with validate → pay → fulfill steps.
2. Implement Lambda functions for each step.
3. Test successful and failed order paths.
4. Add retry logic for transient failures.

## 🧪 Lab 30.2 — Parallel processing

1. Create a Map state that processes an array of 10 items concurrently.
2. Set `MaxConcurrency` to 3 and observe throttled execution.
3. Review execution history in the Step Functions console.

---

## Review questions

1. What is the difference between Standard and Express workflows?
2. How do Retry and Catch differ in Step Functions error handling?
3. What is the purpose of the Map state?
4. How does the "wait for callback" pattern work with task tokens?
5. When would you use a direct service integration vs a Lambda task?

---

*Next: [Chapter 31 — CloudFormation](../part-08-devops/chapter-31-cloudformation.md)*
