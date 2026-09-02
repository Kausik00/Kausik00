# Chapter 12: Load Balancers — ALB, NLB, and GWLB

*AWS Handbook — Pages 49–54 of this PDF edition*
---

## 12.1 Why load balancers?

In production, a single server cannot handle all traffic or survive failures. **Elastic Load Balancing (ELB)** distributes incoming traffic across multiple targets (EC2 instances, containers, IP addresses, Lambda functions) and performs health checks to route around unhealthy targets.

AWS offers three load balancer types, each optimized for different layers of the OSI model and use cases.

---

## 12.2 Load balancer comparison

| Feature | ALB | NLB | GWLB |
|---------|-----|-----|------|
| **Layer** | Layer 7 (HTTP/HTTPS) | Layer 4 (TCP/UDP/TLS) | Layer 3 (IP) |
| **Protocols** | HTTP, HTTPS, gRPC, WebSocket | TCP, UDP, TLS | IP packets |
| **Targets** | Instances, IPs, Lambda | Instances, IPs, ALB | Appliance instances |
| **Static IP** | No (use Global Accelerator) | Yes (per AZ) | N/A |
| **Cross-zone LB** | Optional (default on) | Optional (default off) | N/A |
| **Use case** | Web apps, microservices, path routing | Extreme performance, static IP, TLS passthrough | Inline security appliances |
| **Pricing** | Per LCU-hour | Per NLCU-hour | Per GLCU-hour |

---

## 12.3 Application Load Balancer (ALB)

The **ALB** operates at Layer 7, making routing decisions based on HTTP content: host header, path, query string, and headers.

### Key features

- **Listener rules** — Route by path (`/api/*` → API target group), host (`api.example.com`), or headers.
- **Target groups** — Collections of targets with health checks and stickiness settings.
- **SSL/TLS termination** — Decrypt at the ALB using ACM certificates.
- **WebSocket and HTTP/2** — Native support.
- **AWS WAF integration** — Attach WAF Web ACLs for application-layer protection.
- **Authentication** — Built-in OIDC/Cognito authentication at the ALB.

### ALB architecture

```
Internet → ALB (public subnets, multi-AZ)
              ├── Listener :443 (HTTPS)
              │     ├── Rule: /api/*  → Target Group A (ECS tasks)
              │     ├── Rule: /admin/* → Target Group B (EC2 instances)
              │     └── Default        → Target Group C (static site)
              └── Listener :80 (redirect to 443)
```

### Health checks

| Setting | Typical value |
|---------|---------------|
| Protocol | HTTP |
| Path | `/health` |
| Interval | 30 seconds |
| Healthy threshold | 2 consecutive successes |
| Unhealthy threshold | 3 consecutive failures |
| Success codes | 200 |

### Terraform ALB example

```hcl
resource "aws_lb" "app" {
  name               = "app-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = { Name = "app-alb" }
}

resource "aws_lb_target_group" "web" {
  name     = "web-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.app.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern { values = ["/api/*"] }
  }
}
```

### CLI example

```bash
aws elbv2 create-load-balancer \
  --name app-alb \
  --subnets subnet-aaa subnet-bbb \
  --security-groups sg-alb \
  --scheme internet-facing \
  --type application

aws elbv2 create-target-group \
  --name web-tg \
  --protocol HTTP \
  --port 80 \
  --vpc-id vpc-0abc123 \
  --health-check-path /health
```

---

## 12.4 Network Load Balancer (NLB)

The **NLB** operates at Layer 4, handling millions of requests per second with ultra-low latency. It preserves the client source IP and supports static IP addresses per Availability Zone.

### When to choose NLB

| Scenario | Why NLB |
|----------|---------|
| Non-HTTP protocols (MQTT, gaming) | Layer 4, any TCP/UDP |
| Extreme throughput requirements | Millions of RPS |
| Static IP needed | Elastic IP per AZ |
| TLS passthrough | NLB forwards encrypted traffic to targets |
| PrivateLink service provider | NLB as endpoint service |
| ALB as target | NLB → ALB for static IP + L7 routing |

### NLB characteristics

- **Connection-based** — Not request-based like ALB.
- **Cross-zone load balancing** — Off by default (enable for even distribution).
- **Preserve source IP** — Targets see the real client IP (unlike ALB which adds `X-Forwarded-For`).
- **Target types** — Instance, IP, ALB.

### Health checks for NLB

NLB supports TCP, HTTP, and HTTPS health checks. TCP checks only verify port openness; HTTP/HTTPS checks validate response codes.

---

## 12.5 Gateway Load Balancer (GWLB)

The **GWLB** distributes traffic to **third-party virtual appliances** (firewalls, IDS/IPS, deep packet inspection) in a transparent, bump-in-the-wire fashion.

### Use case

```
VPC traffic → GWLB Endpoint → GWLB → Firewall appliance → GWLB → destination
```

- Deploy security appliances as GWLB targets.
- Traffic is encapsulated using **GENEVE** protocol (port 6081).
- Appliances inspect and forward traffic transparently.
- Common with vendors: Palo Alto, Fortinet, Check Point.

### GWLB components

| Component | Role |
|-----------|------|
| **GWLB** | Distributes flows to appliance fleet |
| **Target group** | Appliance instances (IP or instance type) |
| **GWLB endpoint** | VPC endpoint that routes traffic through GWLB |
| **Route table** | Directs subnet traffic to the GWLB endpoint |

---

## 12.6 Shared ELB concepts

### Listeners and rules

- **Listener** — Checks for connection requests on a port/protocol.
- **Rules** — ALB only; evaluated by priority (lower number first).
- **Default action** — Catches traffic not matched by any rule.

### Target groups

| Setting | Description |
|---------|-------------|
| **Target type** | instance, ip, lambda, alb |
| **Protocol/port** | How the LB communicates with targets |
| **Deregistration delay** | Drain time before removing unhealthy targets (default 300s) |
| **Stickiness** | Session affinity via cookie (ALB) or source IP (NLB) |

### Stickiness

| LB | Method |
|----|--------|
| ALB | Application cookie (LB cookie or app cookie) |
| NLB | Source IP hash (5-tuple for TCP, 3-tuple for UDP) |

### Connection draining

When a target is deregistered or becomes unhealthy, the LB stops sending **new** connections but allows **in-flight** connections to complete during the deregistration delay.

---

## 12.7 SSL/TLS with load balancers

| Approach | LB | Description |
|----------|-----|-------------|
| **Terminate at LB** | ALB, NLB | LB decrypts; backend can use HTTP |
| **TLS passthrough** | NLB | Encrypted traffic forwarded to targets |
| **Mutual TLS (mTLS)** | ALB | Client certificate validation |
| **Certificate** | ACM (free) | Attach to listener |

**Best practice:** Terminate TLS at the ALB with ACM certificates. Use HTTPS between ALB and targets for end-to-end encryption if required.

---

## 12.8 Monitoring and troubleshooting

| Tool | Purpose |
|------|---------|
| **CloudWatch metrics** | RequestCount, TargetResponseTime, HealthyHostCount |
| **Access logs** | S3-stored per-request logs (enable explicitly) |
| **Connection logs** | NLB connection-level logs |
| **Target health** | `aws elbv2 describe-target-health` |

```bash
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/web-tg/abc123

aws elbv2 describe-load-balancer-attributes \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/app-alb/abc123
```

### Common issues

| Symptom | Cause |
|---------|-------|
| 502 Bad Gateway | Target not responding or security group blocks ALB |
| 503 Service Unavailable | No healthy targets in target group |
| Health check failing | Wrong path, port, or security group |
| Slow responses | Target overloaded; check TargetResponseTime metric |

---

## 12.9 Chapter summary

- **ALB** — Layer 7; path/host routing, SSL termination, WAF, authentication.
- **NLB** — Layer 4; extreme performance, static IPs, non-HTTP protocols.
- **GWLB** — Inline security appliances with transparent traffic inspection.
- Configure **health checks**, **security groups**, and **target groups** carefully.
- Use **ACM** for certificates; enable **access logs** for troubleshooting.

---

## 🧪 Lab 12.1 — Deploy an ALB

1. Create an ALB in public subnets with an HTTPS listener (ACM certificate).
2. Create a target group pointing to EC2 instances in private subnets.
3. Configure a health check on `/health`.
4. Add a listener rule: `/api/*` forwards to a separate target group.
5. Verify routing with `curl` against both paths.

## 🧪 Lab 12.2 — NLB with static IP

1. Create an NLB with TCP listener on port 5432.
2. Note the static Elastic IP assigned per AZ.
3. Register RDS or an EC2 PostgreSQL instance as target.
4. Connect from a client using the NLB static IP.

---

## Review questions

1. At which OSI layer does an ALB operate, and what routing decisions can it make?
2. When would you choose NLB over ALB?
3. What is the purpose of a GWLB?
4. Why might ALB health checks fail even when the application is running?
5. What is connection draining, and why does it matter during deployments?

---

*Next: [Chapter 13 — Route 53 DNS Routing](./chapter-13-route53-dns.md)*
