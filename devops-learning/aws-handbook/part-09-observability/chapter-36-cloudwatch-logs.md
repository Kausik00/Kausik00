# Chapter 36: CloudWatch Logs & Insights

*AWS Handbook — Part IX, Pages 721–735*

---

## 36.1 CloudWatch Logs overview

**Amazon CloudWatch Logs** centralizes log data from AWS services, applications, and on-premises servers. Every Lambda function, API Gateway stage, ECS task, and VPC Flow Log can stream to CloudWatch Logs for search, analysis, alerting, and long-term retention.

Effective log management is the foundation of operational troubleshooting and security investigation.

---

## 36.2 Log groups and streams

| Concept | Description |
|---------|-------------|
| **Log group** | Container for related log streams (e.g., `/aws/lambda/api-handler`) |
| **Log stream** | Sequence of events from a single source (e.g., one Lambda instance) |
| **Log event** | Single log entry with timestamp and message |
| **Retention** | 1 day to 10 years (default: never expire) |

### Common log group paths

| Service | Log group pattern |
|---------|-------------------|
| Lambda | `/aws/lambda/<function-name>` |
| API Gateway | `/aws/apigateway/<api-name>` |
| ECS | `/ecs/<task-definition>` |
| RDS | `/aws/rds/instance/<id>/error` |
| VPC Flow Logs | Custom name |
| CloudTrail | Custom name |

```bash
# Set retention policy
aws logs put-retention-policy \
  --log-group-name /aws/lambda/api-handler \
  --retention-in-days 30

# Create log group
aws logs create-log-group --log-group-name /app/production
```

---

## 36.3 Ingesting logs

### AWS service integration

Most AWS services send logs automatically when enabled:

```hcl
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/api-handler"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_lambda_function" "api" {
  # ...
  logging_config {
    log_format = "JSON"
    application_log_level = "INFO"
    system_log_level = "WARN"
  }
}
```

### CloudWatch Agent (EC2/on-premises)

```json
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/application.log",
            "log_group_name": "/app/production",
            "log_stream_name": "{instance_id}/application",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
```

### Subscription filters

Stream logs to Lambda, Kinesis, or Firehose for real-time processing:

```hcl
resource "aws_cloudwatch_log_subscription_filter" "errors" {
  name            = "error-filter"
  log_group_name  = aws_cloudwatch_log_group.app.name
  filter_pattern  = "ERROR"
  destination_arn = aws_lambda_function.alert.arn
}
```

---

## 36.4 CloudWatch Logs Insights

**Logs Insights** is a purpose-built query language for analyzing log data at scale without provisioning servers.

### Query syntax

```
fields @timestamp, @message, @logStream
| filter @message like /ERROR/
| sort @timestamp desc
| limit 50
```

### Common queries

**Error rate by function (Lambda):**

```
fields @timestamp, @message
| filter @message like /ERROR|Exception|error/
| stats count() as errorCount by bin(5m)
```

**Slow API requests:**

```
fields @timestamp, @message
| filter @type = "REPORT"
| filter @duration > 1000
| sort @duration desc
| limit 20
```

**Top IP addresses (VPC Flow Logs):**

```
fields srcAddr, dstAddr, bytes
| filter action = "ACCEPT"
| stats sum(bytes) as totalBytes by srcAddr
| sort totalBytes desc
| limit 10
```

**Parse structured JSON logs:**

```
fields @timestamp, level, message, userId, duration
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

### CLI query

```bash
aws logs start-query \
  --log-group-names /aws/lambda/api-handler \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
```

---

## 36.5 Metric filters

Convert log patterns into CloudWatch metrics for alarming:

```hcl
resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "api-errors"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "ApiErrorCount"
    namespace = "App/Errors"
    value     = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "high-api-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApiErrorCount"
  namespace           = "App/Errors"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

---

## 36.6 Log encryption and access control

| Control | Implementation |
|---------|----------------|
| **Encryption at rest** | KMS key on log group |
| **Encryption in transit** | TLS for all API calls |
| **Resource policies** | Cross-account and service access |
| **IAM policies** | `logs:CreateLogStream`, `logs:PutLogEvents`, `logs:FilterLogEvents` |

### Cross-account log sharing

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::AUDIT_ACCOUNT:root" },
    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
    "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/security/*"
  }]
}
```

---

## 36.7 Log export and archival

| Method | Destination | Use case |
|--------|-------------|----------|
| **Export to S3** | S3 bucket | Long-term archival, Athena analysis |
| **Subscription filter** | Kinesis Firehose → S3/OpenSearch | Real-time streaming |
| **Logs Insights** | Query results | Ad-hoc analysis |

```bash
aws logs create-export-task \
  --log-group-name /aws/lambda/api-handler \
  --from $(date -d '7 days ago' +%s000) \
  --to $(date +%s000) \
  --destination my-log-archive-bucket \
  --destination-prefix lambda-logs/
```

---

## 36.8 Best practices

| Practice | Rationale |
|----------|-----------|
| Set retention policies | Control costs; 30-90 days for most workloads |
| Use structured JSON logging | Enables field-based queries in Insights |
| Include correlation IDs | Trace requests across services |
| Create metric filters for errors | Proactive alarming |
| Encrypt sensitive log groups | KMS for compliance |
| Avoid logging secrets/PII | Redact or mask sensitive data |
| Use log levels appropriately | DEBUG in dev, INFO/WARN in prod |
| Centralize logs in a dedicated account | Security team access, tamper resistance |

### Structured logging example

```python
import json, logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(json.dumps({
        "level": "INFO",
        "message": "Processing order",
        "orderId": event["orderId"],
        "requestId": context.aws_request_id,
        "duration_ms": None,
    }))
```

---

## 36.9 Chapter summary

- **CloudWatch Logs** centralizes log data from AWS services and applications.
- **Logs Insights** provides a powerful query language for log analysis.
- **Metric filters** convert log patterns into alarmable CloudWatch metrics.
- Use **structured JSON logging** and **retention policies** for effective operations.
- **Subscription filters** enable real-time log processing and alerting.

---

## 🧪 Lab 36.1 — Logs Insights queries

1. Deploy a Lambda function that logs structured JSON (level, message, requestId).
2. Invoke it multiple times with success and error paths.
3. Write Insights queries to find errors, calculate average duration, and count by log level.

## 🧪 Lab 36.2 — Error alerting pipeline

1. Create a metric filter for ERROR log entries.
2. Create a CloudWatch alarm on the metric (threshold > 5 in 5 minutes).
3. Connect the alarm to an SNS topic.
4. Trigger errors and verify the alert fires.

---

## Review questions

1. What is the difference between a log group and a log stream?
2. How do metric filters bridge logs and alarms?
3. Why is structured JSON logging recommended over plain text?
4. What is a subscription filter used for?
5. How do you control CloudWatch Logs costs?

---

*Next: [Chapter 37 — X-Ray Distributed Tracing](./chapter-37-xray-tracing.md)*
