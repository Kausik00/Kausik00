# AWS Cloud Curriculum: Services & Tools (Beginner → Advanced)

All major AWS services grouped by domain, with learning priority.

**Legend:** ★ = core (learn first) · ◆ = intermediate · ◇ = advanced/specialized

---

## 1. Account, Identity & Governance ★

| Service / Tool | Purpose |
|----------------|---------|
| **AWS Organizations** ★ | Multi-account structure, SCPs |
| **IAM** ★ | Users, groups, roles, policies, MFA |
| **IAM Identity Center (SSO)** ★ | Workforce federation, permission sets |
| **AWS Control Tower** ◆ | Landing zone automation |
| **AWS Config** ◆ | Resource compliance & history |
| **AWS CloudTrail** ★ | API audit logging |
| **AWS Service Catalog** ◇ | Governed self-service provisioning |
| **AWS Resource Access Manager (RAM)** ◆ | Cross-account resource sharing |
| **AWS Account Factory** ◆ | Automated account vending (Control Tower) |
| **AWS CLI / CloudShell** ★ | Command-line & browser shell |
| **AWS Management Console** ★ | Web UI |
| **AWS CloudFormation** ★ | Infrastructure as Code (native) |
| **AWS CDK** ◆ | IaC in TypeScript/Python/etc. |
| **Terraform + AWS Provider** ★ | Industry-standard IaC |
| **AWS Tagging & Resource Groups** ★ | Cost & ops organization |

### Concepts
- Shared responsibility model
- Root account hygiene (MFA, no daily use)
- Least privilege & permission boundaries
- SCP vs IAM policy
- Cross-account roles & assume-role
- AWS global vs regional services

---

## 2. Networking & Content Delivery ★

| Service | Purpose |
|---------|---------|
| **VPC** ★ | Virtual network, subnets, route tables |
| **Internet Gateway / NAT Gateway** ★ | Public & private egress |
| **VPC Endpoints (Gateway & Interface)** ◆ | Private AWS API access |
| **Security Groups & NACLs** ★ | Stateful vs stateless firewalls |
| **Elastic IP** ★ | Static public IPs |
| **Route 53** ★ | DNS, health checks, routing policies |
| **CloudFront** ★ | CDN, edge caching |
| **ALB / NLB / GWLB** ★ | Layer 7, 4, and gateway load balancers |
| **VPC Peering / Transit Gateway** ◆ | Inter-VPC & hybrid connectivity |
| **AWS VPN / Direct Connect** ◆ | On-prem hybrid networking |
| **PrivateLink** ◆ | Private service exposure |
| **AWS Global Accelerator** ◇ | Anycast for global apps |
| **Route 53 Resolver** ◆ | Hybrid DNS |
| **AWS Network Firewall** ◇ | Managed perimeter firewall |
| **VPC Lattice** ◇ | Service-to-service networking |

### Tools
- **Reachability Analyzer**, **VPC Flow Logs**, **Traffic Mirroring**

---

## 3. Compute ★

| Service | Purpose |
|---------|---------|
| **EC2** ★ | Virtual machines, AMIs, instance types |
| **Auto Scaling Groups** ★ | Horizontal scaling |
| **Elastic Beanstalk** ◆ | PaaS for web apps |
| **Lambda** ★ | Serverless functions |
| **ECS / Fargate** ★ | Container orchestration (AWS-native) |
| **EKS** ★ | Managed Kubernetes |
| **AWS Batch** ◆ | Batch/HPC jobs |
| **Lightsail** ◆ | Simplified VPS |
| **App Runner** ◆ | Container PaaS |
| **EC2 Image Builder** ◆ | Automated AMI pipelines |
| **AWS Outposts / Wavelength / Local Zones** ◇ | Edge & hybrid compute |
| **Serverless Application Repository** ◇ | Share Lambda apps |

### Tools
- **AWS Systems Manager** (Session Manager, Run Command, Patch Manager)
- **EC2 Instance Connect**

---

## 4. Storage ★

| Service | Purpose |
|---------|---------|
| **S3** ★ | Object storage, versioning, lifecycle |
| **EBS** ★ | Block storage for EC2 |
| **EFS** ◆ | Managed NFS |
| **FSx** ◆ | Windows/Lustre/ONTAP/OpenZFS file systems |
| **S3 Glacier** ◆ | Archive tiers |
| **Storage Gateway** ◇ | Hybrid storage |
| **AWS Backup** ◆ | Centralized backup |
| **DataSync / Transfer Family** ◆ | Large data migration |

### Concepts
- Storage classes (S3 Standard, IA, Glacier)
- Encryption at rest (SSE-S3, SSE-KMS, SSE-C)
- S3 bucket policies vs ACLs
- EBS volume types (gp3, io2, st1)

---

## 5. Databases ★

| Service | Purpose |
|---------|---------|
| **RDS** ★ | Managed MySQL, PostgreSQL, MariaDB, Oracle, SQL Server |
| **Aurora** ★ | AWS-native relational, serverless option |
| **DynamoDB** ★ | Serverless NoSQL key-value/document |
| **ElastiCache** ◆ | Redis / Memcached |
| **DocumentDB** ◆ | MongoDB-compatible |
| **Neptune** ◇ | Graph database |
| **Timestream** ◇ | Time-series |
| **Keyspaces** ◇ | Cassandra-compatible |
| **Redshift** ◆ | Data warehouse |
| **QLDB** ◇ | Ledger database |
| **MemoryDB for Redis** ◆ | Durable Redis |
| **RDS Proxy** ◆ | Connection pooling |

---

## 6. Application Integration & Messaging ★

| Service | Purpose |
|---------|---------|
| **SQS** ★ | Managed message queues |
| **SNS** ★ | Pub/sub notifications |
| **EventBridge** ★ | Event bus, scheduling |
| **Step Functions** ◆ | Workflow orchestration |
| **MQ** ◆ | Managed ActiveMQ/RabbitMQ |
| **AppSync** ◆ | GraphQL API |
| **API Gateway** ★ | REST/WebSocket/HTTP APIs |

---

## 7. Developer Tools & CI/CD ★

| Service | Purpose |
|---------|---------|
| **CodeCommit** ◆ | Git repos (legacy; many use GitHub) |
| **CodeBuild** ★ | Managed build |
| **CodeDeploy** ◆ | Deployment automation |
| **CodePipeline** ★ | CI/CD orchestration |
| **CodeArtifact** ◆ | Package repository |
| **Cloud9** ◆ | Cloud IDE |
| **CDK / SAM / Copilot** ◆ | IaC & serverless/container tooling |
| **X-Ray** ◆ | Distributed tracing |
| **CloudWatch Synthetics** ◆ | Canary monitoring |

---

## 8. Observability & Management ★

| Service | Purpose |
|---------|---------|
| **CloudWatch** ★ | Metrics, alarms, dashboards, logs |
| **CloudWatch Logs Insights** ★ | Log query |
| **AWS X-Ray** ◆ | Tracing |
| **Systems Manager** ★ | Ops hub (Parameter Store, Patch, Session) |
| **CloudTrail** ★ | Audit |
| **AWS Health Dashboard** ★ | Service events |
| **Trusted Advisor** ◆ | Best-practice checks |
| **Personal Health Dashboard** ★ | Account-specific events |
| **Service Quotas** ◆ | Limit management |
| **OpsWorks** ◇ | Legacy Chef/Puppet (avoid for new projects) |

---

## 9. Security, Identity & Compliance ★

| Service | Purpose |
|---------|---------|
| **IAM** ★ | (see section 1) |
| **KMS** ★ | Encryption key management |
| **Secrets Manager** ★ | Rotating secrets |
| **Certificate Manager (ACM)** ★ | TLS certificates |
| **WAF & Shield** ◆ | Web firewall & DDoS |
| **GuardDuty** ★ | Threat detection |
| **Inspector** ◆ | Vulnerability scanning |
| **Macie** ◆ | S3 data classification |
| **Security Hub** ◆ | Central security findings |
| **Detective** ◇ | Security investigation |
| **Firewall Manager** ◆ | Central WAF/rule management |
| **Artifact** ◆ | Compliance reports |
| **Audit Manager** ◇ | Continuous audit evidence |
| **CloudHSM** ◇ | Dedicated HSM |
| **Cognito** ◆ | User pools & identity for apps |
| **Verified Permissions** ◇ | Cedar policy engine |
| **IAM Access Analyzer** ◆ | External access findings |

---

## 10. Migration & Transfer ◆

| Service | Purpose |
|---------|---------|
| **Migration Hub** | Migration tracking |
| **Application Migration Service (MGN)** | Lift-and-shift |
| **Database Migration Service (DMS)** | DB replication |
| **Server Migration Service** | (legacy → MGN) |
| **Transfer Family** | SFTP/FTPS/FTP to S3 |
| **Snow Family** | Physical data transfer appliances |

---

## 11. Analytics & Big Data ◆

| Service | Purpose |
|---------|---------|
| **Athena** ◆ | SQL on S3 |
| **Glue** ◆ | ETL & data catalog |
| **EMR** ◆ | Hadoop/Spark |
| **Kinesis** ◆ | Streaming (Data Streams, Firehose, Analytics) |
| **QuickSight** ◆ | BI dashboards |
| **Lake Formation** ◆ | Data lake governance |
| **MSK** ◆ | Managed Kafka |
| **OpenSearch Service** ◆ | Search & analytics (Elasticsearch fork) |
| **Data Pipeline** ◇ | Legacy orchestration |
| **Clean Rooms** ◇ | Privacy-preserving analytics |

---

## 12. Machine Learning & AI ◇

| Service | Purpose |
|---------|---------|
| **SageMaker** ◇ | End-to-end ML platform |
| **Bedrock** ◇ | Foundation models API |
| **Comprehend / Rekognition / Textract / Polly / Transcribe** ◇ | AI APIs |
| **Forecast / Personalize / Kendra** ◇ | Specialized ML |
| **CodeWhisperer / Q Developer** ◆ | AI-assisted development |

---

## 13. IoT, Media & Specialized ◇

| Service | Purpose |
|---------|---------|
| **IoT Core / Greengrass** | Device connectivity |
| **MediaConvert / Live / Package** | Video processing |
| **GameLift** | Game server hosting |
| **WorkSpaces / AppStream** | Virtual desktops |
| **Connect** | Contact center |

---

## 14. Cost & Billing ★

| Service / Tool | Purpose |
|----------------|---------|
| **Cost Explorer** ★ | Spend analysis |
| **Budgets** ★ | Alerts & limits |
| **Cost & Usage Report (CUR)** ◆ | Detailed billing export |
| **Pricing Calculator** ★ | Estimate costs |
| **Savings Plans / Reserved Instances** ◆ | Commitment discounts |
| **Compute Optimizer** ◆ | Right-sizing recommendations |
| **Billing Conductor** ◇ | Reseller/MSP billing |

### Concepts
- Pay-as-you-go vs reserved vs spot
- Tagging strategy for cost allocation
- FinOps culture & unit economics

---

## 15. Well-Architected Framework (conceptual ★)

Six pillars — learn alongside every service:

1. **Operational Excellence** — run & monitor systems
2. **Security** — protect data & assets
3. **Reliability** — recover from failure
4. **Performance Efficiency** — use resources well
5. **Cost Optimization** — avoid unnecessary spend
6. **Sustainability** — minimize environmental impact

**Tool:** AWS Well-Architected Tool (workload reviews)

---

## Certification path (recommended order)

| Order | Certification | Focus |
|-------|---------------|-------|
| 1 | **Cloud Practitioner (CLF)** | Broad AWS vocabulary |
| 2 | **Solutions Architect Associate (SAA)** | Design & core services |
| 3 | **Developer Associate (DVA)** | CI/CD, serverless, APIs |
| 4 | **SysOps Administrator (SOA)** | Operations & monitoring |
| 5 | **DevOps Engineer Professional (DOP)** | Advanced CI/CD & automation |
| 6 | **Solutions Architect Professional (SAP)** | Complex multi-account design |
| 7 | **Security Specialty** | Deep security services |
| 8 | **Networking Specialty** | VPC, hybrid, TGW |

---

## Hands-on lab progression

1. Create IAM user, MFA, CLI profile
2. VPC with public/private subnets + NAT
3. EC2 + ALB + Auto Scaling
4. S3 static site + CloudFront + Route 53
5. RDS Multi-AZ + Secrets Manager
6. Lambda + API Gateway + DynamoDB
7. ECS Fargate or EKS cluster with CI/CD
8. CloudWatch dashboards + alarms + X-Ray
9. Terraform modules for reusable infra
10. Multi-account landing zone (Organizations + Control Tower)
