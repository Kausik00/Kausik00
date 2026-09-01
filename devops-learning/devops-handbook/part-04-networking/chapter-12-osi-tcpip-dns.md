# Chapter 12: OSI Model, TCP/IP, DNS Deep Dive

*DevOps Handbook — Part IV, Pages 201–225*

---

## 12.1 Why models matter during incidents

When a user reports "the site is down," you need a **mental stack** to isolate the layer at fault: physical link, IP routing, DNS, TLS, HTTP, or application logic. The **OSI model** (7 layers) and the practical **TCP/IP model** (4 layers) provide shared vocabulary for engineers and vendors.

You will not configure "Layer 5" in AWS—but you will say "this looks like L4" or "DNS is broken" and save hours.

---

## 12.2 OSI seven layers (reference)

| Layer | Name | PDU | Examples |
|-------|------|-----|----------|
| 7 | Application | Data | HTTP, DNS, SMTP |
| 6 | Presentation | Data | TLS encryption, compression |
| 5 | Session | Data | Session management (often folded into app) |
| 4 | Transport | Segment | TCP, UDP |
| 3 | Network | Packet | IP, ICMP, routing |
| 2 | Data Link | Frame | Ethernet, MAC, switches |
| 1 | Physical | Bits | Cables, fiber, Wi-Fi radio |

**Mnemonic:** *All People Seem To Need Data Processing* (top-down) or *Please Do Not Throw Sausage Pizza Away* (bottom-up).

DevOps work concentrates on **Layers 3–7** in cloud environments; hardware L1/L2 is abstracted but still appears in hybrid/on-prem links.

---

## 12.3 TCP/IP four-layer model (operational)

| TCP/IP layer | Maps to OSI | DevOps touchpoints |
|--------------|-------------|-------------------|
| **Application** | 5–7 | HTTP APIs, DNS queries, gRPC |
| **Transport** | 4 | TCP ports, UDP, load balancer targets |
| **Internet** | 3 | IP addresses, routes, security groups |
| **Network access** | 1–2 | NIC, VPC, subnets, ARP |

Most troubleshooting flows **top-down** (curl fails → dig → ping/trace → SG rules) or **bottom-up** when link issues suspected.

---

## 12.4 IP addressing and CIDR

IPv4 addresses are 32-bit dotted quads; subnets use **CIDR** notation:

```
10.0.1.25/24
│        └── prefix length: 24 network bits, 8 host bits → 256 addresses
└── private RFC1918 range (common in VPCs)
```

Private ranges (RFC 1918):

| Range | CIDR |
|-------|------|
| 10.0.0.0 – 10.255.255.255 | 10.0.0.0/8 |
| 172.16.0.0 – 172.31.255.255 | 172.16.0.0/12 |
| 192.168.0.0 – 192.168.255.255 | 192.168.0.0/16 |

**NAT** maps private IPs to public IPs at egress—understand this before debugging "works inside VPC, fails from internet."

IPv6 adoption grows (128-bit addresses, `/64` typical on subnets). Tools: `ip -6 addr`, `AAAA` records, dual-stack load balancers.

---

## 12.5 TCP vs UDP

| Aspect | TCP | UDP |
|--------|-----|-----|
| Connection | Connection-oriented (3-way handshake) | Connectionless |
| Reliability | Retransmits, ordering | Best-effort |
| Use cases | HTTP, SSH, DB | DNS, QUIC, video, metrics |
| Flow control | Yes | No |
| DevOps example | HTTPS API | CoreDNS, StatsD |

TCP connection establishment:

```
Client → SYN → Server
Client ← SYN-ACK ← Server
Client → ACK → Server
```

`ss` states like `SYN-SENT`, `ESTAB`, `TIME-WAIT` map to this lifecycle—**TIME-WAIT** accumulation can exhaust ports on high-churn load generators.

---

## 12.6 DNS: the distributed phone book

DNS resolves names to records. Critical for **every** deploy that changes IPs or uses CDNs.

### Record types

| Type | Purpose | Example |
|------|---------|---------|
| **A** | IPv4 address | `api.example.com → 203.0.113.10` |
| **AAAA** | IPv6 address | `api.example.com → 2001:db8::1` |
| **CNAME** | Alias to another name | `www → example.com` |
| **MX** | Mail server | Priority + hostname |
| **TXT** | Arbitrary text | SPF, DKIM, domain verification |
| **NS** | Delegates zone | Points to authoritative servers |
| **SRV** | Service location | Port + host for protocols |
| **CAA** | Certificate authority restriction | Security |

### Resolution chain

```
Browser/OS stub resolver
    → Recursive resolver (ISP, 8.8.8.8, corporate DNS)
        → Root (.)
            → TLD (.com)
                → Authoritative NS (example.com)
                    → Answer (A record)
```

Results are **cached** at each hop per **TTL** (seconds). Low TTL (60–300) speeds cutovers; high TTL reduces query load but slows rollback.

---

## 12.7 DNS operations DevOps engineers perform

### Cutover checklist

1. Lower TTL **24–48 hours** before change.
2. Apply new records on authoritative provider.
3. Verify with `dig @authoritative-ns` and public resolvers.
4. Monitor error rates and `curl` from multiple regions.
5. Restore TTL after stable.

### Split-horizon and private zones

Internal services use **private DNS** (Route 53 private zones, Cloud DNS private, Azure Private DNS):

- `db.internal` resolves to `10.0.5.12` inside VPC.
- Same name may not resolve publicly—or resolves differently (**split brain** by design).

Document which resolvers apps use (`/etc/resolv.conf`, CoreDNS `forward` plugin).

---

## 12.8 ICMP and path discovery

**ICMP** supports diagnostics (ping, unreachable messages). Many firewalls block ICMP—"ping fails" does not always mean host down.

```bash
ping -c 4 203.0.113.10
traceroute 203.0.113.10
tracepath 203.0.113.10    # No root required on Linux
mtr 203.0.113.10          # Interactive (install mtr)
```

Use traceroute when latency spikes or routing loops suspected after VPC peering changes.

---

## 12.9 ARP and L2 in VPC context

**ARP** maps IPv4 to MAC on local subnet. In cloud VPCs, you rarely touch ARP directly—but **security groups** and **NACLs** behave like L3/L4 filters on virtual interfaces.

On-prem hybrid: VPN/ Direct Connect extends L3; understand whether broadcasts traverse (usually not).

---

## 12.10 Common failure patterns

| Symptom | Likely layer | First checks |
|---------|--------------|--------------|
| Unknown host | DNS | `dig`, resolver config |
| Connection timed out | L3/L4 firewall/route | SG, NACL, `ip route get` |
| Connection refused | L4 app not listening | `ss -tlnp`, bind address |
| SSL certificate error | L6/TLS | cert SANs, expiry, chain |
| HTTP 502/504 | L7/L4 LB | target health, upstream timeout |

---

## 12.11 Chapter summary

- OSI provides vocabulary; **TCP/IP** maps to daily cloud networking.
- **CIDR** and private IP planning prevent overlapping VPC peering disasters.
- **TCP** reliability vs **UDP** speed trade-offs drive protocol choice.
- **DNS TTL**, record types, and resolver chains explain most "works after 5 minutes" incidents.
- Troubleshoot **top-down** with `curl`, `dig`, `ss`, and cloud network ACLs.

---

## 🧪 Lab 12.1 — DNS TTL experiment

1. Create a test subdomain with TTL 60 on your DNS provider.
2. Point A record to IP A; verify with `dig +trace` or `dig @ns`.
3. Change to IP B; measure propagation time from three resolvers.
4. Repeat with TTL 3600 in a lab zone (document expected delay).

---

## 🧪 Lab 12.2 — Layer mapping drill

1. For five past incidents (or hypothetical scenarios), identify the failing layer.
2. Write the first diagnostic command you would run for each.
3. Peer-review with a colleague or checklist.

---

## Review questions

1. Map HTTP, TCP, and IP to OSI layers.
2. What is the difference between A and CNAME records?
3. Why lower DNS TTL before a migration?
4. What does TCP `TIME-WAIT` indicate, and when is it a problem?
5. Explain split-horizon DNS in one paragraph.

---

*Next: [Chapter 13 — HTTP/HTTPS, TLS, and Certificates](./chapter-13-http-tls.md)*
