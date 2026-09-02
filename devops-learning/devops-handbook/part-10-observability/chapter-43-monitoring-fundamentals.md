# Chapter 43: Monitoring Fundamentals — Metrics, Logs, Traces

*DevOps Handbook — Pages 203–207 of this PDF edition*
---

## 43.1 From monitoring to observability

**Monitoring** asks: "Is the system up? Are known thresholds breached?" Traditional monitoring relies on predefined dashboards and alerts—CPU > 80%, error rate > 1%.

**Observability** asks: "Why is the system behaving this way?" A system is observable when you can infer internal state from **external outputs**—especially for novel failures nobody anticipated.

The three pillars of observability:

| Pillar | Question it answers | Typical tools |
|--------|---------------------|---------------|
| **Metrics** | How much? How fast? Trend over time? | Prometheus, Datadog, CloudWatch |
| **Logs** | What happened? Context and narrative? | ELK, Loki, CloudWatch Logs |
| **Traces** | Where did time go? Cross-service path? | Jaeger, Tempo, Zipkin, X-Ray |

Metrics are cheap at scale; logs are verbose; traces connect distributed requests. Mature platforms **correlate** all three—click from alert → logs → trace span.

---

## 43.2 Metrics: types and best practices

**Metrics** are numeric measurements aggregated over time.

| Type | Description | Example |
|------|-------------|---------|
| **Counter** | Monotonically increasing | `http_requests_total` |
| **Gauge** | Value that goes up/down | `memory_usage_bytes`, queue depth |
| **Histogram** | Distribution in buckets | Request latency buckets |
| **Summary** | Quantiles (client-side) | `http_request_duration_seconds{quantile="0.99"}` |

Prometheus exposition format:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200",handler="/api/orders"} 15432
http_requests_total{method="POST",status="500",handler="/api/orders"} 12
```

**RED method** for services:

- **Rate** — Requests per second
- **Errors** — Failed requests per second
- **Duration** — Latency distribution

**USE method** for resources:

- **Utilization** — % busy
- **Saturation** — Queue length / wait
- **Errors** — Error count

Naming conventions: include unit suffix (`_seconds`, `_bytes`, `_total` for counters). Avoid high-cardinality labels (user IDs, unbounded paths)—they explode storage and query cost.

```python
from prometheus_client import Counter, Histogram, start_http_server

REQUEST_COUNT = Counter(
    "http_requests_total", "Total requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0]
)

def handle_request(method, endpoint, handler):
    with REQUEST_LATENCY.labels(method, endpoint).time():
        status = handler()
    REQUEST_COUNT.labels(method, endpoint, str(status)).inc()
```

---

## 43.3 Logs: structure and aggregation

**Logs** are discrete events with timestamps—historically unstructured text, now increasingly **structured** (JSON).

Unstructured (hard to query):

```
2026-09-01T14:32:01Z ERROR payment failed user=12345 order=987 reason=timeout
```

Structured (machine-parseable):

```json
{
  "timestamp": "2026-09-01T14:32:01.123Z",
  "level": "ERROR",
  "service": "payment-api",
  "trace_id": "4bf92f3577b329da7c93630a8a323129",
  "span_id": "00f067aa0ba902b7",
  "message": "payment failed",
  "user_id": "12345",
  "order_id": "987",
  "error": "gateway timeout"
}
```

Best practices:

| Practice | Rationale |
|----------|-----------|
| Structured JSON | Filter/aggregate in log platforms |
| Consistent field names | Cross-service queries |
| Include trace/span IDs | Jump to distributed trace |
| Log levels (DEBUG–ERROR) | Control volume in prod |
| Never log secrets/PII | Compliance and security |
| Centralize | SSHing to grep individual servers does not scale |

Log levels guide:

- **DEBUG** — Development troubleshooting (usually off in prod)
- **INFO** — Normal lifecycle events (startup, deploy, key business events)
- **WARN** — Recoverable anomalies
- **ERROR** — Failures requiring attention

---

## 43.4 Traces: distributed request flow

In microservices, a single user request traverses many services. **Distributed tracing** assigns a **trace ID** to the request; each service creates **spans** (timed operations) linked by parent-child relationships.

```
Trace ID: abc123
├── Span: API Gateway (50ms)
│   ├── Span: Auth Service (10ms)
│   └── Span: Order Service (35ms)
│       ├── Span: Postgres query (5ms)
│       └── Span: Inventory RPC (20ms)
```

OpenTelemetry span attributes:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_order") as span:
    span.set_attribute("order.id", order_id)
    span.set_attribute("customer.tier", "premium")
    result = charge_payment(order_id)
    span.add_event("payment_completed", {"amount": result.amount})
```

Traces answer: Which downstream call caused latency? Did error originate in service A or B? What was the critical path?

Sample **tail-based sampling**: keep all error traces, sample 1% of success traces—balancing cost and debuggability.

---

## 43.5 The observability data pipeline

```
Apps / Infra
    │
    ├── Metrics ──► Prometheus / Agent ──► TSDB ──► Grafana
    ├── Logs ─────► Fluent Bit / Filebeat ──► Elasticsearch / Loki
    └── Traces ───► OTel Collector ──► Jaeger / Tempo
                           │
                    Alertmanager / PagerDuty
```

**OpenTelemetry (OTel)** is the vendor-neutral standard for instrumenting metrics, logs, and traces with one SDK and exporting to many backends.

Design principles:

1. **Instrument at boundaries** — HTTP handlers, RPC, DB calls, queue publish/consume.
2. **SLO-driven** — Alert on user-impacting symptoms, not every metric (Chapter 47).
3. **Cardinality control** — Label discipline prevents metric explosion.
4. **Retention tiers** — Hot (days), warm (weeks), cold (compliance archive).

---

## 43.6 Alerting philosophy

Alerts should be **actionable**, **urgent**, and **symptom-based**.

| Bad alert | Good alert |
|-----------|------------|
| CPU > 70% on one pod | Error budget burn rate > 2x for 15m |
| Disk 60% full | Disk will fill in 4h at current rate |
| Any ERROR log | Payment success rate < 99.5% for 5m |

Alert routing:

- **Page** (wake someone) — Customer-impacting SLO breach
- **Ticket** — Degraded but not urgent
- **Dashboard** — Informational trend

Reduce **alert fatigue**—on-call engineers ignoring alerts is worse than no alerts.

---

## 43.7 Golden signals and SLIs

Google SRE **four golden signals**:

1. **Latency** — Time to serve request ( distinguish success vs error latency)
2. **Traffic** — Demand on system
3. **Errors** — Rate of failed requests
4. **Saturation** — How "full" the system is

Map golden signals to **Service Level Indicators (SLIs)**—quantifiable measure of service aspect (availability, latency, throughput). Chapter 47 expands SLOs and error budgets.

Example SLI:

```
Availability SLI = successful_requests / total_valid_requests
Latency SLI      = proportion of requests < 300ms
```

---

## 43.8 Instrumentation ownership

| Role | Responsibility |
|------|----------------|
| **Application team** | Business metrics, RED metrics, trace propagation |
| **Platform team** | Collectors, TSDB, dashboards, alert routing |
| **SRE** | SLO definition, on-call, incident process |

"You build it, you run it" includes **you instrument it**. Platform provides plumbing; teams own service-level observability.

---

## 43.9 Chapter summary

- Observability combines metrics (aggregates), logs (events), and traces (request paths) to explain system behavior.
- Use RED/USE methods, structured logging, and trace propagation with correlation IDs.
- Control cardinality, retention, and alert quality to keep systems operable at scale.
- OpenTelemetry unifies instrumentation; backend choice can evolve without re-instrumenting apps.

---

## 🧪 Lab 43.1 — RED metrics for a sample API

1. Add Prometheus client to a sample HTTP service exposing `/metrics`.
2. Instrument request count, error count, and latency histogram per route.
3. Scrape with Prometheus; graph rate and p99 latency in Grafana.
4. Generate load with `hey` or `k6`; observe metrics change.

---

## 🧪 Lab 43.2 — Correlate logs and traces

1. Instrument a two-service demo with OpenTelemetry.
2. Emit JSON logs including `trace_id`.
3. Trigger a request; find log line in Loki/Elasticsearch and open linked trace in Jaeger.

---

## Review questions

1. Distinguish monitoring from observability with an example novel failure.
2. What are the four metric types in Prometheus, and when use each?
3. Explain RED and USE methods and their target systems.
4. Why is structured logging preferred over plain text in production?
5. What is a trace span, and how do spans form a trace tree?
6. Why is high cardinality dangerous in metric labels?
7. What makes an alert "actionable" vs noise?

---

*Continue: Chapter 44 — Prometheus & Grafana Stack*
