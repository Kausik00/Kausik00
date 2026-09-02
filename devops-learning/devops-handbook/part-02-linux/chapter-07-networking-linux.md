# Chapter 7: Networking on Linux — ip, ss, curl, dig

*DevOps Handbook — Pages 27–31 of this PDF edition*
---

## 7.1 Why networking skills matter for DevOps

Every deployment, health check, and incident touches the network: DNS resolution, TCP connections, TLS handshakes, load balancer health probes, and firewall rules. When an application is "down," the failure is often **not** the app—it is DNS, routing, a security group, or a saturated socket backlog.

Linux provides modern tools that replaced much of the legacy `ifconfig` / `netstat` era:

| Tool | Purpose |
|------|---------|
| **`ip`** | Interfaces, addresses, routes, rules |
| **`ss`** | Socket statistics (connections, listening ports) |
| **`curl`** | HTTP/HTTPS client for APIs and debugging |
| **`dig`** | DNS queries and troubleshooting |
| **`traceroute` / `tracepath`** | Path discovery |
| **`tcpdump` / `tshark`** | Packet capture (advanced) |

This chapter focuses on daily diagnostic workflows.

---

## 7.2 The `ip` command suite

The `ip` utility from **iproute2** is the standard for network configuration and inspection on modern Linux.

### View interfaces and addresses

```bash
ip link show                    # Layer 2: interfaces, MAC, state
ip addr show                    # Layer 3: IPv4/IPv6 addresses
ip -br addr                     # Brief one-line-per-interface summary
ip addr show dev eth0           # Single interface
```

Example brief output interpretation:

```
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             10.0.1.25/24 fe80::5054:ff:fe12:3456/64
```

- **`UP`** — interface administratively enabled and carrier detected (for physical links).
- **`127.0.0.1/8`** — loopback; always present.
- **`/24`** — subnet prefix; 256 addresses in this example.

### Routing table

```bash
ip route show                   # Main routing table
ip route get 8.8.8.8            # Which path would a packet take?
ip rule show                    # Policy routing rules (multi-table)
```

If `ip route get` shows an unexpected interface, compare with your cloud subnet route tables and default gateway.

### Temporary address assignment (lab only)

```bash
sudo ip addr add 192.168.99.10/24 dev eth0
sudo ip link set eth0 up
sudo ip route add default via 192.168.99.1
```

Changes made with `ip` are **not persistent** across reboot unless saved via netplan, NetworkManager, or distro-specific config under `/etc`.

---

## 7.3 Sockets and connections with `ss`

`ss` replaces `netstat` for inspecting listening ports and established connections. It reads from `/proc` and is faster on busy servers.

### Common patterns

```bash
ss -tuln                        # TCP/UDP listening ports, numeric
ss -tunap                       # Include process names (needs root for all PIDs)
ss -tn state established        # Established TCP connections
ss -tn sport = :443             # Connections from local port 443
ss -tn dst 10.0.1.50            # Connections to specific destination
```

Flags:

| Flag | Meaning |
|------|---------|
| `-t` | TCP |
| `-u` | UDP |
| `-l` | Listening sockets |
| `-n` | Numeric (no DNS reverse lookup) |
| `-a` | All (listening + non-listening) |
| `-p` | Show process |

### DevOps debugging scenario

A service fails health checks but the process is running:

```bash
sudo ss -tlnp | grep 8080
curl -v http://127.0.0.1:8080/health
curl -v http://10.0.1.25:8080/health   # bind address matters!
```

If `ss` shows `127.0.0.1:8080` but not `0.0.0.0:8080`, the app binds **localhost only**—external load balancers cannot reach it.

---

## 7.4 HTTP debugging with `curl`

`curl` is the universal CLI for HTTP/S, file transfers, and API testing.

### Essential options

```bash
curl -I https://example.com              # HEAD request (headers only)
curl -v https://api.example.com/v1/users  # Verbose: TLS, headers, redirects
curl -sS -o /dev/null -w '%{http_code}\n' https://example.com   # Status only
curl -H 'Authorization: Bearer TOKEN' https://api.example.com/me
curl -X POST -H 'Content-Type: application/json' \
  -d '{"name":"svc"}' https://api.example.com/items
curl --connect-timeout 5 --max-time 30 https://slow.example.com
curl -k https://self-signed.local         # Skip TLS verify (debug only!)
curl -o out.bin https://example.com/file  # Save body to file
curl -L https://short.url/abc             # Follow redirects
```

### Timing breakdown

```bash
curl -w '\nnlookup:%{time_namelookup} connect:%{time_connect} tls:%{time_appconnect} ttfb:%{time_starttransfer} total:%{time_total}\n' \
  -o /dev/null -sS https://example.com
```

| Phase | Indicates |
|-------|-----------|
| `time_namelookup` | DNS delay |
| `time_connect` | TCP handshake to server |
| `time_appconnect` | TLS handshake complete |
| `time_starttransfer` | Time to first byte (server processing) |

High `time_namelookup` → DNS issue. High `time_connect` → routing/firewall. High `time_starttransfer` → backend overload.

---

## 7.5 DNS with `dig`

DNS failures cause mysterious outages: apps cache stale records, TTLs expire during migrations, and split-horizon DNS confuses internal vs external views.

### Basic queries

```bash
dig example.com                 # Default A record query
dig example.com AAAA            # IPv6
dig example.com MX              # Mail exchangers
dig example.com NS              # Name servers
dig @8.8.8.8 example.com        # Query specific resolver
dig +short example.com          # Answer only
dig +trace example.com          # Full delegation trace (education/debug)
```

### Useful flags for SRE work

```bash
dig example.com +noall +answer +stats
dig -x 93.184.216.34            # Reverse DNS (PTR)
dig @1.1.1.1 app.internal.company.com   # Test internal resolver
```

Compare answers from **corporate resolver**, **public resolver (8.8.8.8)**, and **authoritative NS** when debugging propagation.

---

## 7.6 Putting it together: diagnostic workflow

When `curl https://api.myapp.com/health` fails from a server:

```
1. dig api.myapp.com          → Does DNS resolve? Correct IP?
2. ip route get <that-ip>     → Expected egress path?
3. curl -v (with IP / Host)   → TLS? HTTP status? Timeout?
4. ss -tn dst <ip>:443        → Connection state stuck?
5. Check firewall (nftables/iptables, cloud SG)
6. tcpdump (if permitted)     → Packets leaving/returning?
```

Document findings in the incident channel as you go—future you will thank present you.

---

## 7.7 `/etc/hosts`, `resolv.conf`, and systemd-resolved

| File / service | Role |
|----------------|------|
| `/etc/hosts` | Static local overrides (break-glass, testing) |
| `/etc/resolv.conf` | Resolver configuration (may be managed) |
| **systemd-resolved** | Caching stub resolver on many distros |

```bash
resolvectl status               # Current DNS servers and domains
resolvectl query example.com    # Query through systemd-resolved
```

On containers, DNS is often injected by Docker/Kubernetes—always check **`/etc/resolv.conf` inside the pod**, not only on the node.

---

## 7.8 Firewalls at a glance

```bash
sudo nft list ruleset           # nftables (modern default on many distros)
sudo iptables -L -n -v          # Legacy iptables
sudo ufw status verbose         # Ubuntu uncomplicated firewall
```

DevOps engineers rarely invent firewall rules from scratch—they align **host firewall** with **cloud security groups** and **Kubernetes NetworkPolicies**. Still, verifying `DROP` rules locally saves hours of cloud-console hunting.

---

## 7.9 Chapter summary

- Use **`ip`** for interfaces, addresses, and routes; prefer it over deprecated `ifconfig`.
- Use **`ss`** to see listening ports, bind addresses, and connection states.
- Use **`curl -v`** and timing flags to separate DNS, TCP, TLS, and application latency.
- Use **`dig`** to validate DNS from multiple resolvers during cutovers.
- Follow a **structured workflow** instead of random command guessing during incidents.

---

## 🧪 Lab 7.1 — Local service bind address

1. Run `python3 -m http.server 9090` on a VM.
2. Use `ss -tlnp` to see which address it binds.
3. From another host (or curl to the VM's private IP), confirm reachability.
4. Restart bound to `127.0.0.1` only (if supported) and observe external failure.
5. Write two sentences explaining why bind address matters for load balancers.

---

## 🧪 Lab 7.2 — DNS and latency baseline

1. Pick three production-like hostnames (or use `example.com`, `cloudflare.com`, `github.com`).
2. For each, run `dig +short` and `curl -w` timing from your lab machine.
3. Record results in a table: hostname, IP, nlookup, connect, ttfb, total.
4. Change resolver to `8.8.8.8` temporarily and repeat—note differences.

---

## Review questions

1. What does `ss -tuln` show, and what does each letter in the flags mean?
2. How do you test whether an app listens on localhost only vs all interfaces?
3. Which `curl -w` timing field isolates DNS delay?
4. Why run `dig @8.8.8.8` during an internal DNS incident?
5. Name two files/services that affect name resolution on Linux.

---

*Next: [Chapter 8 — Bash Scripting for Automation](./chapter-08-bash-scripting.md)*
