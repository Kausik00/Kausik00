# Chapter 68: SLO Observability Practice

*DevOps Handbook — Pages 357–364 of this PDF edition*

*DevOps Handbook — Workbook*
---

## 68.1 From dashboards people ignore to SLOs people use

Observability practice fails in two opposite ways: **no data**, and **so much data that on-call pages on CPU**. This workbook operationalizes RED and USE, Prometheus **recording rules**, **alert routing**, and **Grafana as code** so that the next incident uses the same graphs and pages that CI already tests.

Chapter 43–47 covered fundamentals, Prometheus/Grafana, logs, traces, and SLO theory. Here we implement a **working reliability stack** for one service and a platform.

| Model | Use when |
|-------|----------|
| **RED** (Rate, Errors, Duration) | Request/response services |
| **USE** (Utilization, Saturation, Errors) | Resources: CPU, disk, queue, thread pool |
| **Four golden signals** | Same family as RED + saturation |
| **SLI/SLO/error budget** | Business reliability targets |

Do not alert on RED **and** USE **and** 40 raw metrics. Alert on **customer-facing SLIs** and a small set of **symptom pages**; keep USE on dashboards and in **diagnostic** alerts with lower urgency.

---

## 68.2 Instrumenting RED properly

For HTTP:

```promql
# Rate
sum(rate(http_requests_total{service="shop"}[5m]))

# Errors
sum(rate(http_requests_total{service="shop",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="shop"}[5m]))

# Duration (histogram)
histogram_quantile(0.99,
  sum by (le) (rate(http_request_duration_seconds_bucket{service="shop"}[5m]))
)
```

**Cardinality:** labels `user_id`, `email`, `request_id` on metrics will **melt** Prometheus. Put high-cardinality identifiers in **traces and logs**. Metrics labels: `service`, `route` (bounded), `status_class`, `region`.

**Route cardinality:** `/users/123` as a label is an incident. Use `/users/:id` from the framework.

**Exemplars** link a histogram bucket to a trace ID—configure Prometheus and Grafana to jump from a latency spike to Tempo/Jaeger (Chapter 46).

Batch/async services: RED becomes **lag, error, throughput** (queue depth is USE saturation).

---

## 68.3 USE for nodes, JVM, and pipelines

| Resource | Utilization | Saturation | Errors |
|----------|-------------|------------|--------|
| CPU | `1 - idle` | run queue | N/A (or machine checks) |
| Memory | used / total | OOM, reclaim | alloc failures |
| Disk | `1 - avail` | `await`, queue | I/O errors |
| NIC | bits / speed | drops, qdisc | checksum |
| Thread pool | busy threads | queue length | rejected |
| Connection pool | in-use / max | waiters | timeouts |

```promql
# Node CPU utilization (cadvisor / node_exporter)
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))

# Disk saturation proxy
rate(node_disk_io_time_seconds_total[5m])

# JVM heap
jvm_memory_used_bytes{area="heap"} / jvm_memory_max_bytes{area="heap"}
```

**Saturation before utilization:** a disk at 40% bytes can be 100% busy (Chapter 61). Page on **latency SLI** first; USE explains **why**.

---

## 68.4 Choosing SLIs that match user experience

| Service | Availability SLI | Latency SLI | Extra |
|---------|------------------|-------------|--------|
| Checkout API | 2xx+3xx+4xx (except 429 policy) / total | 99th < 300ms | payment success |
| Search | result returned | 95th | relevance is product, not SLO |
| Pipeline | jobs succeeded | freshness < 15m | completeness |
| Kafka consumer | lag < N | — | poison messages |
| Platform CI | jobs not queued > 10m | duration | Chapter 67 |

**Do not** count 404 as errors for a public website that expects 404. **Do** count 401 if your SLO is “auth works.” Be explicit.

**Error budget** for 99.9% monthly availability ≈ 43 minutes. Burn-rate alerts (Google SRE workbook) detect **fast burns** (10×) and **slow burns** (1×) separately.

```promql
# Multi-window burn (simplified 5m/1h)
(
  1 -
  (
    sum(rate(http_requests_total{status!~"5.."}[5m]))
    /
    sum(rate(http_requests_total[5m]))
  )
)
> (14.4 * (1 - 0.999))
```

Tune multipliers to your window; do not copy numbers blindly. Test against **historical** incident timelines.

---

## 68.5 Recording rules: make dashboards and alerts cheap

Raw PromQL on huge `rate()` over many series times out Grafana. **Recording rules** precompute.

```yaml
# prometheus/rules/shop.yml
groups:
  - name: shop-red
    interval: 30s
    rules:
      - record: shop:http_requests:rate5m
        expr: sum by (route, status_class, region) (rate(http_requests_total{service="shop"}[5m]))
      - record: shop:http_errors:rate5m
        expr: sum by (route, region) (rate(http_requests_total{service="shop",status_class="5xx"}[5m]))
      - record: shop:http_availability:ratio5m
        expr: |
          1 - (
            shop:http_errors:rate5m
            / clamp_min(sum by (route, region) (shop:http_requests:rate5m), 1e-9)
          )
      - record: shop:http_duration:p99:5m
        expr: |
          histogram_quantile(0.99,
            sum by (le, route, region) (rate(http_request_duration_seconds_bucket{service="shop"}[5m]))
          )
```

Naming convention `level:metric:operations` (Prometheus docs) keeps rules navigable.

**Rules as code:** PRs required; `promtool check rules`; unit test with `promtool test rules`.

```yaml
# shop_test.yml
rule_files: [shop.yml]
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'http_requests_total{service="shop",status="200",route="/buy"}'
        values: '0+10x10'
    promql_expr_test:
      - expr: shop:http_requests:rate5m
        eval_time: 10m
        exp_samples:
          - labels: '{route="/buy",status_class="2xx"}'
            value: 10/60  # illustrative; write real expected
```

Write **real** expected values in the lab; the snippet above is a structure reminder.

**Federation / remote write:** record on the **ingesting** Prometheus or in **Thanos/Mimir Ruler**. Recording in Grafana only (ad-hoc) will not page.

---

## 68.6 Alerting: symptoms, routing, and silence hygiene

### 68.6.1 Alert rules that page vs ticket

```yaml
groups:
  - name: shop-slo
    rules:
      - alert: ShopAvailabilityFastBurn
        expr: shop:slo:burn_rate_1h > 14
        for: 2m
        labels:
          severity: page
          service: shop
          team: checkout
        annotations:
          summary: "Shop availability fast-burn"
          runbook: "https://runbooks.example/shop-availability"
          dashboard: "https://grafana.example/d/shop-red"
      - alert: ShopDiskExpectedFull
        expr: predict_linear(node_filesystem_avail_bytes{mountpoint="/data"}[6h], 24*3600) < 0
        for: 1h
        labels:
          severity: ticket
          team: platform
```

**for:** absorbs blips. Fast-burn uses a short `for`; prediction alerts use long `for`.

**Inhibit:** if `InstanceDown`, inhibit `TargetMissing` on the same instance. Mis-tuned inhibit **hides** remaining symptoms.

### 68.6.2 Alertmanager routing

```yaml
route:
  receiver: default-ticket
  group_by: ['service', 'alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers:
        - severity = page
      receiver: pagerduty-checkout
      continue: false
    - matchers:
        - team = platform
      receiver: slack-platform
receivers:
  - name: pagerduty-checkout
    pagerduty_configs:
      - service_key_file: /etc/am/pd-checkout
  - name: slack-platform
    slack_configs:
      - channel: '#platform-alerts'
        send_resolved: true
  - name: default-ticket
    webhook_configs:
      - url: https://itsm.example/hooks/prom
```

**group_by: ['...']** too fine = 200 pages; too coarse = mixed services in one notification. Start with `service, alertname`.

**Time intervals:** no pages for `severity=ticket` during weekends if a human ticket queue exists; **never** silence availability pages globally for a holiday without an on-call.

**Notification templates** must include graph URL, runbook, and **firing labels**. A page that says `{{ $labels.instance }} down` without `cluster` is how you SSH the wrong region.

### 68.6.3 Dead man’s switch

If Alertmanager or Prometheus dies, **silence is not health**. Heartbeat to Dead Man’s Snitch / PagerDuty integration / `Watchdog` alert that **always fires** and is inverted by the pager.

```yaml
- alert: Watchdog
  expr: vector(1)
  labels: { severity: heartbeat }
```

---

## 68.7 Grafana as code

Click-ops Grafana cannot be reviewed, diffed, or restored. Production patterns:

1. **Grafana Kubernetes Operator** or **Terraform Grafana provider** or **grafonnet/jsonnet** or **dashboard-as-JSON in Git**.
2. **Provisioning** datasources and notification policies from files.
3. **Folder + RBAC** as code.

```yaml
# grafana/provisioning/datasources/ds.yml
apiVersion: 1
datasources:
  - name: Mimir
    type: prometheus
    access: proxy
    url: http://mimir.ns.svc:9009/prometheus
    jsonData:
      timeInterval: 30s
      exemplarTraceIdDestinations:
        - name: traceID
          datasourceUid: tempo
```

```json
{
  "title": "Shop RED",
  "uid": "shop-red",
  "tags": ["slo", "shop"],
  "panels": []
}
```

Prefer **Grafana dashboard UID stable** so runbook links do not rot. Generate JSON from **jsonnet** (`grafonnet`) or Python (`grafanalib`) so repeats (three regions) are loops, not copy-paste.

**Variables:** `cluster`, `namespace`, `service` from label_values. Default to **production**.

**Alerting in Grafana vs Prometheus:** pick **one** source of paging truth. Dual paging is an outage amplifier. Common split: Prometheus Alertmanager pages; Grafana for visualization and **Grafana-managed** only for datasource types Prom cannot see (if any).

**CI:** `grafana dashboard lint` (grafonnet), screenshot diffs in PR (optional), and a **staging Grafana** that applies Git.

---

## 68.7.1 Dashboard design that on-call can use in sixty seconds

A service Grafana folder should contain a **small** set of boards, not forty orphans:

| Dashboard | Panels |
|-----------|--------|
| SLO / error budget | Availability, burn, remaining budget this period |
| RED | Rate, error ratio, p50/p95/p99 by route |
| USE (app) | JVM/Go/Python runtime, pool saturation |
| Dependencies | Downstream error rates, DB, cache |
| Infra | The nodes/pods this service actually uses |

Top of every board: **links** to runbook, traces, logs, Argo app, catalog entity (Chapter 70). Time zone UTC. Default range 6h. A board that defaults to 90 days and 200 panels will not be used during a page.

Use **shared Grafana library panels** for “p99 latency” so histogram_quantile is not reinvented with off-by-one `le` mistakes.

**Permissions:** editors for platform; viewers for product. Production notification channels are not editable by everyone (accidental silence).

---

## 68.7.2 Long-term storage and “the graph is empty”

On-call: “Grafana shows no data.” Decision tree:

1. Datasource URL / tenant header (Mimir org-id) wrong after a cutover.
2. Recording rule name changed; dashboard still queries the old `job:` prefix.
3. Retention: 5m resolution gone after 24h; zoomed range only has 1h aggregates.
4. Label renamed (`service` vs `app`)—relabel in scrape, not in panic.
5. Prometheus restarted and **WAL replay**; brief gap is OK, hour gap is disk.

Document **retention tiers** in the dashboard README: raw 15d, 5m 90d, 1h 1y. SLOs over 30 days must use a recording rule that survives compaction.

---

## 68.8 Tracing and logs in the SLO loop

When a burn alert fires:

1. Open the RED dashboard (rate/err/p99 by route).
2. Jump via exemplar to traces for slow 5xx.
3. Log query **bounded** by trace_id / request_id.
4. If the SLI is fine but users complain, the SLI is **wrong** (map error, regional DNS—Chapter 62).

Do not start in `kubectl logs` unless the page already named a pod.

---

## 68.9 Platform SLOs (the IDP is a service)

Platform teams need SLOs too (Chapter 70):

| Platform SLI | Example target |
|--------------|----------------|
| CI queue time | 95% < 2 minutes |
| Cluster API availability | 99.95% |
| Golden-path scaffold success | 99% |
| Artifact registry availability | 99.9% |
| Mean time to provision namespace | < 10 minutes |

Page platform on-call on **platform SLIs**, not on every app CrashLoop (route those to app teams via labels).

---

## 68.10 Worked incident: slow burn missed by spike-only alerts

**Setup:** Alert only `error_ratio > 5% for 5m`. A 1.2% error rate for 18 hours blew the monthly budget; nobody paged.

**Fix:** Implement multi-window multi-burn SLO alerts. Add a weekly **error budget report** in Grafana (stat panel) emailed to product.

**Lesson:** High-threshold short-window alerts miss death by a thousand 500s.

---

## 🧪 Lab 68.1 — RED dashboard from recording rules

1. Run Prometheus locally with a demo `http_requests_total` (or `prometheus` itself).
2. Add recording rules; `promtool check rules`.
3. Point Grafana at the recorded metrics (empty panels until rules fire—wait `interval`).
4. Export dashboard JSON into Git.

---

## 🧪 Lab 68.2 — Burn-rate unit test

1. Write `promtool test rules` with synthetic series that should fire `FastBurn`.
2. Write a case that should **not** fire (brief spike under `for`).
3. Commit tests in CI (Chapter 67).

---

## 🧪 Lab 68.3 — Alertmanager routes

1. Use `amtool` or a docker Alertmanager.
2. Send two alerts: `severity=page,team=checkout` and `severity=ticket,team=platform`.
3. Prove they hit different receivers (log/webhook to files).
4. Add inhibit; prove InstanceDown suppresses a dependent alert **without** suppressing another service.

---

## 🧪 Lab 68.4 — Grafana provisioning

1. Provision a datasource via YAML.
2. Load a dashboard UID `shop-red`.
3. Delete the Grafana volume; restart; confirm dashboard returns from Git, not from a backup of SQLite clicks.

---

## 68.10.1 SLI implementation pitfalls

**Success definition leaks:** counting only `status=200` treats `301` and `204` as errors. Use a documented set.

**Load-balancer vs app SLI:** the NLB can be healthy while the app 500s; the app can be healthy while TLS at the edge fails (Chapter 62). Pick the **user-visible** hop—usually the edge that serves browsers—and **also** keep an internal SLI so you can split blame.

**Batching windows:** `rate()[1m]` on a 15s scrape is noisy; `[5m]` is a common compromise. Align recording `interval` with scrape.

**Multi-region:** an SLO averaged across regions hides a dead region. Use **worst-region** or **per-region** budgets for anything with partitioned users.

**Synthetic vs real traffic:** synthetics catch “totally down”; they miss “checkout broken for one payment method.” Combine.

---

## 68.11 Cardinality and cost (FinOps meets Prom)

| Control | Practice |
|---------|----------|
| Relabel drop | Drop `pod` from expensive metrics if node-level USE suffices |
| Recording aggregation | Drop instance where not needed |
| Mimir/Thanos compaction | Retention tiers |
| Exemplar sampling | Not every request |
| Log volume | Index IDs, not bodies |

A metric with 2 million series is an **incident** (Chapter 57 cost + this chapter latency). Alert on `prometheus_tsdb_head_series` growth.

---

## 68.12 On-call quality metrics

Track **pages per week**, **% actionable**, **time-to-ack**, **time-to-recover**, **silences created**. If 40% of pages are “known flake,” you do not have an SLO—you have pager-driven burnout. Fix the alert or the system.

---

## Review questions

1. Why can disk USE saturation be high when utilization (bytes) is low?
2. Give a high-cardinality label that should never be on a Prometheus metric. Where does it belong?
3. Why recording rules instead of raw histogram_quantile in every Grafana panel?
4. Explain fast-burn vs slow-burn alerts in terms of error budget.
5. What does Alertmanager `group_by` control, and what is a reasonable default?
6. Why a Watchdog/heartbeat alert?
7. Why store Grafana dashboards in Git with stable UIDs?
8. How do exemplars connect RED latency to traces?
9. When should platform-on-call **not** receive an application CrashLoop page?
10. Design an SLI for a CI merge queue. What is a poor proxy metric?

---

## Further practice

Re-read Chapter 47 after this lab-heavy chapter. Theory without recording rules and routing does not page correctly; routing without SLIs pages too often.
