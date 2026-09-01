# Chapter 24: RDS & Aurora

*AWS Handbook — Part VI, Pages 481–505*

---

## 24.1 Managed relational databases

**Amazon RDS** provides managed relational databases (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server) with automated patching, backups, monitoring, and Multi-AZ failover. **Amazon Aurora** is AWS's cloud-native database engine—MySQL and PostgreSQL compatible—with superior performance, storage auto-scaling, and global distribution.

For most new workloads, **Aurora PostgreSQL** or **Aurora MySQL** is the recommended choice over standard RDS.

---

## 24.2 RDS fundamentals

### Supported engines

| Engine | Versions | Licensing |
|--------|----------|-----------|
| **PostgreSQL** | 12–16 | Open source |
| **MySQL** | 5.7, 8.0 | Open source |
| **MariaDB** | 10.x | Open source |
| **Oracle** | 19c, 21c | BYOL or License Included |
| **SQL Server** | 2019, 2022 | License Included |
| **Aurora** | MySQL 5.7/8.0, PostgreSQL compatible | AWS proprietary |

### Instance classes

| Class | Use case |
|-------|----------|
| **db.t3/t4g** | Dev/test, burstable |
| **db.m6g/m7g** | General purpose, Graviton |
| **db.r6g/r7g** | Memory-optimized, large datasets |
| **db.x2g** | Extreme memory (Aurora) |

### Storage types

| Type | IOPS | Use case |
|------|------|----------|
| **gp3** | 3,000–16,000 | General purpose (default) |
| **io2** | Up to 256,000 | I/O-intensive workloads |
| **magnetic** | Legacy | Deprecated |

---

## 24.3 High availability

### Multi-AZ deployment

RDS synchronously replicates to a **standby instance** in another AZ:

```
Primary (AZ-a) ──sync replication──► Standby (AZ-b)
     │                                      │
     └── Failover (60–120s) ────────────────┘
```

- Automatic failover on primary failure.
- Same endpoint DNS (points to new primary after failover).
- Standby not readable (except Aurora).

### Read replicas

Asynchronous replication for **read scaling** and DR:

| Feature | Multi-AZ | Read Replica |
|---------|----------|--------------|
| Purpose | HA / failover | Read scaling, DR |
| Replication | Synchronous | Asynchronous |
| Endpoint | Same | Separate read endpoint |
| Cross-region | No | Yes |
| Promotion | Automatic | Manual |

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier mydb-replica-1 \
  --source-db-instance-identifier mydb \
  --db-instance-class db.t3.medium
```

---

## 24.4 Amazon Aurora

### Aurora architecture

Unlike RDS (local storage per instance), Aurora uses a **distributed, shared storage layer** across 3 AZs:

```
┌──────────┐  ┌──────────┐
│ Writer   │  │ Reader 1  │  ← Compute (Aurora instances)
└────┬─────┘  └────┬─────┘
     │            │
┌────▼────────────▼─────┐
│  Shared Storage (6 copies across 3 AZs) │
│  Auto-scales 10 GB → 128 TB             │
└─────────────────────────────────────────┘
```

### Aurora advantages over RDS

| Feature | Aurora | RDS |
|---------|--------|-----|
| Storage scaling | Automatic (10 GB–128 TB) | Manual (max 64 TB) |
| Read replicas | Up to 15, < 10ms lag | Up to 5 |
| Failover | ~30 seconds | 60–120 seconds |
| Storage copies | 6 across 3 AZs | 2 (Multi-AZ) |
| Serverless v2 | Yes (auto-scaling ACUs) | No |
| Global Database | < 1 second cross-region | Manual replica setup |
| Backtrack (MySQL) | Rewind to point in time | No |

### Aurora Serverless v2

Automatically scales compute capacity (ACUs) based on demand:

```hcl
resource "aws_rds_cluster" "aurora" {
  engine         = "aurora-postgresql"
  engine_mode    = "provisioned"
  engine_version = "15.4"
  database_name  = "appdb"
  master_username = "admin"
  master_password = var.db_password

  serverlessv2_scaling_configuration {
    min_capacity = 0.5  # ACUs
    max_capacity = 16
  }
}

resource "aws_rds_cluster_instance" "aurora" {
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
}
```

### Aurora Global Database

Cross-region replication with < 1 second lag:

```
Primary Region (us-east-1)          Secondary Region (eu-west-1)
┌─────────────────┐                 ┌─────────────────┐
│ Aurora Cluster   │──< 1s lag ──►│ Aurora Cluster   │
│ (read/write)     │                 │ (read-only)      │
└─────────────────┘                 └─────────────────┘
                                    Promote on failover
```

---

## 24.5 Backups and recovery

| Feature | RDS | Aurora |
|---------|-----|--------|
| Automated backups | 1–35 days retention | 1–35 days retention |
| Manual snapshots | Yes | Yes (cluster snapshot) |
| Point-in-time recovery | 5-minute granularity | 5-minute granularity |
| Backtrack (MySQL) | No | Rewind without restore |

```bash
# Restore to point in time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mydb \
  --target-db-instance-identifier mydb-restored \
  --restore-time 2024-06-15T10:30:00Z
```

---

## 24.6 Security

| Control | Implementation |
|---------|----------------|
| **Network** | Deploy in private subnets; security groups |
| **Encryption at rest** | KMS (enabled by default on new instances) |
| **Encryption in transit** | SSL/TLS connections (force via parameter group) |
| **IAM authentication** | Token-based auth (no password in connection string) |
| **Secrets Manager** | Auto-rotate database credentials |
| **Audit** | PostgreSQL log exports, MySQL audit plugin, CloudTrail |

### IAM database authentication

```python
import boto3

rds = boto3.client("rds")
token = rds.generate_db_auth_token(
    DBHostname="mydb.abc123.us-east-1.rds.amazonaws.com",
    Port=5432,
    DBUsername="iam_user",
    Region="us-east-1",
)
# Use token as password in connection string (valid 15 minutes)
```

---

## 24.7 Parameter and option groups

| Group | Purpose |
|-------|---------|
| **Parameter group** | Engine configuration (max_connections, shared_buffers) |
| **Option group** | Optional features (Oracle OEM, SQL Server SSIS) |

```bash
aws rds modify-db-parameter-group \
  --db-parameter-group-name custom-pg \
  --parameters "ParameterName=max_connections,ParameterValue=200,ApplyMethod=immediate"
```

---

## 24.8 Monitoring

| Tool | Metrics |
|------|---------|
| **CloudWatch** | CPU, connections, IOPS, replica lag, free storage |
| **Performance Insights** | Top SQL, wait events, database load |
| **Enhanced Monitoring** | OS-level metrics (1-second granularity) |
| **Event subscriptions** | SNS notifications for failover, maintenance |

Key alarms:
- `CPUUtilization` > 80%
- `FreeableMemory` < 256 MB
- `DatabaseConnections` approaching `max_connections`
- `ReplicaLag` > 30 seconds

---

## 24.9 Terraform example

```hcl
resource "aws_db_subnet_group" "main" {
  name       = "main"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "app-aurora"
  engine             = "aurora-postgresql"
  engine_version     = "15.4"
  database_name      = "appdb"
  master_username    = "admin"
  manage_master_user_password = true  # Secrets Manager

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 14
  preferred_backup_window = "03:00-04:00"
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.rds.arn

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = { Name = "app-aurora" }
}

resource "aws_rds_cluster_instance" "aurora" {
  count              = 2
  identifier         = "app-aurora-${count.index}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.r6g.large"
  engine             = aws_rds_cluster.aurora.engine
  publicly_accessible = false
}
```

---

## 24.10 Chapter summary

- **RDS** provides managed relational databases; **Aurora** offers superior performance and scaling.
- **Multi-AZ** for HA; **read replicas** for read scaling and cross-region DR.
- **Aurora Serverless v2** auto-scales compute; **Global Database** for multi-region.
- Encrypt at rest and in transit; use **IAM authentication** and **Secrets Manager**.
- Monitor with **Performance Insights** and CloudWatch alarms.

---

## 🧪 Lab 24.1 — Aurora cluster

1. Create an Aurora PostgreSQL cluster with one writer and one reader.
2. Connect via psql from a private EC2 instance.
3. Insert test data and query from the reader endpoint.
4. Simulate failover and verify application reconnects.

## 🧪 Lab 24.2 — Point-in-time recovery

1. Enable automated backups (7-day retention).
2. Create and delete a test table.
3. Restore to a point before the deletion.
4. Verify the table exists in the restored instance.

---

## Review questions

1. What is the difference between Multi-AZ and read replicas?
2. How does Aurora storage differ from RDS storage?
3. What is an ACU in Aurora Serverless v2?
4. How does Aurora Global Database achieve sub-second cross-region replication?
5. Why should databases be deployed in private subnets?

---

*Next: [Chapter 25 — DynamoDB](./chapter-25-dynamodb.md)*
