# Chapter 14: VPC Peering, Transit Gateway, and PrivateLink

*AWS Handbook — Part III, Pages 266–280*

---

## 14.1 Connecting VPCs and services

As organizations grow, workloads spread across multiple VPCs, accounts, and regions. AWS provides several connectivity options, each with different trade-offs for complexity, scalability, and cost.

| Option | Scope | Transitive | Use case |
|--------|-------|------------|----------|
| **VPC Peering** | Same or cross-region | No | Simple 1:1 VPC connections |
| **Transit Gateway** | Hub-and-spoke | Yes (via TGW) | Many VPCs, on-premises, multi-account |
| **PrivateLink** | Service consumer → provider | N/A | Private access to SaaS/services |
| **VPC Endpoints** | VPC → AWS service | N/A | Private access to AWS APIs (S3, DynamoDB) |

---

## 14.2 VPC Peering

A **VPC peering connection** is a networking connection between two VPCs that enables routing using private IP addresses.

### Peering rules

- Peering is **non-transitive**: if A↔B and B↔C, A cannot reach C through B.
- **No overlapping CIDR blocks** between peered VPCs.
- Peering works **same-region** and **cross-region**.
- **No single point of failure** — AWS backbone handles the connection.
- You control access via **route tables** and **security groups** (cross-VPC SG referencing supported in same region).

### Peering setup steps

1. Create peering connection (requester → accepter).
2. Accept the peering connection (same or different account).
3. Update **route tables** in both VPCs to route peer CIDR through the peering connection.
4. Update **security groups** to allow traffic from peer VPC CIDR or SG.

```
VPC A (10.0.0.0/16) ←── Peering ──→ VPC B (10.1.0.0/16)

Route table A: 10.1.0.0/16 → pcx-0abc123
Route table B: 10.0.0.0/16 → pcx-0abc123
```

### CLI example

```bash
# Create peering connection
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-0aaa \
  --peer-vpc-id vpc-0bbb \
  --peer-region us-west-2  # omit for same region

# Accept (in accepter account/region)
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id pcx-0abc123

# Add routes
aws ec2 create-route \
  --route-table-id rtb-0aaa \
  --destination-cidr-block 10.1.0.0/16 \
  --vpc-peering-connection-id pcx-0abc123
```

### Terraform example

```hcl
resource "aws_vpc_peering_connection" "peer" {
  vpc_id        = aws_vpc.a.id
  peer_vpc_id   = aws_vpc.b.id
  peer_region   = "us-west-2"
  auto_accept   = false

  tags = { Name = "a-to-b-peering" }
}

resource "aws_route" "a_to_b" {
  route_table_id            = aws_route_table.a.id
  destination_cidr_block    = aws_vpc.b.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}
```

### When peering breaks down

| VPCs | Peering connections needed |
|------|---------------------------|
| 2 | 1 |
| 5 | 10 (n×(n-1)/2) |
| 10 | 45 |
| 50 | 1,225 |

Peering does not scale beyond a handful of VPCs. Use **Transit Gateway** instead.

---

## 14.3 AWS Transit Gateway

**Transit Gateway (TGW)** is a regional network hub that connects VPCs, VPN connections, and Direct Connect gateways in a **hub-and-spoke** model.

### Architecture

```
                    ┌─────────────────┐
                    │  Transit Gateway │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
      VPC A (spoke)    VPC B (spoke)    On-premises
      10.0.0.0/16      10.1.0.0/16      (VPN/DX)
```

### Key concepts

| Component | Description |
|-----------|-------------|
| **Transit Gateway** | Regional hub |
| **Attachment** | VPC, VPN, DX, peering, Connect |
| **Route table** | Controls which attachments can reach which |
| **Association** | Links attachment to a route table |
| **Propagation** | Auto-adds routes from attachment to route table |

### Route table segmentation

Use multiple TGW route tables for isolation:

| Route table | Attachments | Routes to |
|-------------|-------------|-----------|
| **Production** | Prod VPCs, prod VPN | Other prod VPCs, shared services |
| **Development** | Dev VPCs | Dev VPCs only (not prod) |
| **Shared Services** | Shared VPC | All environments (one-way) |

### Cross-region peering

Connect TGWs in different regions with **inter-region peering** for global connectivity.

### Terraform TGW example

```hcl
resource "aws_ec2_transit_gateway" "main" {
  description                     = "Organization TGW"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  auto_accept_shared_attachments  = "enable"

  tags = { Name = "org-tgw" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "app" {
  subnet_ids         = aws_subnet.private[*].id
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  vpc_id             = aws_vpc.app.id

  tags = { Name = "app-vpc-attachment" }
}

resource "aws_ec2_transit_gateway_route_table" "prod" {
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  tags = { Name = "prod-rt" }
}

resource "aws_ec2_transit_gateway_route_table_association" "app" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.app.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.prod.id
}
```

### TGW pricing

- **Attachment hourly charge** per VPC/VPN/DX attachment.
- **Data processing charge** per GB transited.
- For many VPCs, TGW is more cost-effective and manageable than full-mesh peering.

---

## 14.4 AWS PrivateLink

**PrivateLink** enables private connectivity from your VPC to services (AWS, partner, or your own) without traversing the public internet.

### Two flavors

| Type | Direction | Example |
|------|-----------|---------|
| **Interface VPC Endpoint** | Your VPC → AWS service or partner service | S3 (interface), third-party SaaS |
| **Endpoint Service (Provider)** | Consumer VPC → your service | Expose internal API to customers |

### Interface endpoint architecture

```
Consumer VPC                    Service Provider
┌──────────────┐               ┌──────────────┐
│ EC2 instance │─── ENI ──────►│ NLB → targets│
│              │  (private IP)  │ (your service)│
└──────────────┘               └──────────────┘
     ▲
     │ DNS: com.amazonaws.vpce.region.s3
  VPC Endpoint (interface)
```

### Key points

- Creates **Elastic Network Interfaces (ENIs)** in your subnets.
- Uses **private IP addresses** from your subnet CIDR.
- Security groups apply to the endpoint ENIs.
- **Endpoint policies** control which principals can use the endpoint.

### Gateway vs Interface endpoints

| Feature | Gateway Endpoint | Interface Endpoint |
|---------|------------------|-------------------|
| Services | S3, DynamoDB | Most other AWS services + partner services |
| Cost | Free | Hourly + data charges |
| Access control | Endpoint policy + bucket policy | SG + endpoint policy |
| DNS | Route table entry | Private DNS (optional) |
| IP | Prefix list in route table | ENI with private IP |

```bash
# Create interface endpoint for a service
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0abc123 \
  --service-name com.amazonaws.us-east-1.execute-api \
  --vpc-endpoint-type Interface \
  --subnet-ids subnet-0aaa subnet-0bbb \
  --security-group-ids sg-0endpoint

# Create gateway endpoint for S3
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0abc123 \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-0aaa rtb-0bbb
```

---

## 14.5 Choosing the right connectivity

| Requirement | Solution |
|-------------|----------|
| Two VPCs, same region, simple | VPC Peering |
| 10+ VPCs, hub-and-spoke | Transit Gateway |
| Cross-account service consumption | PrivateLink (endpoint service) |
| Private S3/DynamoDB access | Gateway VPC Endpoint |
| Private access to AWS APIs (EC2, SSM, etc.) | Interface VPC Endpoint |
| On-premises to AWS | VPN or Direct Connect → TGW |
| SaaS provider private access | PrivateLink (consumer) |

---

## 14.6 Security considerations

| Control | Applies to |
|---------|------------|
| **Route tables** | Peering, TGW — control which CIDRs are reachable |
| **Security groups** | Peering (same region SG ref), endpoints, TGW attachments |
| **NACLs** | All traffic paths |
| **Endpoint policies** | VPC endpoints — IAM-style access control |
| **TGW route tables** | Segment environments (prod cannot reach dev) |
| **Resource policies** | S3 bucket policies for gateway endpoints |

---

## 14.7 Chapter summary

- **VPC Peering** connects two VPCs directly; non-transitive; does not scale beyond a few VPCs.
- **Transit Gateway** provides hub-and-spoke connectivity for many VPCs, VPN, and Direct Connect.
- **PrivateLink** enables private access to services without public internet exposure.
- **Gateway endpoints** (S3, DynamoDB) are free; **interface endpoints** create ENIs with hourly charges.
- Choose connectivity based on scale, transitivity needs, and security segmentation requirements.

---

## 🧪 Lab 14.1 — VPC Peering

1. Create two VPCs with non-overlapping CIDRs (10.0.0.0/16 and 10.1.0.0/16).
2. Establish a peering connection and accept it.
3. Update route tables in both VPCs.
4. Launch an instance in each VPC and verify ping/SSH across the peering connection.

## 🧪 Lab 14.2 — S3 Gateway Endpoint

1. Create a gateway VPC endpoint for S3 in your VPC.
2. Attach it to private subnet route tables.
3. From a private instance (no NAT), run `aws s3 ls` and verify it works without internet access.

## 🧪 Lab 14.3 — Transit Gateway (advanced)

1. Create a Transit Gateway with two VPC attachments.
2. Create a TGW route table and associate both attachments.
3. Verify instances in both VPCs can communicate through the TGW.

---

## Review questions

1. Why is VPC peering non-transitive, and what problem does Transit Gateway solve?
2. Can two peered VPCs have overlapping CIDR blocks?
3. What is the difference between a gateway endpoint and an interface endpoint?
4. How does Transit Gateway route table segmentation improve security?
5. When is VPC peering preferred over Transit Gateway?

---

*Next: [Chapter 15 — EC2 Fundamentals](../part-04-compute/chapter-15-ec2-fundamentals.md)*
