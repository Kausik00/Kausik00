# DevOps & AWS Learning Hub

Complete handbooks with **all chapters written** and downloadable PDFs.

The page numbers in each handbook **index match that PDF’s footer** (not estimates).

| Resource | Chapters | This edition | PDF |
|----------|----------|--------------|-----|
| [DevOps Handbook](./devops-handbook/00-table-of-contents.md) | 60 | **298 pages** | [devops-handbook.pdf](./pdf/devops-handbook.pdf) |
| [AWS Handbook](./aws-handbook/00-table-of-contents.md) | 41 | **214 pages** | [aws-handbook.pdf](./pdf/aws-handbook.pdf) |
| [DevOps Curriculum](./curriculum-devops.md) | reference | **9 pages** | [devops-curriculum.pdf](./pdf/devops-curriculum.pdf) |
| [AWS Curriculum](./curriculum-aws.md) | reference | **9 pages** | [aws-curriculum.pdf](./pdf/aws-curriculum.pdf) |
| Combined guide | all of the above | **531 pages** | [devops-aws-complete-guide.pdf](./pdf/devops-aws-complete-guide.pdf) |

## Download PDFs

Pre-built PDFs are in the [`pdf/`](./pdf/) folder. On GitHub: browse to the file and click **Download**.

| PDF | Description |
|-----|-------------|
| [devops-handbook.pdf](./pdf/devops-handbook.pdf) | 60 chapters, **298 pages** (index matches footer) |
| [aws-handbook.pdf](./pdf/aws-handbook.pdf) | 41 chapters, **214 pages** (index matches footer) |
| [devops-aws-complete-guide.pdf](./pdf/devops-aws-complete-guide.pdf) | All content, **531 pages** — see [combined index](./pdf/COMBINED-INDEX.md) |
| [devops-curriculum.pdf](./pdf/devops-curriculum.pdf) | DevOps tools & concepts (**9 pages**) |
| [aws-curriculum.pdf](./pdf/aws-curriculum.pdf) | AWS services list (**9 pages**) |

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
