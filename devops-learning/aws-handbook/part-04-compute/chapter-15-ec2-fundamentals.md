# Chapter 15: EC2 — Instance Types, AMIs, and Launch Templates

*AWS Handbook — Part IV, Pages 281–305*

---

## 15.1 Amazon EC2 overview

**Elastic Compute Cloud (EC2)** provides resizable virtual machines in the cloud. You choose:

- **Instance type** — CPU, memory, network, storage
- **AMI** — Operating system image
- **Networking** — VPC, subnet, security groups
- **Storage** — EBS volumes
- **IAM role** — Permissions without access keys

---

## 15.2 Instance families

| Family | Use case | Examples |
|--------|----------|----------|
| **T** (burstable) | Dev, low-traffic web | t3.micro, t3.small |
| **M** (general) | Balanced workloads | m6i.large |
| **C** (compute) | CPU-intensive | c6i.xlarge |
| **R** (memory) | Databases, caches | r6i.large |
| **G/P** (GPU) | ML, graphics | g5.xlarge |
| **I** (storage) | High IOPS databases | i3.large |

Naming: `m6i.large` = family **m**, gen **6**, Intel **i**, size **large**.

### Purchasing options

| Option | Cost | Interruption |
|--------|------|--------------|
| On-Demand | Highest | Never |
| Reserved / Savings Plans | 30–70% less | Never |
| Spot | Up to 90% less | Can be terminated with 2-min notice |
| Dedicated Host | Compliance | Never |

---

## 15.3 AMIs and launch templates

**AMI (Amazon Machine Image)** — Template for root volume: OS + optional software.

Sources:

- AWS-provided (Amazon Linux 2023, Ubuntu)
- Marketplace
- Custom (built with EC2 Image Builder or Packer)

**Launch Template** — Reusable EC2 configuration (instance type, AMI, SG, user data, IAM role). Preferred over launch configurations.

```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.micro \
  --key-name my-key \
  --security-group-ids sg-xxx \
  --subnet-id subnet-xxx \
  --iam-instance-profile Name=EC2-S3-ReadRole \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=web-01}]'
```

---

## 15.4 User data — bootstrap scripts

Run commands on first boot:

```bash
#!/bin/bash
yum update -y
yum install -y nginx
systemctl enable nginx
systemctl start nginx
echo "<h1>Hello from $(hostname)</h1>" > /usr/share/nginx/html/index.html
```

Pass via console, CLI `--user-data`, or launch template. Logs: `/var/log/cloud-init-output.log`.

---

## 15.5 Auto Scaling Groups (ASG)

ASG maintains desired instance count and replaces unhealthy instances.

```hcl
resource "aws_autoscaling_group" "web" {
  name                = "web-asg"
  vpc_zone_identifier = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  target_group_arns   = [aws_lb_target_group.web.arn]
  health_check_type   = "ELB"
  min_size            = 2
  max_size            = 10
  desired_capacity    = 2

  launch_template {
    id      = aws_launch_template.web.id
    version = "$Latest"
  }
}
```

Pair with **ALB** for traffic distribution and **scaling policies** on CPU or request count.

---

## 15.6 EC2 best practices

- Use **IAM roles**, never embed access keys
- **Session Manager** instead of SSH where possible (no open port 22)
- **IMDSv2** required (`HttpTokens: required`) — prevents SSRF credential theft
- **Encrypted EBS** volumes by default
- **Patch** via SSM Patch Manager or golden AMI pipelines
- **Right-size** with CloudWatch metrics and Compute Optimizer

---

## 15.7 Chapter summary

- Choose instance **family and size** based on workload profile.
- Use **launch templates** and **user data** for repeatable deployments.
- **ASG + ALB** provides scalable, self-healing web tiers.

---

## 🧪 Lab 15.1

1. Launch Amazon Linux 2023 t3.micro with nginx user data.
2. Attach IAM role for S3 read.
3. Create launch template and ASG (min 1, max 2) behind an ALB.

---

*Next: [Chapter 20 — S3](../part-05-storage/chapter-20-s3-fundamentals.md)*
