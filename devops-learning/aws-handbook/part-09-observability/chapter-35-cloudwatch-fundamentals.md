# Chapter 35: CloudWatch — Metrics, Alarms, and Dashboards

*AWS Handbook — Part IX, Pages 701–720*

---

## 35.1 Amazon CloudWatch overview

**CloudWatch** is AWS's observability service for **metrics**, **logs**, **alarms**, and **dashboards**. Nearly every AWS service emits CloudWatch metrics automatically.

---

## 35.2 Metrics

A **metric** is a time-series datapoint (e.g., `CPUUtilization` for EC2).

| Concept | Description |
|---------|-------------|
| **Namespace** | Grouping (AWS/EC2, AWS/S3, custom) |
| **Metric name** | e.g., CPUUtilization |
| **Dimensions** | InstanceId, FunctionName, etc. |
| **Resolution** | Standard 1 min; high-resolution down to 1 sec |

### View metrics

```bash
aws cloudwatch list-metrics --namespace AWS/EC2
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-0abc123 \
  --start-time 2026-09-01T00:00:00Z \
  --end-time 2026-09-01T12:00:00Z \
  --period 300 \
  --statistics Average
```

### Custom metrics

```python
import boto3
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='MyApp/Orders',
    MetricData=[{
        'MetricName': 'OrdersProcessed',
        'Value': 42,
        'Unit': 'Count'
    }]
)
```

---

## 35.3 Alarms

Alarms trigger actions when metrics breach thresholds.

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name high-cpu-web-server \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:ops-alerts \
  --dimensions Name=InstanceId,Value=i-0abc123
```

### Alarm states

| State | Meaning |
|-------|---------|
| **OK** | Within threshold |
| **ALARM** | Breached threshold |
| **INSUFFICIENT_DATA** | Not enough datapoints |

### Composite alarms

Combine multiple alarms with AND/OR logic to reduce alert noise.

---

## 35.4 Dashboards

Visualize metrics in the console or via API. Example Terraform:

```hcl
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "production-overview"
  dashboard_body = jsonencode({
    widgets = [{
      type   = "metric"
      width  = 12
      height = 6
      properties = {
        metrics = [
          ["AWS/EC2", "CPUUtilization", "InstanceId", "i-0abc123"],
          [".", "NetworkIn", ".", "."]
        ]
        period = 300
        stat   = "Average"
        region = "us-east-1"
        title  = "EC2 Web Server"
      }
    }]
  })
}
```

---

## 35.5 CloudWatch Logs (overview)

| Feature | Purpose |
|---------|---------|
| **Log groups / streams** | Organize application logs |
| **Logs Insights** | SQL-like query language |
| **Subscription filters** | Stream to Lambda, Kinesis, OpenSearch |
| **Metric filters** | Turn log patterns into metrics |

```bash
aws logs tail /aws/lambda/my-function --follow
```

---

## 35.6 Observability best practices on AWS

1. **Alarm on symptoms** — Error rate, latency p99, not just CPU
2. **SNS → PagerDuty/Slack** for on-call routing
3. **Dashboards per service** + one executive overview
4. **Log retention** — Set retention policies (cost control)
5. **X-Ray** for distributed tracing (complements CloudWatch)
6. Use **Container Insights** / **Lambda Insights** for managed runtimes

---

## 35.7 Chapter summary

- CloudWatch collects **metrics** from AWS and custom apps.
- **Alarms** notify via SNS when thresholds breach.
- **Dashboards** and **Logs** complete the operational picture.

---

## 🧪 Lab 35.1

1. Create SNS topic `ops-alerts` (email subscription).
2. Create CPU alarm on an EC2 instance.
3. Build a dashboard with EC2 CPU, ALB request count, and RDS connections.
4. Run a Logs Insights query on a Lambda log group.

---

*Continue: Chapter 36 — CloudWatch Logs Deep Dive (outline in TOC)*
