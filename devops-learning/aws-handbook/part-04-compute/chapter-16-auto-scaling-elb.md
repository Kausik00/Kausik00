# Chapter 16: Auto Scaling & Elastic Load Balancing Integration

*AWS Handbook — Part IV, Pages 306–325*

---

## 16.1 Why Auto Scaling?

Manual capacity management cannot keep pace with variable demand. **Amazon EC2 Auto Scaling** automatically adjusts the number of EC2 instances (or other resources) based on conditions you define. Combined with **Elastic Load Balancing**, you get a self-healing, elastic application tier that scales out during traffic spikes and scales in during quiet periods—optimizing both performance and cost.

---

## 16.2 Auto Scaling components

| Component | Description |
|-----------|-------------|
| **Launch template / configuration** | AMI, instance type, security groups, user data |
| **Auto Scaling group (ASG)** | Collection of EC2 instances with min, max, desired capacity |
| **Scaling policies** | Rules that trigger scale-out or scale-in |
| **Health checks** | EC2 status checks and/or ELB health checks |
| **Lifecycle hooks** | Custom actions during instance launch/terminate |

### ASG capacity settings

| Setting | Meaning |
|---------|---------|
| **Minimum** | Floor; ASG never goes below this |
| **Desired** | Target number of instances |
| **Maximum** | Ceiling; ASG never exceeds this |

---

## 16.3 Launch templates vs launch configurations

**Launch templates** are the modern approach (launch configurations are legacy):

| Feature | Launch Template | Launch Configuration |
|---------|-----------------|---------------------|
| Multiple versions | Yes | No |
| Mix instance types (Spot + On-Demand) | Yes | No |
| Latest features | Yes | Deprecated |
| Modify without replacement | Yes | No |

### Launch template example (Terraform)

```hcl
resource "aws_launch_template" "web" {
  name_prefix   = "web-"
  image_id      = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"

  vpc_security_group_ids = [aws_security_group.web.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    yum install -y httpd
    systemctl start httpd
    echo "<h1>$(hostname)</h1>" > /var/www/html/index.html
    EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = { Name = "web-asg-instance" }
  }
}
```

---

## 16.4 Auto Scaling group with ALB

```
Internet → ALB → Target Group ← ASG registers instances
                      ↑
              Health checks (HTTP /health)
```

### Terraform ASG + ALB integration

```hcl
resource "aws_autoscaling_group" "web" {
  name                = "web-asg"
  vpc_zone_identifier = aws_subnet.private[*].id
  target_group_arns   = [aws_lb_target_group.web.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = 2
  max_size         = 10
  desired_capacity = 2

  launch_template {
    id      = aws_launch_template.web.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "web-asg"
    propagate_at_launch = true
  }
}
```

**Critical settings:**

- `health_check_type = "ELB"` — ASG replaces instances that fail ALB health checks, not just EC2 status checks.
- `health_check_grace_period` — Time (seconds) before health checks count after launch. Allow your app to start.

---

## 16.5 Scaling policies

### Target tracking (recommended)

Maintain a metric at a target value. AWS automatically creates scale-out and scale-in policies.

| Metric | Use case |
|--------|----------|
| `ASGAverageCPUUtilization` | General compute workloads |
| `ALBRequestCountPerTarget` | Request-driven scaling |
| Custom CloudWatch metric | Application-specific (queue depth, latency) |

```hcl
resource "aws_autoscaling_policy" "cpu_target" {
  name                   = "cpu-target-tracking"
  autoscaling_group_name = aws_autoscaling_group.web.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60.0
  }
}
```

### Step scaling

Scale by steps based on alarm breach magnitude:

| CPU utilization | Action |
|-----------------|--------|
| 50–70% | Add 1 instance |
| 70–90% | Add 2 instances |
| > 90% | Add 4 instances |

### Simple scaling

Single adjustment per alarm. Less flexible; prefer target tracking or step scaling.

### Scheduled scaling

Pre-define capacity for known patterns:

```bash
aws autoscaling put-scheduled-update-group-action \
  --auto-scaling-group-name web-asg \
  --scheduled-action-name scale-up-morning \
  --recurrence "0 8 * * MON-FRI" \
  --desired-capacity 10 \
  --time-zone "America/New_York"
```

### Predictive scaling

Machine learning predicts traffic patterns and proactively scales. Works alongside dynamic policies.

---

## 16.6 Instance refresh

**Instance refresh** replaces instances in an ASG with new ones (e.g., after AMI update) without manual intervention.

| Setting | Description |
|---------|-------------|
| **Min healthy percentage** | Minimum healthy instances during refresh (e.g., 90%) |
| **Instance warmup** | Time before new instances count toward capacity |
| **Checkpoint** | Pause refresh at percentage milestones |

```bash
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name web-asg \
  --preferences '{
    "MinHealthyPercentage": 90,
    "InstanceWarmup": 300,
    "CheckpointPercentages": [50, 100]
  }'
```

---

## 16.7 Lifecycle hooks

Lifecycle hooks pause instance launch or termination for custom actions:

| Hook | Use case |
|------|----------|
| **Launching** | Install software, pull config, register with service mesh |
| **Terminating** | Drain connections, deregister from service discovery |

```
Instance launching → Hook (wait) → Custom action (Lambda/SSM) → Continue → InService
Instance terminating → Hook (wait) → Drain logs, deregister → Continue → Terminated
```

Default heartbeat timeout: 3600 seconds (1 hour). Extend or complete via `complete-lifecycle-action`.

---

## 16.8 Mixed instances and Spot

ASGs support **mixed instance policies** combining On-Demand and Spot:

```hcl
resource "aws_autoscaling_group" "mixed" {
  mixed_instances_policy {
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.web.id
        version            = "$Latest"
      }
      override { instance_type = "t3.micro" }
      override { instance_type = "t3.small" }
    }
    instances_distribution {
      on_demand_base_capacity                  = 2
      on_demand_percentage_above_base_capacity = 25
      spot_allocation_strategy                 = "capacity-optimized"
    }
  }
}
```

This keeps 2 On-Demand instances as baseline, with 25% On-Demand above that and the rest Spot.

---

## 16.9 Warm pools

**Warm pools** pre-initialize instances in `Stopped` or `Running:Wait` state for faster scale-out:

- Instances in `Stopped` state incur EBS charges but no compute charges.
- Instances in `Running:Wait` incur compute charges but scale out in seconds.

---

## 16.10 Monitoring and troubleshooting

| Metric | Alarm threshold idea |
|--------|---------------------|
| `GroupDesiredCapacity` | Track scaling events |
| `GroupInServiceInstances` | Should match desired |
| `GroupTerminatingInstances` | Spike during scale-in |
| `WarmPoolDesiredCapacity` | Warm pool sizing |

```bash
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names web-asg

aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name web-asg \
  --max-records 10
```

### Common issues

| Symptom | Cause |
|---------|-------|
| Instances launch then terminate | Failing health checks; check grace period |
| ASG won't scale out | Max capacity reached; scaling policy cooldown |
| Uneven AZ distribution | Check `AZRebalance` and subnet configuration |
| Spot interruptions | Use capacity-optimized allocation; diversify instance types |

---

## 16.11 Chapter summary

- **Auto Scaling groups** maintain desired capacity with min/max bounds.
- Integrate with **ALB** using `health_check_type = "ELB"` and target group registration.
- **Target tracking** scaling policies are the simplest and most effective for most workloads.
- **Instance refresh** enables rolling AMI updates without downtime.
- **Mixed instances** and **warm pools** optimize cost and scale-out speed.

---

## 🧪 Lab 16.1 — ASG with ALB

1. Create a launch template with a simple web server and `/health` endpoint.
2. Create an ASG (min 2, max 6) in private subnets attached to an ALB target group.
3. Add a target tracking policy on `ASGAverageCPUUtilization` at 50%.
4. Generate load with `ab` or `hey` and watch instances scale out.
5. Stop load and observe scale-in after cooldown.

## 🧪 Lab 16.2 — Instance refresh

1. Update the launch template AMI or user data.
2. Start an instance refresh with 50% checkpoint.
3. Monitor `describe-scaling-activities` until complete.
4. Verify all instances serve the updated content.

---

## Review questions

1. What is the difference between `health_check_type = "EC2"` and `"ELB"`?
2. Why is a health check grace period important?
3. How does target tracking scaling differ from step scaling?
4. What is the purpose of lifecycle hooks?
5. How do warm pools improve scale-out speed?

---

*Next: [Chapter 17 — Lambda](./chapter-17-lambda.md)*
