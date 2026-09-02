# Chapter 33: CodePipeline, CodeBuild, and CodeDeploy

*AWS Handbook — Pages 167–172 of this PDF edition*
---

## 33.1 CI/CD on AWS

Continuous Integration and Continuous Delivery automate the path from code commit to production deployment. AWS provides a native CI/CD suite:

| Service | Role |
|---------|------|
| **CodeCommit** | Git repository (being deprecated; use GitHub/GitLab) |
| **CodeBuild** | Build and test code |
| **CodeDeploy** | Deploy to EC2, ECS, Lambda, on-premises |
| **CodePipeline** | Orchestrate the full pipeline |
| **CodeArtifact** | Package repository (npm, Maven, PyPI) |

---

## 33.2 CodePipeline

**CodePipeline** orchestrates stages from source to deployment:

```
Source → Build → Test → Deploy (Staging) → Approval → Deploy (Production)
```

### Pipeline stages

| Stage | Actions |
|-------|---------|
| **Source** | GitHub, CodeCommit, S3, ECR |
| **Build** | CodeBuild, Jenkins, custom |
| **Test** | CodeBuild, third-party |
| **Deploy** | CodeDeploy, CloudFormation, ECS, Lambda, S3 |
| **Approval** | Manual approval gate |

### Terraform pipeline

```hcl
resource "aws_codepipeline" "app" {
  name     = "app-pipeline"
  role_arn = aws_iam_role.pipeline.arn

  artifact_store {
    location = aws_s3_bucket.artifacts.bucket
    type     = "S3"
  }

  stage {
    name = "Source"
    action {
      name             = "GitHub"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]
      configuration = {
        ConnectionArn    = aws_codestarconnections_connection.github.arn
        FullRepositoryId = "org/app-repo"
        BranchName       = "main"
      }
    }
  }

  stage {
    name = "Build"
    action {
      name             = "Build"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["build_output"]
      configuration = {
        ProjectName = aws_codebuild_project.app.name
      }
    }
  }

  stage {
    name = "Deploy"
    action {
      name            = "DeployECS"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "ECS"
      version         = "1"
      input_artifacts = ["build_output"]
      configuration = {
        ClusterName = aws_ecs_cluster.main.name
        ServiceName = aws_ecs_service.web.name
        FileName    = "imagedefinitions.json"
      }
    }
  }
}
```

---

## 33.3 CodeBuild

**CodeBuild** compiles source code, runs tests, and produces deployment artifacts:

### buildspec.yml

```yaml
version: 0.2

env:
  variables:
    NODE_ENV: production
  parameter-store:
    DB_PASSWORD: /app/db-password
  secrets-manager:
    API_KEY: app/api-key

phases:
  install:
    runtime-versions:
      nodejs: 20
    commands:
      - npm ci

  pre_build:
    commands:
      - npm run lint
      - npm run test:unit

  build:
    commands:
      - npm run build
      - docker build -t $IMAGE_REPO_NAME:$IMAGE_TAG .

  post_build:
    commands:
      - aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI
      - docker push $IMAGE_REPO_NAME:$IMAGE_TAG
      - printf '[{"name":"web","imageUri":"%s"}]' $IMAGE_REPO_NAME:$IMAGE_TAG > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
    - dist/**/*
  discard-paths: no

cache:
  paths:
    - node_modules/**/*
    - .npm/**/*
```

### CodeBuild features

| Feature | Purpose |
|---------|---------|
| **Custom images** | Docker-based build environments |
| **VPC support** | Access private resources during build |
| **Caching** | S3 or local cache for dependencies |
| **Reports** | Test and coverage reports |
| **Batch builds** | Matrix builds across configurations |
| **Arm builds** | Graviton-based build environments |

```hcl
resource "aws_codebuild_project" "app" {
  name          = "app-build"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = 15

  artifacts { type = "CODEPIPELINE" }
  source {
    type      = "CODEPIPELINE"
    buildspec = "buildspec.yml"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_MEDIUM"
    image                       = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = true  # required for Docker builds
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "ECR_URI"
      value = aws_ecr_repository.app.repository_url
    }
  }

  cache {
    type     = "S3"
    location = "${aws_s3_bucket.cache.bucket}/codebuild-cache"
  }
}
```

---

## 33.4 CodeDeploy

**CodeDeploy** automates application deployments to various compute platforms:

| Target | Deployment type |
|--------|-----------------|
| **EC2 / On-premises** | In-place or blue/green |
| **ECS** | Blue/green with ALB traffic shifting |
| **Lambda** | Canary or linear traffic shifting |

### ECS blue/green deployment

```
ALB Target Group A (blue)  ← current production
ALB Target Group B (green) ← new version

1. Deploy new task definition to green target group
2. Shift traffic: 10% → 50% → 100% to green
3. Monitor CloudWatch alarms
4. Auto-rollback if alarms trigger
5. Terminate blue tasks
```

### appspec.yml (ECS)

```yaml
version: 0.0
Resources:
  - TargetService:
      Type: AWS::ECS::Service
      Properties:
        TaskDefinition: arn:aws:ecs:us-east-1:123456789012:task-definition/web:5
        LoadBalancerInfo:
          ContainerName: web
          ContainerPort: 8080
        PlatformVersion: LATEST
        NetworkConfiguration:
          AwsvpcConfiguration:
            Subnets: [subnet-aaa, subnet-bbb]
            SecurityGroups: [sg-ecs]
            AssignPublicIp: DISABLED
```

### Lambda canary deployment

```yaml
version: 0.0
Resources:
  - MyFunction:
      Type: AWS::Lambda::Function
      Properties:
        Name: api-handler
        Alias: live
        CurrentVersion: "3"
        TargetVersion: "4"
```

Traffic shifting: 10% every 5 minutes to the new version, with automatic rollback on alarm.

---

## 33.5 Deployment strategies comparison

| Strategy | Downtime | Rollback speed | Complexity |
|----------|----------|----------------|------------|
| **In-place** | Brief (rolling) | Slow (redeploy) | Low |
| **Blue/green** | None | Fast (switch ALB) | Medium |
| **Canary** | None | Fast (shift back) | Medium |
| **Linear** | None | Fast | Medium |
| **Rolling (ECS)** | None | Moderate | Low |

---

## 33.6 GitHub Actions alternative

Many teams use GitHub Actions with OIDC federation instead of CodePipeline:

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
          aws-region: us-east-1
      - run: npm ci && npm test && npm run build
      - run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI
          docker build -t $ECR_URI:$GITHUB_SHA .
          docker push $ECR_URI:$GITHUB_SHA
          aws ecs update-service --cluster app --service web --force-new-deployment
```

---

## 33.7 Security best practices

| Practice | Implementation |
|----------|----------------|
| Least-privilege IAM roles | Separate roles for pipeline, build, deploy |
| Encrypted artifacts | S3 SSE-KMS on artifact bucket |
| No long-term credentials | OIDC federation for GitHub/GitLab |
| Secrets in Parameter Store/Secrets Manager | Never in buildspec or code |
| VPC for builds accessing private resources | CodeBuild VPC configuration |
| Manual approval for production | CodePipeline approval stage |

---

## 33.8 Chapter summary

- **CodePipeline** orchestrates CI/CD from source to deployment.
- **CodeBuild** compiles, tests, and packages applications with `buildspec.yml`.
- **CodeDeploy** automates deployments to EC2, ECS, and Lambda with blue/green and canary strategies.
- Use **OIDC federation** instead of long-term credentials for external Git providers.
- Choose deployment strategy based on downtime tolerance and rollback requirements.

---

## 🧪 Lab 33.1 — CodePipeline for ECS

1. Create a CodeBuild project with a Docker buildspec.
2. Create a CodePipeline: GitHub source → CodeBuild → ECS deploy.
3. Push a code change and watch the pipeline execute.
4. Verify the new container version is running in ECS.

## 🧪 Lab 33.2 — Blue/green ECS deployment

1. Configure CodeDeploy for ECS blue/green with ALB.
2. Deploy a new task definition version.
3. Observe traffic shifting from blue to green target group.
4. Trigger a CloudWatch alarm and verify automatic rollback.

---

## Review questions

1. What is the role of each service in the CodePipeline → CodeBuild → CodeDeploy flow?
2. What is the purpose of `buildspec.yml`?
3. How does ECS blue/green deployment minimize downtime?
4. Why should CI/CD use OIDC instead of access keys?
5. What deployment strategy provides the fastest rollback?

---

*Next: [Chapter 34 — Systems Manager & Parameter Store](./chapter-34-systems-manager.md)*
