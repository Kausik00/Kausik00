# Chapter 41: Well-Architected Review & Capstone Design

*AWS Handbook — Part X, Pages 791–800*

---

## 41.1 The AWS Well-Architected Framework

Throughout this handbook, we have covered individual AWS services and patterns. The **AWS Well-Architected Framework** ties everything together into six pillars that define what "good" cloud architecture looks like. This capstone chapter applies the framework to a realistic design exercise, demonstrating how to evaluate and improve an architecture holistically.

---

## 41.2 The six pillars

| Pillar | Focus | Key questions |
|--------|-------|---------------|
| **Operational Excellence** | Run and monitor systems | Can you deploy, respond to events, and improve? |
| **Security** | Protect information and systems | Is data protected? Are threats detected? |
| **Reliability** | Recover from failures | Can the system recover and meet demand? |
| **Performance Efficiency** | Use resources efficiently | Is the right technology used at the right scale? |
| **Cost Optimization** | Avoid unnecessary costs | Are you paying only for what you need? |
| **Sustainability** | Minimize environmental impact | Are resources used efficiently to reduce carbon? |

---

## 41.3 Capstone scenario

Design a **multi-tier e-commerce platform** with these requirements:

| Requirement | Detail |
|-------------|--------|
| **Traffic** | 10,000 concurrent users; 1M orders/month |
| **Availability** | 99.95% uptime SLA |
| **Data** | Customer PII, payment references (PCI scope) |
| **Regions** | Primary: us-east-1; DR: eu-west-1 |
| **Team** | 5 developers, 2 DevOps engineers |
| **Budget** | Optimize for cost without sacrificing reliability |

---

## 41.4 Proposed architecture

```
                        ┌─────────────────────────────────┐
                        │         Route 53 (DNS)           │
                        │    Latency routing + failover    │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │   CloudFront + WAF + Shield      │
                        │   (static assets + API cache)    │
                        └──────────────┬──────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │  us-east-1       │    │  us-east-1       │    │  eu-west-1       │
     │  ALB (public)    │    │  API Gateway     │    │  (DR standby)    │
     └────────┬────────┘    └────────┬────────┘    └─────────────────┘
              │                        │
     ┌────────▼────────┐    ┌─────────▼────────┐
     │  ECS Fargate     │    │  Lambda           │
     │  (web frontend)  │    │  (order API)      │
     └─────────────────┘    └─────────┬────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │ Aurora PostgreSQL│    │  DynamoDB        │    │  ElastiCache     │
     │ (Multi-AZ)       │    │  (sessions/cart) │    │  Redis (cache)   │
     └─────────────────┘    └─────────────────┘    └─────────────────┘
              │
     ┌────────▼────────┐
     │  SQS → Lambda    │
     │  (order process) │
     └─────────┬────────┘
               ▼
     ┌─────────────────┐
     │  SNS → email/SMS │
     │  (notifications) │
     └─────────────────┘
```

---

## 41.5 Pillar-by-pillar review

### Operational Excellence

| Design decision | Rationale |
|-----------------|-----------|
| Infrastructure as Code (CDK) | Reproducible environments; version-controlled |
| CI/CD via CodePipeline | Automated testing and deployment |
| CloudWatch dashboards + alarms | Centralized monitoring |
| Runbooks in Systems Manager | Documented incident response |
| ECS Exec for debugging | No SSH bastion needed |

**Review questions:**
- [ ] Are deployments automated with rollback capability?
- [ ] Are runbooks documented for common incidents?
- [ ] Is infrastructure defined in code (not console clicks)?
- [ ] Are changes tracked in version control?

### Security

| Design decision | Rationale |
|-----------------|-----------|
| IAM Identity Center for human access | Centralized SSO, MFA, audit |
| Private subnets for all compute/data | No direct internet exposure |
| KMS encryption (RDS, S3, DynamoDB, EBS) | Data at rest protection |
| Secrets Manager for DB credentials | Automatic rotation |
| WAF + Shield on CloudFront | OWASP protection, DDoS mitigation |
| GuardDuty + Security Hub | Threat detection and compliance |
| CloudTrail organization trail | API audit logging |
| VPC endpoints for AWS services | No internet traversal for API calls |
| PCI scope reduction | No card data stored; tokenization via payment provider |

**Review questions:**
- [ ] Is all data encrypted at rest and in transit?
- [ ] Are security groups following least-privilege (SG references)?
- [ ] Is GuardDuty enabled with automated response?
- [ ] Are secrets rotated automatically?
- [ ] Is the root account secured with MFA and not used daily?

### Reliability

| Design decision | Rationale |
|-----------------|-----------|
| Multi-AZ Aurora | Automatic failover (< 30 seconds) |
| ECS Fargate across 3 AZs | Container-level HA |
| ALB health checks | Unhealthy targets removed automatically |
| SQS with DLQ | Order processing resilience |
| Aurora Global Database (DR) | Cross-region failover capability |
| Auto Scaling (ECS + Aurora Serverless) | Handle traffic spikes |
| Route 53 health checks + failover | DNS-level DR |
| AWS Backup for RDS and EBS | Point-in-time recovery |

**Review questions:**
- [ ] Are all tiers deployed across multiple AZs?
- [ ] Is there a tested DR plan with defined RTO/RPO?
- [ ] Are health checks configured on all load balancers?
- [ ] Do async workflows use DLQs?
- [ ] Has failover been tested in the last 6 months?

### Performance Efficiency

| Design decision | Rationale |
|-----------------|-----------|
| CloudFront CDN | Static asset caching at edge |
| ElastiCache Redis | Database query caching |
| DynamoDB on-demand | Auto-scaling for cart/session data |
| Aurora Serverless v2 for variable load | Right-size database compute |
| Lambda for spiky order processing | Scale to zero, pay per request |
| Graviton instances (ARM) where supported | 20% better price-performance |

**Review questions:**
- [ ] Is caching used at multiple layers (CDN, application, database)?
- [ ] Are instance types right-sized based on metrics?
- [ ] Is serverless used for variable/spiky workloads?
- [ ] Are Graviton instances evaluated for cost savings?

### Cost Optimization

| Design decision | Rationale |
|-----------------|-----------|
| Fargate (no idle EC2) | Pay per task, not per instance |
| Aurora Serverless v2 | Scale down during off-peak |
| S3 lifecycle policies | Move old data to IA/Glacier |
| Reserved capacity for baseline | Savings Plans for predictable compute |
| CloudWatch cost anomaly detection | Alert on unexpected spend |
| Right-sizing reviews quarterly | Identify over-provisioned resources |

**Estimated monthly cost (simplified):**

| Service | Estimate |
|---------|----------|
| ECS Fargate (4 tasks) | $120 |
| Aurora Serverless v2 (2-8 ACU) | $200 |
| DynamoDB on-demand | $50 |
| ElastiCache (cache.r6g.large) | $150 |
| CloudFront + WAF | $100 |
| Lambda + API Gateway | $30 |
| Other (S3, SQS, SNS, monitoring) | $50 |
| **Total** | **~$700/month** |

**Review questions:**
- [ ] Are unused resources identified and removed?
- [ ] Are Savings Plans or Reserved Instances used for baseline?
- [ ] Are S3 lifecycle policies configured?
- [ ] Is cost allocation tagging enforced?

### Sustainability

| Design decision | Rationale |
|-----------------|-----------|
| Graviton (ARM) instances | Lower energy per computation |
| Serverless (Lambda, Fargate) | No idle resource waste |
| S3 lifecycle to IA/Glacier | Reduce storage energy footprint |
| Right-sizing | Fewer resources = less energy |
| Region selection | Choose regions with renewable energy commitment |

---

## 41.6 Well-Architected Tool review process

AWS provides a free **Well-Architected Tool** in the console:

1. **Create a workload** — Define the architecture scope.
2. **Answer pillar questions** — ~50 questions across six pillars.
3. **Review risks** — High and medium risks identified with remediation guidance.
4. **Improve** — Implement changes and re-review.

```bash
# Well-Architected Tool is console-based; use the API for automation
aws wellarchitected create-workload \
  --workload-name "E-Commerce Platform" \
  --description "Production e-commerce workload" \
  --environment PRODUCTION \
  --lenses "wellarchitected" \
  --review-owner "platform-team@example.com" \
  --aws-regions us-east-1 eu-west-1
```

### Review cadence

| Trigger | Action |
|---------|--------|
| New workload launch | Initial review before production |
| Major architecture change | Re-review affected pillars |
| Quarterly | Scheduled review of all production workloads |
| Post-incident | Review reliability and operational excellence |

---

## 41.7 Anti-patterns to avoid

| Anti-pattern | Risk | Fix |
|--------------|------|-----|
| Single AZ deployment | AZ failure = outage | Multi-AZ everything |
| Public RDS/EC2 | Data breach | Private subnets + SG references |
| Root account for daily work | Credential compromise | IAM Identity Center |
| No monitoring/alarms | Silent failures | CloudWatch alarms on all tiers |
| Manual deployments | Human error, slow recovery | CI/CD pipeline |
| Hardcoded secrets | Credential leak | Secrets Manager |
| No backup testing | Backup exists but doesn't restore | Quarterly DR drills |
| Over-permissive IAM | Privilege escalation | Least privilege + SCPs |
| Ignoring costs until bill arrives | Budget overrun | Budgets + anomaly detection |

---

## 41.8 Handbook journey recap

| Part | Topics covered |
|------|----------------|
| **I — Foundations** | Shared responsibility, global infrastructure, CLI, billing |
| **II — IAM** | Users, roles, policies, Identity Center, Organizations, SCPs |
| **III — Networking** | VPC, NAT, security groups, NACLs, ALB/NLB, Route 53, TGW |
| **IV — Compute** | EC2, Auto Scaling, Lambda, ECS, EKS |
| **V — Storage** | S3, EBS, EFS, backup and DR |
| **VI — Databases** | RDS, Aurora, DynamoDB, ElastiCache, DMS |
| **VII — Integration** | API Gateway, SQS/SNS/EventBridge, Step Functions |
| **VIII — DevOps** | CloudFormation, CDK, CodePipeline, Systems Manager |
| **IX — Observability** | CloudWatch, Logs Insights, X-Ray, CloudTrail, Config |
| **X — Security** | KMS, Secrets Manager, ACM, GuardDuty, WAF, Shield |

---

## 41.9 Chapter summary

- The **Well-Architected Framework** provides six pillars for evaluating cloud architectures.
- Apply the framework systematically: design, review, improve, repeat.
- The capstone e-commerce design demonstrates multi-pillar thinking in practice.
- Use the **Well-Architected Tool** for structured reviews with risk identification.
- Avoid common **anti-patterns** that compromise security, reliability, and cost.

---

## 🧪 Lab 41.1 — Well-Architected review

1. Open the AWS Well-Architected Tool in the console.
2. Create a workload for a project you have built (or the capstone design).
3. Complete the review for all six pillars.
4. Document the top 5 high-risk items and propose remediation.

## 🧪 Lab 41.2 — Architecture documentation

1. Draw the architecture diagram for your capstone (or real project).
2. Annotate each component with its pillar contributions.
3. Identify one improvement per pillar.
4. Estimate the cost impact of each improvement.

---

## Review questions

1. Name the six Well-Architected Framework pillars.
2. What is the target availability of 99.95% in downtime per year?
3. How does the capstone design address the security pillar?
4. Why should Well-Architected reviews be repeated after major changes?
5. What is the most common anti-pattern you have seen in AWS environments?

---

## Final thoughts

You have completed the AWS Handbook—from cloud foundations through security and compliance. The AWS ecosystem evolves continuously; subscribe to AWS blogs, re:Invent sessions, and service announcements to stay current. The Well-Architected Framework is your compass for every new design decision.

Build securely. Automate everything. Monitor relentlessly. Review regularly.

*— End of AWS Handbook —*
