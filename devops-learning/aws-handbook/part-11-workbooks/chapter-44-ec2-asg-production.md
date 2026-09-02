# Chapter 44: EC2 and Auto Scaling in Production

This workbook turns Chapters 15–16 into an operations playbook: launch templates that are actually immutable, Auto Scaling groups that survive AZ loss, load-balancer health that matches application health, and the IAM, networking, and observability details that separate a lab ASG from a production fleet. You will build a small service, break it on purpose, and watch the group replace instances without a human SSH session.

---

## 44.1 The production mental model

An EC2 Auto Scaling group (ASG) is a desired-state controller for instances. You declare a launch template (AMI, instance type, user data, IAM instance profile, block devices, metadata options) and a group (subnets, size, health checks, scaling policies). The control plane launches, attaches, detaches, and terminates. You do not “log in and patch the box” as the primary change process. You bake a new AMI or a new user-data contract, create a new launch template version, and roll.

| Piece | Owns | Common failure |
|-------|------|----------------|
| AMI | OS, agents, baked packages | Drift if you patch live |
| Launch template | Instance shape and metadata | IMDSv1 left on; public IP on private subnet |
| ASG | Count, AZ spread, replace unhealthies | Health check too tight or too loose |
| ELB | Traffic, TLS, target health | ASG EC2 health only; ELB 5xx ignored |
| Scaling policy | Capacity vs load | CPU-only on an I/O-bound app |
| Lifecycle hook | Drain, deregister, flush | Terminations cut in-flight work |

---

## 44.2 Launch templates that you can defend in a review

**IMDSv2 required.** Instance Metadata Service v1 is a SSRF magnet.

```bash
aws ec2 create-launch-template \
  --launch-template-name web-prod \
  --launch-template-data '{
    "ImageId": "ami-0abcdef1234567890",
    "InstanceType": "m7g.large",
    "IamInstanceProfile": {"Name": "web-prod-profile"},
    "MetadataOptions": {
      "HttpTokens": "required",
      "HttpPutResponseHopLimit": 1,
      "HttpEndpoint": "enabled"
    },
    "Monitoring": {"Enabled": true},
    "BlockDeviceMappings": [{
      "DeviceName": "/dev/xvda",
      "Ebs": {"VolumeSize": 30, "VolumeType": "gp3", "Encrypted": true, "DeleteOnTermination": true}
    }],
    "NetworkInterfaces": [{
      "DeviceIndex": 0,
      "AssociatePublicIpAddress": false,
      "Groups": ["sg-app"],
      "DeleteOnTermination": true
    }]
  }'
```

`HttpPutResponseHopLimit` of 1 blocks containers on the instance from reaching IMDS unless you deliberately raise it for ECS/EKS on EC2. For those platforms, follow the platform guidance rather than copying hop limit 1 blindly.

**Detailed monitoring** (`Monitoring.Enabled`) is one-minute CloudWatch metrics. Standard five-minute metrics make CPU scaling sluggish.

**Encrypted EBS by default** at the account level plus explicit `Encrypted: true` on the mapping. Unencrypted root volumes still appear in old templates.

**Burstable vs fixed.** `t3`/`t4g` are fine for spiky low-CPU admin tools. Production request-serving fleets usually want `m`/`c`/`r` families so you are not surprised by CPU credit exhaustion. Graviton (`m7g`, `c7g`) is often the cost and performance default in 2026; confirm your AMI architecture.

---

## 44.3 User data: keep it thin

User data should register the instance, pull a versioned artifact, and start a systemd unit. It should not compile software.

```bash
#!/bin/bash
set -euo pipefail
dnf install -y amazon-cloudwatch-agent
aws s3 cp s3://app-artifacts-prod/releases/${APP_VERSION}/web.rpm /tmp/web.rpm
rpm -Uvh /tmp/web.rpm
systemctl enable --now web.service
```

Bake the CloudWatch agent and SSM agent into the AMI with Image Builder or Packer. Every extra yum/dnf call at boot is a race against NAT, repo mirrors, and scale-out latency.

---

## 44.4 Auto Scaling group settings that matter

| Setting | Production default | Why |
|---------|-------------------|-----|
| Min / desired / max | min ≥ 2 (or 3 across AZs) | One instance is not HA |
| Subnets | All private app subnets in 3 AZs | Spread |
| Health check type | ELB when behind a load balancer | EC2 checks only see “the kernel is up” |
| Health check grace | Longer than boot + warmup | Prevents kill loops |
| Default instance warmup | Matches real ready time | Prevents premature scale-in |
| Capacity rebalance | On for Spot mixed policy | Proactive replacement |
| Termination policies | OldestLaunchTemplate, then Default | Prefer new template versions gone last? Actually: you usually want *oldest instance* or *oldest launch template* depending on rollout style — document it |
| New instances protected from scale-in | Off except during incidents | Forgotten protection is a stuck group |
| Max instance lifetime | Optional 7–14 days | Forces AMI refresh |

**ELB health versus application health.** The target group health check path must fail when the process cannot serve business traffic (database down, dependency timeout), not merely when nginx answers 200 on `/`. A `/healthz` that always returns 200 is how you serve errors at scale.

---

## 44.5 Scaling policies

**Target tracking** is the default. Example: ALBRequestCountPerTarget = 800, or ASGAverageCPUUtilization = 50.

**Step scaling** is for custom metrics with non-linear behavior.

**Predictive scaling** helps weekday traffic shapes if you have history.

**Scheduled scaling** handles known events (product launch at 09:00).

```bash
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name web-prod \
  --policy-name cpu-tt \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    },
    "TargetValue": 50.0
  }'
```

Do not attach five competing policies without understanding cooldown and warmup. Target tracking plus a poorly tuned step policy will fight.

**Scale-in protection during deploys.** Instance refresh with a warmup and a min healthy percentage is safer than terminating a random half of the fleet.

---

## 44.6 Mixed instances and Spot

A mixed-instances policy can combine On-Demand base capacity with Spot above the base.

```hcl
mixed_instances_policy {
  launch_template {
    launch_template_specification {
      launch_template_id = aws_launch_template.web.id
      version            = "$Latest"
    }
    override {
      instance_type = "m7g.large"
    }
    override {
      instance_type = "m6g.large"
    }
    override {
      instance_type = "c7g.large"
    }
  }
  instances_distribution {
    on_demand_base_capacity                  = 3
    on_demand_percentage_above_base_capacity = 0
    spot_allocation_strategy                 = "price-capacity-optimized"
  }
}
```

Spot is not “free HA.” Handle `EC2 Spot Instance Interruption Warning` via EventBridge, drain the target, and rely on Capacity Rebalancing. Stateless web tiers work. Sticky local disk does not.

---

## 44.7 Load balancer integration

- **ALB** for HTTP/S, host/path routing, OIDC, WAF.
- **NLB** for extreme performance, static IP, TLS offload optional, or non-HTTP.
- Register the ASG with the target group (`aws_autoscaling_attachment` or `target_group_arns` on the group).
- Enable **connection draining** (deregistration delay) so scale-in does not cut HTTP/2 streams.
- Stickiness is a compatibility crutch; prefer session stores in DynamoDB, ElastiCache, or JWT.

Health check recipe:

| Field | Example |
|-------|---------|
| Protocol / path | HTTPS `/ready` |
| Matcher | 200 |
| Interval | 15s |
| Timeout | 5s |
| Healthy threshold | 2 |
| Unhealthy threshold | 3 |

`/ready` checks dependency connectivity. `/live` checks process liveness only. Kubernetes taught this split; ASGs benefit too. Point the target group at `/ready`.

---

## 44.8 Terraform skeleton

```hcl
resource "aws_launch_template" "web" {
  name_prefix = "web-prod-"
  image_id    = var.ami
  instance_type = "m7g.large"

  iam_instance_profile { name = aws_iam_instance_profile.web.name }

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  monitoring { enabled = true }

  vpc_security_group_ids = [aws_security_group.app.id]

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    APP_VERSION = var.app_version
  }))
}

resource "aws_autoscaling_group" "web" {
  name                = "web-prod"
  min_size            = 3
  max_size            = 30
  desired_capacity    = 3
  vpc_zone_identifier = var.private_subnet_ids
  health_check_type   = "ELB"
  health_check_grace_period = 180
  target_group_arns   = [aws_lb_target_group.web.arn]

  launch_template {
    id      = aws_launch_template.web.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 90
      instance_warmup        = 180
    }
  }

  tag {
    key                 = "Name"
    value               = "web-prod"
    propagate_at_launch = true
  }
}
```

Pin `$Latest` only if your pipeline always creates a known-good template version. Many teams pin an explicit version number and promote it.

---

## 44.9 Observability and SSM instead of SSH

Required metrics: `GroupInServiceInstances`, `GroupTerminatingInstances`, ALB `TargetResponseTime`, `HTTPCode_Target_5XX_Count`, `UnHealthyHostCount`, per-instance CPU, disk, and your application saturation metric.

SSM Session Manager: no inbound 22. The instance profile needs `AmazonSSMManagedInstanceCore` plus least-privilege S3 if you write session logs.

```bash
aws ssm start-session --target i-0123456789abcdef0
```

Patching: AWS Systems Manager Patch Manager against a maintenance window, or (better) AMI pipeline + instance refresh. Mixing both without a policy produces snowflakes.

---

## 44.10 Warm pools, lifecycle hooks, and instance refresh

**Warm pools** pre-initialize instances for slow-booting JVMs. You pay for stopped or running warm instances; measure before adopting.

**Lifecycle hooks** on `autoscaling:EC2_INSTANCE_LAUNCHING` can fail a launch if a configuration management step fails. On `TERMINATING`, wait for the load balancer to drain and for workers to finish.

```bash
aws autoscaling complete-lifecycle-action \
  --lifecycle-hook-name drain \
  --auto-scaling-group-name web-prod \
  --lifecycle-action-result CONTINUE \
  --instance-id i-0123456789abcdef0
```

If you never call `complete-lifecycle-action`, the hook times out (default one hour) and the group stalls.

**Instance refresh** is the production rolling replace. Combine with an ALB and a high `min_healthy_percentage`.

---

## 44.11 Lab 1 — Healthy fleet behind an ALB

1. Create a VPC with public and private subnets (reuse Chapter 42).
2. Launch template: Amazon Linux, IMDSv2, encrypted gp3, SSM role, simple HTTP server on 8080 that serves `/ready` with 200.
3. ALB in public subnets, target group to 8080, ASG min=3 in private subnets.
4. Confirm three healthy targets. Stop the web process on one instance via SSM. Confirm ELB marks unhealthy and ASG replaces.
5. Change user data to break `/ready`. Deploy via new template version and instance refresh. Confirm the refresh rolls back or stalls according to your settings — then fix.

Cleanup NAT, ALB, and instances.

---

## 44.12 Lab 2 — Scaling policy behavior

1. Generate load with `hey` or `ab` against the ALB.
2. Watch `RequestCount` and CPU. Tune target tracking.
3. Set min=3, max=6. Observe max cap (latency rises). Raise max. Document the saturation metric you would use in production (p99 latency, queue depth, not only CPU).

---

## 44.13 Lab 3 — Spot interruption

1. Convert the group to mixed instances with Spot.
2. Simulate interruption with AWS Fault Injection Simulator or terminate a Spot instance.
3. Confirm Capacity Rebalance launched a replacement before or as traffic shifted.
4. Record how many 5xx the ALB showed. If the number is ugly, increase deregistration delay and hook the drain.

---

## 44.14 Failure modes

| Symptom | Likely cause |
|---------|----------------|
| Instances loop Launching → Terminating | User data fails; health check fails before grace; AMI missing SSM and you cannot debug |
| All instances in one AZ | Subnet list incomplete; AZ out of IPs |
| Scale-out but unhealthy | Security group does not allow ALB SG on app port |
| Slow scale-in | Deregistration delay, lifecycle hook timeout, scale-in protection |
| CPU credits exhausted | t-family in production |
| “It works in SSH” but ELB unhealthy | Health check hits the wrong port or HTTP vs HTTPS |

---

## 44.15 Production checklist

- Launch template: encrypted disks, IMDSv2, detailed monitoring, no public IP in private subnets.
- Instance profile: SSM, CloudWatch agent, least-privilege app permissions, no `*`.
- ASG: multi-AZ, ELB health, grace and warmup measured from real boot graphs.
- ALB/NLB: access logs to S3, WAF if public HTTP, ACM certificate, HTTP→HTTPS redirect.
- Change process: AMI or template version + instance refresh; documented rollback.
- Alarms: unhealthy hosts, 5xx, group size at max, failed instance launches.

---

## 44.16 Review questions

1. Why is EC2 status-check health insufficient for a web ASG behind an ALB?
2. What does `HttpTokens=required` enforce?
3. When would you raise IMDS hop limit above 1?
4. Why bake agents into the AMI instead of installing them in user data?
5. What is the risk of `$Latest` on a launch template in Terraform?
6. How does deregistration delay interact with ASG scale-in?
7. Why is CPU a poor sole scaling metric for a queue worker?
8. What does `price-capacity-optimized` try to optimize for Spot?
9. How do lifecycle hooks fail closed if your complete-lifecycle Lambda is down?
10. Why is min=1 an availability defect even with an ALB?

**Answers (brief):** (1) The instance can be up while the app is down. (2) IMDSv2 session token required. (3) Nested virtualization/containers that hop through a bridge (ECS/EKS guidance). (4) Faster, more reliable boots; fewer external dependencies. (5) Unintended template versions roll out. (6) Instance stays in-service until delay expires; slow scale-in, fewer dropped connections. (7) CPU may be idle while the queue grows. (8) Fewer interruptions and better capacity, not only cheapest price. (9) Hook waits then abandons per timeout — launches/terminations stall or proceed incorrectly. (10) One instance or one AZ is a single point of failure.

---

## 44.17 AMI pipelines and golden images

Production ASGs should consume AMIs from a pipeline (EC2 Image Builder or Packer in CodeBuild). The pipeline:

1. Starts from a current Amazon Linux or Bottlerocket base.
2. Applies CIS-ish hardening, agents (SSM, CloudWatch, Inspector), and your baseline packages.
3. Runs tests (boots in a private subnet, SSM ping, `/ready` if you bake the app — or don’t bake the app if you want a thinner image).
4. Shares the AMI to prod accounts via RAM or `modify-image-attribute`.
5. Updates a Parameter Store parameter `/prod/web/ami` that Terraform reads.

```bash
aws ssm get-parameter --name /prod/web/ami --query 'Parameter.Value' --output text
aws ec2 describe-images --image-ids ami-0abcdef1234567890 --query 'Images[0].{Name:Name,Created:CreationDate,Arch:Architecture}'
```

Bottlerocket reduces SSH surface and mutable packages; it changes how you debug (API, not yum). Choose deliberately.

**Nitro Enclaves** and **dedicated hosts** are out of scope for most fleets. **Hibernation** is a niche. **Capacity Reservations** matter when you cannot miss a scale-out in a constrained family.

---

## 44.18 What to do next

If your fleet is becoming a container platform, take the same ideas (health, rollouts, instance profiles) into ECS or EKS. Chapter 45 covers Lambda event patterns for the work you should *not* run on a standing ASG: sporadic, event-driven, or spiky to zero.
