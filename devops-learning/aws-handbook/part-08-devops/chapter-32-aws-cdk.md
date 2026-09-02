# Chapter 32: AWS CDK

*AWS Handbook — Pages 161–165 of this PDF edition*
---

## 32.1 What is the AWS CDK?

The **AWS Cloud Development Kit (CDK)** lets you define cloud infrastructure using familiar programming languages (TypeScript, Python, Java, C#, Go). CDK synthesizes your code into CloudFormation templates, combining the expressiveness of a general-purpose language with CloudFormation's deployment engine.

CDK is ideal for teams that find YAML/JSON templates limiting and want reusable constructs, unit tests, and IDE support.

---

## 32.2 CDK concepts

| Concept | Description |
|---------|-------------|
| **App** | Root of the CDK application |
| **Stack** | Unit of deployment (maps to CloudFormation stack) |
| **Construct** | Reusable component (L1, L2, L3) |
| **Synthesis** | Generate CloudFormation template from code |
| **Deployment** | `cdk deploy` creates/updates CloudFormation stack |

### Construct levels

| Level | Description | Example |
|-------|-------------|---------|
| **L1 (Cfn)** | Direct CloudFormation resource | `CfnBucket` |
| **L2** | Curated construct with sensible defaults | `s3.Bucket` |
| **L3** | Opinionated patterns combining multiple resources | `ApplicationLoadBalancedFargateService` |

---

## 32.3 Getting started (TypeScript)

```bash
npm install -g aws-cdk
cdk init app --language typescript
npm install @aws-cdk/aws-lambda @aws-cdk/aws-apigatewayv2-integrations
```

### Basic stack

```typescript
import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";

export class AppStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const bucket = new s3.Bucket(this, "DataBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const fn = new lambda.Function(this, "ApiHandler", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "app.handler",
      code: lambda.Code.fromAsset("lambda"),
      environment: { BUCKET_NAME: bucket.bucketName },
    });

    bucket.grantReadWrite(fn);

    const api = new apigwv2.HttpApi(this, "Api", {
      defaultIntegration: new integrations.HttpLambdaIntegration(
        "LambdaIntegration", fn
      ),
    });

    new cdk.CfnOutput(this, "ApiUrl", { value: api.url! });
  }
}

const app = new cdk.App();
new AppStack(app, "AppStack", { env: { account: "123456789012", region: "us-east-1" } });
```

### Python equivalent

```python
from aws_cdk import (
    App, Stack, CfnOutput, RemovalPolicy,
    aws_s3 as s3,
    aws_lambda as lambda_,
)
from constructs import Construct

class AppStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        bucket = s3.Bucket(
            self, "DataBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        fn = lambda_.Function(
            self, "Processor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.handler",
            code=lambda_.Code.from_asset("lambda"),
            environment={"BUCKET_NAME": bucket.bucket_name},
        )
        bucket.grant_read_write(fn)

app = App()
AppStack(app, "AppStack")
app.synth()
```

---

## 32.4 CDK workflow

```bash
cdk synth          # Generate CloudFormation template
cdk diff           # Compare deployed stack with current code
cdk deploy         # Deploy stack(s)
cdk destroy        # Delete stack(s)
cdk ls             # List stacks in the app
cdk bootstrap      # Prepare account/region (one-time)
```

### Bootstrapping

CDK requires an S3 bucket and ECR repo for assets (Lambda code, Docker images):

```bash
cdk bootstrap aws://123456789012/us-east-1
```

---

## 32.5 Reusable constructs

### Creating a construct

```typescript
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";

interface DatabaseProps {
  vpc: ec2.IVpc;
  instanceType: ec2.InstanceType;
}

export class Database extends Construct {
  public readonly endpoint: string;

  constructor(scope: Construct, id: string, props: DatabaseProps) {
    super(scope, id);

    const cluster = new rds.DatabaseCluster(this, "Cluster", {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_15_4,
      }),
      vpc: props.vpc,
      writer: rds.ClusterInstance.provisioned("Writer", {
        instanceType: props.instanceType,
      }),
      readers: [
        rds.ClusterInstance.provisioned("Reader", {
          instanceType: props.instanceType,
        }),
      ],
      storageEncrypted: true,
    });

    this.endpoint = cluster.clusterEndpoint.hostname;
  }
}
```

### Using the construct

```typescript
const db = new Database(this, "AppDatabase", {
  vpc,
  instanceType: ec2.InstanceType.of(ec2.InstanceClass.R6G, ec2.InstanceSize.LARGE),
});
```

---

## 32.6 CDK Pipelines

**CDK Pipelines** is a high-level construct for CI/CD:

```typescript
import { pipelines } from "aws-cdk-lib";

const pipeline = new pipelines.CodePipeline(this, "Pipeline", {
  pipelineName: "AppPipeline",
  synth: new pipelines.ShellStep("Synth", {
    input: pipelines.CodePipelineSource.gitHub("org/repo", "main"),
    commands: ["npm ci", "npm run build", "npx cdk synth"],
  }),
});

pipeline.addStage(new AppStage(this, "Prod", { env: prodEnv }));
```

Stages deploy to different environments with automatic approvals between them.

---

## 32.7 Testing CDK

### Snapshot tests

```typescript
import { Template } from "aws-cdk-lib/assertions";

test("S3 bucket is encrypted", () => {
  const stack = new AppStack(app, "TestStack");
  const template = Template.fromStack(stack);

  template.hasResourceProperties("AWS::S3::Bucket", {
    BucketEncryption: {
      ServerSideEncryptionConfiguration: [{
        ServerSideEncryptionByDefault: { SSEAlgorithm: "AES256" },
      }],
    },
  });
});
```

### Fine-grained assertions

```typescript
template.resourceCountIs("AWS::S3::Bucket", 1);
template.hasResource("AWS::IAM::Role", {
  Properties: { AssumeRolePolicyDocument: { /* ... */ } },
});
```

---

## 32.8 CDK vs CloudFormation vs Terraform

| Feature | CDK | CloudFormation | Terraform |
|---------|-----|----------------|-----------|
| Language | TypeScript, Python, etc. | YAML/JSON | HCL |
| AWS integration | Deepest | Native | Via provider |
| Multi-cloud | No | No | Yes |
| State management | CloudFormation | CloudFormation | Remote state |
| Constructs/libraries | Rich ecosystem | Modules (limited) | Modules (extensive) |
| Learning curve | Moderate | Low | Moderate |

---

## 32.9 Best practices

| Practice | Rationale |
|----------|-----------|
| Use L2 constructs over L1 | Sensible defaults, less boilerplate |
| Create reusable L3 constructs | Consistency across teams |
| Use `cdk diff` before deploy | Preview changes |
| Set `removalPolicy` explicitly | Prevent accidental data loss |
| Use aspects for cross-cutting concerns | Tagging, encryption, compliance |
| Write snapshot tests | Catch unintended infrastructure changes |
| Pin CDK version | Reproducible builds |
| Use environments for multi-account | `env: { account, region }` |

---

## 32.10 Chapter summary

- **CDK** defines infrastructure in TypeScript, Python, or other languages; synthesizes to CloudFormation.
- **Constructs** (L1/L2/L3) provide reusable building blocks.
- **CDK Pipelines** enables CI/CD for infrastructure deployments.
- Test with **snapshot assertions** and fine-grained resource checks.
- Bootstrap accounts once; use `cdk diff` and `cdk deploy` for safe updates.

---

## 🧪 Lab 32.1 — CDK web application

1. Initialize a CDK TypeScript project.
2. Create a stack with S3, Lambda, and HTTP API.
3. Run `cdk synth` and inspect the generated CloudFormation template.
4. Deploy with `cdk deploy` and test the API endpoint.

## 🧪 Lab 32.2 — Reusable construct

1. Create a `VpcStack` construct with public/private subnets.
2. Create an `AppStack` that imports the VPC and deploys ECS Fargate.
3. Write a snapshot test verifying the VPC has 2 AZs and 4 subnets.

---

## Review questions

1. What is the relationship between CDK and CloudFormation?
2. What is the difference between L1, L2, and L3 constructs?
3. Why is `cdk bootstrap` required before the first deployment?
4. How do CDK snapshot tests help prevent infrastructure regressions?
5. When would you choose CDK over raw CloudFormation templates?

---

*Next: [Chapter 33 — CodePipeline, CodeBuild, CodeDeploy](./chapter-33-codepipeline.md)*
