# Chapter 34: Systems Manager & Parameter Store

*AWS Handbook — Pages 173–178 of this PDF edition*
---

## 34.1 AWS Systems Manager overview

**AWS Systems Manager** is a unified operations hub for managing AWS and hybrid resources. It eliminates the need for SSH bastion hosts, manual patching, and ad-hoc scripting by providing centralized visibility, automation, and configuration management.

Key capabilities include **Session Manager** (browser-based shell access), **Patch Manager**, **Run Command**, **State Manager**, and integration with **Parameter Store** and **Secrets Manager**.

---

## 34.2 Session Manager

**Session Manager** provides secure, auditable shell access to EC2 instances and on-premises servers without opening inbound SSH ports:

```
Engineer → AWS Console/CLI → Session Manager → SSM Agent → EC2 instance
```

### Advantages over SSH

| Feature | SSH | Session Manager |
|---------|-----|-----------------|
| Inbound port 22 | Required | Not required |
| Bastion host | Often needed | Not needed |
| Key management | SSH keys | IAM permissions |
| Audit logging | Manual | CloudWatch Logs + S3 automatically |
| Access control | Security groups + keys | IAM policies |

### Requirements

1. **SSM Agent** installed on the instance (pre-installed on Amazon Linux, Windows AMIs).
2. **IAM instance profile** with `AmazonSSMManagedInstanceCore` policy.
3. **Network path** to SSM endpoints (internet, NAT, or VPC endpoints).

```bash
# Start a session
aws ssm start-session --target i-0abc123

# Port forwarding (access RDS through instance)
aws ssm start-session \
  --target i-0abc123 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["mydb.abc.rds.amazonaws.com"],"portNumber":["5432"],"localPortNumber":["5432"]}'
```

### Session logging

```hcl
resource "aws_ssm_document" "session_prefs" {
  name            = "SSM-SessionManagerRunShell"
  document_type   = "Session"
  document_format = "JSON"
  content = jsonencode({
    schemaVersion = "1.0"
    sessionType   = "Standard_Stream"
    inputs = {
      s3BucketName                = aws_s3_bucket.session_logs.bucket
      s3KeyPrefix                 = "session-logs/"
      cloudWatchLogGroupName      = aws_cloudwatch_log_group.sessions.name
      cloudWatchEncryptionEnabled = true
    }
  })
}
```

---

## 34.3 Run Command

Execute commands across fleets without SSH:

```bash
# Run command on tagged instances
aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:Environment,Values=production" \
  --parameters 'commands=["yum update -y", "systemctl restart httpd"]' \
  --comment "Patch and restart web servers"

# Check command status
aws ssm list-command-invocations \
  --command-id abc-123 \
  --details
```

### Common documents

| Document | Purpose |
|----------|---------|
| `AWS-RunShellScript` | Run shell commands (Linux) |
| `AWS-RunPowerShellScript` | Run PowerShell (Windows) |
| `AWS-UpdateSSMAgent` | Update SSM Agent |
| `AWS-ConfigureAWSPackage` | Install SSM packages |

---

## 34.4 Patch Manager

Automate OS patching across your fleet:

```
Maintenance Window → Patch Baseline → Scan → Install → Reboot (if needed)
```

```hcl
resource "aws_ssm_patch_baseline" "amazon_linux" {
  name             = "amazon-linux-baseline"
  operating_system = "AMAZON_LINUX_2"

  approval_rule {
    approve_after_days = 7
    patch_filter {
      key    = "CLASSIFICATION"
      values = ["Security", "Critical"]
    }
  }
}

resource "aws_ssm_maintenance_window" "patch" {
  name     = "patch-window"
  schedule = "cron(0 2 ? * SUN *)"  # Sundays at 2 AM
  duration = 4
  cutoff   = 1
}
```

---

## 34.5 State Manager

**State Manager** maintains desired configuration state on instances (similar to Ansible/Chef):

```yaml
# Association: ensure CloudWatch agent is installed
schemaVersion: "2.2"
description: Install and configure CloudWatch agent
mainSteps:
  - action: aws:configurePackage
    name: installCWAgent
    inputs:
      action: Install
      name: AmazonCloudWatchAgent
  - action: aws:runCommand
    name: configureCWAgent
    inputs:
      documentType: SSMDocument
      documentPath: AmazonCloudWatch-ManageAgent
      parameters:
        action: configure
        mode: ec2
```

Associations run on a schedule or at instance launch, ensuring compliance.

---

## 34.6 Parameter Store

**Systems Manager Parameter Store** provides hierarchical storage for configuration data and secrets:

| Type | Cost | Use case |
|------|------|----------|
| **String** | Free | Configuration values, AMI IDs |
| **StringList** | Free | Comma-separated values |
| **SecureString** | Free (KMS charges apply) | Passwords, API keys, tokens |

### Hierarchy

```
/app/prod/database/host
/app/prod/database/port
/app/prod/database/password  (SecureString)
/app/dev/database/host
/shared/ami/amazon-linux-2023
```

### Creating parameters

```bash
aws ssm put-parameter \
  --name "/app/prod/database/host" \
  --value "mydb.abc.us-east-1.rds.amazonaws.com" \
  --type String \
  --tags "Key=Environment,Value=prod"

aws ssm put-parameter \
  --name "/app/prod/database/password" \
  --value "super-secret" \
  --type SecureString \
  --key-id alias/app-secrets
```

### Reading parameters

```bash
# Single parameter
aws ssm get-parameter \
  --name "/app/prod/database/password" \
  --with-decryption

# By path (all under /app/prod/)
aws ssm get-parameters-by-path \
  --path "/app/prod/" \
  --recursive \
  --with-decryption
```

### In application code

```python
import boto3

ssm = boto3.client("ssm")
response = ssm.get_parameters_by_path(
    Path="/app/prod/",
    Recursive=True,
    WithDecryption=True,
)
config = {p["Name"].split("/")[-1]: p["Value"] for p in response["Parameters"]}
```

### Terraform

```hcl
resource "aws_ssm_parameter" "db_host" {
  name  = "/app/${var.environment}/database/host"
  type  = "String"
  value = aws_rds_cluster.main.endpoint
}

resource "aws_ssm_parameter" "db_password" {
  name   = "/app/${var.environment}/database/password"
  type   = "SecureString"
  key_id = aws_kms_key.app.id
  value  = var.db_password
}
```

---

## 34.7 Parameter Store vs Secrets Manager

| Feature | Parameter Store | Secrets Manager |
|---------|-----------------|-----------------|
| **Cost** | Free (Standard); KMS for SecureString | $0.40/secret/month + API calls |
| **Rotation** | Manual or Lambda | Built-in rotation for RDS |
| **Cross-account** | Via RAM | Via resource policy |
| **Max size** | 4 KB (advanced: 8 KB) | 64 KB |
| **Versioning** | Yes | Yes |
| **Use case** | Config, non-rotating secrets | Database credentials, API keys with rotation |

**Guideline:** Use Parameter Store for configuration and non-rotating secrets. Use Secrets Manager for credentials requiring automatic rotation.

---

## 34.8 Inventory and Compliance

| Feature | Purpose |
|---------|---------|
| **Inventory** | Collect OS, application, and custom metadata from instances |
| **Compliance** | Track patch compliance against baselines |
| **OpsCenter** | Investigate and remediate operational issues |

```bash
aws ssm get-inventory \
  --filters '[{"Key":"AWS:InstanceInformation.PlatformName","Values":["Amazon Linux"],"Type":"Equal"}]'
```

---

## 34.9 VPC endpoints for SSM

For instances without internet access, create VPC interface endpoints:

| Endpoint | Purpose |
|----------|---------|
| `com.amazonaws.region.ssm` | Systems Manager API |
| `com.amazonaws.region.ssmmessages` | Session Manager |
| `com.amazonaws.region.ec2messages` | SSM Agent communication |

```hcl
resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
```

---

## 34.10 Chapter summary

- **Session Manager** replaces SSH with IAM-controlled, auditable shell access.
- **Run Command** and **Patch Manager** automate fleet operations.
- **Parameter Store** provides hierarchical configuration and secret storage.
- Use **Secrets Manager** for credentials requiring automatic rotation.
- Deploy **VPC endpoints** for SSM in private subnets without internet access.

---

## 🧪 Lab 34.1 — Session Manager access

1. Launch an EC2 instance with SSM instance profile (no SSH key, no port 22).
2. Connect via Session Manager in the console.
3. Enable session logging to S3 and CloudWatch Logs.
4. Review the session log after disconnecting.

## 🧪 Lab 34.2 — Parameter Store configuration

1. Create a hierarchy of parameters under `/app/dev/`.
2. Write a script that reads all parameters and prints configuration.
3. Update a Lambda function to read database credentials from Parameter Store.
4. Rotate a SecureString parameter and verify the application picks up the new value.

---

## Review questions

1. What are the advantages of Session Manager over traditional SSH?
2. What IAM policy must an EC2 instance have for Session Manager?
3. When should you use Secrets Manager instead of Parameter Store?
4. How does State Manager differ from Run Command?
5. Which VPC endpoints are required for Session Manager in a private subnet?

---

*Next: [Chapter 35 — CloudWatch Fundamentals](../part-09-observability/chapter-35-cloudwatch-fundamentals.md)*
