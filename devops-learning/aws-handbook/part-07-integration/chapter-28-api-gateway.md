# Chapter 28: API Gateway

*AWS Handbook — Part VII, Pages 561–580*

---

## 28.1 What is Amazon API Gateway?

**Amazon API Gateway** is a fully managed service for creating, publishing, securing, and monitoring HTTP, REST, and WebSocket APIs at any scale. It acts as the front door for serverless backends (Lambda), container services (ECS/EKS), and legacy applications.

API Gateway handles request routing, authentication, throttling, caching, and API versioning—freeing backend services from these cross-cutting concerns.

---

## 28.2 API types

| Type | Protocol | Use case |
|------|----------|----------|
| **REST API** | HTTP/REST | Full-featured; request/response transformation |
| **HTTP API** | HTTP | Simpler, cheaper, lower latency; Lambda/proxy integrations |
| **WebSocket API** | WebSocket | Real-time bidirectional communication |
| **Private REST API** | HTTP/REST | Internal APIs via VPC endpoint |

**Recommendation:** Use **HTTP API** for new Lambda-based APIs (70% cheaper, lower latency). Use **REST API** when you need request validation, API keys, or advanced transformation.

---

## 28.3 REST API architecture

```
Client → API Gateway → Integration
                          ├── Lambda function
                          ├── HTTP endpoint (ALB, EC2)
                          ├── AWS service (DynamoDB, SQS, Step Functions)
                          └── Mock (testing)
```

### Key components

| Component | Description |
|-----------|-------------|
| **Resource** | URL path segment (`/users`, `/users/{id}`) |
| **Method** | HTTP verb (GET, POST, PUT, DELETE) |
| **Integration** | Backend that processes the request |
| **Stage** | Deployment environment (dev, staging, prod) |
| **Deployment** | Snapshot of API configuration |

---

## 28.4 HTTP API with Lambda

### Terraform example

```hcl
resource "aws_apigatewayv2_api" "api" {
  name          = "app-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://app.example.com"]
    allow_methods = ["GET", "POST", "PUT", "DELETE"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_users" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /users"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "post_users" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /users"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId    = "$context.requestId"
      ip           = "$context.identity.sourceIp"
      method       = "$context.httpMethod"
      path         = "$context.path"
      status       = "$context.status"
      responseTime = "$context.responseLatency"
    })
  }

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
```

---

## 28.5 Authentication and authorization

| Method | Description |
|--------|-------------|
| **IAM** | SigV4 signing; service-to-service |
| **Cognito User Pools** | JWT tokens for user-facing APIs |
| **Lambda authorizer** | Custom auth logic (any token format) |
| **JWT authorizer** (HTTP API) | Validate JWT from any OIDC provider |
| **API keys** | Simple key-based access (REST API only) |
| **Resource policy** | IP-based or VPC-based restrictions |

### Lambda authorizer example

```python
def handler(event, context):
    token = event["authorizationToken"]
    if not validate_token(token):
        raise Exception("Unauthorized")  # Returns 401

    return {
        "principalId": "user-123",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": event["methodArn"],
            }],
        },
        "context": {
            "userId": "user-123",
            "role": "admin",
        },
    }
```

---

## 28.6 Throttling and quotas

API Gateway protects backends with built-in throttling:

| Level | Default |
|-------|---------|
| **Account** | 10,000 requests/second (can increase) |
| **Per API/stage** | Configurable burst and rate limits |
| **Per method** | Usage plans with API keys |

### Usage plans

```hcl
resource "aws_api_gateway_usage_plan" "basic" {
  name = "basic-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  throttle_settings {
    burst_limit = 50
    rate_limit  = 25
  }

  quota_settings {
    limit  = 10000
    period = "MONTH"
  }
}
```

---

## 28.7 Request/response transformation

REST API supports **mapping templates** (VTL) for request/response transformation:

```
Client sends JSON → API Gateway transforms → DynamoDB PutItem format
DynamoDB response → API Gateway transforms → Client JSON response
```

HTTP API passes the request directly to Lambda (proxy integration) with less transformation capability but better performance.

### Request validation (REST API)

```json
{
  "type": "object",
  "required": ["name", "email"],
  "properties": {
    "name": { "type": "string", "minLength": 1 },
    "email": { "type": "string", "format": "email" }
  }
}
```

---

## 28.8 Caching

API Gateway can cache responses at the stage level:

| Setting | Value |
|---------|-------|
| **TTL** | 0–3600 seconds |
| **Cache key** | Query parameters, headers |
| **Encryption** | In-transit and at-rest |
| **Cost** | Per-hour cache capacity |

Enable caching for read-heavy endpoints with infrequently changing data. Invalidate cache on deployments.

---

## 28.9 Custom domains and TLS

```hcl
resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = "api.example.com"

  domain_name_configuration {
    certificate_arn = aws_acm_certificate.api.arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.prod.id
}
```

Route 53 alias record points `api.example.com` to the API Gateway domain.

---

## 28.10 WebSocket API

For real-time applications (chat, gaming, live dashboards):

```
Client ←──WebSocket──→ API Gateway ←──→ Lambda/DynamoDB
         $connect              Route by route key
         $disconnect           $default, custom routes
         $default
```

```hcl
resource "aws_apigatewayv2_api" "websocket" {
  name                       = "chat-api"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}
```

---

## 28.11 Monitoring

| Tool | Data |
|------|------|
| **CloudWatch Metrics** | Count, Latency, 4XXError, 5XXError, IntegrationLatency |
| **CloudWatch Logs** | Access logs, execution logs |
| **X-Ray** | Distributed tracing through API Gateway → Lambda → DynamoDB |

Key alarms:
- `5XXError` > 1% of requests
- `Latency` p99 > 3000ms
- `Count` approaching throttle limits

---

## 28.12 Chapter summary

- **API Gateway** is the managed front door for HTTP, REST, and WebSocket APIs.
- Use **HTTP API** for new Lambda backends; **REST API** for advanced features.
- Secure with **Cognito**, **Lambda authorizers**, or **IAM**.
- Configure **throttling**, **caching**, and **custom domains** for production.
- Monitor with CloudWatch metrics, access logs, and X-Ray tracing.

---

## 🧪 Lab 28.1 — HTTP API + Lambda CRUD

1. Create an HTTP API with Lambda integration for a DynamoDB-backed CRUD API.
2. Implement GET /items, POST /items, GET /items/{id}, DELETE /items/{id}.
3. Add a JWT authorizer (Cognito or custom).
4. Configure access logging and test with `curl`.

## 🧪 Lab 28.2 — Throttling and usage plans

1. Create a REST API with API key requirement.
2. Create a usage plan with 100 requests/day quota.
3. Exceed the quota and verify 429 responses.
4. Review CloudWatch metrics for throttled requests.

---

## Review questions

1. When should you choose REST API over HTTP API?
2. How does a Lambda authorizer work?
3. What is the difference between burst limit and rate limit?
4. How do you attach a custom domain with TLS to API Gateway?
5. What CloudWatch metric indicates backend integration problems?

---

*Next: [Chapter 29 — SQS, SNS, and EventBridge](./chapter-29-sqs-sns-eventbridge.md)*
