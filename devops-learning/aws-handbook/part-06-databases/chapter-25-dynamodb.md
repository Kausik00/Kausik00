# Chapter 25: DynamoDB — Tables, Indexes, and Streams

*AWS Handbook — Pages 121–126 of this PDF edition*
---

## 25.1 What is DynamoDB?

**Amazon DynamoDB** is a fully managed, serverless NoSQL database providing single-digit millisecond performance at any scale. Unlike RDS, there are no servers to provision, patch, or scale—DynamoDB handles capacity automatically (on-demand mode) or lets you provision read/write capacity units.

DynamoDB excels at key-value and document data models with predictable access patterns.

---

## 25.2 Core concepts

| Concept | Description |
|---------|-------------|
| **Table** | Collection of items (like a table without schema enforcement) |
| **Item** | A record (up to 400 KB) |
| **Attribute** | A field within an item (name-value pair) |
| **Primary key** | Uniquely identifies each item |
| **Partition key** | Hash key (required) |
| **Sort key** | Range key (optional; enables queries on range) |

### Primary key types

| Type | Structure | Example |
|------|-----------|---------|
| **Simple** | Partition key only | `UserId` |
| **Composite** | Partition key + sort key | `UserId` + `OrderDate` |

---

## 25.3 Capacity modes

| Mode | Billing | Use case |
|------|---------|----------|
| **On-demand** | Per request | Unpredictable traffic, new apps |
| **Provisioned** | Per RCU/WCU per hour | Predictable, cost-optimized at scale |
| **Provisioned + Auto Scaling** | Provisioned with automatic adjustment | Variable but bounded traffic |

### Capacity units

| Unit | Definition |
|------|------------|
| **RCU** (Read Capacity Unit) | 1 strongly consistent read/sec for 4 KB item |
| **WCU** (Write Capacity Unit) | 1 write/sec for 1 KB item |

**Eventually consistent reads** cost half the RCUs of strongly consistent reads.

---

## 25.4 Indexes

### Global Secondary Index (GSI)

- Different partition key and sort key from the base table.
- Eventually consistent (by default).
- Separate provisioned or on-demand capacity.
- Up to 20 GSIs per table.

```
Base table: PK=UserId, SK=OrderDate
GSI:        PK=ProductId, SK=OrderDate  → Query orders by product
```

### Local Secondary Index (LSI)

- Same partition key, different sort key.
- Must be created at table creation time.
- Shares table capacity.
- Up to 5 LSIs per table.

### When to use which

| Need | Index type |
|------|------------|
| Query by different partition key | GSI |
| Query by different sort key (same partition) | LSI |
| Add index after table creation | GSI only |
| Strongly consistent reads on index | LSI only |

---

## 25.5 Query and Scan

### Query (efficient)

Access items by partition key (and optionally sort key condition):

```python
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("Orders")

response = table.query(
    KeyConditionExpression="UserId = :uid AND OrderDate > :date",
    ExpressionAttributeValues={
        ":uid": "user-123",
        ":date": "2024-01-01",
    },
)
```

### Scan (expensive)

Reads every item in the table. Avoid in production; use GSIs instead.

### Best practices

- Design access patterns first, then schema.
- Use composite keys to model one-to-many relationships.
- Prefer Query over Scan.
- Use `ProjectionExpression` to return only needed attributes.
- Paginate with `LastEvaluatedKey`.

---

## 25.6 DynamoDB Streams

**Streams** capture item-level changes (insert, update, delete) in near real-time:

| View type | Data captured |
|-----------|---------------|
| `KEYS_ONLY` | Partition and sort key only |
| `NEW_IMAGE` | Entire item after change |
| `OLD_IMAGE` | Entire item before change |
| `NEW_AND_OLD_IMAGES` | Both (most common) |

### Stream consumers

| Consumer | Use case |
|----------|----------|
| **Lambda** | Event-driven processing, CDC |
| **Kinesis Data Streams** | Extended retention, fan-out |
| **DynamoDB (Kinesis adapter)** | Legacy integration |

### Lambda trigger example

```hcl
resource "aws_lambda_event_source_mapping" "dynamo" {
  event_source_arn  = aws_dynamodb_table.orders.stream_arn
  function_name     = aws_lambda_function.processor.arn
  starting_position = "LATEST"
  batch_size        = 100

  filter_criteria {
    filter {
      pattern = jsonencode({
        eventName = ["INSERT", "MODIFY"]
      })
    }
  }
}
```

---

## 25.7 Advanced features

### DynamoDB Accelerator (DAX)

In-memory cache for microsecond read latency. Transparent to application (drop-in replacement for DynamoDB endpoint).

### Global Tables

Multi-region, multi-active replication:

```
us-east-1 table ←──sync──→ eu-west-1 table
     │                          │
  Application A            Application B
  (read/write)             (read/write)
```

- Conflict resolution: last writer wins.
- RPO: sub-second; RTO: near-zero (DNS failover).

### Transactions

`TransactWriteItems` and `TransactGetItems` for ACID operations across up to 100 items (same or different tables).

### TTL (Time to Live)

Automatically delete items after a specified timestamp attribute. No WCU consumed for TTL deletions.

```bash
aws dynamodb update-time-to-live \
  --table-name Sessions \
  --time-to-live-specification "Enabled=true,AttributeName=ExpiresAt"
```

### Point-in-time recovery (PITR)

Continuous backup with per-second restore capability (35-day window).

---

## 25.8 Single-table design

DynamoDB best practice: model multiple entity types in one table using composite keys:

```
PK              SK              Attributes
USER#123        PROFILE         name, email
USER#123        ORDER#2024-001  total, status
USER#123        ORDER#2024-002  total, status
PRODUCT#ABC     METADATA        name, price
PRODUCT#ABC     REVIEW#001      rating, text
```

GSI for alternate access patterns:

```
GSI1PK=PRODUCT#ABC  GSI1SK=REVIEW#001  → All reviews for a product
```

---

## 25.9 Terraform example

```hcl
resource "aws_dynamodb_table" "orders" {
  name         = "Orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "UserId"
  range_key    = "OrderDate"

  attribute {
    name = "UserId"
    type = "S"
  }
  attribute {
    name = "OrderDate"
    type = "S"
  }
  attribute {
    name = "ProductId"
    type = "S"
  }

  global_secondary_index {
    name            = "ProductIndex"
    hash_key        = "ProductId"
    range_key       = "OrderDate"
    projection_type = "ALL"
  }

  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }

  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }

  tags = { Name = "orders-table" }
}
```

---

## 25.10 Monitoring

| Metric | Alarm threshold idea |
|--------|---------------------|
| `ConsumedReadCapacityUnits` | Approaching provisioned limit |
| `ConsumedWriteCapacityUnits` | Approaching provisioned limit |
| `ThrottledRequests` | Any throttling → scale capacity |
| `SuccessfulRequestLatency` | p99 > 10ms |
| `UserErrors` | 4xx errors from client |

Enable **Contributor Insights** for per-item access pattern analysis.

---

## 25.11 Chapter summary

- **DynamoDB** is serverless NoSQL with single-digit ms latency at any scale.
- Design **access patterns first**; use composite keys and **GSIs** for query flexibility.
- **Streams** enable event-driven architectures and change data capture.
- **Global Tables** provide multi-region active-active replication.
- Prefer **on-demand** for unpredictable workloads; **single-table design** for complex models.

---

## 🧪 Lab 25.1 — Orders table

1. Create a DynamoDB table with composite key (UserId + OrderDate).
2. Add a GSI on ProductId.
3. Insert 20 orders across 5 users and 3 products.
4. Query orders for one user; query orders for one product via GSI.

## 🧪 Lab 25.2 — Streams + Lambda

1. Enable DynamoDB Streams on your table.
2. Create a Lambda function triggered by stream events.
3. Insert/update items and verify Lambda processes changes.
4. Add a filter for INSERT events only.

---

## Review questions

1. What is the difference between a GSI and an LSI?
2. Why should you avoid Scan operations in production?
3. How do DynamoDB Streams enable change data capture?
4. What is single-table design and why is it recommended?
5. When would you choose provisioned capacity over on-demand?

---

*Next: [Chapter 26 — ElastiCache](./chapter-26-elasticache.md)*
