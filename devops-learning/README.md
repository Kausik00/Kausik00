# DevOps & AWS Learning Hub

A structured path from zero to advanced, plus two handbook series:

| Resource | Target size | Status |
|----------|-------------|--------|
| [DevOps Curriculum](./curriculum-devops.md) | Reference list | Complete |
| [AWS Curriculum](./curriculum-aws.md) | Reference list | Complete |
| [DevOps Handbook](./devops-handbook/00-table-of-contents.md) | ~1,200 pages | TOC + Part I–II written; Parts III–XII outlined |
| [AWS Handbook](./aws-handbook/00-table-of-contents.md) | ~800 pages | TOC + Part I–II written; Parts III–X outlined |

## Download PDFs

Pre-built PDFs are in the [`pdf/`](./pdf/) folder:

| PDF | Description |
|-----|-------------|
| [devops-handbook.pdf](./pdf/devops-handbook.pdf) | DevOps handbook — 11 chapters + full TOC |
| [aws-handbook.pdf](./pdf/aws-handbook.pdf) | AWS handbook — 11 chapters + full TOC |
| [devops-curriculum.pdf](./pdf/devops-curriculum.pdf) | DevOps tools & concepts reference |
| [aws-curriculum.pdf](./pdf/aws-curriculum.pdf) | AWS services reference |
| [devops-aws-complete-guide.pdf](./pdf/devops-aws-complete-guide.pdf) | All content in one PDF |

**Rebuild PDFs** after editing markdown:

```bash
./scripts/build-pdfs.sh
```

Requires `pandoc` and `wkhtmltopdf`.

---

1. **Start with the curricula** — they list every tool, concept, and AWS service in learning order.
2. **Follow the handbook TOCs** — each chapter has a page budget; work through sequentially.
3. **Expand on demand** — ask an AI assistant or instructor to flesh out any chapter number from the TOC.

## Suggested study pace

| Phase | Duration (self-paced) | Focus |
|-------|----------------------|-------|
| Foundations | 4–8 weeks | Linux, Git, networking, scripting |
| Core DevOps | 8–12 weeks | CI/CD, containers, IaC, cloud basics |
| Intermediate | 8–12 weeks | Kubernetes, observability, security |
| Advanced | 12+ weeks | SRE, platform engineering, multi-cloud, FinOps |

## Page convention

Each handbook "page" ≈ 400 words of instructional content + diagrams/commands. Labs and exercises add extra pages in the TOC estimates.
