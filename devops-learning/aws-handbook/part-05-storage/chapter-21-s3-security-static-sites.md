# Chapter 21: S3 Security, Encryption, and Static Websites

*AWS Handbook — Pages 96–101 of this PDF edition*
---

## 21.1 S3 security model

Amazon S3 security operates at multiple layers: **identity-based policies** (IAM), **resource-based policies** (bucket policies), **ACLs** (legacy), **block public access** settings, and **encryption**. Understanding how these layers interact is critical for preventing data breaches—the majority of S3 incidents involve misconfigured public access.

---

## 21.2 Block Public Access

**S3 Block Public Access** is the first line of defense. Enable it at the **account level** and verify it on every bucket:

| Setting | Effect |
|---------|--------|
| BlockPublicAcls | Blocks new public ACLs |
| IgnorePublicAcls | Ignores existing public ACLs |
| BlockPublicPolicy | Blocks bucket policies granting public access |
| RestrictPublicBuckets | Restricts access to buckets with public policies |

```bash
aws s3control put-public-access-block \
  --account-id 123456789012 \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

**Best practice:** Enable account-level block public access. Only disable for buckets that intentionally serve public content (static websites, CDN origins).

---

## 21.3 Bucket policies

Bucket policies are **resource-based** JSON policies attached to buckets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontOAC",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-static-site/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/E1234567890"
        }
      }
    }
  ]
}
```

### Common policy patterns

| Pattern | Principal | Use case |
|---------|-----------|----------|
| Cross-account access | Another account's IAM role | Shared data lake |
| CloudFront OAC | `cloudfront.amazonaws.com` | Static website via CDN |
| VPC endpoint restriction | `"*"` with `aws:SourceVpce` condition | Private S3 access |
| Deny unencrypted uploads | `"*"` with `Deny` + `s3:x-amz-server-side-encryption` | Compliance |

### Deny insecure transport

```json
{
  "Sid": "DenyInsecureTransport",
  "Effect": "Deny",
  "Principal": "*",
  "Action": "s3:*",
  "Resource": [
    "arn:aws:s3:::my-bucket",
    "arn:aws:s3:::my-bucket/*"
  ],
  "Condition": {
    "Bool": {
      "aws:SecureTransport": "false"
    }
  }
}
```

---

## 21.4 IAM policies for S3

Identity-based policies attach to IAM users, groups, or roles:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::app-data-${aws:username}/*"
    }
  ]
}
```

### Policy evaluation for S3

```
Request → Block Public Access → Bucket Policy → IAM Policy → ACL → Allow/Deny
```

Explicit **Deny** in any policy wins. Both identity and resource policies must allow for cross-account access.

---

## 21.5 Encryption

S3 supports encryption at rest and in transit.

### Server-side encryption (SSE)

| Type | Key management | Use case |
|------|----------------|----------|
| **SSE-S3** | AWS-managed (AES-256) | Default; no key management |
| **SSE-KMS** | AWS KMS customer-managed or AWS-managed key | Audit trail, key rotation, cross-account |
| **SSE-C** | Customer-provided key | You manage keys outside AWS |
| **DSSE-KMS** | Dual-layer KMS encryption | Highest security requirements |

### Default encryption

```bash
aws s3api put-bucket-encryption \
  --bucket my-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "arn:aws:kms:us-east-1:123456789012:key/abc-123"
      },
      "BucketKeyEnabled": true
    }]
  }'
```

**Bucket Key** reduces KMS API calls (and costs) by using a bucket-level key that wraps object keys.

### Client-side encryption

Encrypt data before uploading with the AWS Encryption SDK or your own encryption library. You manage keys entirely.

### Encryption in transit

- All S3 API calls use HTTPS by default.
- Enforce with bucket policy `aws:SecureTransport` condition.
- TLS 1.2+ required.

---

## 21.6 Access Points and Object Lambda

### S3 Access Points

Named network endpoints with dedicated bucket policies—simplify access for shared buckets:

```
Shared bucket → Access Point "finance" (finance team policy)
              → Access Point "engineering" (engineering team policy)
```

### S3 Object Lambda

Transform objects on retrieval (resize images, redact PII, convert formats) without modifying the stored object.

---

## 21.7 Static website hosting

S3 can host static websites (HTML, CSS, JS, images):

### Setup steps

1. Enable static website hosting on the bucket.
2. Set `index.html` as index document and `error.html` as error document.
3. Upload website files.
4. Configure bucket policy for public read (or use CloudFront OAC for private bucket).

```bash
aws s3 website s3://my-static-site/ \
  --index-document index.html \
  --error-document error.html
```

### Production architecture (recommended)

```
User → Route 53 → CloudFront → S3 (private bucket via OAC)
                      ↓
                   ACM certificate (HTTPS)
                   WAF (optional)
```

**Never expose S3 directly to the internet in production.** Use CloudFront with Origin Access Control (OAC) to keep the bucket private.

### Terraform static site

```hcl
resource "aws_s3_bucket" "site" {
  bucket = "my-static-site"
}

resource "aws_s3_bucket_website_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  index_document { suffix = "index.html" }
  error_document { key = "error.html" }
}

resource "aws_cloudfront_distribution" "site" {
  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.site.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }
}
```

---

## 21.8 S3 access logging and monitoring

| Feature | Purpose |
|---------|---------|
| **Server access logging** | Log all bucket requests to another bucket |
| **CloudTrail data events** | API-level logging (GetObject, PutObject) |
| **S3 Storage Lens** | Organization-wide storage analytics |
| **S3 Inventory** | Scheduled reports of objects and metadata |
| **Macie** | ML-based sensitive data discovery |

```bash
aws cloudtrail put-event-selectors \
  --trail-name org-trail \
  --event-selectors '[{
    "ReadWriteType": "All",
    "IncludeManagementEvents": true,
    "DataResources": [{
      "Type": "AWS::S3::Object",
      "Values": ["arn:aws:s3:::sensitive-bucket/"]
    }]
  }]'
```

---

## 21.9 Pre-signed URLs and temporary access

Grant time-limited access without making objects public:

```python
import boto3

s3 = boto3.client("s3")
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "my-bucket", "Key": "report.pdf"},
    ExpiresIn=3600,  # 1 hour
)
```

Use cases: download links, upload forms, sharing files with external parties.

---

## 21.10 Chapter summary

- Enable **Block Public Access** at the account level; only disable for intentional public buckets.
- Use **bucket policies** and **IAM policies** together for fine-grained access control.
- Encrypt with **SSE-KMS** for audit trails; enable **Bucket Key** to reduce KMS costs.
- Host static websites behind **CloudFront + OAC**, not direct S3 public access.
- Monitor with **CloudTrail data events**, **access logging**, and **Macie**.

---

## 🧪 Lab 21.1 — Secure bucket

1. Create a bucket with default SSE-KMS encryption and block public access.
2. Add a bucket policy denying unencrypted uploads and insecure transport.
3. Attempt to upload without encryption — verify denial.
4. Upload with `--server-side-encryption aws:kms` — verify success.

## 🧪 Lab 21.2 — Static website with CloudFront

1. Create an S3 bucket with static website files.
2. Create a CloudFront distribution with OAC (bucket stays private).
3. Configure Route 53 alias record and ACM certificate.
4. Verify HTTPS access through CloudFront.

---

## Review questions

1. What are the four S3 Block Public Access settings?
2. When would you use SSE-KMS over SSE-S3?
3. Why should production static sites use CloudFront OAC instead of public bucket policies?
4. How does a pre-signed URL provide temporary access?
5. What is the purpose of S3 Bucket Key?

---

*Next: [Chapter 22 — EBS & EFS](./chapter-22-ebs-efs.md)*
