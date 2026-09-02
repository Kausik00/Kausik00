# Chapter 14: Load Balancing, Proxies, and CDN

*DevOps Handbook — Pages 60–64 of this PDF edition*
---

## 14.1 Why load balancing exists

Single servers fail and saturate. **Load balancers** distribute traffic across healthy backends, terminate TLS, enforce routing rules, and provide a stable **virtual IP/DNS name** while instances churn behind them.

Goals:

| Goal | Mechanism |
|------|-----------|
| **Availability** | Health checks remove bad targets |
| **Scalability** | Add backends horizontally |
| **Maintainability** | Rolling deploys without client reconfiguration |
| **Security** | WAF, TLS offload, DDoS absorption (with CDN) |

---

## 14.2 Layer 4 vs Layer 7 load balancing

| Type | OSI layer | Sees | Routing basis | Examples |
|------|-----------|------|---------------|----------|
| **L4 (NLB)** | Transport | IP, port, TCP/UDP | IP:port, flow hash | AWS NLB, HAProxy TCP mode |
| **L7 (ALB/HTTP)** | Application | HTTP headers, path, cookies | URL path, Host, headers | AWS ALB, nginx, Envoy |

**L4** is faster and protocol-agnostic—great for databases, gRPC-TLS passthrough, or extreme throughput.

**L7** enables path-based routing (`/api → service A`), host-based routing (`api.` vs `www.`), sticky sessions, and request manipulation.

Many architectures stack both: **CDN/L7 edge → L7 ingress → L4 service mesh**.

---

## 14.3 Load balancing algorithms

| Algorithm | Behavior | Use when |
|-----------|----------|----------|
| **Round robin** | Cycle targets evenly | Homogeneous backends |
| **Least connections** | Send to least busy | Long-lived connections |
| **Weighted** | Favor stronger instances | Mixed instance sizes |
| **IP hash** | Same client → same backend | Simple session stickiness |
| **Random / Maglev** | Hash tables for stability | Large clusters (Google LB) |

**Health checks** must reflect **application** health—not just TCP open port. Return 200 on `/health` with dependency checks (DB ping) when appropriate.

Unhealthy threshold and interval tune flapping vs slow detection:

```
interval: 10s
timeout: 5s
healthy_threshold: 2
unhealthy_threshold: 3
```

---

## 14.4 Reverse proxies vs forward proxies

| | Reverse proxy | Forward proxy |
|---|---------------|---------------|
| **Sits** | In front of servers | In front of clients |
| **Clients know** | Backend exists (often hidden) | Proxy exists |
| **Examples** | nginx, Traefik, ALB | Corporate HTTP proxy, Squid |
| **DevOps use** | Ingress, API gateway | Egress control from CI/VPC |

A **reverse proxy** terminates client connections and opens new ones to upstreams—enabling TLS offload, buffering, and rate limits.

---

## 14.5 Common proxy software

### nginx (ingress workhorse)

```nginx
upstream api_backend {
    least_conn;
    server 10.0.1.10:8080 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8080 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    location / {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### HAProxy

Popular for TCP and HTTP with advanced health checks and stick tables.

### Envoy

Data plane for Istio and modern API gateways; dynamic config via xDS.

Choose based on team expertise and platform (managed cloud LB vs self-run on VMs/K8s).

---

## 14.6 Session persistence (stickiness)

Stateful apps without shared session store may need **sticky sessions**:

- **Cookie-based** (ALB insert cookie).
- **Source IP affinity** (breaks behind carrier NAT—fragile).

Prefer **external session store** (Redis) over stickiness when possible—stickiness complicates deploys and failover.

---

## 14.7 Content Delivery Networks (CDN)

A **CDN** caches static and cacheable dynamic content at **edge PoPs** close to users—reducing latency and origin load.

| Benefit | Explanation |
|---------|-------------|
| **Latency** | RTT to edge << RTT to origin region |
| **Scale** | Absorb traffic spikes at edge |
| **DDoS** | Distributed scrubbing (vendor-dependent) |
| **TLS at edge** | Terminate close to user |

Providers: CloudFront, Fastly, Cloudflare, Akamai, Google Cloud CDN.

### Cache control

Origin sets policy via headers:

```http
Cache-Control: public, max-age=3600
Cache-Control: no-store
ETag: "abc123"
```

**Cache key** often includes path, query string rules, and `Vary` headers—misconfiguration serves wrong content to wrong users (classic bug: caching authenticated pages without `private`).

### Purge and invalidation

Deploy new `app.js` → purge `/static/*` or use **filename hashing** (`app.a1b2c3.js`) so cache busting is automatic.

---

## 14.8 Global load balancing and failover

**Geo DNS** or **anycast** routes users to nearest healthy region:

```
User in EU → GSLB → eu-west-1 (healthy)
Failover → us-east-1 if region unhealthy
```

Requires **state replication** or accept read-only failover; DNS TTL and health probe design determine RTO.

---

## 14.9 Kubernetes ingress pattern

```
Internet → Cloud LB → Ingress Controller (nginx/Envoy)
    → Service (ClusterIP) → Pod endpoints
```

`Ingress` resources define host/path rules; **Gateway API** is the evolving standard with clearer L4/L7 separation.

Service mesh adds **sidecar proxies** for east-west L7 policy without changing Service types.

---

## 14.10 Observability for load balancers

Monitor:

| Metric | Indicates |
|--------|-----------|
| **Request count / latency p99** | User experience |
| **5xx rate** | Upstream or LB misconfig |
| **Healthy host count** | Deploy or health check failures |
| **TLS handshake time** | Cert or cipher issues |
| **Cache hit ratio** | CDN efficiency |

Log **X-Request-ID** from edge through origin for distributed traces.

---

## 14.11 Chapter summary

- **L4** balances connections; **L7** routes HTTP semantics—choose per use case.
- Health checks and algorithms must match **workload shape** (short vs long connections).
- **Reverse proxies** enable TLS, routing, and security at the edge.
- **CDNs** cache at PoPs—control with headers, hashed assets, and purge strategy.
- Instrument LB and CDN metrics as part of **SLO dashboards**.

---

## 🧪 Lab 14.1 — nginx upstream failover

1. Run two backend containers on ports 8081/8082 returning different bodies.
2. Configure nginx upstream with one server marked down.
3. curl through nginx; confirm traffic to healthy only.
4. Stop healthy container; observe 502 until nginx marks unhealthy.

---

## 🧪 Lab 14.2 — CDN cache headers

1. Serve a static file from a simple web server with `Cache-Control: max-age=60`.
2. If CDN unavailable, use two curl requests and `Age` header via local cache proxy—or document expected CDN behavior.
3. Change file content without purge; explain stale risk.
4. Switch to content-hashed filename; show safe long `max-age`.

---

## Review questions

1. When would you choose L4 over L7 load balancing?
2. Why is TCP-open health check insufficient for many apps?
3. Difference between reverse and forward proxy?
4. How do cache keys cause authenticated content leaks?
5. What Kubernetes component typically replaces raw nginx on bare VMs?

---

*Next: [Chapter 15 — Cloud Networking Patterns (VPC overview)](./chapter-15-cloud-networking-vpc.md)*
