# DevOps & AWS Learning Hub

Complete handbooks with **all chapters written** and downloadable PDFs.

| Resource | Chapters | PDF |
|----------|----------|-----|
| [DevOps Handbook](./devops-handbook/00-table-of-contents.md) | **60 chapters** (~1,200 pages planned) | [devops-handbook.pdf](./pdf/devops-handbook.pdf) (2.0 MB) |
| [AWS Handbook](./aws-handbook/00-table-of-contents.md) | **41 chapters** (~800 pages planned) | [aws-handbook.pdf](./pdf/aws-handbook.pdf) (1.4 MB) |
| [DevOps Curriculum](./curriculum-devops.md) | Tools & concepts reference | [devops-curriculum.pdf](./pdf/devops-curriculum.pdf) |
| [AWS Curriculum](./curriculum-aws.md) | Services reference | [aws-curriculum.pdf](./pdf/aws-curriculum.pdf) |
| **Combined guide** | Everything | [devops-aws-complete-guide.pdf](./pdf/devops-aws-complete-guide.pdf) (3.3 MB) |

## Download PDFs

Pre-built PDFs are in the [`pdf/`](./pdf/) folder. On GitHub: browse to the file and click **Download**.

| PDF | Description |
|-----|-------------|
| [devops-handbook.pdf](./pdf/devops-handbook.pdf) | Full DevOps handbook — 60 chapters |
| [aws-handbook.pdf](./pdf/aws-handbook.pdf) | Full AWS handbook — 41 chapters |
| [devops-aws-complete-guide.pdf](./pdf/devops-aws-complete-guide.pdf) | Curricula + both handbooks |
| [devops-curriculum.pdf](./pdf/devops-curriculum.pdf) | DevOps tools & concepts |
| [aws-curriculum.pdf](./pdf/aws-curriculum.pdf) | AWS services list |

**Rebuild PDFs** after editing markdown:

```bash
./scripts/build-pdfs.sh
```

Requires `pandoc` and `wkhtmltopdf`.

## Handbook coverage

### DevOps Handbook (60 chapters, 12 parts)

1. Introduction & Mindset
2. Linux & Shell
3. Git & Collaboration
4. Networking
5. Scripting & Programming
6. Infrastructure as Code (Terraform, Ansible, Packer)
7. Containers (Docker, Compose, registries)
8. Kubernetes (architecture, workloads, Helm, GitOps)
9. CI/CD (GitHub Actions, Jenkins, GitLab, DORA)
10. Observability & SRE (Prometheus, ELK, OpenTelemetry, chaos)
11. Security / DevSecOps (SAST, Vault, SBOM, Falco)
12. Advanced (platform engineering, FinOps, MLOps, capstone)

### AWS Handbook (41 chapters, 10 parts)

1. Cloud Foundations
2. IAM & Organizations
3. Networking (VPC, ALB, Route 53, TGW)
4. Compute (EC2, Lambda, ECS, EKS)
5. Storage (S3, EBS, EFS, Backup)
6. Databases (RDS, DynamoDB, ElastiCache)
7. Application Integration (API Gateway, SQS, Step Functions)
8. DevOps on AWS (CloudFormation, CDK, CodePipeline)
9. Observability (CloudWatch, X-Ray, CloudTrail)
10. Security & Well-Architected capstone

## Suggested study order

```
Linux + Git → Networking → Python/Bash → Terraform → Docker → Kubernetes
     → CI/CD → Observability → Security → AWS (parallel or after cloud basics)
```

Each chapter includes concepts, commands, examples, hands-on labs, and review questions.
