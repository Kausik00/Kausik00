# Chapter 53: Multi-Account Landing Zone

A landing zone is the opinionated multi-account foundation on which every workload in this handbook sits. It is not a single VPC. It is Organizations plus identity, logging, security tooling, network hub, account vending, and the Service Control Policies (SCPs) that make unsafe API calls impossible even for account administrators. AWS Control Tower automates much of this; many enterprises still compose the same pieces by hand or with Customizations for Control Tower (CfCT) and Account Factory for Terraform (AFT).

This chapter assumes you can already create an organization (Chapter 8). Here we go deeper: OU design, Control Tower guardrails, SCP strategy that does not lock you out, account vending workflows, and labs that you can run in a test organization.

---

## 53.1 Why multiple accounts beat one fat account

| Concern | Single account | Multi-account landing zone |
|---------|----------------|----------------------------|
| Blast radius | One IAM mistake is global | Compromise contained to an OU |
| Billing | Tags only | Account + OU + tags |
| Soft limits | Shared quotas | Per-account quotas |
| Compliance | One audit scope | Isolated PCI / prod / sandbox |
| Privileged access | Hard to constrain root | SCPs + Identity Center permission sets |

AWS accounts are the strongest isolation boundary short of an organization. VPCs and IAM cannot match account-level isolation for billing, service quotas, and "this role cannot even see the other environment's KMS keys."

---

## 53.2 Organizations anatomy

```
Management account (do not run workloads)
├── Root
│   ├── Security OU
│   │   ├── Log Archive
│   │   ├── Audit (Security Tooling)
│   ├── Infrastructure OU
│   │   ├── Network Hub
│   │   ├── Shared Services (Identity, CI)
│   ├── Sandbox OU
│   │   └── (vended developer accounts)
│   ├── Workloads OU
│   │   ├── Prod
│   │   └── Nonprod
│   └── Suspended / Quarantine OU
```

**Management account** pays the consolidated bill, owns Organizations, and should not host applications. Break-glass root and a tiny set of org-admin permission sets live here.

**Log Archive** receives immutable CloudTrail organizations trails, VPC flow log destinations, and Config snapshots.

**Audit / Security Tooling** is where GuardDuty administrator, Security Hub, Detective, and Inspector aggregators run. Security engineers log in here, not into prod, for investigations.

**Network Hub** owns Transit Gateway, shared VPC (if RAM), Direct Connect GW, and central egress.

**Workloads** split prod vs nonprod so SCPs can be stricter on prod (no disable of CloudTrail, no leave organization).

**Sandbox** is where developers may have power-user rights but SCPs still block expensive GPU families, leaving the org, and public RDS.

**Suspended** is for accounts being offboarded: SCP that Deny `*` except billing and Organizations leave/close procedures.

---

## 53.3 Control Tower — what it actually provisions

AWS Control Tower sets up a **landing zone** with:

- An organization (or uses existing).
- Shared accounts: Log Archive, Audit (names configurable).
- IAM Identity Center (successor to AWS SSO) enabled in the home Region.
- CloudTrail organization trail, AWS Config in governed Regions.
- Baseline **guardrails**: preventive (SCPs) and detective (Config rules).
- Account Factory to vend accounts into OUs.

| Control Tower concept | Underlying AWS |
|-----------------------|----------------|
| Landing zone version | CloudFormation + service-linked orchestration |
| Guardrail preventive | SCP |
| Guardrail detective | Config + Lambda/remediation |
| Account Factory | Organizations CreateAccount + StackSets |
| AFT | CodePipeline + Terraform in a dedicated account |

Control Tower **home Region** is where Identity Center and the landing zone API live. Additional **governed Regions** get Config and StackSets. Ungoverned Regions should be denied by SCP (`aws:RequestedRegion`) or you will have a shadow IT Region with no trail.

### Landing zone upgrade discipline

Control Tower landing zone versions lag new AWS features. Read the release notes. Upgrades can recreate or replace baseline stacks. Always:

1. Snapshot the current guardrail list.
2. Run upgrade in a pre-prod Control Tower if you have a test org (rare) or during a change window.
3. Validate Identity Center still maps permission sets.
4. Re-apply CfCT/AFT customizations after.

Never click "repair" casually; repair re-applies AWS-owned baselines and can overwrite manual SCP edits on AWS-managed policies. Put custom SCPs in **separate** policies attached to OUs, not by editing AWS-created SCPs.

---

## 53.4 OU design patterns

### Pattern A — environment first (common)

Workloads/Prod, Workloads/Nonprod, Sandbox. Simple SCPs: prod cannot create IAM users; sandbox cannot purchase Reserved Instances.

### Pattern B — domain first (large orgs)

Retail/Prod, Payments/Prod, Data/Prod. Better when different compliance regimes need different SCP packs. More Account Factory products.

### Pattern C — hybrid

OU by environment, nested OU by domain under Prod only. SCPs inherit: root deny leave-org, Prod deny disable-security, Payments extra PCI denials.

**Inheritance:** SCPs are inherited from root down. Effective permission is the **intersection** of identity policy AND every SCP in the chain. An Allow in identity cannot override an SCP Deny. An SCP Allow does not grant anything by itself.

That last sentence is the most common Control Tower interview trap. SCPs are **guards**, not grants.

---

## 53.5 SCP strategy that does not brick the org

### Rules of engagement

1. Never attach a Deny `*` without a NotAction exception for Organizations, IAM break-glass, and billing until you have tested in a child sandbox OU.
2. Keep a **break-glass** permission set in the management account that is not subject to workload SCPs (management account is not affected by SCPs — another trap: **SCPs do not apply to the management account**).
3. Use `aws:PrincipalARN` conditions to exempt automation roles (StackSet execution, Control Tower, AFT).
4. Version SCPs in git. Apply via pipeline with a canary OU first.

### Starter SCP pack (illustrative)

**Deny leaving the organization** (all workload OUs):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyLeaveOrg",
      "Effect": "Deny",
      "Action": ["organizations:LeaveOrganization"],
      "Resource": "*"
    }
  ]
}
```

**Deny unapproved Regions:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonHomeRegions",
      "Effect": "Deny",
      "NotAction": [
        "cloudfront:*",
        "iam:*",
        "route53:*",
        "support:*",
        "sts:*",
        "wafv2:*",
        "budgets:*",
        "globalaccelerator:*",
        "organizations:*",
        "account:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2", "eu-west-1"]
        }
      }
    }
  ]
}
```

Global services must be in `NotAction` or you break IAM and CloudFront. Maintain this list as AWS adds global services.

**Deny disabling security services in prod:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyGuardDutyOff",
      "Effect": "Deny",
      "Action": [
        "guardduty:DeleteDetector",
        "guardduty:DisassociateFromMasterAccount",
        "guardduty:DisassociateMembers",
        "guardduty:StopMonitoringMembers"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyCloudTrailStop",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:StopLogging",
        "cloudtrail:DeleteTrail",
        "cloudtrail:PutEventSelectors"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyConfigOff",
      "Effect": "Deny",
      "Action": [
        "config:DeleteConfigurationRecorder",
        "config:StopConfigurationRecorder",
        "config:DeleteDeliveryChannel"
      ],
      "Resource": "*"
    }
  ]
}
```

**Require IMDSv2 on RunInstances:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RequireImdsV2",
      "Effect": "Deny",
      "Action": "ec2:RunInstances",
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "StringNotEquals": {
          "ec2:MetadataHttpTokens": "required"
        }
      }
    }
  ]
}
```

Test this with Account Factory — some older launch paths omit the token requirement and will fail vending. Exempt the AFT/Control Tower roles if needed, then fix the launch template.

**Deny public S3 ACLs** (defense in depth with Block Public Access):

```json
{
  "Sid": "DenyPublicS3Acl",
  "Effect": "Deny",
  "Action": ["s3:PutBucketAcl", "s3:PutObjectAcl"],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "s3:x-amz-acl": [
        "public-read",
        "public-read-write",
        "authenticated-read"
      ]
    }
  }
}
```

### SCP size and count limits

Organizations limits: number of SCPs per OU, policy size (typically 5120 bytes per SCP). You will hit size limits. Split by theme (regions, security-off, iam-users, expensive-instances). Use `Fn::Sub` in CloudFormation or a generator, not hand-merged JSON blobs in Confluence.

---

## 53.6 Resource Control Policies and Declarative Policies

AWS has been expanding **organization policies** beyond SCPs: tag policies, backup policies, AI services opt-out, chat applications, and **Resource Control Policies (RCPs)** that constrain resource-based policies (for example, blocking S3 bucket policies that grant `*` principals).

Landing zone design in 2026 should treat RCPs as complementary to SCPs:

| Policy | Protects against | Applies to |
|--------|------------------|------------|
| SCP | Identity-based calls in member accounts | Principals in those accounts |
| RCP | Resource policies that overshare | Resources in those accounts |
| Tag policy | Non-compliant tags | Tagged resources |
| Backup policy | Missing backup plans | Plan assignment |

Do not assume an SCP Deny on `s3:PutBucketPolicy` is enough if a Lambda in another account can be granted via a bucket policy you already allowed. RCPs close that class of mistakes.

---

## 53.7 Identity Center permission sets

Landing zones fail when every engineer is a local IAM user. **IAM Identity Center** permission sets map IdP groups to accounts.

| Permission set | Typical group | Notes |
|----------------|---------------|-------|
| `PlatformAdmin` | platform-eng | Power user minus org leave; used in infra accounts |
| `WorkloadDev` | app-developers | App deploy roles; no IAM user create |
| `SecurityAudit` | secops | Read-only + Security Hub in audit account |
| `BillingRead` | finops | Cost Explorer, Budgets |
| `BreakGlass` | on-call + CISO | Time-bounded, logged, MFA hardware |

Session duration: 1 hour for prod, 8 hours for sandbox. Require MFA at IdP. Permission sets should attach **permission boundaries** for any set that can create roles.

Cross-account: developers assume `WorkloadDeploy` in prod via Identity Center, not long-lived keys. CI uses IAM roles in a shared-services account assumed via OIDC from GitHub/GitLab (Chapter 7 patterns).

---

## 53.8 Account vending

### Control Tower Account Factory

Console or API: email, name, OU, SSO user. Provisions baseline StackSets. Good for low volume.

### Account Factory for Terraform (AFT)

AFT is the production-grade vending machine:

```
Request (VCS) → AFT management account pipeline
  → Organizations CreateAccount
  → Control Tower enroll
  → Global customizations (all accounts)
  → Account customizations (by type: sandbox, prod, data)
  → Customization CodePipeline in each vended account (optional)
```

Account requests are Terraform:

```hcl
module "sandbox_alice" {
  source = "./modules/aft-account-request"
  control_tower_parameters = {
    AccountEmail = "alice-sandbox@example.com"
    AccountName  = "alice-sandbox"
    ManagedOrganizationalUnit = "Sandbox"
    SSOUserEmail = "alice@example.com"
    SSOUserFirstName = "Alice"
    SSOUserLastName  = "Ng"
  }
  account_tags = {
    owner = "alice"
    type  = "sandbox"
  }
  change_management_parameters = {
    change_requested_by = "alice"
    change_reason       = "new hire sandbox"
  }
  custom_fields = {
    vpc_cidr = "10.48.0.0/16"
  }
}
```

**Vending checklist** the customization stage must enforce:

- [ ] CloudTrail already org-wide (do not duplicate)
- [ ] Config recorder on
- [ ] GuardDuty member auto-accept
- [ ] Security Hub member
- [ ] Default VPC deleted in all Regions (or SCP + detective)
- [ ] Account-level S3 Block Public Access
- [ ] EBS encryption by default
- [ ] IMDSv2 hop limit 1 on the org
- [ ] Budget + anomaly detection
- [ ] Identity Center assignment from tags
- [ ] Catalog portfolios shared via RAM/Service Catalog
- [ ] Network: TGW attachment or RAM shared subnets
- [ ] Alternate contacts (security, operations, billing)

### Account closure

AWS account closure is delayed and irreversible after the window. Process:

1. Move to Suspended OU (Deny `*` SCP).
2. Remove Identity Center assignments.
3. Backup unique data to log-archive if required.
4. Close via Organizations or Account API.
5. Keep records of account ID for CloudTrail history in log archive.

Do not reuse emails carelessly; AWS account email uniqueness and recovery are painful.

---

## 53.9 Networking in the landing zone

Two dominant patterns:

**Centralized egress + TGW:** Spoke VPCs attach to Transit Gateway in Network Hub. Egress VPC has NAT and inspection (Gateway Load Balancer / Network Firewall). Spokes have no IGW. DNS via Route 53 profiles or shared resolver rules.

**Shared VPC (RAM):** Platform owns subnets; accounts receive subnet shares. Stronger central control, noisier neighbor risk, simpler for small orgs.

| Decision | Prefer TGW spokes | Prefer shared VPC |
|----------|-------------------|-------------------|
| Team count | Many, need isolation | Few platform-owned apps |
| Inspection | Central GWLB easy | Also possible |
| CIDR | Per-account VPC | One VPC planning |
| Kubernetes | Per-account clusters | ENI density issues |

Chapter 57 covers TGW and PrivateLink in specialty depth. The landing zone decision is: **no workload account creates its own DX or TGW**. SCP Deny `ec2:CreateTransitGateway` outside Network Hub.

---

## 53.10 Logging and security aggregation

| Signal | Where it lands |
|--------|----------------|
| CloudTrail org trail | Log Archive S3, KMS, Object Lock |
| VPC Flow Logs | S3 or CWL in log archive via dest policy |
| Config snapshots | Log Archive |
| GuardDuty findings | Audit account administrator |
| Security Hub | Audit, with org aggregation |
| IAM Access Analyzer | Org analyzer in audit |
| CloudWatch (app) | Stay in workload account; metric streams optional |

S3 Object Lock on the CloudTrail bucket in **compliance mode** is the gold standard for non-repudiation. Management account trail plus org trail duplication is a common Control Tower confusion — prefer a single org trail and disable account-level duplicates to save cost, unless a compliance regime demands both.

---

## 53.11 Customizations for Control Tower (CfCT)

CfCT is a CodePipeline in the management (or delegated) account that deploys:

- Additional CloudFormation StackSets to OUs
- SCPs from a `policies` folder
- Sometimes Config conformance packs

Keep CfCT **idempotent**. Do not mix CfCT SCPs with console-edited SCPs. AFT customizations vs CfCT: AFT is per-account Terraform (great for VPC CIDR uniqueness); CfCT is org-wide CloudFormation (great for IAM roles that every account needs). Many orgs run both: CfCT for AWS-native baselines, AFT for Terraform network.

---

## 53.12 Delegated administrators

Do not operate GuardDuty, Security Hub, Macie, Inspector, License Manager, and CloudFormation StackSets from the management account. Register **delegated administrators** in the Audit or a dedicated Security Tooling account.

```bash
aws organizations register-delegated-administrator \
  --account-id 444444444444 \
  --service-principal guardduty.amazonaws.com
```

This reduces who must log into the management account — the highest-value target in the estate.

---

## 53.13 Lab A — SCP canary on a sandbox OU

**Goal:** Prove a Region-deny SCP before attaching it to Prod.

**Prerequisites:** Test organization or a sandbox OU you may break. Do not use production.

1. Create OU `scp-canary` under Sandbox. Move a disposable account into it.

2. Attach only `DenyLeaveOrg` first. Confirm you can still `aws sts get-caller-identity` and create an S3 bucket in `us-east-1`.

3. Attach Region deny allowing only `us-east-1`. Attempt:

```bash
aws s3 mb s3://canary-ue1-$RANDOM --region us-east-1
aws ec2 describe-instances --region ap-southeast-2
```

The second call should fail with `ExplicitDeny` / `UnauthorizedOperation` depending on API.

4. Attempt IAM `create-user` in us-east-1 — should work if IAM is global and in NotAction.

5. Document the exact error string in your runbook so on-call does not confuse SCP deny with IAM deny (Chapter 59).

6. Detach the Region SCP before moving the account back.

**Success criteria:** Allowed Region works; disallowed Region fails; management account (if you mistakenly tested there) still works — proving SCPs skip management.

---

## 53.14 Lab B — vend an account (Control Tower or Organizations)

If Control Tower is enabled:

1. Account Factory → create `lab-vend-01` in Sandbox OU.
2. Wait until enrolled (can take tens of minutes).
3. Sign in via Identity Center.
4. Confirm Config recorder, CloudTrail events appearing in Log Archive, default VPCs as per your customization.
5. Attempt `cloudtrail delete-trail` if a local trail exists — should fail if preventive guardrail is on.
6. Close or move to Suspended when done (watch the close delay).

If you only have Organizations (no Control Tower):

```bash
aws organizations create-account \
  --email lab-vend-01@example.com \
  --account-name lab-vend-01 \
  --iam-user-access-to-billing ALLOW
```

Poll `describe-create-account-status`. Move account to OU. Deploy a StackSet instance with a tiny IAM role. Invite GuardDuty member from Audit.

**Success criteria:** Account ID recorded; baseline role exists; you can assume it from Identity Center or a management role.

---

## 53.15 Cost and quotas of a landing zone

Multi-account is not free:

- AWS Config per-Region per-account
- CloudTrail storage (org trail is cheaper than N trails, still not zero)
- GuardDuty per-account
- NAT in shared egress (centralized is usually cheaper than NAT per spoke)
- Control Tower and AFT pipeline minutes

FinOps: use **Cost Categories** mapped to OU and account tags. Budgets per account on vend. Sandbox SCPs denying `ec2:RunInstances` for instance families `g5`, `p4`, `p5` save more money than any rightsizing meeting.

Service quotas: request increases on **workload accounts**, not the management account. VPC and ENI quotas bite EKS first.

---

## 53.16 Anti-patterns

| Anti-pattern | Why it hurts | Do this instead |
|--------------|--------------|-----------------|
| Workloads in management account | SCPs do not apply; blast radius | Empty management |
| One SCP Deny `*` with random NotAction | Lockout | Canary OU, git, exemptions |
| IAM users in every account | Key sprawl | Identity Center |
| Editing Control Tower SCPs in console | Overwritten on repair | Separate custom SCPs |
| Unique snowflake accounts | Undocumented | AFT types |
| Sharing root credentials | Unrecoverable incidents | Hardware MFA, break-glass runbook |
| Default VPCs left everywhere | Accidental public EC2 | Delete + detective |

---

## 53.17 Mapping to Well-Architected and exams

SAA loves: "company wants isolation and centralized billing" → Organizations + linked accounts. DOP loves: StackSets, Control Tower, automated account vending, SCP vs IAM. Security Specialty loves: CloudTrail in log archive, GuardDuty admin, SCP cannot affect management account.

Interview answer in one breath: "We isolate by account, bind identity with Identity Center, constrain with SCPs and RCPs, vend through AFT, inspect traffic in a hub VPC, and never run apps in the management account."

---

## 53.18 Operating model after go-live

Landing zone is a product. Staff it:

- **Platform** owns Control Tower version, AFT, network hub, catalog portfolios.
- **Security** owns guardrail exceptions, delegated admin, detective remediation.
- **FinOps** owns cost categories and sandbox limits.
- **App teams** own workload accounts, not org policy.

Exception process: ticket → temporary SCP exemption with expiry (tag `exception-until`) → Config rule alerts if still present. Infinite exceptions are just an undocumented second landing zone.

---

## 53.19 Chapter checklist

- [ ] OU tree documented and reflected in Organizations.
- [ ] Management account workload-free.
- [ ] Identity Center permission sets, no standing IAM users.
- [ ] SCP pack in git, canary-tested.
- [ ] GuardDuty/Security Hub delegated to Audit.
- [ ] Org CloudTrail to Object Locked bucket.
- [ ] Account vending checklist automated.
- [ ] Region deny in place for unused Regions.
- [ ] Labs A and B completed.

Chapter 54 assumes this landing zone exists and asks a harder question: when a Region or account fails, which runbook do you execute, and how do you prove RPO/RTO with drills rather than slides.
