# Chapter 57: Networking Specialty Notes — TGW, PrivateLink, Hybrid, Route 53

These notes are a **Networking Specialty-oriented** companion to Chapters 9–14. Associate exams stop at "use a Transit Gateway for many VPCs." Specialty and production networks require route table design, appliance mode, Direct Connect overlay, PrivateLink operational limits, hybrid DNS, and Route 53 failure modes. Read this with a notepad: draw every lab before you type.

This is not a dump of every exam domain (no full Network Firewall signature list, no every Global Accelerator knob). It is the spine you will reuse: **how packets and names actually move**.

---

## 57.1 Mental model

Every AWS connectivity feature is one of:

| Mechanism | What is shared | What is not shared |
|-----------|----------------|--------------------|
| VPC peering | Routes to CIDRs (non-transitive) | Security groups referenced cross-VPC (same Region) |
| Transit Gateway | Transitive routing via TGW route tables | Overlapping CIDRs without extra NAT |
| PrivateLink | A service (ENIs + NLB/GWLB) | Your route table (no CIDR leak) |
| VPN / DX | IP reachability to on-premises | Your IAM |
| VPC endpoints (gateway) | Prefix list routes to S3/DDB | Other AWS APIs |
| VPC endpoints (interface) | PrivateLink to AWS APIs | Gateway-style prefix lists |

If you need **transitive** routing among many VPCs and on-premises, you are in TGW (or Cloud WAN) land. If you need to **expose a service** to other VPCs/accounts without sharing all routes, you are in PrivateLink land. Mixing them is normal: TGW for east-west RFC1918, PrivateLink for SaaS-style APIs.

---

## 57.2 Transit Gateway deep dive

A Transit Gateway is a regional hub. Attachments include VPC, VPN, DX Gateway (via TGW attachment), Peering (inter-Region TGW), Connect (GRE for SD-WAN), and Network Function (some appliance patterns).

### Route tables, not "one big router"

The default "one route table, associate all, propagate all" makes a **full mesh**. That is rarely what security wants.

Typical production:

| TGW route table | Associations | Propagations | Static routes |
|-----------------|--------------|--------------|---------------|
| `spokes` | App VPCs | Inspection VPC, maybe shared services | 0.0.0.0/0 → inspection |
| `inspection` | Inspection VPC | Spokes (or static CIDRs) | Return routes |
| `onprem` | VPN/DX | Shared services | Summaries |
| `shared` | Shared services | Spokes + onprem | — |

**Isolation:** Dev and prod spokes associate to different TGW route tables that do not propagate each other. They might both reach inspection and shared services.

### Appliance mode

If you send traffic to a fleet of firewalls in an inspection VPC, **disable source/destination check** on firewall ENIs and enable **appliance mode** on the inspection VPC attachment. Appliance mode pins a flow to the same AZ attachment so stateful firewalls see both directions.

Without appliance mode, asymmetric routing through two AZs **silently drops** return packets. This is the number-one TGW+firewall outage.

### ASymmetric routing checklist

- [ ] Appliance mode on inspection attachment
- [ ] TGW multicast unused unless you know you need it
- [ ] Spoke route tables: RFC1918 → TGW, not IGW
- [ ] Inspection VPC route tables: TGW → GWLB endpoint / firewall ENI per AZ
- [ ] Return: firewall → TGW
- [ ] MTU: DX/VPN/GRE overhead; clamp MSS on firewalls

### TGW peering (inter-Region)

Inter-Region TGW peering is **not transitive beyond the peer** in the way people hope. You attach a static route in each TGW route table toward the peer for the remote CIDRs. Encrypts on the AWS backbone. Latency is real; do not pretend us-east-1 to ap-southeast-2 is a LAN.

Dynamic routing over peering is limited compared to VPC attachments with BGP on Connect/VPN. Read the current quota docs before designing 5000 routes.

### Connect attachments (GRE)

SD-WAN appliances in a VPC use **Connect** (GRE + BGP) to TGW. You get dynamic routing without 100 Site-to-Site VPN tunnels. Useful when the WAN vendor already speaks BGP.

### Quotas you will hit

| Quota | Why it hurts |
|-------|----------------|
| Routes per TGW route table | Summarize on-premises |
| Attachments per TGW | Account/VPC sprawl |
| Bandwidth per VPC attachment per AZ | Elephant flows; add AZs, inspect sizing |
| Prefixes from DX | Summarize |

---

## 57.3 VPC peering vs TGW vs PrivateLink (decision table)

| Requirement | Pick |
|-------------|------|
| Two VPCs, same Region, no overlap, simple | Peering |
| Many VPCs, transitive, on-premises | TGW |
| Overlapping CIDRs must talk | NAT + TGW or re-IP; peering will not |
| Expose an API to 100 customer VPCs | PrivateLink |
| Shared services (LDAP) to many VPCs | TGW or PrivateLink (LDAP over PrivateLink is awkward; often shared VPC/TGW) |
| S3 from private subnet | Gateway endpoint, not TGW |

Peering is **not transitive**: A–B and B–C does not give A–C. That is the SAA trap and the Specialty "why we bought TGW" story.

---

## 57.4 PrivateLink operational notes

### Provider side

You create a **Network Load Balancer** (or GWLB for appliances) in your service VPC, then an **endpoint service** (`vpce-svc-...`). You approve consumer principals (account IDs). You may require acceptance.

- NLB can be internal.
- Preserve client IP: NLB target group proxy protocol / IP targets depending on mode.
- Cross-zone: understand NLB cross-zone billing and flow hash.
- Private DNS on the endpoint service: consumers resolve your private hosted zone name to their endpoint ENI IPs **in their VPC**.

### Consumer side

Interface endpoint ENIs appear in selected subnets (one per AZ you pick). Security groups on the **endpoint ENI** control who in the consumer VPC may connect.

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-consumer \
  --service-name com.amazonaws.vpce.us-east-1.vpce-svc-0123 \
  --vpc-endpoint-type Interface \
  --subnet-ids subnet-a subnet-b \
  --security-group-ids sg-endpoint
```

### Failure modes

| Symptom | Cause |
|---------|--------|
| Timeout | Consumer SG, NLB SG/NACL, provider target unhealthy |
| Works in AZ-a not AZ-b | Endpoint not in that AZ; NLB zonal shift; AZ mismatch |
| DNS to public still | Private DNS not enabled; split-horizon not set |
| Connection reset | MTU; idle timeout NLB 350s default vs app |
| Approval pending | Provider did not accept |

### Gateway vs interface endpoints for AWS APIs

S3 and DynamoDB offer **gateway** endpoints (route table prefix lists, free). Most other AWS APIs use **interface** endpoints (hourly + data). A common cost surprise: every interface endpoint in every AZ in every account. Centralize via **PrivateLink to a shared proxy** or shared endpoints in a network account with careful DNS — or accept the bill for isolation.

S3 now also has interface endpoints for some features (Object Lambda, etc.). Default still: gateway for bulk S3 from EC2.

---

## 57.5 Hybrid connectivity

### Site-to-Site VPN

- Two tunnels per connection for AWS-side AZ diversity.
- BGP vs static. BGP preferred with DX backup.
- Accelerated VPN uses Global Accelerator for public internet path quality, not a DX replacement.
- Throughput: scale with **equal-cost multipath** across multiple VPNs (TGW) or rely on DX.

### Direct Connect

Physical cross-connect to an AWS DX location. **Virtual interfaces (VIFs):**

| VIF | Use |
|-----|-----|
| Private | To a VGW in one VPC (legacy simple) |
| Transit | To a **DX Gateway** associated with **Transit Gateway** (modern hub) |
| Public | To AWS public prefixes (S3 public endpoints, etc.) |

**DX Gateway** lets one DX attach to TGWs/VGWs in multiple Regions. You still pay regional data patterns; you do not magically collapse latency.

**MACsec** on dedicated connections for L2 encryption when policy says so. VPN overlay on DX for encryption if MACsec not available (VPN on DX).

**Resiliency:** Two connections, two locations, two providers — the AWS resiliency toolkit recommendations. A single 10G in one building is not HA.

### Routing on hybrid

On-premises advertises summaries (10.0.0.0/8 is a blunt instrument; more specific AWS CIDRs may win or blackhole — **longest prefix match**). AWS route priority among VPN, DX, peering is documented and exam-tested: more specific wins; then BGP attributes (AS path, MED, local pref on your CE).

**AS path prepending** to make DX preferred over VPN is standard. On failover, prepend or withdraw.

### Cloud WAN (notes)

Cloud WAN is a global network with segments (like VRFs) and core network policies (JSON). Specialty candidates should know it exists for global TGW-like segmentation. If your org already runs TGW per Region + peering, Cloud WAN may replace the peering mesh. Migration is a project, not a weekend.

---

## 57.6 Route 53 at specialty depth

### Record types you must not confuse

| Type | Use |
|------|-----|
| A/AAAA | IPv4/IPv6 |
| CNAME | Name to name; **not** at zone apex |
| Alias | AWS resources; **works at apex**; no extra charge for AWS aliases |
| MX/TXT/SRV | Mail, verification, services |
| NAPTR | Telephony/SIP rarer |

### Routing policies

| Policy | Specialty note |
|--------|----------------|
| Simple | Multi-value if multiple IPs, no health |
| Weighted | Canary DNS; combine with health |
| Latency | Based on AWS latency maps, not user speedtest |
| Failover | Primary/secondary; health checks |
| Geolocation | Default record **required** or some users get SERVFAIL |
| Geoproximity | Bias; Route 53 Traffic Flow |
| Multi-value | Up to 8 healthy; not a load balancer |
| IP-based | CIDR collections |

**Health checks:** HTTP/HTTPS/TCP, string match, latency. **Calculated** health checks AND/OR children. **Inverted** for "healthy when origin down" is a footgun.

Health checkers are global. Do not point them at an internal-only ALB without a public or hybrid path. For private endpoints, use CloudWatch alarms + Route 53 health check that sources the alarm (or custom).

### Split-horizon DNS

Private hosted zone associated with VPCs. Same name as public zone is allowed: VPC resolvers see private. On-premises needs **Resolver inbound** (IPs in subnets) on BIND forwarders. Outbound rules forward `corp.local` to on-premises IPs. Rules can be **shared with RAM** across accounts — do that instead of 80 outbound endpoints.

### Resolver DNS Firewall

Filter outbound domains (block malware, allowlists). Associate rules with VPCs. Specialty: know it is not a replacement for Network Firewall, it is DNS-layer.

### Alias vs CNAME to ALB

Always alias when the target is ALB, CloudFront, NLB, S3 website. Alias tracks IP changes. CNAME at apex is invalid in DNS; Route 53 alias solves apex CloudFront.

### DNSSEC

Signing on public hosted zones; DS in parent. Breaks if you rotate keys badly. Not related to IAM.

---

## 57.7 Load balancers in a network design

Already covered in Chapter 12; Specialty extras:

- **NLB** static IP per AZ, PrivateLink required front.
- **GWLB** + GENEVE to appliances; pair with TGW appliance mode.
- **ALB** host/path routing; OIDC; WAF.
- **IP targets** for on-premises via TGW/DX (target type IP).
- **Zonal shift** (ARC) for ALB/NLB in an impaired AZ.

Cross-zone load balancing: ALB on by default; NLB historically off (and billed when on). Asymmetry with zonal endpoints is a debugging classic.

---

## 57.8 IPv6 notes

- Dual-stack VPCs, AAAA in Route 53.
- Egress-only IGW for private IPv6 egress without inbound.
- Many hybrid shops are IPv4-only on DX; 6-to-4 is not "just enable IPv6 on the VPC."
- PrivateLink and NLB IPv6 support has been expanding — verify per service.

---

## 57.9 Security groups, NACLs, and middleboxes

Specialty scenario: "traffic from spoke to on-premises dies after inserting a firewall."

Walk the path:

1. Instance SG egress
2. NACL subnet out/in (ephemeral ports on return — NACL gotcha)
3. TGW
4. Inspection ENI SG
5. Firewall policy
6. Return path reverse, **stateful SG vs stateless NACL**

NACL ephemeral: allow inbound 1024–65535 on the return path for clients, or you will "fix" the firewall and still fail.

---

## 57.10 Lab A — TGW isolated spokes with shared services

**Goal:** Two spoke VPCs cannot talk to each other; both talk to a shared-services VPC.

1. Create `vpc-spoke-a` 10.1.0.0/16, `vpc-spoke-b` 10.2.0.0/16, `vpc-shared` 10.10.0.0/16 in a sandbox Region. Two subnets each.

2. Create TGW. Create route tables `rtb-spokes-a`, `rtb-spokes-b`, `rtb-shared`.

3. Attach all VPCs. Associate spoke-a attachment to `rtb-spokes-a`, etc.

4. Propagate shared attachment into both spoke tables. Propagate each spoke into **shared only**, not into the other spoke.

5. In each VPC route table, add 10.0.0.0/8 or specific CIDRs → TGW.

6. Launch tiny instances; security groups allow ICMP from 10.0.0.0/8.

7. Ping: A→shared yes, B→shared yes, A→B no.

**Success criteria:** Document the TGW route tables (screenshot or `search-transit-gateway-routes`). This is the isolation pattern used in landing zones.

Tear down TGW attachments before VPCs; ENIs and TGW are sticky.

---

## 57.11 Lab B — PrivateLink producer/consumer

**Goal:** Consumer VPC reaches an nginx on an NLB in producer VPC with no peering routes.

1. Producer VPC: instance + internal NLB TCP 80, target the instance.
2. `create-vpc-endpoint-service-configuration` with that NLB. Note service name.
3. Allow your account as principal.
4. Consumer VPC: interface endpoint in two AZs, SG allow 80 from a consumer instance SG.
5. Enable private DNS if you set a name; or curl the endpoint DNS `vpce-....amazonaws.com`.
6. Confirm consumer has **no** route to producer CIDR.

**Success criteria:** HTTP 200 without peering. Then revoke acceptance and confirm failure.

---

## 57.12 Lab C — Resolver outbound to a fake corporate domain

**Goal:** Instances in a VPC resolve `app.corp.internal` via a BIND or dnsmasq you run on an EC2 (simulating on-premises).

1. Run dnsmasq in a "on-prem" VPC or subnet, advertise `app.corp.internal` → 10.9.9.9.
2. Create Resolver outbound endpoint in the AWS VPC.
3. Create a forwarding rule `corp.internal` → dnsmasq IP. Associate the VPC.
4. `dig app.corp.internal` from an instance.

If this fails: SG on dnsmasq UDP/TCP 53, inbound resolver, route to dnsmasq, rule association.

---

## 57.13 Lab D — Route 53 failover with calculated health

**Goal:** Fail over only if **both** `/health` and a CloudWatch alarm are bad.

1. Two S3 websites or two tiny HTTP origins.
2. Health checks on each URL.
3. Calculated health check AND.
4. Failover record.
5. Break one signal then both; observe DNS.

**Success criteria:** You can explain why AND vs OR matters for flapping.

---

## 57.14 Exam-style micro questions (not a full set)

1. Overlapping CIDR, need connectivity → NAT, PrivateLink, or re-IP; not peering.
2. Transitive on-premises to many VPCs → DX GW + TGW.
3. Customer consumes your SaaS → PrivateLink.
4. Apex domain to CloudFront → Alias A.
5. Geolocation without default → some users fail.
6. Firewall asymmetry → appliance mode.
7. S3 from private subnet cheaply → gateway endpoint.
8. Hybrid DNS → Resolver in/out + RAM share rules.

---

## 57.15 Troubleshooting cookbook (network)

| Tool | Use |
|------|-----|
| Reachability Analyzer | SG/NACL/route path |
| Network Access Analyzer | Network insights |
| VPC Flow Logs | ACCEPT/REJECT |
| TGW Flow Logs | Attachment-level |
| CloudWatch on NLB | Healthy hosts, reset counts |
| `tcpdump` + SSM | Last resort on instance |
| Route 53 query logs | Who asked what |

Chapter 59 generalizes troubleshooting. For networking, always answer: **did the packet leave, was it rejected, did DNS lie, was the path asymmetric?**

---

## 57.16 Cloud WAN, RAM, and shared subnets (short)

**RAM** shares subnets, Resolver rules, TGW, and more. Shared subnets: the owner account owns the VPC; participants launch ENIs. Security groups: participants cannot always modify owner SGs as they wish — read current sharing rules. This is how some landing zones avoid TGW data processing costs at the expense of noisy neighbors.

---

## 57.17 Data processing costs (FinOps for networks)

| Path | Cost flavor |
|------|-------------|
| Same AZ | Cheapest |
| Cross-AZ | Data transfer AZ |
| TGW | Attachment processing + data |
| NAT Gateway | Hourly + per GB |
| Interface endpoint | Hourly per AZ + per GB |
| DX | Port-hour + outbound from AWS |

Design inspection so **elephant S3 backups** do not hairpin through NAT+firewall to the internet. Gateway endpoints and S3 private paths save both money and firewall CPU.

---

## 57.18 Chapter checklist

- [ ] Can draw TGW route tables for isolated spokes.
- [ ] Know appliance mode and NACL ephemerals.
- [ ] Can explain PrivateLink vs peering in one sentence.
- [ ] DX VIF types and DX Gateway + TGW.
- [ ] Route 53 policies including geolocation default.
- [ ] Resolver RAM-shared rules.
- [ ] Labs A–C completed.

Next: a serverless reference that assumes this network exists — API Gateway, Lambda in VPC, DynamoDB endpoints, EventBridge, and SAM.
