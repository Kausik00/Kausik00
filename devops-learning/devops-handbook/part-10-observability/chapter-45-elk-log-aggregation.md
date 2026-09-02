# Chapter 45: ELK/EFK Log Aggregation

*DevOps Handbook — Pages 214–219 of this PDF edition*
---

## 45.1 Centralized logging rationale

Production systems generate millions of log lines across containers, VMs, and serverless functions. SSHing to individual hosts and running `grep` does not scale and fails when pods are ephemeral.

**Centralized log aggregation** collects, indexes, and searches logs from all sources in one platform—enabling correlation, compliance retention, and security analytics.

The dominant open-source stack:

| Stack | Components |
|-------|------------|
| **ELK** | Elasticsearch, Logstash, Kibana |
| **EFK** | Elasticsearch, Fluent Bit/Fluentd, Kibana |
| **ECK** | Elastic Cloud on Kubernetes (operator) |

Alternatives: **Grafana Loki** (label-based, pairs with Prometheus), **OpenSearch** (AWS fork of Elasticsearch), cloud-native **CloudWatch Logs**, **Datadog**, **Splunk**.

---

## 45.2 Architecture overview

```
Sources                Shipper              Storage           UI
───────                ───────              ───────           ──
App containers ──► Fluent Bit ──► Elasticsearch ◄── Kibana
K8s audit logs         │              (indices)
Syslog                 │
VM files ──────► Logstash ───────► (optional ingest pipelines)
```

Data flow:

1. **Generate** — Apps write stdout/stderr (JSON preferred) or log files
2. **Ship** — Agents (Fluent Bit, Filebeat) forward logs
3. **Process** — Parse, enrich, filter (Logstash or ingest pipelines)
4. **Store** — Elasticsearch indexes documents for search
5. **Visualize** — Kibana Discover, Dashboards, alerting

---

## 45.3 Elasticsearch fundamentals

**Elasticsearch** is a distributed search and analytics engine storing logs as JSON documents in **indices**.

Concepts:

| Term | Meaning |
|------|---------|
| **Index** | Collection of documents (like a database) |
| **Document** | Single log entry (JSON) |
| **Shard** | Horizontal partition of index |
| **Replica** | Copy for HA and read scaling |
| **Mapping** | Schema (field types) |

Index naming patterns:

```
logs-{service}-{yyyy.MM.dd}
filebeat-8.11.0-2026.09.01
```

**Index Lifecycle Management (ILM)** automates rollover, warm, cold, delete phases—controlling cost:

| Phase | Action |
|-------|--------|
| Hot | Active writes, fast storage |
| Warm | Shrink shards, reduce replicas |
| Cold | Searchable snapshots, cheap storage |
| Delete | Remove after retention period |

Example ILM policy (conceptual): hot 7 days → warm 30 days → delete at 90 days.

---

## 45.4 Fluent Bit vs Logstash vs Filebeat

| Tool | Role | Resource use |
|------|------|--------------|
| **Fluent Bit** | Lightweight forwarder; K8s DaemonSet standard | Very low |
| **Fluentd** | Richer routing; heavier | Medium |
| **Filebeat** | Elastic Beats shipper; simple file/container logs | Low |
| **Logstash** | Heavy transformation pipeline | High (JVM) |

Fluent Bit Kubernetes config snippet:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*.log
        Parser            docker
        DB                /var/log/flb_kube.db
        Mem_Buf_Limit     50MB

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Merge_Log           On
        Keep_Log            Off
        K8S-Logging.Parser  On

    [OUTPUT]
        Name            es
        Match           *
        Host            elasticsearch.logging.svc
        Port            9200
        Index           k8s-logs
        Suppress_Type_Name On
        tls             On
        tls.verify      On
```

Deploy Fluent Bit as **DaemonSet**—one pod per node tailing `/var/log/containers/*.log`.

---

## 45.5 Logstash pipelines

**Logstash** receives, transforms, and outputs events:

```ruby
input {
  beats {
    port => 5044
  }
}

filter {
  if [service] == "payment-api" {
    json {
      source => "message"
    }
    mutate {
      remove_field => ["message"]
    }
  }

  if [level] == "ERROR" {
    mutate {
      add_tag => ["needs_review"]
    }
  }

  geoip {
    source => "client_ip"
  }
}

output {
  elasticsearch {
    hosts => ["https://elasticsearch:9200"]
    user => "logstash_internal"
    password => "${LOGSTASH_PASSWORD}"
    index => "logs-%{[service]}-%{+YYYY.MM.dd}"
  }
}
```

**Ingest pipelines** (Elasticsearch-native) reduce Logstash dependency for simpler transforms.

Prefer parsing at **application** (structured JSON on stdout)—shipper stays dumb, fast, reliable.

---

## 45.6 Kibana for search and dashboards

**Kibana** provides:

- **Discover** — Ad-hoc search with KQL (Kibana Query Language)
- **Visualize** — Charts, tables, maps
- **Dashboard** — Combined operational views
- **Alerting** — Log threshold rules (Elastic Stack alerting)

KQL examples:

```
service: "payment-api" and level: "ERROR"
trace_id: "4bf92f3577b329da7c93630a8a323129"
@timestamp >= "2026-09-01T00:00:00" and kubernetes.namespace: "production"
response.status >= 500
```

Link logs to traces: include `trace_id` and `span_id` fields matching OpenTelemetry/Jaeger.

Saved searches for on-call:

- Payment errors last hour
- OOMKilled container events
- Authentication failures spike

---

## 45.7 EFK on Kubernetes (ECK)

Elastic **ECK operator** manages Elasticsearch, Kibana, Beats CRDs:

```yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: logging
spec:
  version: 8.11.0
  nodeSets:
    - name: default
      count: 3
      config:
        node.store.allow_mmap: false
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 100Gi
```

Sizing guidance:

| Daily log volume | Starting cluster |
|------------------|------------------|
| < 50 GB/day | 3 nodes, 8 GB heap each |
| 50–500 GB/day | Dedicated masters, hot/warm tiers |
| > 500 GB/day | Index lifecycle, dedicated ingest, consult Elastic sizing |

Heap: stay below 50% RAM, max ~31 GB per node (compressed pointers).

---

## 45.8 Security and compliance

- **TLS everywhere** — Shipper to Elasticsearch, Kibana access
- **Authentication** — Native, SAML, OIDC integration
- **RBAC** — Index-level, document-level security (paid features in Elastic)
- **Audit logs** — Who searched what (compliance)
- **PII scrubbing** — Filter at ingest; never index credit cards, passwords

```ruby
# Logstash mutate — drop sensitive fields
filter {
  mutate {
    remove_field => ["password", "credit_card", "ssn"]
  }
}
```

Regulatory retention: ILM delete phase after required period; legal hold overrides.

---

## 45.9 Loki as an alternative

**Grafana Loki** indexes labels (like Prometheus), not full text—lower cost, less flexible search.

```
{namespace="production", app="api"} |= "error" | json | level="ERROR"
```

Choose Loki when already on Grafana/Prometheus and logs are structured. Choose ELK when full-text search, complex analytics, and Elastic ecosystem (SIEM) are required.

---

## 45.10 Operational best practices

| Practice | Benefit |
|----------|---------|
| JSON structured logs | Faster queries, smaller pipelines |
| Consistent `@timestamp` UTC | Cross-region correlation |
| Sample DEBUG in prod | Cost control |
| Dedicated logging cluster | Blast radius isolation from app cluster |
| Monitor the monitors | Alert on ingest lag, cluster health yellow/red |
| Test disaster recovery | Snapshot/restore to S3 repository |

Common failures:

- **Mapping explosions** — Dynamic fields from poorly structured logs
- **Hot shards** — Uneven index sizing; use rollover
- **Ingest backpressure** — Scale Fluent Bit buffers or Elasticsearch ingest nodes

---

## 45.11 Chapter summary

- ELK/EFK centralizes logs: shippers (Fluent Bit/Filebeat) → Elasticsearch → Kibana.
- Structure logs at the source; use ILM for retention and cost control.
- Fluent Bit DaemonSets are the Kubernetes standard for container log collection.
- Secure the stack with TLS, RBAC, and PII filtering; consider Loki for label-centric workloads.

---

## 🧪 Lab 45.1 — Docker Compose ELK

1. Deploy Elasticsearch, Logstash, Kibana, and Filebeat via Docker Compose.
2. Configure a sample app to log JSON to stdout; Filebeat ships to Logstash → ES.
3. In Kibana Discover, search by `level:ERROR` and create a visualization of errors over time.

---

## 🧪 Lab 45.2 — Fluent Bit on Kubernetes

1. Install Fluent Bit DaemonSet pointing to a managed or local Elasticsearch.
2. Deploy a pod that logs JSON with `trace_id` field.
3. Query logs in Kibana by `trace_id`; verify kubernetes metadata enrichment (pod name, namespace).

---

## Review questions

1. Compare ELK and EFK—what component differs and why choose Fluent Bit?
2. What is an Elasticsearch index lifecycle policy, and why use it?
3. Why should applications emit structured JSON instead of plain text?
4. Explain the role of a DaemonSet log shipper in Kubernetes.
5. What causes mapping explosions, and how do you prevent them?
6. When would you choose Grafana Loki over Elasticsearch?
7. How do you correlate logs with distributed traces in Kibana?

---

*Continue: Chapter 46 — OpenTelemetry Distributed Tracing*
