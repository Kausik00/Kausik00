# Chapter 47: Data Services Cookbook (RDS, Aurora, DynamoDB, ElastiCache)

*AWS Handbook — Pages 253–259 of this PDF edition*

Relational, key-value, and cache layers show up together in every serious AWS architecture. This workbook treats them as one system: which workload belongs where, how they fail, how they authenticate, how they back up, and how Terraform and CLI make the design repeatable. It assumes Chapters 24–26. The goal is a cookbook you can use in a design review, not a feature list copied from the console.

---

## 47.1 Decision table

| Question | Prefer RDS | Prefer Aurora | Prefer DynamoDB | Prefer ElastiCache |
|----------|------------|---------------|-----------------|-------------------|
| Need SQL, joins, transactions, existing schema | Yes | Yes (MySQL/PostgreSQL compatible) | No | No (not a database of record) |
| Need storage that grows with little ops | Maybe (storage autoscaling) | Yes | Yes | RAM is the limit |
| Need single-digit ms at huge key-value scale | Unlikely | Unlikely | Yes | Yes, if data fits memory |
| Need cache in front of DB | Complement | Complement | DAX or ElastiCache | That is the product |
| Multi-region active-active | Hard | Aurora Global (read-mostly) or write forwarding patterns | Global Tables | Not a source of truth |
| Serverless-ish | RDS/Aurora Serverless v2 | Aurora Serverless v2 | On-demand | Not really |

**Anti-pattern:** DynamoDB because “it is serverless,” then modeling a relational schema with five `Scan`s per request. **Anti-pattern:** ElastiCache as the only copy of session data with no TTL policy and no rebuild path.

---

## 47.2 RDS in production

RDS is a managed engine (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle, Db2) on instances you size.

**Must-haves:**

- Multi-AZ (synchronous standby) for HA, not a read replica
- Subnet group using isolated data subnets in at least two (preferably three) AZs
- Security group: only app SG (or RDS Proxy SG) on 5432/3306
- Encryption at rest (KMS CMK), TLS in transit (`sslmode=require` / `rds.force_ssl`)
- Parameter group and option group in version control
- Enhanced Monitoring and Performance Insights on for production
- Automated backups with a retention that matches RPO; copy snapshots to another region if RTO requires it
- Disable public accessibility

```bash
aws rds create-db-instance \
  --db-instance-identifier orders-pg \
  --engine postgres \
  --engine-version 16.4 \
  --db-instance-class db.m7g.large \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:us-east-1:111122223333:key/KEY \
  --multi-az \
  --no-publicly-accessible \
  --vpc-security-group-ids sg-data \
  --db-subnet-group-name data-isolated \
  --backup-retention-period 7 \
  --enable-performance-insights \
  --deletion-protection \
  --master-username appadmin \
  --manage-master-user-password
```

`--manage-master-user-password` stores the master secret in Secrets Manager. Applications should still use a *least-privilege application user*, not the master.

**Read replicas** scale reads and can promote in DR. Replication lag is a first-class SLO. Do not write to a replica.

**RDS Proxy** sits between bursty compute (Lambda, Fargate tasks) and the instance. It multiplexes connections and can authenticate with Secrets Manager + IAM.

---

## 47.3 Aurora specifics

Aurora separates compute from a distributed storage volume replicated across AZs.

| Feature | Why it matters |
|---------|----------------|
| Storage auto-grows | You do not pre-provision 10 TB “just in case” |
| Fast clone | Cheap copy-on-write environments |
| Backtrack (MySQL) | Rewind without restoring a snapshot |
| Global Database | Low-RPO DR; secondary region read replicas |
| Serverless v2 | ACU scaling; still need VPC, still need connection management |
| Writer + readers | Failover promotes a reader; applications need the **cluster endpoint** vs **reader endpoint** vs **instance endpoints** |

Use the cluster writer endpoint for writes. Use the reader endpoint for read-only traffic that can tolerate lag. Custom endpoints group instance classes.

```hcl
resource "aws_rds_cluster" "orders" {
  cluster_identifier          = "orders"
  engine                      = "aurora-postgresql"
  engine_version              = "16.4"
  database_name               = "orders"
  master_username             = "appadmin"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.data.name
  vpc_security_group_ids      = [aws_security_group.data.id]
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.data.arn
  backup_retention_period     = 7
  deletion_protection         = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
}

resource "aws_rds_cluster_instance" "orders" {
  count              = 3
  identifier         = "orders-${count.index}"
  cluster_identifier = aws_rds_cluster.orders.id
  instance_class     = "db.r7g.large"
  engine             = aws_rds_cluster.orders.engine
}
```

---

## 47.4 DynamoDB design that will not melt

DynamoDB is not “RDS without SQL.” You design **access patterns first**.

1. List every query: get order by id, list orders by customer recently, etc.
2. Pick partition key for even load. Hot partitions (one customer = 50% of traffic) need write sharding.
3. Sort key for range queries. GSIs for alternate patterns. LSIs only if you knew them at table create.
4. Item size ≤ 400 KB. Large blobs belong in S3 with a pointer.
5. Capacity: on-demand for spiky or unknown; provisioned + auto scaling for steady high volume if cheaper.

```bash
aws dynamodb create-table \
  --table-name orders \
  --attribute-definitions \
      AttributeName=pk,AttributeType=S \
      AttributeName=sk,AttributeType=S \
      AttributeName=gsi1pk,AttributeType=S \
      AttributeName=gsi1sk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
  --global-secondary-indexes '[{
      "IndexName": "gsi1",
      "KeySchema": [{"AttributeName":"gsi1pk","KeyType":"HASH"},{"AttributeName":"gsi1sk","KeyType":"RANGE"}],
      "Projection": {"ProjectionType":"ALL"}
  }]' \
  --billing-mode PAY_PER_REQUEST \
  --sse-specification Enabled=true,SSEType=KMS,KMSMasterKeyId=alias/data \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES
```

**Transactions** (`TransactWriteItems`) for all-or-nothing across items. **Conditions** for optimistic locking (`version` attribute). **TTL** for sessions. **PITR** for production tables. **Streams** to Lambda for projections, search indexes, or audit.

**Global Tables** replicate across regions. Conflict resolution is last-writer-wins per item. Design for idempotency.

IAM: `dynamodb:GetItem` on `table/orders` and `table/orders/index/*` as needed. Avoid `Scan` in production IAM if you can; it is a foot-gun.

---

## 47.5 ElastiCache cookbook

Redis/Valkey-compatible or Memcached. Redis OSS / Valkey for data structures, replication, and persistence options; Memcached for simple object cache with easy horizontal scale.

**Production Redis/Valkey:**

- Cluster mode enabled for large datasets and online resharding
- Multi-AZ with automatic failover
- In-transit encryption and at-rest encryption
- AUTH token or IAM authentication where supported; never open `0.0.0.0/0`
- Parameter group: eviction policy (`allkeys-lru` vs `volatile-lru`) matching whether keys have TTLs
- Subnet group in data subnets; security group from app only

```hcl
resource "aws_elasticache_replication_group" "sessions" {
  replication_group_id       = "sessions"
  description                = "session cache"
  engine                     = "valkey"
  engine_version             = "8.0"
  node_type                  = "cache.r7g.large"
  num_node_groups            = 2
  replicas_per_node_group    = 1
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.data.name
  security_group_ids         = [aws_security_group.cache.id]
}
```

**Cache patterns:**

| Pattern | Behavior |
|---------|----------|
| Cache-aside | App reads cache; on miss, reads DB, writes cache |
| Write-through | App writes cache and DB together |
| Write-behind | Dangerous without a queue; usually skip |
| Stampede control | TTL jitter; singleflight lock on miss |

ElastiCache is not durable enough to be the order ledger. If Redis is down, the app must still serve from RDS/DynamoDB, perhaps slower.

---

## 47.6 Putting them together: a reference orders stack

```
API / workers
    │
    ├─ ElastiCache: session, hot product pages (TTL)
    ├─ DynamoDB: shopping cart, idempotency keys, high-churn keys
    ├─ Aurora PostgreSQL: orders, payments references, reporting joins
    └─ SQS: async fulfillment (not in this chapter, but the glue)
```

**Consistency:** cart in DynamoDB can be eventually consistent; charging a card cannot. **Failover:** Aurora failover is tens of seconds; DynamoDB regional events are rare but Global Tables have a different failure model; ElastiCache failover drops in-memory data unless you designed persistence (and even then, treat it as cache).

**Secrets:** RDS and cache passwords in Secrets Manager with rotation. RDS IAM auth for apps that can use tokens. DynamoDB uses IAM only (no password).

---

## 47.7 Backup, PITR, and DR matrix

| Service | Backup primitive | Typical RPO | Cross-region |
|---------|------------------|-------------|--------------|
| RDS | Automated snapshots + PITR | Minutes (backup window / PITR) | Snapshot copy |
| Aurora | Continuous + PITR, clones | Seconds-to-minutes | Global DB or snapshot |
| DynamoDB | On-demand backups + PITR (35 days) | Seconds with PITR | Global Tables or backup restore |
| ElastiCache | Snapshots (Redis/Valkey) | Last snapshot | Copy snapshot; rebuild from DB otherwise |

Test restore quarterly. An untested snapshot is a rumor.

```bash
aws rds restore-db-cluster-to-point-in-time \
  --source-db-cluster-identifier orders \
  --db-cluster-identifier orders-pitr-test \
  --restore-to-time 2026-09-01T12:00:00Z \
  --use-latest-restorable-time false
```

---

## 47.8 Observability that predicts outages

**RDS/Aurora:** `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections`, `ReadLatency`/`WriteLatency`, `ReplicaLag`, wait events in Performance Insights, slow query log.

**DynamoDB:** `UserErrors`, `SystemErrors`, `ThrottledRequests`, `SuccessfulRequestLatency`, `ConsumedReadCapacityUnits`, online GSI backfill.

**ElastiCache:** `CPUUtilization`, `EngineCPUUtilization` (Redis), `Evictions`, `CurrConnections`, `ReplicationLag`.

Alarms: connections near `max_connections`, storage < 20%, replica lag above SLO, DynamoDB throttles > 0 for 5 minutes on a provisioned table, cache hit rate collapse.

---

## 47.9 Lab 1 — Aurora + proxy + failover

1. Create an Aurora PostgreSQL cluster with two instances in different AZs.
2. Place RDS Proxy in app subnets (or dedicated), targeting the cluster.
3. Run a small client loop (`SELECT 1` and a write) against the proxy endpoint.
4. Failover the cluster (`aws rds failover-db-cluster`).
5. Measure error count and reconnect time. Compare connecting to an *instance* endpoint (wrong) vs cluster/proxy (right).

---

## 47.10 Lab 2 — DynamoDB access patterns

1. Model `PK=CUSTOMER#id`, `SK=ORDER#ulid` and a GSI `GSI1PK=STATUS#OPEN`, `GSI1SK=DATE#...`.
2. Put 1,000 items. Query by customer. Query open orders via GSI.
3. Enable PITR. Delete the table (in a lab account!). Restore. Confirm item count.
4. Turn on a stream; attach a Lambda that writes to S3. Place one order; confirm the object.

---

## 47.11 Lab 3 — Cache stampede

1. Tiny Redis (or even a local docker if you must) plus a slow “DB” mock (sleep 500ms).
2. 100 concurrent cache misses on one key.
3. Implement mutex/singleflight or probabilistic early expiration.
4. Graph DB QPS with and without protection.

Then repeat against ElastiCache in AWS if budget allows.

---

## 47.12 Terraform security group sketch

```hcl
resource "aws_security_group" "data" {
  name   = "data-db"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] } # tighten in real modules
}
```

Tighten egress: data subnets often need no internet if you use VPC endpoints for Secrets Manager and CloudWatch.

---

## 47.13 Cost notes (prelude to Chapter 49)

- Aurora ACUs and RDS instance class dominate if you oversize “for Black Friday” all year.
- DynamoDB on-demand is cost-effective until a Scan-heavy workload arrives.
- ElastiCache is billed for nodes whether you use the RAM or not; rightsize and use reserved nodes when stable.
- Idle Multi-AZ RDS in every developer account is a classic bill shock. Use Aurora clones or shared non-prod with obfuscated data.

---

## 47.14 Review questions

1. Why is a read replica not a substitute for Multi-AZ on RDS?
2. Which Aurora endpoint should writers use, and why?
3. When do you pick DynamoDB on-demand vs provisioned?
4. What is a hot partition, and how do you mitigate it?
5. Why is ElastiCache a bad system of record for orders?
6. How does RDS Proxy help Lambda?
7. What does PITR give you that a nightly snapshot does not?
8. Why encrypt DynamoDB with a CMK instead of AWS-owned keys in regulated workloads?
9. What happens to in-flight Redis keys on failover if persistence is off?
10. How should an app behave if the cache is unreachable but Aurora is healthy?

**Answers (brief):** (1) Replicas are async; Multi-AZ is the HA standby. (2) Cluster writer endpoint so DNS follows failover. (3) On-demand for unknown/spiky; provisioned when you can predict and save. (4) One key takes most throughput; shard keys, write spreading. (5) Memory-centric, eviction, weaker durability. (6) Connection multiplexing and fewer TLS/auth handshakes to the engine. (7) Restore to a time inside the retention window, not only 02:00 snapshots. (8) Key policy, rotation, and audit of who can decrypt. (9) They may be gone; clients reconnect to a possibly empty cache. (10) Bypass cache (cache-aside) and serve from the database.

---

## 47.15 Migrations, blue/green, and parameter groups

RDS blue/green deployments (where supported) create a staging copy, replicate, then switch. Practice in non-prod. Aurora major version upgrades are a project: clone, run the app, then upgrade the writer with a change window.

DMS (Chapter 27) belongs when you leave on-premises or a self-managed engine. For homogeneous Aurora upgrades, prefer native tools first.

**Parameter groups:** `shared_buffers`, `max_connections`, `rds.force_ssl`, log_min_duration. Changing static parameters forces reboot — treat as a deploy. Never share a custom parameter group across unrelated apps; a change for one reboots the other.

**Auth:** IAM database authentication for humans and some apps; rotating passwords in Secrets Manager for others. Disable password auth only when you have proven every client.

**DynamoDB contrib:** DynamoDB Local for unit tests; NoSQL Workbench for index design; PartiQL for ad hoc, not for hot paths. **Contributor Insights** shows hot keys.

**Cache aside reference client (pseudo):**

```text
value = redis.get(key)
if value is nil:
    value = db.query(...)
    redis.setex(key, ttl + jitter(), value)
return value
```

Jitter of ±10% on TTL prevents synchronized expiry of a popular keyset after a deploy.

**Security groups vs Public Accessibility:** an RDS instance can be “not public” and still reachable from too many SGs. Audit ingress rules quarterly.

---

## 47.16 What to do next

You now have data stores that must be watched as security objects, not only as performance objects. Chapter 48 covers GuardDuty, Security Hub, findings, and incident response when those stores — or the IAM that guards them — are under attack.
