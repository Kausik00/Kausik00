# Chapter 62: Networking Packet Labs

*DevOps Handbook — Workbook*
---

## 62.1 Why packet-level debugging still matters in 2026

Cloud load balancers, service meshes, and eBPF dataplanes hide TCP. They do not abolish it. When a TLS handshake stalls, DNS returns `SERVFAIL` only from one AZ, or “the firewall is open” but SYN packets never elicit SYN-ACK, **the packet is the ground truth**. This workbook trains you to capture, filter, and interpret that truth with `tcpdump`, Wireshark/tshark, `dig`/`delv`, OpenSSL, `mtr`, and host firewalls (`nftables`, security groups, NetworkPolicy).

The professional habit is **capture first, interpret second, change third**. A five-second `tcpdump` taken during the failure is worth more than an hour of adding log lines after the connection recovered.

| Layer (practical) | Question | Tools |
|-------------------|----------|--------|
| L2/L3 | ARP/neighbor, routing, MTU | `ip`, `ping`, `mtr`, pcap |
| L4 | Handshake, RST, retransmission | tcpdump, ss, conntrack |
| L7 name | Which answer, from which resolver? | dig, packet on 53/853 |
| L7 TLS | Where in the handshake? | openssl s_client, pcap + keylog |
| Policy | Who dropped it? | nft, iptables, SG flow logs, kube-proxy |

---

## 62.2 Capture craft: tcpdump that you can hand to a teammate

Bad captures are huge, encrypted blobs on the wrong interface. Good captures are **time-bounded, filtered, snaplen-aware, and named**.

```bash
# List interfaces; do not guess
ip -br l
tcpdump -D

# Write a rotating capture on the interface that faces the client
sudo tcpdump -i eth0 -nn -tttt -s 0 \
  -C 50 -W 6 \
  -w /var/tmp/eth0-%Y%m%d%H%M.pcap \
  'host 203.0.113.10 and (port 443 or port 80)'

# Quick stdout for a live incident (no -w)
sudo tcpdump -i any -nn -tttt 'tcp port 443 and host 198.51.100.20'
```

Flags you will actually use:

| Flag | Purpose |
|------|---------|
| `-nn` | No DNS/port name resolution (resolution *is* an incident amplifier) |
| `-tttt` | Human timestamps |
| `-s 0` | Full packet (default snaplen historically truncated TLS ClientHello) |
| `-i any` | All interfaces; Linux “cooked” capture may hide L2 |
| `-p` | No promiscuous mode (sometimes required in clouds) |
| `-c 10000` | Hard stop |
| `-C` / `-W` | Rotate files so you do not fill the disk (Chapter 61) |

**Filter language (BPF)** is evaluated in the kernel. Keep it simple. Complex userland filtering happens later in Wireshark.

```bash
# SYN-only (connection attempts)
'tcp[tcpflags] & tcp-syn != 0'

# RST
'tcp[tcpflags] & tcp-rst != 0'

# DNS
'udp port 53 or tcp port 53 or port 853'

# TLS (approximate; SNI is in ClientHello)
'tcp port 443'

# Not SSH so you can capture while connected
'not port 22'
```

If you SSH to the host and capture `port 22`, you drown in your own session. Exclude management ports or capture on a **different** interface.

Packet capture on Kubernetes nodes often requires the **pod netns**:

```bash
# Find container PID then enter netns
crictl inspect <cid> | jq -r '.info.pid'
sudo nsenter -t <pid> -n tcpdump -i any -nn port 8080
```

---

## 62.3 Reading TCP without folklore

A healthy HTTP/TLS session:

1. SYN → SYN-ACK → ACK (handshake).
2. TLS records (or HTTP).
3. FIN/ACK teardown or RST on abort.

**Failure signatures:**

| Capture pattern | Meaning |
|-----------------|---------|
| Client SYN, no SYN-ACK | Drop, blackhole, wrong destination, or server not listening |
| SYN, SYN-ACK, no client ACK | Client or middlebox problem; asymmetric routing |
| Immediate RST from server | Nothing listening, or policy reject that sends RST |
| Handshake then stall, retransmissions | Loss, MTU/PMTUD blackhole, server application stuck |
| ACK with shrinking window → 0 | Receiver window full (app not reading) |
| Spurious RST after data | NAT timeout, firewall idle policy, LB flow expiry |

```bash
# Retransmits and sockets on the host
ss -ti
nstat -az | grep -i Tcp
netstat -s | grep -i retrans   # if net-tools present
```

**Window zero** is not “the network is slow.” It is the application or kernel not draining the receive buffer. Pair pcap with `strace` on the server (Chapter 61).

**MTU / PMTUD:** ICMP fragmentation-needed dropped by overly aggressive security groups causes TCP to stall on large segments (classic VPN + jumbo mismatch). Test with:

```bash
ping -M do -s 1472 198.51.100.10     # 1500 MTU Ethernet
tracepath 198.51.100.10
```

Capture ICMP type 3 code 4 alongside TCP. If large packets die and small pings live, you have an MTU incident, not an application bug.

---

## 62.4 Wireshark and tshark: from pcap to a story

Wireshark is for **interactive** analysis; `tshark` is for **servers and CI**. Same dissection engine.

```bash
# Conversations and endpoints (CLI)
tshark -r capture.pcap -q -z conv,tcp
tshark -r capture.pcap -q -z io,phs

# Follow one stream by index after you identify it
tshark -r capture.pcap -q -z follow,tcp,ascii,0

# Export TLS ClientHello SNI (encrypted payloads still show handshake metadata)
tshark -r capture.pcap -Y "tls.handshake.type == 1" -T fields \
  -e frame.time -e ip.src -e ip.dst -e tls.handshake.extensions_server_name
```

Display filters (Wireshark language, **not** BPF):

```
tcp.flags.reset == 1
tcp.analysis.retransmission
tcp.analysis.zero_window
dns.flags.rcode != 0
tls.handshake.type == 1
http.request.uri contains "health"
```

**Expert info** in Wireshark flags retransmissions and out-of-order. Out-of-order is common on multi-path and does not always mean loss. Correlate with `tcp.analysis.lost_segment`.

### Decrypting TLS in a lab (never in shared prod without policy)

Use an SSLKEYLOGFILE from a **test** client:

```bash
export SSLKEYLOGFILE=/tmp/keys.log
curl -v https://example.com/
# Wireshark: Preferences → Protocols → TLS → (Pre)-Master-Secret log filename
```

Production decryption belongs to authorized TLS inspection architecture, not an engineer’s laptop. For incidents, you usually need handshake metadata (SNI, alerts, certificate) which is visible without secrets on TLS 1.2; TLS 1.3 encrypts more of the handshake—SNI may be encrypted with ECH. Know what your capture *cannot* show.

---

## 62.5 DNS failures: client, stub, recursive, authoritative

DNS outages masquerade as “the app is down.” Classify **which box** failed.

```
Application → stub (glibc / musl) → configured resolvers (kube-dns, VPC DNS)
         → recursive (Unbound, Cloud DNS) → authoritative
```

```bash
# What the host actually uses
cat /etc/resolv.conf
resolvectl status          # systemd-resolved
getent ahosts api.internal.example

dig +norecurse api.example.com @ns-auth.example.com
dig api.example.com @1.1.1.1
dig +trace api.example.com
delv api.example.com       # DNSSEC validation view

# Capture the real queries (often 127.0.0.53 or 169.254.169.253)
sudo tcpdump -i any -nn -s0 port 53 or port 853
```

| Symptom | Likely layer | Evidence |
|---------|--------------|----------|
| `NXDOMAIN` | Wrong name, search domain, or split-horizon | Query name in pcap ≠ what you think |
| `SERVFAIL` | Recursive/auth failure or DNSSEC | `delv`, auth logs |
| Timeout | UDP loss, blocked 53, or truncated + TCP blocked | pcap: query, no response; or TC bit then no TCP |
| Intermittent wrong IP | TTL race, stale cache, dual records | Compare resolver vs auth; check nscd/systemd-resolved |
| Works in `dig`, fails in app | Search list, IPv6 AAAA blackhole, musl vs glibc | `getaddrinfo` traces, `strace` `connect` |
| Works in pod A, not B | CoreDNS, ndots, NetworkPolicy | `ndots:5` + search generating extra queries |

Kubernetes `ndots:5` plus a short name can emit **five search queries** before the real name. Under CoreDNS CPU saturation this looks like random timeouts. Fix with FQDNs (trailing dot) or a better `dnsConfig`.

```yaml
dnsConfig:
  options:
    - name: ndots
      value: "2"
```

**Split-horizon / Private DNS:** the same QNAME returns a public IP from a laptop and a private IP from a VPC. Capturing *on the failing resolver path* is the only way to win the argument.

---

## 62.6 TLS handshake debugging as a sequence diagram

OpenSSL remains the portable probe:

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com -showcerts </dev/null
openssl s_client -connect 10.0.1.20:443 -servername api.example.com -tls1_2
echo | openssl s_client -connect api.example.com:443 2>/dev/null | openssl x509 -noout -dates -subject -issuer
```

Handshake stages and typical failures:

| Stage | Failure | Typical cause |
|-------|---------|---------------|
| TCP connect | `Connection refused` / timeout | Not TLS; go back to L4 |
| ClientHello → no ServerHello | Middlebox, wrong SNI, or server hang | pcap: ClientHello only |
| Certificate | verify error | Missing chain, name mismatch, expired, wrong trust store |
| CertificateExpired | clock | NTP (Chapter 61 timedatectl) |
| Handshake failure alert | Protocol/cipher mismatch | Old client vs TLS 1.3-only |
| Alert `unrecognized_name` | SNI | Virtual host misconfig |
| HTTP 421 / wrong cert | SNI routing | Multiple sites one IP |

```bash
# Cipher and protocol matrix
nmap --script ssl-enum-ciphers -p 443 api.example.com   # lab only; noisy

# curl as a better UX around the same handshake
curl -vI https://api.example.com/ --connect-to api.example.com:443:10.0.1.20:443
```

**mTLS:** capture will show client certificate request. Failures are often file permissions on the key, wrong CA bundle, or expired client cert—not “the mesh is down.” Sidecar identity (SPIFFE) adds another trust domain; compare the URI SAN you expect versus `openssl x509 -text`.

**Time** is a TLS dependency. A host 40 minutes in the future fails Let’s Encrypt leaf validation. Always include `timedatectl` in TLS tickets.

---

## 62.7 Path visualization: ping, traceroute, and mtr

`ping` success does not prove TCP 443 works (ICMP may be allowed while SYN is dropped). `traceroute` UDP/ICMP may be filtered. **`mtr`** combines hop discovery with loss statistics over time—the right default for “the path is flaky.”

```bash
mtr -rwzbc 100 198.51.100.10          # report mode, 100 cycles
mtr -rwzbc 50 -T -P 443 api.example.com  # TCP to port 443
mtr -rwzbc 50 -u -P 53 1.1.1.1
```

| Observation | Interpretation |
|-------------|----------------|
| Loss at hop 8, 0% at hop 9+ | ICMP rate-limit on that hop; **ignore** |
| Loss that persists to destination | Real loss on that path |
| High latency one hop, then lower | Load balancer or ICMP deprioritization |
| TCP mtr fails, ICMP ping works | Middlebox filtering TCP |
| Asymmetric paths | Different return ISP; capture both ends |

Cloud **Network Load Balancers** and **GSLB** make hop lists look like nonsense (anycast, hidden hops). Treat mtr as a **change detector** (compare before/after) more than a literal map of every device.

Pair with VPC Flow Logs / Azure NSG flow / GCP VPC logs when you do not have tcpdump on both endpoints.

---

## 62.8 Firewalls: host, cloud, and Kubernetes

“The firewall” is usually **four** independent policies:

1. Cloud security group / NACL / firewall rule
2. Host `nftables`/`iptables`/`firewalld`
3. kube-proxy or eBPF dataplane + NetworkPolicy
4. Application or mesh authorization

```bash
# Host
sudo nft list ruleset
sudo iptables-save
sudo firewall-cmd --list-all-zones
sudo conntrack -L | head

# Did conntrack see the attempt?
sudo conntrack -E
```

**Security groups are stateful; NACLs are not.** Ephemeral return ports bite people who “opened 443 inbound on the NACL” but forgot outbound ephemeral ranges.

Kubernetes NetworkPolicy default-deny is a common “it works until we added a policy” incident. Debug with:

```bash
kubectl get networkpolicy -A
# Packet path: client pod → node → overlay → dest
# Capture in both pod netns (Lab 62.3)
```

`REJECT` versus `DROP`: REJECT yields ICMP unreachable or TCP RST (fast fail); DROP yields client timeouts (slow, expensive incidents). Know which your platform uses.

---

## 62.9 Worked incident: “TLS timeout to RDS”

**Symptom:** App timeouts to `db.internal:5432` after a rotation to TLS-required.

**Wrong path:** Bump timeouts in the ORM.

**Packet path:** tcpdump on app host shows TCP handshake OK, ClientHello sent, **no ServerHello**. Server (managed) does not speak TLS on 5432 the way the client expects, *or* a sidecar intercepts 5432.

**Second capture** on a bastion using `openssl s_client -connect ...:5432` vs `psql sslmode=require`.

**Root cause:** The security group allowed 5432, but a **transparent proxy** on the node redirected 5432 to an HTTP proxy. Pcap showed HTTP `CONNECT` failure, not PostgreSQL SSL.

**Lesson:** Identify the **next hop MAC/IP** in the capture. If it is not the RDS ENI, you are not talking to the database.

---

## 62.10 Capture ethics, PII, and performance

Pcaps contain credentials, cookies, and PII. Store them in the incident bucket with retention and access control. Prefer BPF filters that avoid dumping full HTTP bodies in production (`-s 128` only when you do not need TLS records).

Capture overhead: `tcpdump -i any -s 0` on a 25 Gbps host can **drop packets** (which you will misread as loss) or CPU-spin. Check `tcpdump` printed “packets dropped by kernel.” Use hardware timestamping / cloud mirroring / vpc traffic mirror for high PPS.

---

## 62.11 Lab-ready reference: ports and what they prove

| Probe | Proves |
|-------|--------|
| `nc -vz host 443` | TCP accept, not TLS or HTTP |
| `openssl s_client` | TLS to that SNI, not app auth |
| `curl -vI` | HTTP status from *some* server |
| `dig @resolver` | That resolver’s answer |
| `mtr -T -P 443` | TCP path to port |
| pcap | Who sent RST, whether SYN-ACK exists |

Never conclude “DNS is fine” from a browser; browsers have their own caches and DoH.

---

## 🧪 Lab 62.1 — tcpdump a failed handshake

1. Run `nc -l 127.0.0.1 9443` (plain TCP, no TLS).
2. In another terminal, `openssl s_client -connect 127.0.0.1:9443`.
3. Capture: `tcpdump -i lo -nn -s0 -w /tmp/tlsfail.pcap port 9443`.
4. Open in Wireshark/tshark: confirm TCP handshake succeeds, ClientHello sent, then RST or timeout.
5. Write a three-line incident summary a teammate could act on.

---

## 🧪 Lab 62.2 — DNS search-path surprise

1. On a Linux VM, set `search corp.example internal.example` and `ndots:5` in resolv.conf (lab VM only).
2. `tcpdump -i any port 53` while running `getent hosts api` (short name).
3. Count queries. Repeat with `getent hosts api.corp.example.` (trailing dot).
4. Relate the extra queries to a CoreDNS CPU graph (screenshot or PromQL from a kind cluster if available).

---

## 🧪 Lab 62.3 — DROP versus REJECT

1. Add an `iptables`/`nft` rule that **drops** inbound TCP 8080, then one that **rejects**.
2. From a client, time `nc -vz` in both cases.
3. Capture both. Identify ICMP unreachable vs silence vs RST.
4. Document which behavior your production security groups use.

---

## 🧪 Lab 62.4 — mtr lie vs real loss

1. Run `mtr -rwzbc 50` to a public anycast IP (e.g., a CDN).
2. Note a hop with loss that **does not** continue to the destination.
3. Run `mtr -T -P 443` to the same name.
4. Write why ICMP hop loss was a false positive.

---

## 62.12 Chapter map

| If you see… | Do this |
|-------------|---------|
| Timeouts, no RST | Capture SYN/SYN-ACK; check DROP vs routing |
| Fast RST | Listen sockets, policy REJECT, wrong dest |
| TLS verify errors | Chain, SNI, clock, trust store |
| Name errors | Capture 53; compare stub vs recursive vs auth |
| Flaky path | mtr TCP; ignore single-hop ICMP loss |
| “Firewall open” | Enumerate **all four** policy layers |

---

## Review questions

1. Why is `-nn` mandatory on a DNS-related incident capture?
2. Draw the TCP three-way handshake and annotate where a security group DROP appears in a pcap versus a host `REJECT`.
3. A hop in mtr shows 30% loss but the destination shows 0% loss. What do you conclude?
4. `dig` succeeds, the JVM fails. Give three distinct explanations and the tool that proves each.
5. Which TLS fields remain useful in a pcap when you cannot decrypt TLS 1.3 application data?
6. Explain `ndots:5` impact on CoreDNS. How do you reduce query amplification?
7. How do you capture packets inside a Kubernetes pod’s network namespace?
8. What does a TCP zero window tell you about the receiver?
9. Why can ping succeed when HTTPS fails? List two independent reasons.
10. A colleague emails a 2 GB pcap from `tcpdump -i any` on a busy node. What three capture hygiene rules would have made this file useful?

---

## Further practice

Chapter 12–13 cover DNS and TLS theory; this workbook is the operational drill. Combine with Chapter 66 when the packet path includes kube-proxy, CNI, and NetworkPolicy.
