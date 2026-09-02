# Chapter 46: OpenTelemetry Distributed Tracing

*DevOps Handbook — Pages 220–225 of this PDF edition*
---

## 46.1 The tracing problem

Microservices decompose monoliths into independently deployable units—each request may traverse API gateways, auth services, business logic, databases, caches, and message queues. When latency spikes or errors appear, **which hop failed?**

**Distributed tracing** records the path of a request across process boundaries. **OpenTelemetry (OTel)** is the CNCF standard unifying tracing, metrics, and logs instrumentation under one vendor-neutral API—replacing OpenTracing and OpenCensus.

Benefits:

- End-to-end latency breakdown
- Dependency mapping (service graph)
- Root cause analysis for errors
- Performance regression detection per release

---

## 46.2 Traces, spans, and context propagation

| Concept | Definition |
|---------|------------|
| **Trace** | End-to-end journey of a request (shared trace ID) |
| **Span** | Single timed operation within a trace |
| **Parent span** | Upstream operation that triggered child work |
| **Context propagation** | Passing trace ID/span ID across HTTP/gRPC/message headers |

W3C **Trace Context** standard headers:

```
traceparent: 00-4bf92f3577b329da7c93630a8a323129-00f067aa0ba902b7-01
tracestate: congo=t61rcWkgMzE
```

Format: `version-trace_id-parent_span_id-flags`

```
Trace 4bf92f3577b329da...
├── [span A] API Gateway          120ms
│   ├── [span B] Auth validate       15ms
│   └── [span C] Order service     95ms
│       ├── [span D] DB query       8ms
│       └── [span E] Inventory gRPC  70ms  ← bottleneck
```

Span attributes (metadata):

- `http.method`, `http.status_code`
- `db.system`, `db.statement` (sanitized)
- `service.name`, `deployment.environment`

Span events: point-in-time annotations within a span (e.g., "cache miss").

---

## 46.3 OpenTelemetry architecture

```
Application (OTel SDK)
        │
        ▼
OTel Collector (optional but recommended)
        │
        ├──► Jaeger / Tempo / Zipkin (traces)
        ├──► Prometheus / Mimir (metrics)
        └──► Elasticsearch / Loki (logs)
```

Components:

| Component | Role |
|-----------|------|
| **OTel API** | Instrumentation interfaces in app code |
| **OTel SDK** | Sampling, batching, export |
| **Instrumentation libraries** | Auto-instrument HTTP, gRPC, DB drivers |
| **OTel Collector** | Receive, process, export; vendor-agnostic hub |
| **Backend** | Storage and UI (Jaeger, Grafana Tempo) |

---

## 46.4 Instrumentation: auto vs manual

**Auto-instrumentation** (agents) attaches without code changes:

```bash
# Python example
opentelemetry-instrument \
  --traces_exporter otlp \
  --metrics_exporter otlp \
  --service_name order-api \
  --exporter_otlp_endpoint http://otel-collector:4317 \
  python app.py
```

Java: `-javaagent:opentelemetry-javaagent.jar`

**Manual instrumentation** for business logic:

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("order-service", "1.0.0")

def create_order(order_data):
    with tracer.start_as_current_span("create_order") as span:
        span.set_attribute("order.customer_id", order_data["customer_id"])
        try:
            validate(order_data)
            order_id = persist(order_data)
            span.set_attribute("order.id", order_id)
            return order_id
        except ValidationError as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
```

Ensure **context propagation** across async boundaries (thread pools, asyncio, message queues)—dropped context breaks trace chains.

---

## 46.5 OTel Collector configuration

Collector pipelines: **receivers → processors → exporters**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
  resource:
    attributes:
      - key: deployment.environment
        value: production
        action: upsert
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: latency
        type: latency
        latency:
          threshold_ms: 1000
      - name: probabilistic
        type: probabilistic
        probabilistic:
          sampling_percentage: 5

exporters:
  otlp/jaeger:
    endpoint: jaeger-collector:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, tail_sampling, batch, resource]
      exporters: [otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheus]
```

**Tail sampling** at collector evaluates complete traces—keep all errors and slow traces, sample routine success paths.

---

## 46.6 Sampling strategies

Tracing every request at high QPS is expensive. Sampling reduces volume while preserving debuggability.

| Strategy | Behavior |
|----------|----------|
| **Always on** | Dev/test only |
| **Probabilistic head** | Random % at trace start; simple but may miss errors |
| **Rate limiting** | Max traces per second |
| **Tail sampling** | Decide after trace completes; keep errors/slow |

Head sampling in SDK:

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

sampler = TraceIdRatioBased(0.1)  # 10% of traces
```

Production recommendation: **tail sampling in Collector** with error and latency policies plus low baseline probabilistic sample.

---

## 46.7 Backends: Jaeger and Grafana Tempo

**Jaeger** (CNCF graduated): UI for trace search, dependency graphs, compare traces.

Deploy Jaeger on Kubernetes:

```yaml
# Simplified — use Jaeger Operator in production
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
spec:
  template:
    spec:
      containers:
        - name: jaeger
          image: jaegertracing/all-in-one:1.52
          ports:
            - containerPort: 16686  # UI
            - containerPort: 4317   # OTLP gRPC
```

**Grafana Tempo**: object storage backend (S3/GCS), integrates natively with Grafana—trace-to-log correlation via `trace_id`.

Trace search:

- By trace ID (from logs or error message)
- By service + operation + duration
- By tags (`http.status_code=500`)

---

## 46.8 Correlating traces, logs, and metrics

**Exemplars** link metrics to traces—a histogram bucket points to example trace ID.

Logs include trace context:

```json
{
  "message": "order created",
  "trace_id": "4bf92f3577b329da7c93630a8a323129",
  "span_id": "00f067aa0ba902b7"
}
```

Grafana **Trace to logs** jump: from span → Loki query `{trace_id="..."}`.

Metrics derived from traces (span metrics connector in Collector): RED metrics per service from trace data without duplicate instrumentation.

---

## 46.9 Service mesh tracing

**Istio** and **Linkerd** generate spans automatically for mesh traffic—application instrumentation still needed for in-process detail.

Istio enables tracing via Telemetry API; spans exported to OTel Collector.

Mesh traces show network latency (TLS, retries); app traces show business logic—combine both.

---

## 46.10 Adoption roadmap

1. **Deploy Collector** — Central export point before picking backend
2. **Auto-instrument ingress** — API gateway, primary services
3. **Propagate context** — Verify cross-service trace continuity
4. **Add manual spans** — Critical business operations
5. **Tail sampling** — Cost control in production
6. **Integrate Grafana/Jaeger** — On-call workflows, dashboards
7. **SLO dashboards** — Latency from trace metrics

Anti-patterns:

- Instrumentation without sampling plan (cost surprise)
- Broken context in async/message paths
- Storing full SQL with PII in span attributes

---

## 46.11 Chapter summary

- OpenTelemetry standardizes traces, metrics, and logs with vendor-neutral SDKs and Collector.
- Traces consist of spans linked by context propagation (W3C Trace Context headers).
- Use auto-instrumentation plus manual spans; tail sampling preserves errors while controlling cost.
- Correlate traces with logs (`trace_id`) and metrics (exemplars) for full observability.

---

## 🧪 Lab 46.1 — OTel + Jaeger locally

1. Run OTel Collector, Jaeger, and a two-service demo (e.g., frontend → backend).
2. Auto-instrument both services with OTel agents.
3. Generate traffic; verify end-to-end trace in Jaeger UI.
4. Introduce artificial 2s delay in backend; identify span in critical path.

---

## 🧪 Lab 46.2 — Tail sampling

1. Configure Collector tail sampling: 100% errors, 5% success.
2. Generate 1000 successful requests and 50 failing requests.
3. Compare trace counts in Jaeger; confirm error traces retained.

---

## Review questions

1. What is the difference between a trace and a span?
2. Explain W3C Trace Context propagation across HTTP services.
3. Why is tail sampling preferred over head sampling in production?
4. What role does the OpenTelemetry Collector play?
5. How do you correlate logs with traces in Grafana?
6. When is manual instrumentation necessary beyond auto-instrumentation?
7. What are exemplars, and how do they connect metrics to traces?

---

*Continue: Chapter 47 — SLOs, Error Budgets, Incident Response*
