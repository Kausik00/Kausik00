# Chapter 31: CloudFormation Deep Dive

*AWS Handbook — Part VIII, Pages 621–645*

---

## 31.1 Infrastructure as Code with CloudFormation

**AWS CloudFormation** is AWS's native Infrastructure as Code (IaC) service. You define resources in YAML or JSON templates; CloudFormation provisions, updates, and deletes them as a single **stack**. Changes are tracked, rollback is automatic on failure, and drift detection identifies manual modifications.

For AWS-only environments, CloudFormation provides the deepest service integration and zero licensing cost.

---

## 31.2 Template structure

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Web application stack

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Mappings:
  RegionMap:
    us-east-1:
      AMI: ami-0c55b159cbfafe1f0
    eu-west-1:
      AMI: ami-0d71ea30463e0ff8d

Conditions:
  IsProd: !Equals [!Ref Environment, prod]

Resources:
  WebServer:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: !FindInMap [RegionMap, !Ref "AWS::Region", AMI]
      InstanceType: !If [IsProd, t3.medium, t3.micro]

Outputs:
  PublicIP:
    Value: !GetAtt WebServer.PublicIp
    Export:
      Name: !Sub "${AWS::StackName}-PublicIP"
```

### Intrinsic functions

| Function | Purpose | Example |
|----------|---------|---------|
| `!Ref` | Reference parameter or resource | `!Ref WebServer` |
| `!GetAtt` | Get resource attribute | `!GetAtt WebServer.PublicIp` |
| `!Sub` | String substitution | `!Sub "arn:aws:s3:::${Bucket}"` |
| `!Join` | Concatenate strings | `!Join ["-", [a, b]]` |
| `!Select` | Pick from list | `!Select [0, !GetAZs ""]` |
| `!If` | Conditional value | `!If [IsProd, t3.medium, t3.micro]` |
| `!FindInMap` | Lookup in mapping | `!FindInMap [RegionMap, !Ref "AWS::Region", AMI]` |

---

## 31.3 Stack operations

```bash
# Validate template
aws cloudformation validate-template --template-body file://template.yaml

# Create stack
aws cloudformation create-stack \
  --stack-name web-app-dev \
  --template-body file://template.yaml \
  --parameters ParameterKey=Environment,ParameterValue=dev \
  --capabilities CAPABILITY_IAM

# Update stack
aws cloudformation update-stack \
  --stack-name web-app-dev \
  --template-body file://template.yaml \
  --parameters ParameterKey=Environment,ParameterValue=staging

# Delete stack (removes all resources)
aws cloudformation delete-stack --stack-name web-app-dev

# Describe events (troubleshooting)
aws cloudformation describe-stack-events --stack-name web-app-dev
```

### Change sets

Preview changes before applying:

```bash
aws cloudformation create-change-set \
  --stack-name web-app-dev \
  --template-body file://template-v2.yaml \
  --change-set-name update-to-v2

aws cloudformation describe-change-set \
  --stack-name web-app-dev \
  --change-set-name update-to-v2

aws cloudformation execute-change-set \
  --stack-name web-app-dev \
  --change-set-name update-to-v2
```

---

## 31.4 Nested stacks

Break large templates into reusable modules:

```yaml
Resources:
  NetworkStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://s3.amazonaws.com/templates/network.yaml
      Parameters:
        VpcCidr: 10.0.0.0/16

  AppStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: NetworkStack
    Properties:
      TemplateURL: https://s3.amazonaws.com/templates/app.yaml
      Parameters:
        VpcId: !GetAtt NetworkStack.Outputs.VpcId
        SubnetIds: !GetAtt NetworkStack.Outputs.PrivateSubnetIds
```

### Cross-stack references

Export values from one stack and import in another:

```yaml
# Stack A (network)
Outputs:
  VpcId:
    Value: !Ref MyVpc
    Export:
      Name: !Sub "${AWS::StackName}-VpcId"

# Stack B (application)
Resources:
  WebServer:
    Properties:
      VpcId: !ImportValue network-stack-VpcId
```

---

## 31.5 StackSets

Deploy stacks across multiple accounts and regions from a single template:

```bash
aws cloudformation create-stack-set \
  --stack-set-name baseline-security \
  --template-body file://security-baseline.yaml \
  --permission-model SERVICE_MANAGED \
  --auto-deployment Enabled=true

aws cloudformation create-stack-instances \
  --stack-set-name baseline-security \
  --deployment-targets OrganizationalUnitIds=["ou-abc-123"] \
  --regions us-east-1 eu-west-1
```

Use cases: organization-wide guardrails, logging, security baselines.

---

## 31.6 IAM in CloudFormation

### CAPABILITY flags

| Flag | When required |
|------|---------------|
| `CAPABILITY_IAM` | Template creates IAM resources |
| `CAPABILITY_NAMED_IAM` | Template creates named IAM resources |
| `CAPABILITY_AUTO_EXPAND` | Template uses macros (SAM, CDK) |

### Least-privilege IAM example

```yaml
Resources:
  LambdaRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: DynamoDBAccess
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                Resource: !GetAtt OrdersTable.Arn
```

---

## 31.7 Drift detection

Manual changes outside CloudFormation create **drift**:

```bash
aws cloudformation detect-stack-drift --stack-name web-app-dev

aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id abc-123

aws cloudformation describe-stack-resource-drifts \
  --stack-name web-app-dev
```

**Best practice:** All infrastructure changes go through CloudFormation. Use SCPs to deny direct resource creation where possible.

---

## 31.8 Custom resources

When CloudFormation lacks native support, use **custom resources** backed by Lambda:

```yaml
Resources:
  CustomDNS:
    Type: Custom::DNSRecord
    Properties:
      ServiceToken: !GetAtt DNSLambda.Arn
      HostedZoneId: Z1234567890
      Name: app.example.com
      Value: !GetAtt WebServer.PublicIp
```

The Lambda handles Create, Update, and Delete requests and sends a response to CloudFormation's pre-signed S3 URL.

---

## 31.9 CloudFormation Hooks

**Hooks** validate resources before provisioning (proactive compliance):

| Hook | Purpose |
|------|---------|
| **Guard Hooks** | Evaluate templates against policy rules |
| **Lambda Hooks** | Custom validation logic |

```bash
aws cloudformation activate-type \
  --type HOOK \
  --type-name MyOrg::S3::EncryptionCheck \
  --publisher-id 123456789012
```

---

## 31.10 Best practices

| Practice | Rationale |
|----------|-----------|
| Use parameters for environment-specific values | Reuse templates across environments |
| Use mappings for region-specific constants | AMI IDs, instance types |
| Use conditions for optional resources | Prod-only resources (WAF, Multi-AZ) |
| Tag all resources | Cost allocation, automation |
| Use nested stacks for modularity | Manageable template sizes |
| Enable termination protection on prod stacks | Prevent accidental deletion |
| Use change sets for production updates | Preview before apply |
| Store templates in S3 with versioning | Audit trail, rollback |
| Run drift detection regularly | Catch manual changes |

---

## 31.11 Chapter summary

- **CloudFormation** provisions AWS infrastructure from declarative YAML/JSON templates.
- **Stacks** group related resources; **nested stacks** and **StackSets** enable modularity and multi-account deployment.
- Use **change sets** to preview updates; **drift detection** catches manual changes.
- **Custom resources** extend CloudFormation with Lambda-backed logic.
- Follow IaC best practices: parameters, conditions, tagging, and termination protection.

---

## 🧪 Lab 31.1 — Multi-tier stack

1. Write a CloudFormation template with VPC, subnets, security groups, ALB, and EC2.
2. Deploy with parameters for environment (dev/prod).
3. Update the template to add an RDS instance (prod only, using conditions).
4. Create a change set and review before applying.

## 🧪 Lab 31.2 — Drift detection

1. Deploy a stack and manually modify a security group in the console.
2. Run drift detection and identify the drifted resource.
3. Update the stack to reconcile the drift.

---

## Review questions

1. What is the purpose of CloudFormation change sets?
2. How do nested stacks improve template organization?
3. What capability flag is required when creating IAM roles in a template?
4. What is stack drift and how do you detect it?
5. When would you use StackSets instead of individual stacks?

---

*Next: [Chapter 32 — AWS CDK](./chapter-32-aws-cdk.md)*
