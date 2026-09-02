# Chapter 22: EBS & EFS

*AWS Handbook — Pages 103–108 of this PDF edition*
---

## 22.1 Block vs file storage on AWS

AWS provides two primary storage services for compute workloads:

| Service | Type | Attachment | Use case |
|---------|------|------------|----------|
| **Amazon EBS** | Block storage | Single EC2 instance (per volume) | Boot volumes, databases, single-instance apps |
| **Amazon EFS** | File storage (NFS) | Multiple instances simultaneously | Shared files, content management, web serving |

Understanding when to use each—and their performance, durability, and cost characteristics—is essential for architecting reliable applications.

---

## 22.2 Amazon EBS deep dive

**Elastic Block Store (EBS)** provides persistent block-level storage volumes for EC2 instances. Think of EBS as a virtual hard drive.

### Volume types

| Type | Storage | IOPS | Throughput | Use case |
|------|---------|------|------------|----------|
| **gp3** | SSD | 3,000–16,000 (configurable) | 125–1,000 MB/s | General purpose (default) |
| **gp2** | SSD | 3–16,000 (burst/scaled) | 128–250 MB/s | Legacy general purpose |
| **io2 Block Express** | SSD | Up to 256,000 | Up to 4,000 MB/s | Mission-critical databases |
| **io1/io2** | SSD | Up to 64,000 | Up to 1,000 MB/s | High-IOPS databases |
| **st1** | HDD | 500 baseline | Up to 500 MB/s | Throughput-intensive (big data) |
| **sc1** | HDD | 250 baseline | Up to 250 MB/s | Cold data, infrequent access |

**Recommendation:** Use **gp3** for most workloads. It offers better price-performance than gp2 with independently configurable IOPS and throughput.

### Key characteristics

- **AZ-bound** — A volume exists in one AZ; snapshot and restore to another AZ.
- **Durability** — 99.999% (replicated within AZ).
- **Encryption** — All volume types support encryption (default with account setting).
- **Size** — 1 GB to 64 TB per volume.
- **Multi-attach** — io1/io2 support attachment to multiple instances (cluster file systems only).

### Creating and attaching volumes

```bash
# Create a gp3 volume
aws ec2 create-volume \
  --availability-zone us-east-1a \
  --size 100 \
  --volume-type gp3 \
  --iops 3000 \
  --throughput 125 \
  --encrypted \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=data-vol}]'

# Attach to instance
aws ec2 attach-volume \
  --volume-id vol-0abc123 \
  --instance-id i-0def456 \
  --device /dev/sdf

# Format and mount (on the instance)
sudo mkfs -t xfs /dev/xvdf
sudo mkdir /data && sudo mount /dev/xvdf /data
echo '/dev/xvdf /data xfs defaults,nofail 0 2' | sudo tee -a /etc/fstab
```

### Terraform

```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  iops              = 3000
  throughput        = 125
  encrypted         = true
  kms_key_id        = aws_kms_key.ebs.arn

  tags = { Name = "app-data" }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.app.id
}
```

---

## 22.3 EBS snapshots

**Snapshots** are point-in-time backups stored in S3 (managed by AWS):

| Feature | Detail |
|---------|--------|
| **Incremental** | Only changed blocks since last snapshot |
| **Cross-region** | Copy snapshots for DR |
| **Cross-account** | Share snapshots with other accounts |
| **Fast Snapshot Restore** | Pre-warm snapshots for immediate IOPS (costly) |
| **Lifecycle** | Automate with Data Lifecycle Manager (DLM) |

```bash
# Create snapshot
aws ec2 create-snapshot \
  --volume-id vol-0abc123 \
  --description "Daily backup" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=daily-backup}]'

# Create AMI from snapshot (for golden images)
aws ec2 register-image \
  --name "app-ami-v2" \
  --block-device-mappings '[{
    "DeviceName": "/dev/xvda",
    "Ebs": {"SnapshotId": "snap-0abc123", "VolumeSize": 20, "VolumeType": "gp3"}
  }]'
```

### DLM policy example

```hcl
resource "aws_dlm_lifecycle_policy" "ebs_backup" {
  description        = "Daily EBS snapshots"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    schedule {
      name = "daily"
      create_rule { interval = 24; interval_unit = "HOURS"; times = ["03:00"] }
      retain_rule { count = 7 }
      copy_tags = true
    }
    target_tags = { Backup = "true" }
  }
}
```

---

## 22.4 Amazon EFS deep dive

**Elastic File System (EFS)** provides scalable, elastic NFS file storage accessible from multiple EC2 instances, ECS tasks, and Lambda functions simultaneously.

### Performance modes

| Mode | Throughput | Use case |
|------|------------|----------|
| **General Purpose** | Low latency | Web serving, CMS, dev environments |
| **Max I/O** | Higher aggregate throughput | Big data, media processing |

### Throughput modes

| Mode | Behavior |
|------|----------|
| **Bursting** | Scales with storage size; burst credits |
| **Provisioned** | Set throughput independent of storage size |
| **Elastic** (default) | Automatically scales throughput up and down |

### Storage classes

| Class | Description |
|-------|-------------|
| **Standard** | Frequently accessed files |
| **Infrequent Access (IA)** | Lifecycle policy moves files after N days |
| **Archive** | Rarely accessed; lowest cost |
| **One Zone** | Single AZ; lower cost, less resilience |

### EFS architecture

```
EC2 Instance A ──┐
EC2 Instance B ──┼── Mount Target (per AZ) ── EFS File System
ECS Tasks      ──┘     (ENI in subnet)
```

### Creating EFS

```bash
# Create file system
aws efs create-file-system \
  --performance-mode generalPurpose \
  --throughput-mode elastic \
  --encrypted \
  --tags Key=Name,Value=shared-data

# Create mount targets in each AZ
aws efs create-mount-target \
  --file-system-id fs-0abc123 \
  --subnet-id subnet-0aaa \
  --security-groups sg-0efs

# Mount on EC2 (Amazon Linux)
sudo yum install -y amazon-efs-utils
sudo mount -t efs -o tls fs-0abc123:/ /mnt/efs
```

### Terraform

```hcl
resource "aws_efs_file_system" "shared" {
  creation_token   = "shared-data"
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"
  encrypted        = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = { Name = "shared-efs" }
}

resource "aws_efs_mount_target" "az" {
  count           = length(var.private_subnet_ids)
  file_system_id  = aws_efs_file_system.shared.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}
```

---

## 22.5 EBS vs EFS comparison

| Feature | EBS | EFS |
|---------|-----|-----|
| Type | Block | File (NFS) |
| Access | Single instance (multi-attach for io1/io2) | Multiple instances |
| AZ | Single AZ | Regional (multi-AZ) |
| Max size | 64 TB | Petabyte scale |
| Latency | Sub-millisecond | Low (NFS overhead) |
| Cost | Lower per GB | Higher per GB |
| Boot volume | Yes | No |
| Backup | Snapshots | AWS Backup |

---

## 22.6 Instance Store (ephemeral)

**Instance store** volumes are physically attached to the host:

- **Highest IOPS** and lowest latency.
- **Ephemeral** — data lost on stop/terminate or hardware failure.
- Use for temporary data: caches, buffers, scratch space.
- Cannot be detached and reattached.

---

## 22.7 EBS optimization and monitoring

| Metric | What to watch |
|--------|---------------|
| `VolumeQueueLength` | I/O wait; sustained > 1 may need more IOPS |
| `VolumeReadBytes` / `VolumeWriteBytes` | Throughput utilization |
| `BurstBalance` (gp2) | Burst credit depletion |
| `PercentIOLimit` (io1/io2) | IOPS utilization |

### Right-sizing tips

- Start with gp3; increase IOPS/throughput independently.
- Use CloudWatch metrics to identify I/O-bound volumes.
- Consider io2 Block Express for databases requiring > 64K IOPS.

---

## 22.8 Chapter summary

- **EBS** provides block storage for single-instance workloads; **gp3** is the default choice.
- **Snapshots** enable backup, AMI creation, and cross-region DR.
- **EFS** provides shared NFS file storage across multiple instances and AZs.
- Use **DLM** for automated snapshot lifecycle management.
- Choose EBS for databases and boot volumes; EFS for shared file access.

---

## 🧪 Lab 22.1 — EBS volume lifecycle

1. Launch an EC2 instance and attach a 20 GB gp3 volume.
2. Format, mount, and write test data.
3. Create a snapshot, terminate the instance, launch a new instance, and restore from snapshot.
4. Verify data persistence.

## 🧪 Lab 22.2 — Shared EFS

1. Create an EFS file system with mount targets in two AZs.
2. Launch EC2 instances in both AZs and mount the EFS.
3. Write a file from Instance A and read it from Instance B.
4. Configure a lifecycle policy to move files to IA after 30 days.

---

## Review questions

1. What is the key difference between EBS and EFS access patterns?
2. Why is gp3 preferred over gp2 for new workloads?
3. What happens to instance store data when an EC2 instance is stopped?
4. How do EBS snapshots support disaster recovery?
5. When would you use EFS Infrequent Access storage class?

---

*Next: [Chapter 23 — AWS Backup & DR](./chapter-23-backup-dr.md)*
