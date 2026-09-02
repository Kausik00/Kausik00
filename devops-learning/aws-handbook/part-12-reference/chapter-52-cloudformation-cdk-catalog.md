# Chapter 52: CloudFormation and CDK Catalog

This reference chapter is a working catalog of CloudFormation and AWS CDK patterns you can copy into pipelines, Service Catalog products, and platform modules. Chapters 31 and 32 covered syntax and first stacks. Here the goal is operational: reusable templates, nested and nested-of-nested composition, change-set discipline, CDK construct libraries, and a governed catalog that application teams consume without reinventing IAM, networking, or logging.

Treat every snippet as a starting point, not a one-click production deploy. Substitute account IDs, CIDRs, and KMS aliases for your landing zone. Run the labs in a sandbox account with billing alerts enabled.

---

## 52.1 Why a catalog exists

Without a catalog, every team writes a slightly different VPC, a slightly different ECS task role, and a slightly different log retention policy. Drift accumulates. Security reviews become archaeology. A **platform catalog** solves three problems at once:

| Problem | Catalog response |
|---------|------------------|
| Inconsistent IAM | Golden roles and permission boundaries as products |
| Slow security review | Pre-approved constructs with Guard/cfn-nag in CI |
| Stack sprawl | Nested stacks and CDK apps with shared versioning |
| Knowledge silos | Documented products with parameters, not tribal YAML |
| Upgrade risk | Semantic versions and change-set previews |

The catalog is not a dump of every AWS resource type. It is a **small set of opinionated products**: network baseline, compute runtime, data store, observability sidecar, and identity glue. Application stacks compose those products.

---

## 52.2 CloudFormation template catalog — core layout

Store templates in a dedicated repository. A layout that scales to dozens of products:

```
cfn-catalog/
  products/
    vpc-baseline/
      template.yaml
      product.yaml          # Service Catalog metadata
      tests/cfn-lint.yaml
    ecs-service/
      template.yaml
    rds-postgres/
      template.yaml
  nested/
    kms-key.yaml
    cloudwatch-alarms.yaml
  pipelines/
    deploy-catalog.yaml
  policies/
    cfn-guard.rules
```

### Template skeleton every product should share

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: "vpc-baseline v3.2.1 — dual-AZ VPC with flow logs"

Metadata:
  AWS::CloudFormation::Interface:
    ParameterGroups:
      - Label: { default: Network }
        Parameters: [Environment, VpcCidr, EnableNat]
      - Label: { default: Observability }
        Parameters: [FlowLogRetention]
    ParameterLabels:
      VpcCidr:
        default: VPC CIDR (RFC1918, non-overlapping)

Parameters:
  Environment:
    Type: String
    AllowedValues: [sandbox, dev, staging, prod]
  VpcCidr:
    Type: String
    AllowedPattern: "^10\\.(\\d{1,3})\\.(\\d{1,3})\\.0/16$"
    ConstraintDescription: Must be 10.x.y.0/16 in this landing zone
  EnableNat:
    Type: String
    Default: "true"
    AllowedValues: ["true", "false"]
  FlowLogRetention:
    Type: Number
    Default: 90
    MinValue: 7
    MaxValue: 3653

Conditions:
  CreateNat: !Equals [!Ref EnableNat, "true"]
  IsProd: !Equals [!Ref Environment, prod]

Resources:
  # ... see 52.3

Outputs:
  VpcId:
    Description: VPC ID for nested or cross-stack use
    Value: !Ref Vpc
    Export:
      Name: !Sub "${AWS::StackName}-VpcId"
```

Interface metadata is not cosmetic. Service Catalog and the console group parameters so application owners do not hunt through fifty keys. `AllowedPattern` on CIDR is cheaper than a failed VPC create two minutes later.

---

## 52.3 Nested stacks versus nested of nested

**Nested stacks** are CloudFormation's composition primitive: a parent stack creates `AWS::CloudFormation::Stack` resources whose templates live in S3. Use nested stacks when:

- A logical unit exceeds ~400 resources or becomes unreadable.
- You want independent rollback of a child (limited — parent still owns lifecycle).
- Multiple parents share the same child template version.

Avoid infinite nesting. Two levels (parent → children) is the practical maximum for most teams. Three levels is acceptable for KMS + logging leaves. Deeper than that, debugging `CREATE_FAILED` becomes a graph walk.

### Parent that nests KMS and VPC

```yaml
Resources:
  KmsStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Sub https://s3.${AWS::Region}.amazonaws.com/${CatalogBucket}/nested/kms-key.yaml
      Parameters:
        AliasName: !Sub alias/${Environment}/data
        EnableKeyRotation: "true"
      Tags:
        - Key: catalog.product
          Value: kms-key

  VpcStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: KmsStack
    Properties:
      TemplateURL: !Sub https://s3.${AWS::Region}.amazonaws.com/${CatalogBucket}/nested/vpc-baseline.yaml
      Parameters:
        Environment: !Ref Environment
        VpcCidr: !Ref VpcCidr
        FlowLogKmsKeyId: !GetAtt KmsStack.Outputs.KeyArn
```

Child outputs surface through `!GetAtt ChildStack.Outputs.OutputName`. Do not export from nested children if the parent already exports; duplicate export names fail the stack.

### Change sets for nested stacks

Always create a change set before executing:

```bash
aws cloudformation create-change-set \
  --stack-name shop-prod-network \
  --change-set-name cs-$(date +%Y%m%d%H%M) \
  --template-body file://parent.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --include-nested-stacks \
  --parameters ParameterKey=Environment,ParameterValue=prod

aws cloudformation describe-change-set \
  --stack-name shop-prod-network \
  --change-set-name cs-202609021200 \
  --include-nested-stacks
```

`--include-nested-stacks` is required to see child replacements. A silent `Replacement: True` on an RDS nested stack is a production incident waiting for execute.

---

## 52.4 StackSets for multi-account catalog rollout

When the catalog must exist in every account (Config rules, CloudTrail bucket policy helpers, IAM boundary), use **CloudFormation StackSets** from the management or a delegated administrator account.

| Attribute | Stack | StackSet |
|-----------|-------|----------|
| Scope | One account, one region | Many accounts, many regions |
| Identity | Caller credentials | Administration role + execution role |
| Failure mode | Rollback the stack | Per-instance; others continue |
| Drift | Detect on stack | Detect per stack instance |
| Typical use | App environment | Org-wide guardrails |

```yaml
# Execution role trust (in target accounts) — simplified
Resources:
  StackSetExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: AWSCloudFormationStackSetExecutionRole
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub arn:aws:iam::${AdminAccountId}:role/AWSCloudFormationStackSetAdministrationRole
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/AdministratorAccess  # tighten in production
```

In production, replace `AdministratorAccess` with a custom policy that can only create the catalog resource types. Pair StackSets with **service-managed permissions** when AWS Organizations is the source of truth for target OUs. Account vending (Chapter 53) should automatically receive baseline StackSet instances.

---

## 52.5 cfn-lint, Guard, and cfn-nag in the catalog pipeline

A catalog without static analysis is a malware distribution system for IAM stars. Minimum gates:

| Tool | What it catches | Fail the build when |
|------|-----------------|---------------------|
| cfn-lint | Schema, intrinsic misuse | Any error; warnings for W* you adopt |
| AWS SAM / Guard | Policy-as-code (encryption, public S3) | Rule set `catalog-mandatory` |
| cfn-nag | IAM wildcards, SG 0.0.0.0/0 | High findings |
| Checkov | Multi-IaC overlap | HIGH on catalog products |

Example Guard rules for catalog products:

```guard
rule s3_bucket_sse_kms when Resources.*[ Type == "AWS::S3::Bucket" ] {
  Properties.BucketEncryption.ServerSideEncryptionConfiguration[*].ServerSideEncryptionByDefault.SSEAlgorithm == "aws:kms"
}

rule rds_not_public when Resources.*[ Type == "AWS::RDS::DBInstance" ] {
  Properties.PubliclyAccessible == false
}

rule sg_no_ssh_world when Resources.*[ Type == "AWS::EC2::SecurityGroup" ] {
  let ingress = Properties.SecurityGroupIngress.*
  when %ingress.FromPort == 22 {
    %ingress.CidrIp != "0.0.0.0/0"
  }
}
```

Pipeline stage (CodeBuild):

```bash
#!/usr/bin/env bash
set -euo pipefail
cfn-lint products/**/*.yaml
cfn-guard validate --data products --rules policies/cfn-guard.rules
cfn_nag_scan --input-path products --fail-on-warnings
```

Do not skip these on "emergency" templates. Emergency templates become permanent.

---

## 52.6 Macros, transforms, and language extensions

CloudFormation **macros** rewrite templates at deploy time. `AWS::Serverless-2016-10-31` (SAM) and `AWS::Include` are the macros you will use daily. Custom macros (Lambda-backed) belong in the catalog when you need org-specific sugar, for example injecting standard tags.

```yaml
Transform: AWS::LanguageExtensions

Resources:
  LogGroups:
    Fn::ForEach::EnvLog:
      - Env
      - [dev, staging, prod]
      - ${Env}AppLogs:
          Type: AWS::Logs::LogGroup
          Properties:
            LogGroupName: !Sub /app/${Env}
            RetentionInDays: 30
```

Language Extensions (`Fn::ForEach`) reduce copy-paste but make change sets harder to read. Prefer CDK loops for application code; use `Fn::ForEach` only in YAML products that must remain YAML for Service Catalog consumers who do not run Node/Python.

`AWS::Include` pulls snippets from S3. Version the include objects (`s3://catalog/includes/alarms-v2.yaml`). Never include `latest` without an object lock or version ID; silent include changes produce unreproducible stacks.

---

## 52.7 AWS CDK construct catalog

CDK is the preferred authoring experience for teams that already write TypeScript or Python. The catalog becomes a **private construct library** published to CodeArtifact.

```
@org/cdk-catalog/
  lib/
    network/vpc-baseline.ts
    compute/ecs-fargate-service.ts
    data/aurora-postgres.ts
    obs/alarm-defaults.ts
    iam/workload-role.ts
  test/
    vpc-baseline.test.ts
```

### L2 versus L3 in the catalog

| Level | Meaning | Catalog use |
|-------|---------|-------------|
| L1 (`Cfn*`) | 1:1 CloudFormation | Escape hatch only |
| L2 | Intentful AWS constructs | Building blocks inside L3 |
| L3 (patterns) | Opinionated multi-resource | What you publish to app teams |

Application teams should almost never import L1 from the catalog. If they need an L1, the catalog is incomplete.

### Example L3: Fargate service with defaults

```typescript
import { Construct } from "constructs";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as logs from "aws-cdk-lib/aws-logs";
import * as iam from "aws-cdk-lib/aws-iam";

export interface OrgFargateServiceProps {
  readonly cluster: ecs.ICluster;
  readonly vpc: ec2.IVpc;
  readonly image: ecs.ContainerImage;
  readonly containerPort: number;
  readonly desiredCount?: number;
  readonly environmentName: "dev" | "staging" | "prod";
}

export class OrgFargateService extends Construct {
  public readonly service: ecs.FargateService;
  public readonly targetGroup: elbv2.ApplicationTargetGroup;

  constructor(scope: Construct, id: string, props: OrgFargateServiceProps) {
    super(scope, id);

    const taskDef = new ecs.FargateTaskDefinition(this, "Task", {
      cpu: props.environmentName === "prod" ? 512 : 256,
      memoryLimitMiB: props.environmentName === "prod" ? 1024 : 512,
    });

    taskDef.addToTaskRolePolicy(
      new iam.PolicyStatement({
        actions: ["kms:Decrypt", "kms:GenerateDataKey"],
        resources: ["arn:aws:kms:*:*:key/*"], // tighten via props.kmsKey
        conditions: {
          StringEquals: { "kms:ViaService": `ecs.${this.node.tryGetContext("region")}.amazonaws.com` },
        },
      })
    );

    const logGroup = new logs.LogGroup(this, "Logs", {
      retention: props.environmentName === "prod"
        ? logs.RetentionDays.THREE_MONTHS
        : logs.RetentionDays.TWO_WEEKS,
    });

    const container = taskDef.addContainer("app", {
      image: props.image,
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: "app" }),
    });
    container.addPortMappings({ containerPort: props.containerPort });

    this.service = new ecs.FargateService(this, "Service", {
      cluster: props.cluster,
      taskDefinition: taskDef,
      desiredCount: props.desiredCount ?? 2,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      circuitBreaker: { rollback: true },
      enableExecuteCommand: props.environmentName !== "prod",
    });
  }
}
```

Note the opinions: private subnets only, log retention by environment, execute-command off in prod, circuit breaker on. Catalogs encode **policy as defaults**. Optional props can relax defaults only behind a `breakGlass: true` that GuardDuty-style reviews flag.

### CDK Aspects for org-wide mutations

```typescript
import { IAspect, CfnResource, Aspects } from "aws-cdk-lib";
import { IConstruct } from "constructs";

class MandatoryTags implements IAspect {
  visit(node: IConstruct): void {
    if (CfnResource.isCfnResource(node)) {
      node.addPropertyOverride("Tags", [
        { Key: "org:environment", Value: process.env.ENV ?? "unknown" },
        { Key: "org:cost-center", Value: process.env.COST_CENTER ?? "unset" },
      ]);
    }
  }
}

Aspects.of(app).add(new MandatoryTags());
```

Aspects are the CDK equivalent of a CloudFormation macro. Use them for tags, encryption flags, and deletion policies — not for rewriting entire resource graphs.

### cdk-nag

```typescript
import { Aspects } from "aws-cdk-lib";
import { AwsSolutionsChecks } from "cdk-nag";

Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
```

Suppressions must cite a ticket:

```typescript
NagSuppressions.addResourceSuppressions(bucket, [
  {
    id: "AwsSolutions-S1",
    reason: "Access logs live on the org log-archive bucket; see SEC-2144",
  },
]);
```

A suppression without a reason is a failed code review.

---

## 52.8 AWS Service Catalog — how teams consume the catalog

**AWS Service Catalog** is the distribution plane. Platform engineers publish products; developers launch them with constrained parameters.

| Concept | Role |
|---------|------|
| Product | Versioned CloudFormation or Terraform (via engine) template |
| Portfolio | Group of products (Network, Data, Compute) |
| Constraint | Launch role, template constraint, notification |
| TagOption | Mandatory tags at launch |
| Provisioned product | A launched instance (a stack under the hood) |

### Launch role constraint

Developers should not need `iam:CreateRole` in their daily role. The launch role is assumed by Service Catalog:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "ec2:*Vpc*",
        "ec2:*Subnet*",
        "ec2:*Route*",
        "ec2:*SecurityGroup*",
        "ec2:*NatGateway*",
        "ec2:*InternetGateway*",
        "logs:*",
        "iam:PassRole"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestTag/org:catalog": "true"
        }
      }
    }
  ]
}
```

Tighten `Resource` with ARNs as products stabilize. Template constraints (JSON schema) prevent `InstanceType: p4d.24xlarge` in a sandbox product.

### Service Catalog + CI

On merge to `main` of `cfn-catalog`:

1. Lint and Guard.
2. Upload templates to versioned S3 (`products/vpc-baseline/3.2.1.yaml`).
3. `aws servicecatalog create-provisioning-artifact` with the new S3 URL.
4. Optionally `update-provisioned-product` for a canary account.

Keep previous artifacts active for one release so teams can roll back without git archaeology.

---

## 52.9 CDK Pipelines as the catalog CI

```typescript
import { SecretValue, Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as pipelines from "aws-cdk-lib/pipelines";
import * as codecommit from "aws-cdk-lib/aws-codecommit";

export class CatalogPipelineStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const repo = codecommit.Repository.fromRepositoryName(this, "Repo", "cdk-catalog");

    const pipeline = new pipelines.CodePipeline(this, "Pipeline", {
      synth: new pipelines.ShellStep("Synth", {
        input: pipelines.CodePipelineSource.codeCommit(repo, "main"),
        commands: [
          "npm ci",
          "npm run lint",
          "npm test",
          "npx cdk synth",
        ],
      }),
      dockerEnabledForSynth: true,
    });

    pipeline.addStage(new CatalogWave(this, "Sandbox", { account: "111111111111", region: "us-east-1" }));
    pipeline.addStage(new CatalogWave(this, "Prod", { account: "222222222222", region: "us-east-1" }), {
      pre: [new pipelines.ManualApprovalStep("PromoteCatalog")],
    });
  }
}
```

Self-mutating pipelines (`CodePipeline` construct) update themselves when you change the pipeline stack. That is convenient and dangerous: review pipeline diffs as carefully as product diffs. A poisoned pipeline can push a poisoned catalog to every account.

---

## 52.10 Drift, imports, and brownfield

Catalogs meet reality when someone clicked in the console.

**Detect drift** on every production stack weekly:

```bash
aws cloudformation detect-stack-drift --stack-name shop-prod-ecs
aws cloudformation describe-stack-resource-drifts --stack-name shop-prod-ecs \
  --query "StackResourceDrifts[?StackResourceDriftStatus!='IN_SYNC']"
```

Remediation options:

1. **Revert console change** — restore IaC as source of truth.
2. **Import into template** — `resource import` then update template to match.
3. **Replace resource** — last resort; check replacement policy.

CDK `cdk import` exists but is finicky with custom names. Prefer CloudFormation import for single resources, then `cdk diff` until empty.

---

## 52.11 Parameter and secret handling

Never put secrets in Parameters with `NoEcho` as your only control. `NoEcho` hides console display; the value still appears in change sets and Lambda environment for custom resources if you pass it through.

Pattern:

| Secret type | Store | Reference |
|-------------|-------|-----------|
| DB master password | Secrets Manager, rotation | Dynamic reference `{{resolve:secretsmanager:...}}` |
| Third-party API key | Secrets Manager | Same |
| Non-secret config | SSM Parameter Store | `{{resolve:ssm:/app/dev/log_level}}` |
| Cross-account AMI ID | SSM public parameter or mapping | `{{resolve:ssm:/amis/web/x86}}` |

```yaml
MasterUserPassword: "{{resolve:secretsmanager:prod/rds/shop:SecretString:password}}"
```

Dynamic references are resolved at CloudFormation processing time on each create/update that touches the property. Rotation of the secret does **not** automatically rotate the RDS password unless you use Secrets Manager rotation for RDS. Document that distinction in the product README.

---

## 52.12 Deletion policies and retain-on-delete

Catalog products for data stores must default to retain:

```yaml
DeletionPolicy: Snapshot
UpdateReplacePolicy: Snapshot
```

For S3 buckets with compliance data:

```yaml
DeletionPolicy: Retain
UpdateReplacePolicy: Retain
```

Application teams hate leftover buckets. Platform teams hate deleted audit logs. The catalog sides with retain, and a separate **janitor product** (Step Functions + Config) ages out retained resources with dual approval.

---

## 52.13 Lab A — publish a VPC product and launch it

**Goal:** A CloudFormation template in S3, registered as a Service Catalog product, launched into a sandbox account.

**Prerequisites:** Sandbox account, IAM permissions for Service Catalog admin, an S3 bucket `org-catalog-${ACCOUNT}` with versioning.

### Steps

1. Write `vpc-baseline.yaml` with a VPC, two public and two private subnets, one NAT (condition), VPC flow logs to CloudWatch, and KMS on the log group.

2. Lint:

```bash
cfn-lint vpc-baseline.yaml
```

3. Upload:

```bash
aws s3 cp vpc-baseline.yaml s3://org-catalog-${ACCOUNT}/products/vpc-baseline/1.0.0.yaml
```

4. Create product and portfolio (CLI):

```bash
aws servicecatalog create-product \
  --name vpc-baseline \
  --owner platform \
  --product-type CLOUD_FORMATION_TEMPLATE \
  --provisioning-artifact-parameters \
    Name=v1.0.0,Type=CLOUD_FORMATION_TEMPLATE,Info={LoadTemplateFromURL=https://org-catalog-${ACCOUNT}.s3.amazonaws.com/products/vpc-baseline/1.0.0.yaml}

# Note ProductId from output, then:
aws servicecatalog create-portfolio --display-name Network --provider-name platform
aws servicecatalog associate-product-with-portfolio --product-id prod-xxx --portfolio-id port-xxx
aws servicecatalog associate-principal-with-portfolio \
  --portfolio-id port-xxx \
  --principal-arn arn:aws:iam::${ACCOUNT}:role/Developer \
  --principal-type IAM
```

5. As the Developer role, provision:

```bash
aws servicecatalog provision-product \
  --product-id prod-xxx \
  --provisioning-artifact-id pa-xxx \
  --provisioned-product-name sandbox-vpc-a \
  --provisioning-parameters Key=Environment,Value=sandbox Key=VpcCidr,Value=10.20.0.0/16
```

6. Verify flow logs exist and NAT is absent if you set `EnableNat=false`.

7. Tear down: `terminate-provisioned-product`, then empty and delete leftover ENIs if the stack stuck on ENI deletion (common lab gotcha).

**Success criteria:** Provisioned product `AVAILABLE`; `describe-stacks` shows expected subnet count; Guard would still pass if you re-lint the launched template.

---

## 52.14 Lab B — CDK construct library with a consumer app

**Goal:** Publish `@org/cdk-catalog` locally (npm pack) and consume `OrgFargateService` from a sample app.

### Steps

1. `cdk init lib --language typescript` in `cdk-catalog`. Add the construct from section 52.7. Unit test with `aws-cdk-lib/assertions`:

```typescript
import { Template } from "aws-cdk-lib/assertions";
import { App, Stack } from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import { OrgFargateService } from "../lib/compute/ecs-fargate-service";

test("prod service uses 512 CPU", () => {
  const app = new App();
  const stack = new Stack(app, "Test");
  const vpc = new ec2.Vpc(stack, "Vpc", { maxAzs: 2 });
  const cluster = new ecs.Cluster(stack, "Cluster", { vpc });
  new OrgFargateService(stack, "Svc", {
    vpc,
    cluster,
    image: ecs.ContainerImage.fromRegistry("public.ecr.aws/amazonlinux/amazonlinux:2023"),
    containerPort: 8080,
    environmentName: "prod",
  });
  const template = Template.fromStack(stack);
  template.hasResourceProperties("AWS::ECS::TaskDefinition", {
    Cpu: "512",
  });
});
```

2. `npm test && npm pack`. In a sibling `demo-app`, `npm install ../cdk-catalog/org-cdk-catalog-1.0.0.tgz`.

3. `cdk synth` and confirm no public subnets on the service.

4. Optional: `cdk deploy` to sandbox; hit the ALB health check.

5. Destroy: `cdk destroy --force`.

**Success criteria:** Test passes; synth JSON has `AssignPublicIp` false or no public subnet association.

---

## 52.15 Versioning and compatibility matrix

Catalog versions follow semver:

| Bump | When | Consumer action |
|------|------|-----------------|
| PATCH | Alarm threshold, docs | Optional upgrade |
| MINOR | New optional parameter | Upgrade when needed |
| MAJOR | Parameter rename, replacement resources | Planned migration |

Publish a compatibility matrix in the catalog README:

| Product | Min CDK | CFN resource spec | Breaking notes |
|---------|---------|-------------------|----------------|
| vpc-baseline 3.x | n/a (YAML) | 2024+ | NAT optional |
| ecs-fargate 2.x | 2.120+ | ECS Exec default off in prod | 1.x had Exec on |
| aurora-pg 4.x | 2.140+ | Requires KMS CMK param | 3.x allowed AWS managed |

Never delete a major line until no provisioned products reference it. Service Catalog lists artifact IDs; export that weekly.

---

## 52.16 Custom resources — when and how

If CloudFormation lacks a resource, you may add a Lambda-backed custom resource **in the catalog**, not in random app stacks.

Rules:

- Idempotent `Create/Update/Delete`.
- Timeout less than CloudFormation's 1 hour default; set `ServiceTimeout`.
- Log to a log group with retention.
- IAM role scoped to the API you wrap.
- Prefer Cloud Control API / new resource types over custom resources when available.

```python
import boto3
import cfnresponse

def handler(event, context):
    try:
        request_type = event["RequestType"]
        if request_type == "Delete":
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return
        # upsert logic
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {"Id": "x"})
    except Exception as e:
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)})
```

A hung custom resource blocks stack rollback. Always send a response, even on delete of a resource that never created.

---

## 52.17 Cross-stack references and SSM instead of exports

`Export`/`Fn::ImportValue` create hard couplings: you cannot delete or replace the exporter while importers exist. For catalogs, prefer:

1. **SSM parameters** written by the network product (`/org/network/prod/vpc-id`).
2. **Lookup in CDK** `ec2.Vpc.fromLookup` with tags.
3. **Service Catalog outputs** consumed by the next product's parameters.

Exports remain fine for tightly coupled nested children in one parent.

---

## 52.18 Cost and governance tags

Every catalog product must apply:

| Tag | Example |
|-----|---------|
| `org:product` | `vpc-baseline` |
| `org:product-version` | `3.2.1` |
| `org:environment` | `prod` |
| `org:cost-center` | `cc-1042` |
| `org:data-class` | `internal` |

Activate these as cost allocation tags. Without them, showback for "who launched 40 NAT gateways" is guesswork.

---

## 52.19 Failure modes unique to catalogs

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Circular dependency | Nested stack output used in sibling create | Split or use SSM |
| `Export cannot be deleted` | ImportValue still in use | Remove importer first |
| Service Catalog `IN_PROGRESS` forever | Launch role missing a permission | CloudTrail `AccessDenied` |
| CDK `fatal: unique id` | Construct id collision across versions | Qualify ids with version or hash |
| StackSet `PARTIAL` | SCP deny in one OU | Chapter 53 SCPs |

---

## 52.20 What to put in the catalog versus what to leave to apps

**Catalog (platform-owned):** VPC, TGW attachments, shared KMS, ECS cluster, Aurora parameter groups, standard alarms, WAF ACL associations, IAM permission boundaries, log destinations.

**App-owned:** container image, task CPU/memory within allowed ranges, environment variables (non-secret), alarm thresholds tighter than defaults, feature flags.

If an app team needs a new AWS service, they open a catalog RFC: threat model, Guard rules, cost estimate, then a v0.1 product in sandbox only.

---

## 52.21 Exam and interview hooks

- Nested stacks vs StackSets vs CDK pipelines — pick by blast radius and identity model.
- Change sets with `--include-nested-stacks`.
- Service Catalog launch constraints vs IAM user power.
- cdk-nag suppressions need reasons.
- Dynamic references versus Parameter `NoEcho`.
- Drift detection is not a backup; it is a process.

---

## 52.22 Chapter checklist

- [ ] Products live in git with semver and Guard rules.
- [ ] Nested depth ≤ 2 for human-debuggable graphs.
- [ ] StackSets cover org-wide baselines only.
- [ ] CDK L3 constructs encode production defaults.
- [ ] Service Catalog launch roles are least privilege.
- [ ] Secrets never sit in plaintext parameters.
- [ ] Data products default to Snapshot/Retain.
- [ ] Labs A and B completed in sandbox.

The next chapter places this catalog inside a multi-account landing zone: who may publish, which OU receives which portfolio, and how SCPs stop even a catalog admin from creating an internet-open RDS.
