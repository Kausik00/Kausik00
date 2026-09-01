# Chapter 20: S3 — Buckets, Objects, Versioning, and Lifecycle

*AWS Handbook — Part V, Pages 401–425*

---

## 20.1 Amazon S3 overview

**Simple Storage Service (S3)** is object storage: store files (objects) in containers (buckets). Virtually unlimited scale; 99.999999999% durability.

Use cases:

- Static websites and assets
- Data lakes and backups
- Application uploads
- Log archives
- Terraform state files

---

## 20.2 Core concepts

| Concept | Description |
|---------|-------------|
| **Bucket** | Global unique name; lives in a region |
| **Object** | File + metadata; up to 5 TB |
| **Key** | Object path (e.g., `images/photo.jpg`) |
| **Prefix** | Simulated folders via key prefixes |

```bash
aws s3 mb s3://my-unique-bucket-name-12345
aws s3 cp report.pdf s3://my-bucket/reports/2026/
aws s3 ls s3://my-bucket/reports/
aws s3 sync ./local-dir s3://my-bucket/backup/
aws s3 rm s3://my-bucket/old/ --recursive
```

---

## 20.3 Storage classes

| Class | Use case | Retrieval |
|-------|----------|-----------|
| **Standard** | Frequent access | Immediate |
| **Standard-IA** | Infrequent access | Immediate, min storage charge |
| **Glacier Instant** | Archive, instant retrieval | Immediate |
| **Glacier Flexible** | Archive | Minutes to hours |
| **Glacier Deep Archive** | Long-term archive | 12–48 hours |
| **Intelligent-Tiering** | Unknown access patterns | Auto-moves tiers |

---

## 20.4 Versioning and lifecycle

### Versioning

Protects against accidental deletes; keeps all versions of objects.

```bash
aws s3api put-bucket-versioning \
  --bucket my-bucket \
  --versioning-configuration Status=Enabled
```

### Lifecycle rules

Automatically transition or expire objects:

```json
{
  "Rules": [{
    "ID": "archive-old-logs",
    "Status": "Enabled",
    "Filter": { "Prefix": "logs/" },
    "Transitions": [{
      "Days": 30,
      "StorageClass": "STANDARD_IA"
    }, {
      "Days": 90,
      "StorageClass": "GLACIER"
    }],
    "Expiration": { "Days": 365 }
  }]
}
```

---

## 20.5 Security

### Block Public Access (account and bucket level)

**Enable by default** on all buckets unless hosting a public static site intentionally.

### Encryption

| Method | Description |
|--------|-------------|
| SSE-S3 | AWS-managed keys |
| SSE-KMS | KMS keys; audit trail |
| SSE-C | Customer-provided keys |
| Client-side | Encrypt before upload |

### Bucket policies vs ACLs

- **Bucket policies** (JSON) — Preferred; resource-based IAM
- **ACLs** — Legacy; avoid for new projects

Example: allow CloudFront OAC to read objects (not public internet).

---

## 20.6 Static website hosting

```bash
# Enable static website hosting on bucket
aws s3 website s3://my-bucket/ --index-document index.html
```

Front with **CloudFront** + **ACM certificate** for HTTPS. Do not expose bucket directly to public.

---

## 20.7 S3 performance tips

- Use **multipart upload** for files > 100 MB
- Prefix keys for parallelism (S3 scales automatically)
- **S3 Transfer Acceleration** for long-distance uploads
- **S3 Inventory** for auditing object metadata

---

## 20.8 Chapter summary

- S3 stores **objects in buckets** with global-unique names.
- Enable **versioning** and **lifecycle** for data protection and cost control.
- **Block public access**; use bucket policies and CloudFront for controlled delivery.

---

## 🧪 Lab 20.1

1. Create bucket with versioning and default encryption (SSE-S3).
2. Upload files; delete one; restore previous version.
3. Add lifecycle rule to transition `logs/` to IA after 30 days.
4. Host static `index.html` behind CloudFront.

---

*Next: [Chapter 35 — CloudWatch](../part-09-observability/chapter-35-cloudwatch-fundamentals.md)*
