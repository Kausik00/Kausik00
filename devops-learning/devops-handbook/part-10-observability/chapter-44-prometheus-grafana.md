# Chapter 44: Prometheus & Grafana Stack

*DevOps Handbook — Pages 208–213 of this PDF edition*
---

## 44.1 The Prometheus ecosystem

**Prometheus** is an open-source monitoring system and time-series database (TSDB) designed for cloud-native environments. Created at SoundCloud, now a CNCF graduated project, it powers metrics collection for Kubernetes and microservices worldwide.

**Grafana** visualizes metrics from Prometheus (and 100+ other sources), providing dashboards, alerting UI, and exploration.

Typical stack:

```
Exporters / Apps ──scrape──► Prometheus ──query──► Grafana
       ▲                         │
       │                         ├── Alertmanager ──► PagerDuty/Slack
   Service discovery             └── Recording rules
   (K8s, Consul, EC2)
```

Prometheus uses a **pull model**: it scrapes HTTP `/metrics` endpoints on intervals. Pushgateway exists for short-lived batch jobs but is not the default pattern.

---

## 44.2 Prometheus architecture

| Component | Role |
|-----------|------|
| **Prometheus server** | Scrapes, stores TSDB, evaluates rules |
| **Exporters** | Expose third-party metrics (node_exporter, mysqld_exporter) |
| **Alertmanager** | Dedupes, routes, silences alerts |
| **Pushgateway** | Accept push for batch jobs |
| **Service discovery** | Dynamic scrape targets |

Data model:

- **Metric name** + **labels** identify a time series
- **Samples**: float value + millisecond timestamp
- Retention default ~15 days (configurable); long-term storage via Thanos, Cortex, Mimir

---

## 44.3 Prometheus configuration

`prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: production
    region: us-east-1

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: node
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: $1
```

**Relabeling** filters and transforms targets before scrape—essential for Kubernetes pod discovery.

Pod annotation example:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

---

## 44.4 PromQL essentials

**PromQL** (Prometheus Query Language) queries time series.

Basic selectors:

```promql
# Instant vector: current value
http_requests_total

# Filter by label
http_requests_total{status="500", service="api"}

# Rate over 5 minutes (counter → per-second rate)
rate(http_requests_total[5m])

# Error ratio
sum(rate(http_requests_total{status=~"5.."}[5m])) 
/ 
sum(rate(http_requests_total[5m]))

# p99 latency from histogram
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)

# CPU usage (node exporter)
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

Common functions:

| Function | Use |
|----------|-----|
| `rate()` | Per-second rate for counters |
| `increase()` | Total increase over range |
| `histogram_quantile()` | Percentiles from histogram buckets |
| `avg_over_time()` | Gauge averages |
| `predict_linear()` | Disk fill prediction |
| `absent()` | Detect missing metrics |

---

## 44.5 Alerting rules and Alertmanager

Recording rules pre-compute expensive queries; alerting rules fire when conditions hold.

`rules/api.yml`:

```yaml
groups:
  - name: api_alerts
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job, service)

      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
            /
            sum(rate(http_requests_total[5m])) by (service)
          ) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High 5xx rate on {{ $labels.service }}"
          description: "Error rate {{ $value | humanizePercentage }} for 5m"

      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
          ) > 1
        for: 10m
        labels:
          severity: warning
```

Alertmanager routing (`alertmanager.yml`):

```yaml
route:
  receiver: default
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: pagerduty
    - match:
        severity: warning
      receiver: slack

receivers:
  - name: pagerduty
    pagerduty_configs:
      - service_key: SECRET
  - name: slack
    slack_configs:
      - api_url: SECRET
        channel: '#alerts'
  - name: default
    slack_configs:
      - api_url: SECRET
        channel: '#alerts-low'
```

Use **inhibition rules** to suppress noisy dependent alerts (node down inhibits all pod alerts on that node).

---

## 44.6 Grafana dashboards

Install Grafana, add Prometheus data source (`http://prometheus:9090`), build dashboards.

Example panel queries:

| Panel | PromQL |
|-------|--------|
| Request rate | `sum(rate(http_requests_total[5m])) by (service)` |
| Error rate | ratio query above |
| p50/p95/p99 | `histogram_quantile(0.95, ...)` |
| Saturation | `process_resident_memory_bytes`, queue depth gauges |

Dashboard best practices:

- **Row per service** or golden signals template
- **Variables** — `$service`, `$environment` dropdowns via label values
- **Annotations** — Deploy markers from CI webhook
- **Version control** — Export JSON to Git (Grafana provisioning or Grafana-as-code tools like **Grafonnet**, **Terraform grafana provider**)

Provisioning example `datasources.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

---

## 44.7 Kubernetes deployment patterns

**kube-prometheus-stack** Helm chart bundles Prometheus, Alertmanager, Grafana, and default Kubernetes dashboards:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

**Prometheus Operator** manages Prometheus, Alertmanager, ServiceMonitor, PodMonitor CRDs:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-metrics
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: api
  namespaceSelector:
    matchNames:
      - production
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics
```

**Thanos** or **Grafana Mimir** add long-term storage and global query across clusters.

---

## 44.8 Exporters and instrumentation

Common exporters:

| Exporter | Metrics source |
|----------|----------------|
| `node_exporter` | Linux host CPU, memory, disk, network |
| `blackbox_exporter` | Probe HTTP/TCP/ICMP uptime |
| `kube-state-metrics` | Kubernetes object state |
| `postgres_exporter` | PostgreSQL stats |
| `redis_exporter` | Redis stats |

Application instrumentation via Prometheus client libraries (Go, Python, Java, etc.) or **OpenTelemetry** exporting to Prometheus format.

Blackbox probe config:

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: [200, 201, 204]
      preferred_ip_protocol: ip4
```

---

## 44.9 Operations and troubleshooting

| Issue | Investigation |
|-------|---------------|
| Target down | Prometheus → Status → Targets; check network, TLS, path |
| Missing metrics | Verify exposition format, label typos |
| High memory | Reduce retention, cardinality, scrape frequency |
| Alert storm | Alertmanager grouping, inhibition, `for:` duration |
| Query timeout | Recording rules, optimize PromQL, scale Prometheus |

Capacity planning: ~1–2 bytes per sample; estimate `(metrics × labels × scrape_freq × retention)`.

Security: authenticate Grafana, restrict Prometheus admin API, TLS for scrape in zero-trust networks.

---

## 44.10 Chapter summary

- Prometheus scrapes and stores metrics; PromQL analyzes time series; Alertmanager routes alerts.
- Grafana visualizes Prometheus data with dashboards, variables, and provisioning-as-code.
- Kubernetes deployments use ServiceMonitors, kube-prometheus-stack, and optional long-term storage (Thanos/Mimir).
- Control cardinality, use recording rules, and design actionable alerts tied to symptoms.

---

## 🧪 Lab 44.1 — Local Prometheus + Grafana

1. Run Prometheus, node_exporter, and Grafana via Docker Compose.
2. Scrape node metrics; build a dashboard with CPU, memory, disk panels.
3. Add an alerting rule for disk > 85%; route to a webhook receiver (use webhook.site for testing).

---

## 🧪 Lab 44.2 — ServiceMonitor on Kubernetes

1. Deploy kube-prometheus-stack on a test cluster.
2. Expose a sample app with `/metrics`; create ServiceMonitor.
3. Confirm targets appear in Prometheus UI; import a RED metrics dashboard.

---

## Review questions

1. Why does Prometheus use pull-based scraping instead of push by default?
2. Explain the difference between recording rules and alerting rules.
3. Write PromQL for 5xx error rate as a percentage over 5 minutes.
4. What problem does Alertmanager solve that Prometheus alerts alone do not?
5. How do ServiceMonitors differ from static scrape configs?
6. Why is high label cardinality a problem for Prometheus?
7. When would you add Thanos or Mimir to the stack?

---

*Continue: Chapter 45 — ELK/EFK Log Aggregation*
