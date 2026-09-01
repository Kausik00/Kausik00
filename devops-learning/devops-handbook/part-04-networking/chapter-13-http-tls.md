# Chapter 13: HTTP/HTTPS, TLS, and Certificates

*DevOps Handbook — Part IV, Pages 226–245*

---

## 13.1 HTTP: the application protocol of the web

**HTTP** (Hypertext Transfer Protocol) is a stateless request/response protocol at OSI Layer 7. DevOps engineers encounter HTTP in health checks, API gateways, ingress controllers, and CI cache headers daily.

### Request structure

```http
GET /api/v1/users HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer eyJhbGc...
User-Agent: curl/8.5.0
```

### Response structure

```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 42
Cache-Control: no-store

{"users":[]}
```

### Common methods

| Method | Idempotent | Typical use |
|--------|------------|-------------|
| **GET** | Yes | Read resource |
| **POST** | No | Create, actions |
| **PUT** | Yes | Replace resource |
| **PATCH** | No* | Partial update |
| **DELETE** | Yes | Remove resource |
| **HEAD** | Yes | Headers only (health) |

*PATCH idempotency depends on implementation.

### Status codes (DevOps essentials)

| Code | Meaning | Action |
|------|---------|--------|
| **200** | OK | Success |
| **301/302** | Redirect | Check Location header |
| **400** | Bad request | Client payload issue |
| **401/403** | Authn/authz | Credentials or policy |
| **404** | Not found | Route or resource missing |
| **429** | Rate limited | Backoff, quotas |
| **500** | Server error | App bug or dependency |
| **502/503/504** | Gateway/upstream | LB, overload, timeout |

---

## 13.2 HTTP/1.1 vs HTTP/2 vs HTTP/3

| Version | Transport | Notes |
|---------|-----------|-------|
| **HTTP/1.1** | TCP | Head-of-line blocking on one connection |
| **HTTP/2** | TCP + TLS (common) | Multiplexed streams, header compression |
| **HTTP/3** | QUIC (UDP) | Faster handshakes, mobile lossy networks |

Ingress controllers (nginx, Envoy, ALB) terminate HTTP/2 from clients and may speak HTTP/1.1 to legacy backends—know your **end-to-end protocol** when debugging streaming and timeouts.

---

## 13.3 HTTPS and TLS

**HTTPS** is HTTP over **TLS** (Transport Layer Security). TLS provides:

1. **Confidentiality** — encrypted payload.
2. **Integrity** — tamper detection.
3. **Authentication** — server (and optionally client) identity via certificates.

### TLS handshake (simplified)

```
ClientHello (supported ciphers, SNI)
    ← ServerHello, certificate, key exchange
Client verifies cert chain → generates session keys
Encrypted application data (HTTP)
```

**SNI** (Server Name Indication) lets one IP host many HTTPS sites—virtual hosting at TLS layer. Missing SNI breaks multi-tenant ingress.

Inspect with:

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
curl -vI https://api.example.com
```

---

## 13.4 Certificates and PKI

A **certificate** binds a public key to identities (DNS names in **SAN**—Subject Alternative Name). Browsers trust **Certificate Authorities (CAs)** rooted in the system trust store.

| Component | Role |
|-----------|------|
| **Private key** | Stays secret on server or HSM |
| **CSR** | Certificate Signing Request → sent to CA |
| **Leaf cert** | Presented to clients |
| **Intermediate + root** | Chain of trust to a trusted root |

### Let's Encrypt and ACME

**ACME** automates issuance (cert-manager on Kubernetes, Caddy, Traefik). Certs are short-lived (90 days)—automation is mandatory.

```yaml
# cert-manager Certificate (illustrative)
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
spec:
  secretName: api-tls-secret
  dnsNames:
    - api.example.com
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
```

---

## 13.5 mTLS (mutual TLS)

Standard TLS authenticates the **server** to the client. **mTLS** also requires clients to present certificates—common in service meshes (Istio, Linkerd) and zero-trust internal APIs.

DevOps tasks:

- Rotate client certs before expiry.
- Store CA bundles in trust stores for sidecars.
- Monitor handshake failure metrics.

---

## 13.6 Cipher suites and hardening

Weak ciphers and old TLS versions (1.0, 1.1) are disabled in modern compliance baselines. Prefer **TLS 1.2+** and **TLS 1.3** where supported.

Test external posture:

```bash
# Using testssl.sh or SSL Labs API for audits
nmap --script ssl-enum-ciphers -p 443 api.example.com
```

Align ingress `ssl_protocols` / `ssl_ciphers` with security team policy—document exceptions.

---

## 13.7 HTTP headers DevOps should know

| Header | Purpose |
|--------|---------|
| **Host** | Virtual host routing |
| **X-Forwarded-For** / **Forwarded** | Client IP through proxies |
| **X-Request-ID** | Correlation across services |
| **Strict-Transport-Security** | Force HTTPS (HSTS) |
| **Content-Security-Policy** | Mitigate XSS |
| **Cache-Control** | CDN and browser caching |

Misconfigured **X-Forwarded-For** trust allows IP spoofing in rate limits—only trust headers from known L7 proxies.

---

## 13.8 Timeouts, keep-alive, and load balancers

| Setting | Symptom if wrong |
|---------|------------------|
| **Client idle timeout** | Premature connection close |
| **LB idle timeout** | 502 during long requests |
| **Upstream read timeout** | 504 gateway timeout |
| **Keep-alive** | Extra TCP/TLS handshakes if disabled |

AWS ALB default idle timeout is 60s—long-running exports may need tuning on both app and LB.

---

## 13.9 Debugging TLS in production

Checklist:

1. **Expiry** — `openssl x509 -enddate`; alert 30 days ahead.
2. **Chain** — missing intermediate → Android/old clients fail.
3. **SAN** — cert must cover exact hostname (`api` vs `api.internal`).
4. **Clock skew** — NTP drift causes "cert not yet valid."
5. **SNI** — curl without `-H 'Host:'` or wrong `-servername`.

```bash
echo | openssl s_client -connect wrong-host.example.com:443 -servername api.example.com 2>&1 | grep subject
```

---

## 13.10 Chapter summary

- HTTP methods and status codes drive **health checks and SLOs**.
- **TLS** encrypts and authenticates; understand handshake, SNI, and chains.
- Automate cert lifecycle with **ACME/cert-manager**—manual renewals fail at scale.
- **mTLS** secures east-west traffic in meshes and zero-trust designs.
- Align **timeouts and forwarded headers** between apps, proxies, and LBs.

---

## 🧪 Lab 13.1 — Inspect a live certificate

1. Run `openssl s_client` against three HTTPS sites you operate or public APIs.
2. Record issuer, SANs, and expiry dates in a table.
3. Simulate SNI: connect by IP with `-servername` and observe cert change on shared IP hosts.

---

## 🧪 Lab 13.2 — Broken chain simulation

1. In a lab nginx/ingress, serve a leaf cert without intermediate bundle.
2. Verify failure with `curl` on a minimal trust store container.
3. Fix by appending intermediate; document the full chain file order.

---

## Review questions

1. What is the difference between HTTP 502 and 504?
2. What role does SNI play on shared load balancer IPs?
3. Name the three security properties TLS provides.
4. Why are short-lived Let's Encrypt certs acceptable?
5. What header carries client IP through proxies, and what is the spoofing risk?

---

*Next: [Chapter 14 — Load Balancing, Proxies, and CDN](./chapter-14-load-balancing-cdn.md)*
