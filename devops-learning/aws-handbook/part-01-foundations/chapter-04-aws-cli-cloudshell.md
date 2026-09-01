# Chapter 4: AWS CLI, CloudShell, and SDK Overview

*AWS Handbook — Part I, Pages 56–80*

---

## 4.1 Why the CLI matters for DevOps

The **AWS Management Console** is excellent for exploration, but production workflows demand **repeatability**, **version control**, and **automation**. The **AWS Command Line Interface (CLI)** is the universal tool that every AWS service exposes through a consistent interface. Combined with **CloudShell** (browser-based shell) and **SDKs** (programmatic libraries), you can script deployments, integrate CI/CD pipelines, and build applications that call AWS APIs directly.

DevOps engineers typically spend 70–80% of their AWS interaction time in CLI and IaC tools, reserving the console for debugging and one-off investigations.

---

## 4.2 Installing and configuring the AWS CLI

### Installation options

| Platform | Method |
|----------|--------|
| Linux/macOS | `curl` installer or package manager |
| Windows | MSI installer or `winget` |
| CI/CD | Pre-installed on GitHub Actions runners; use in Docker |
| CloudShell | Pre-installed; no setup required |

### AWS CLI v2 vs v1

Always use **CLI v2**. It supports SSO, improved pagination, `aws s3` performance improvements, and interactive `aws configure sso`.

### Initial configuration

```bash
# Interactive setup with long-term access keys (avoid for daily use; prefer SSO)
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region name: us-east-1
# Default output format: json

# Verify identity
aws sts get-caller-identity
```

Configuration files live at:

| File | Purpose |
|------|---------|
| `~/.aws/credentials` | Access keys per profile |
| `~/.aws/config` | Region, output format, SSO settings |

### Named profiles

```bash
aws configure --profile dev
aws s3 ls --profile dev

# Environment variable override
export AWS_PROFILE=prod
aws ec2 describe-instances --query 'Reservations[].Instances[].InstanceId'
```

### SSO configuration (recommended for humans)

```bash
aws configure sso
# SSO session name: my-org
# SSO start URL: https://my-org.awsapps.com/start
# SSO region: us-east-1
# CLI default client Region: us-east-1

aws sso login --profile dev-admin
aws sts get-caller-identity --profile dev-admin
```

---

## 4.3 AWS CloudShell

**AWS CloudShell** is a browser-based shell environment pre-authenticated with your console credentials. It includes the AWS CLI v2, Python, Node.js, Git, and 1 GB persistent storage per region.

### When to use CloudShell

| Use CloudShell | Use local CLI |
|----------------|---------------|
| Quick API calls from console | Daily development |
| No local install available | CI/CD pipelines |
| Temporary troubleshooting | Scripts in version control |
| Learning and labs | Large file transfers |

### CloudShell features

- **Automatic credentials** — Uses your current console session IAM permissions.
- **Persistent home directory** — Files survive across sessions (per region).
- **Network access** — Can reach public AWS APIs; VPC access requires additional setup.
- **Limitations** — 1 GB storage, no inbound connections, session timeout after inactivity.

```bash
# Example: list S3 buckets from CloudShell
aws s3 ls

# Install a Python package (persists in home directory)
pip install --user boto3
```

---

## 4.4 CLI essentials: structure and patterns

Every AWS CLI command follows this pattern:

```
aws <service> <operation> [--parameters] [--global-options]
```

### Global options

| Option | Purpose |
|--------|---------|
| `--region` | Override default region |
| `--profile` | Use named profile |
| `--output` | `json`, `yaml`, `text`, `table` |
| `--query` | JMESPath filter on response |
| `--dry-run` | Validate without executing (where supported) |
| `--no-cli-pager` | Disable pager for scripts |

### JMESPath query examples

```bash
# List running EC2 instance IDs only
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].InstanceId' \
  --output text

# Get bucket names and creation dates as a table
aws s3api list-buckets \
  --query 'Buckets[].{Name:Name,Created:CreationDate}' \
  --output table
```

### Pagination

```bash
# CLI v2 auto-paginates most list operations
aws ec2 describe-instances --output json

# Manual control
aws s3api list-objects-v2 --bucket my-bucket --max-items 100
```

### Waiters

```bash
aws ec2 run-instances --image-id ami-0c55b159cbfafe1f0 --instance-type t3.micro ...

aws ec2 wait instance-running --instance-ids i-0abc123
aws ec2 wait instance-status-ok --instance-ids i-0abc123
```

---

## 4.5 AWS SDK overview

SDKs wrap AWS APIs in language-native libraries. They handle request signing, retries, and pagination.

| SDK | Language | Package |
|-----|----------|---------|
| **Boto3** | Python | `pip install boto3` |
| **AWS SDK for JavaScript v3** | Node.js | `@aws-sdk/client-s3` |
| **AWS SDK for Go v2** | Go | `github.com/aws/aws-sdk-go-v2` |
| **AWS SDK for .NET** | C# | `AWSSDK.S3` |

### Credential chain (SDK and CLI)

Both resolve credentials in this order:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. Shared credentials file (`~/.aws/credentials`)
3. IAM role (EC2 instance profile, ECS task role, Lambda execution role)
4. SSO cached credentials

**Best practice:** Applications on AWS use **IAM roles**, never hard-coded keys.

### Boto3 example

```python
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
response = s3.list_buckets()
for bucket in response["Buckets"]:
    print(bucket["Name"])
```

### SDK with assumed role

```python
import boto3

sts = boto3.client("sts")
assumed = sts.assume_role(
    RoleArn="arn:aws:iam::123456789012:role/CrossAccountRole",
    RoleSessionName="my-session",
)
creds = assumed["Credentials"]
client = boto3.client(
    "s3",
    aws_access_key_id=creds["AccessKeyId"],
    aws_secret_access_key=creds["SecretAccessKey"],
    aws_session_token=creds["SessionToken"],
)
```

---

## 4.6 Terraform provider configuration

Terraform uses the AWS provider, which shares the same credential chain as the CLI.

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "dev"
}

resource "aws_s3_bucket" "logs" {
  bucket = "my-app-logs-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}
```

---

## 4.7 CLI security best practices

| Practice | Rationale |
|----------|-----------|
| Use SSO, not long-term access keys | Keys can leak; SSO sessions expire |
| Never commit credentials to Git | Use IAM roles in CI/CD |
| Use `--profile` or `AWS_PROFILE` | Separate dev/staging/prod |
| Enable MFA for sensitive operations | Extra layer for destructive actions |
| Rotate any remaining access keys | Limit blast radius |
| Use `aws sts get-caller-identity` before destructive commands | Confirm correct account |

---

## 4.8 Useful CLI productivity tips

```bash
# Auto-complete (bash)
complete -C '/usr/local/bin/aws_completer' aws

# Generate CLI skeleton for complex commands
aws ec2 run-instances --generate-cli-skeleton input > run-instance.json
# Edit JSON, then:
aws ec2 run-instances --cli-input-json file://run-instance.json

# Filter help by service
aws ec2 help | grep describe

# Export credentials for third-party tools (short-lived)
eval "$(aws configure export-credentials --profile dev --format env)"
```

---

## 4.9 Chapter summary

- The **AWS CLI** is the foundation of automation; configure profiles and prefer **SSO**.
- **CloudShell** provides instant CLI access from the console without local setup.
- **SDKs** (Boto3, etc.) use the same credential chain; applications on AWS should use **IAM roles**.
- Master **JMESPath queries**, **waiters**, and **pagination** for efficient scripting.
- Terraform and other IaC tools inherit CLI credential configuration.

---

## 🧪 Lab 4.1 — CLI and CloudShell workflow

1. Install AWS CLI v2 locally (or open **CloudShell** in the console).
2. Configure an SSO profile: `aws configure sso`.
3. Run `aws sts get-caller-identity` and note your account ID and ARN.
4. List all regions: `aws ec2 describe-regions --query 'Regions[].RegionName' --output table`.
5. Create a test S3 bucket (unique name): `aws s3 mb s3://cli-lab-$(aws sts get-caller-identity --query Account --output text)-$(date +%s)`.
6. Upload a file: `echo "hello" > test.txt && aws s3 cp test.txt s3://YOUR-BUCKET/`.
7. Delete the bucket and objects when done.

## 🧪 Lab 4.2 — Boto3 script

1. On an EC2 instance with an instance profile (or locally with configured credentials), write a Python script that lists all EC2 instances and prints ID, type, and state.
2. Run it with `python3 list_instances.py`.
3. Extend the script to tag instances missing an `Owner` tag.

---

## Review questions

1. What is the difference between `~/.aws/credentials` and `~/.aws/config`?
2. How does the SDK credential chain resolve credentials on an EC2 instance with an instance profile?
3. What JMESPath query would return only S3 bucket names from `aws s3api list-buckets`?
4. When should you use CloudShell instead of a local CLI installation?
5. Why is SSO preferred over long-term access keys for human users?

---

*Next: [Chapter 5 — IAM Fundamentals](../part-02-iam/chapter-05-iam-fundamentals.md)*
