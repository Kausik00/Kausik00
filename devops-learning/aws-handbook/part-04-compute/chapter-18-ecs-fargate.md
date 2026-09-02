# Chapter 18: ECS & Fargate

*AWS Handbook — Pages 82–86 of this PDF edition*
---

## 18.1 Container orchestration on AWS

**Amazon Elastic Container Service (ECS)** is AWS's native container orchestration platform. It schedules, deploys, and manages Docker containers across a cluster of EC2 instances or serverlessly via **AWS Fargate**. ECS integrates deeply with AWS networking, IAM, load balancing, and monitoring.

For teams that want AWS-native container management without the complexity of Kubernetes, ECS (especially with Fargate) is the recommended choice.

---

## 18.2 ECS architecture

```
┌─────────────────────────────────────────────────┐
│  ECS Cluster                                     │
│  ┌─────────────┐  ┌─────────────┐              │
│  │  Service A   │  │  Service B   │              │
│  │  (3 tasks)   │  │  (2 tasks)   │              │
│  └──────┬──────┘  └──────┬──────┘              │
│         │                 │                      │
│  ┌──────▼─────────────────▼──────┐              │
│  │  Task Definitions              │              │
│  │  (container images, CPU, mem)  │              │
│  └───────────────────────────────┘              │
│                                                   │
│  Capacity: EC2 instances OR Fargate (serverless) │
└─────────────────────────────────────────────────┘
```

### Key components

| Component | Description |
|-----------|-------------|
| **Cluster** | Logical grouping of tasks/services |
| **Task definition** | Blueprint: image, CPU, memory, ports, env vars, IAM role |
| **Task** | Running instance of a task definition (1+ containers) |
| **Service** | Maintains desired count of tasks; integrates with ALB |
| **Container instance** | EC2 host running the ECS agent (EC2 launch type only) |

---

## 18.3 EC2 vs Fargate launch types

| Feature | EC2 Launch Type | Fargate Launch Type |
|---------|-----------------|---------------------|
| **Infrastructure** | You manage EC2 instances | AWS manages infrastructure |
| **Pricing** | EC2 instance hours | Per vCPU/memory per task hour |
| **Scaling** | ASG for instances + service scaling | Service scaling only |
| **Control** | Host access, GPU, custom AMIs | No host access |
| **Best for** | Cost optimization, GPU, daemon tasks | Simplicity, variable workloads |

**Recommendation:** Start with Fargate. Move to EC2 if you need GPU, persistent host storage, or significant cost optimization at scale.

---

## 18.4 Task definitions

A **task definition** is a JSON blueprint specifying how containers run:

```json
{
  "family": "web-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/webAppTaskRole",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/web-app:latest",
      "portMappings": [
        { "containerPort": 8080, "protocol": "tcp" }
      ],
      "environment": [
        { "name": "ENV", "value": "production" }
      ],
      "secrets": [
        { "name": "DB_PASSWORD", "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:db-pass" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/web-app",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "web"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### IAM roles

| Role | Purpose |
|------|---------|
| **Task execution role** | Pull images from ECR, write logs, fetch secrets |
| **Task role** | Permissions for the application (S3, DynamoDB, etc.) |

---

## 18.5 ECS services and load balancing

An **ECS service** maintains a desired number of running tasks and optionally registers them with a load balancer.

### Terraform ECS Fargate service

```hcl
resource "aws_ecs_service" "web" {
  name            = "web-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 8080
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  depends_on = [aws_lb_listener.https]
}
```

### Deployment types

| Type | Description |
|------|-------------|
| **Rolling update** | Replace tasks incrementally (default) |
| **Blue/green** | Via CodeDeploy; shift traffic between target groups |
| **Canary** | Via CodeDeploy; gradual traffic shift |

---

## 18.6 Auto Scaling ECS services

Scale tasks based on CloudWatch metrics:

```hcl
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

---

## 18.7 Amazon ECR

**Elastic Container Registry (ECR)** stores Docker images:

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t web-app .
docker tag web-app:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/web-app:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/web-app:latest
```

### ECR features

| Feature | Purpose |
|---------|---------|
| **Image scanning** | Vulnerability scanning on push |
| **Lifecycle policies** | Auto-delete old images |
| **Cross-account/region replication** | DR and multi-account |
| **Pull-through cache** | Cache upstream registries (Docker Hub, etc.) |

---

## 18.8 Networking modes

| Mode | Use case |
|------|----------|
| **awsvpc** | Required for Fargate; each task gets its own ENI and IP |
| **bridge** | EC2 only; Docker bridge networking (legacy) |
| **host** | EC2 only; task uses host network directly |

**Fargate requires `awsvpc`** — plan IP address capacity in subnets (each task consumes one IP).

---

## 18.9 Service Connect and Service Discovery

| Feature | Purpose |
|---------|-------------|
| **Cloud Map service discovery** | DNS-based discovery (`api.local`) |
| **ECS Service Connect** | Built-in service mesh; observability, retries, traffic splitting |

Service Connect simplifies inter-service communication without managing a full service mesh.

---

## 18.10 ECS Exec

**ECS Exec** provides interactive shell access to running containers (like `kubectl exec`):

```bash
aws ecs execute-command \
  --cluster my-cluster \
  --task abc123 \
  --container web \
  --interactive \
  --command "/bin/bash"
```

Requires SSM permissions on the task role and `enableExecuteCommand` on the service.

---

## 18.11 Chapter summary

- **ECS** orchestrates containers on EC2 or **Fargate** (serverless).
- **Task definitions** define container images, resources, and IAM roles.
- **Services** maintain desired task count and integrate with ALB.
- **ECR** stores container images with scanning and lifecycle policies.
- Use **awsvpc** networking, **auto scaling**, and **ECS Exec** for production operations.

---

## 🧪 Lab 18.1 — Fargate web service

1. Create an ECR repository and push a simple web container.
2. Create an ECS cluster, task definition, and Fargate service (2 tasks).
3. Attach an ALB and verify HTTP access.
4. Scale to 4 tasks and observe load distribution.

## 🧪 Lab 18.2 — ECS Exec debugging

1. Enable ECS Exec on your service.
2. Connect to a running container and inspect logs, env vars, and network.
3. Use ECS Exec to troubleshoot a misconfigured environment variable.

---

## Review questions

1. What is the difference between a task definition and a task?
2. When would you choose EC2 launch type over Fargate?
3. What are the two IAM roles in an ECS task definition?
4. Why does Fargate require awsvpc networking mode?
5. How does ECS service auto scaling differ from EC2 Auto Scaling?

---

*Next: [Chapter 19 — EKS](./chapter-19-eks.md)*
