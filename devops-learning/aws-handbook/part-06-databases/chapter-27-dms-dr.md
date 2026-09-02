# Chapter 27: Database Migration (DMS) & DR

*AWS Handbook — Pages 131–136 of this PDF edition*
---

## 27.1 Database migration challenges

Migrating databases to AWS—whether from on-premises, another cloud, or between AWS engines—is one of the highest-risk activities in cloud adoption. **AWS Database Migration Service (DMS)** simplifies heterogeneous and homogeneous migrations with minimal downtime.

Combined with **Schema Conversion Tool (SCT)** for schema translation and **native replication features** for ongoing DR, AWS provides a complete migration toolkit.

---

## 27.2 AWS DMS overview

**DMS** replicates data between source and target databases continuously:

| Migration type | Description |
|----------------|-------------|
| **Full load** | One-time copy of all data |
| **Full load + CDC** | Initial copy + ongoing change data capture |
| **CDC only** | Ongoing replication (source already loaded) |

### Supported sources and targets

| Source | Target |
|--------|--------|
| On-premises Oracle, SQL Server, MySQL, PostgreSQL, MongoDB | RDS, Aurora, Redshift, S3, DynamoDB, Kinesis |
| EC2-hosted databases | Same as above |
| RDS / Aurora | Cross-engine (e.g., Oracle → PostgreSQL) |
| S3 | RDS, Redshift |

### DMS components

| Component | Description |
|-----------|-------------|
| **Replication instance** | EC2 instance running DMS engine |
| **Source endpoint** | Connection to source database |
| **Target endpoint** | Connection to target database |
| **Replication task** | Defines what to migrate and how |
| **Table mappings** | Rules for schema selection and transformation |

---

## 27.3 Migration workflow

```
1. Assess    → SCT analyzes source schema; identifies incompatibilities
2. Convert   → SCT converts schema to target engine (if heterogeneous)
3. Provision → Create target RDS/Aurora instance
4. Replicate → DMS full load + CDC
5. Cutover   → Switch application to target; stop DMS task
6. Validate  → Data validation and application testing
```

### Heterogeneous vs homogeneous

| Type | Example | SCT needed? |
|------|---------|-------------|
| **Homogeneous** | MySQL → Aurora MySQL | No |
| **Heterogeneous** | Oracle → Aurora PostgreSQL | Yes |
| **Homogeneous** | SQL Server → RDS SQL Server | No |
| **Heterogeneous** | MongoDB → DynamoDB | Partial |

---

## 27.4 DMS replication instance

| Size | vCPU | Memory | Use case |
|------|------|--------|----------|
| dms.t3.medium | 2 | 4 GB | Small databases (< 100 GB) |
| dms.r5.large | 2 | 16 GB | Medium workloads |
| dms.r5.4xlarge | 16 | 128 GB | Large, high-throughput migrations |
| dms.c5.9xlarge | 36 | 72 GB | Maximum throughput |

**Multi-AZ** replication instances provide automatic failover for ongoing CDC tasks.

### Terraform example

```hcl
resource "aws_dms_replication_subnet_group" "main" {
  replication_subnet_group_id          = "dms-subnet-group"
  replication_subnet_group_description = "DMS subnet group"
  subnet_ids                           = aws_subnet.private[*].id
}

resource "aws_dms_replication_instance" "main" {
  replication_instance_id     = "dms-replication"
  replication_instance_class  = "dms.r5.large"
  allocated_storage           = 100
  multi_az                    = true
  replication_subnet_group_id = aws_dms_replication_subnet_group.main.id
  vpc_security_group_ids      = [aws_security_group.dms.id]
}

resource "aws_dms_endpoint" "source" {
  endpoint_id   = "source-oracle"
  endpoint_type = "source"
  engine_name   = "oracle"
  server_name   = "on-prem-oracle.example.com"
  port          = 1521
  database_name = "ORCL"
  username      = "dms_user"
  password      = var.source_password
}

resource "aws_dms_endpoint" "target" {
  endpoint_id   = "target-aurora-pg"
  endpoint_type = "target"
  engine_name   = "aurora-postgresql"
  server_name   = aws_rds_cluster.aurora.endpoint
  port          = 5432
  database_name = "appdb"
  username      = "admin"
  password      = var.target_password
}

resource "aws_dms_replication_task" "migration" {
  replication_task_id      = "oracle-to-aurora-pg"
  migration_type         = "full-load-and-cdc"
  replication_instance_arn = aws_dms_replication_instance.main.replication_instance_arn
  source_endpoint_arn    = aws_dms_endpoint.source.endpoint_arn
  target_endpoint_arn    = aws_dms_endpoint.target.endpoint_arn

  table_mappings = file("${path.module}/table-mappings.json")

  replication_task_settings = jsonencode({
    TargetMetadata = { TargetSchema = "public" }
    FullLoadSettings = { TargetTablePrepMode = "DROP_AND_CREATE" }
    ChangeProcessingDdlHandlingPolicy = {
      HandleSourceTableDropped   = true
      HandleSourceTableTruncated = true
    }
  })
}
```

---

## 27.5 Schema Conversion Tool (SCT)

**SCT** automates schema conversion for heterogeneous migrations:

1. Connect to source database.
2. Analyze schema objects (tables, views, stored procedures, triggers).
3. Convert to target engine syntax.
4. Report incompatible objects for manual review.
5. Apply converted schema to target.

### Common conversion challenges

| Source (Oracle) | Target (PostgreSQL) | SCT action |
|-----------------|---------------------|------------|
| `VARCHAR2` | `VARCHAR` | Auto-convert |
| `NUMBER` | `NUMERIC` | Auto-convert |
| PL/SQL procedures | PL/pgSQL | Partial auto-convert |
| Packages | Schemas + functions | Manual review |
| Sequences | `SERIAL` / sequences | Auto-convert |

---

## 27.6 Migration strategies

### Big bang

Migrate everything in one maintenance window:

- **Pros:** Simple, clean cutover.
- **Cons:** Extended downtime; high risk.
- **When:** Small databases, tolerant downtime windows.

### Trickle (parallel run)

DMS replicates continuously; application reads from both during transition:

```
Phase 1: DMS full load + CDC running
Phase 2: Application writes to source; reads from source
Phase 3: Application writes to source; reads from target (validate)
Phase 4: Application writes to target; reads from target
Phase 5: Decommission source
```

- **Pros:** Minimal downtime (minutes for cutover).
- **Cons:** Complex application changes; dual-write period.

### Zero-ETL integrations

AWS-native integrations that eliminate DMS for supported paths:

| Integration | Source → Target |
|-------------|-----------------|
| **Aurora zero-ETL to Redshift** | Aurora → Redshift analytics |
| **S3 zero-ETL to Redshift** | S3 → Redshift |
| **OpenSearch zero-ETL** | Aurora/DMS → OpenSearch |

---

## 27.7 Data validation

DMS provides built-in data validation:

```json
{
  "ValidationSettings": {
    "EnableValidation": true,
    "ValidationMode": "ROW_LEVEL",
    "ThreadCount": 5,
    "FailureMaxCount": 10000
  }
}
```

Additionally:
- Row count comparison between source and target.
- Checksum validation for critical tables.
- Application-level integration testing.

---

## 27.8 Ongoing replication for DR

DMS is not just for migration—it enables ongoing replication for DR:

```
On-premises Oracle ──CDC──► Aurora PostgreSQL (DR region)
                                │
                          Promote on failover
```

| Feature | Benefit |
|---------|---------|
| **CDC** | Near-real-time replication |
| **Multi-AZ instance** | DMS failover protection |
| **Table filtering** | Replicate only critical tables |
| **Transformation rules** | Mask PII in DR copy |

For AWS-native DR, prefer **Aurora Global Database** or **RDS cross-region read replicas** over DMS when source is already on AWS.

---

## 27.9 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Full load slow | Undersized replication instance | Scale up instance class |
| CDC lag increasing | Network or target write bottleneck | Scale instance; optimize target |
| LOB columns failing | LOB settings too small | Increase `LobMaxSize` in task settings |
| FK constraint errors | Load order wrong | Disable FK checks during load |
| Connection timeout | Security group or network ACL | Verify SG rules and route tables |

```bash
aws dms describe-replication-tasks \
  --filters Name=replication-task-id,Values=oracle-to-aurora-pg

aws dms describe-table-statistics \
  --replication-task-arn arn:aws:dms:us-east-1:123456789012:task:abc123
```

---

## 27.10 Chapter summary

- **DMS** migrates databases with full load and ongoing CDC for minimal downtime.
- **SCT** converts schemas for heterogeneous migrations (Oracle → PostgreSQL, etc.).
- Use **trickle migration** for near-zero-downtime cutovers.
- DMS also supports **ongoing replication** for DR scenarios.
- Validate data thoroughly before and after cutover.

---

## 🧪 Lab 27.1 — Homogeneous migration

1. Create a source MySQL RDS instance with sample data.
2. Create a target Aurora MySQL cluster.
3. Configure DMS endpoints and a full-load + CDC replication task.
4. Verify data replication; insert new rows on source and confirm CDC delivery.

## 🧪 Lab 27.2 — Migration assessment

1. Install SCT on an EC2 instance.
2. Connect to a sample database and run an assessment report.
3. Review conversion warnings and manual action items.
4. Document a migration plan with estimated downtime.

---

## Review questions

1. What is the difference between full load and CDC in DMS?
2. When is SCT required for a database migration?
3. What is trickle migration and how does it minimize downtime?
4. How does DMS support ongoing DR replication?
5. What factors determine the size of a DMS replication instance?

---

*Next: [Chapter 28 — API Gateway](../part-07-integration/chapter-28-api-gateway.md)*
