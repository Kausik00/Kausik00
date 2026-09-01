# Chapter 37: X-Ray & Distributed Tracing

*AWS Handbook — Part IX, Pages 736–750*

---

## 37.1 Why distributed tracing?

In microservice architectures, a single user request traverses multiple services: API Gateway → Lambda → DynamoDB → SQS → another Lambda → SNS. When latency spikes or errors occur, traditional logging cannot show the full request path.

**AWS X-Ray** provides end-to-end tracing, showing the complete journey of a request with timing, errors, and dependencies visualized as a service map.

---

## 37.2 X-Ray concepts

| Concept | Description |
|---------|-------------|
| **Trace** | Complete path of a request through services |
| **Segment** | Work done by a single service (e.g., Lambda execution) |
| **Subsegment** | Downstream call within a segment (e.g., DynamoDB query) |
| **Annotation** | Indexed key-value pairs for filtering (e.g., `userId=123`) |
| **Metadata** | Non-indexed data attached to segments |
| **Service map** | Visual graph of service dependencies |
| **Trace ID** | Unique identifier propagated across services |

---

## 37.3 How X-Ray works

```
Request → API Gateway (segment) → Lambda (segment)
                                      ├── DynamoDB (subsegment)
                                      ├── SQS (subsegment)
                                      └── Lambda 2 (segment)
                                              └── SNS (subsegment)
```

1. First service generates a **trace ID** and **segment**.
2. Trace ID propagates via HTTP header (`X-Amzn-Trace-Id`) or message attribute.
3. Each downstream service creates its own segment linked to the trace.
4. Segments are sent to the X-Ray daemon (or SDK) and stored by the X-Ray service.

---

## 37.4 Enabling X-Ray

### AWS service integration

| Service | Enable method |
|---------|---------------|
| **Lambda** | `tracing_config { mode = "Active" }` |
| **API Gateway** | Stage tracing enabled |
| **ECS** | X-Ray daemon sidecar container |
| **EKS** | ADOT (AWS Distro for OpenTelemetry) collector |
| **Elastic Beanstalk** | Enable in environment config |
| **Step Functions** | `tracing_configuration { enabled = true }` |

### Lambda with active tracing

```hcl
resource "aws_lambda_function" "api" {
  # ...
  tracing_config {
    mode = "Active"
  }
}

resource "aws_iam_role_policy" "xray" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
      Resource = "*"
    }]
  })
}
```

### API Gateway

```hcl
resource "aws_apigatewayv2_stage" "prod" {
  # ...
  default_route_settings {
    detailed_metrics_enabled = true
    throttling_burst_limit   = 100
    throttling_rate_limit    = 50
  }
}
```

---

## 37.5 SDK instrumentation

For custom applications, use the X-Ray SDK:

### Python

```python
from aws_xray_sdk.core import xray_recorder, patch_all
from aws_xray_sdk.core import lambda_launcher

patch_all()  # auto-instrument boto3, requests, etc.

@xray_recorder.capture("process_order")
def process_order(order_id):
    xray_recorder.put_annotation("orderId", order_id)
    xray_recorder.put_metadata("order", {"id": order_id, "source": "api"})

    # Subsegment for DynamoDB call (auto-patched by patch_all)
    table.put_item(Item={"orderId": order_id, "status": "processing"})

def handler(event, context):
    process_order(event["orderId"])
    return {"statusCode": 200}
```

### Node.js

```javascript
const AWSXRay = require("aws-xray-sdk");
const AWS = AWSXRay.captureAWS(require("aws-sdk"));

exports.handler = async (event) => {
  const segment = AWSXRay.getSegment();
  segment.addAnnotation("orderId", event.orderId);

  const subsegment = segment.addNewSubsegment("validateOrder");
  try {
    // business logic
    subsegment.close();
  } catch (err) {
    subsegment.addError(err);
    subsegment.close();
    throw err;
  }
};
```

---

## 37.6 Service map

The **service map** visualizes dependencies and health:

```
[Client] → [API Gateway] → [Lambda: api-handler] → [DynamoDB: Orders]
                              ↓ (error rate 2%)
                           [SQS: orders-queue] → [Lambda: processor]
```

- **Green** edges: healthy (< 5% error rate).
- **Red/yellow** edges: elevated errors or latency.
- **Node size**: proportional to request volume.

Use the service map to identify bottlenecks, error hotspots, and unexpected dependencies.

---

## 37.7 Trace analysis

### Filtering traces

| Filter | Example |
|--------|---------|
| By annotation | `annotation.orderId = "12345"` |
| By response time | `responsetime > 3` |
| By error | `error = true` |
| By service | `service("api-handler")` |
| Combined | `service("api-handler") { error = true }` |

### Trace detail view

Each trace shows:
- **Timeline** — waterfall of segments with duration.
- **Segments** — per-service breakdown with metadata.
- **Exceptions** — stack traces for errors.
- **Annotations** — searchable key-value pairs.

```bash
aws xray get-trace-summaries \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --filter-expression 'service("api-handler") { error = true }'
```

---

## 37.8 X-Ray with OpenTelemetry

AWS supports **OpenTelemetry (OTel)** as the modern standard for instrumentation:

| Component | AWS implementation |
|-----------|-------------------|
| **SDK** | OpenTelemetry SDK (language-specific) |
| **Collector** | ADOT (AWS Distro for OpenTelemetry) |
| **Backend** | X-Ray, CloudWatch, Prometheus, Jaeger |

ADOT collector on ECS/EKS/EC2 receives OTLP traces and exports to X-Ray:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  awsxray:
    region: us-east-1

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [awsxray]
```

---

## 37.9 Sampling

X-Ray uses sampling to control costs—by default, 1 request/second plus 5% of additional requests are traced.

### Custom sampling rules

```json
{
  "version": 2,
  "rules": [{
    "description": "Trace all errors",
    "host": "*",
    "http_method": "*",
    "url_path": "*",
    "fixed_target": 0,
    "rate": 1.0,
    "priority": 100,
    "service_name": "*",
    "service_type": "*",
    "resource_arn": "*"
  }, {
    "description": "Sample 10% of API calls",
    "host": "*",
    "http_method": "*",
    "url_path": "/api/*",
    "fixed_target": 1,
    "rate": 0.1,
    "priority": 200,
    "service_name": "api-handler",
    "service_type": "AWS::Lambda::Function",
    "resource_arn": "*"
  }]
}
```

---

## 37.10 X-Ray groups and insights

| Feature | Purpose |
|---------|---------|
| **Groups** | Filter traces by criteria; track error rates and latency |
| **Insights** | Automatically detect anomalies in trace data |
| **Encryption** | KMS encryption for trace data |

---

## 37.11 Chapter summary

- **X-Ray** provides end-to-end distributed tracing across AWS services and custom applications.
- **Segments** and **subsegments** capture timing and errors at each service boundary.
- Enable active tracing on Lambda, API Gateway, and ECS; use SDKs for custom instrumentation.
- The **service map** visualizes dependencies and identifies bottlenecks.
- Use **sampling rules** to balance observability with cost; consider **OpenTelemetry** for modern instrumentation.

---

## 🧪 Lab 37.1 — Lambda tracing

1. Enable active X-Ray tracing on a Lambda function behind API Gateway.
2. Invoke the API with success and error scenarios.
3. View the service map and trace timeline in the X-Ray console.
4. Filter traces by error and identify the failing subsegment.

## 🧪 Lab 37.2 — Custom annotations

1. Add X-Ray SDK annotations (`userId`, `orderId`) to a Lambda function.
2. Generate traffic with different user IDs.
3. Filter traces by annotation in the X-Ray console.
4. Create an X-Ray group for high-latency traces (> 2 seconds).

---

## Review questions

1. What is the difference between a segment and a subsegment?
2. How does the trace ID propagate between services?
3. Why is sampling important for X-Ray cost management?
4. What does the X-Ray service map show?
5. How does OpenTelemetry relate to X-Ray?

---

*Next: [Chapter 38 — CloudTrail & AWS Config](./chapter-38-cloudtrail-config.md)*
