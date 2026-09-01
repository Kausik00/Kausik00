# Chapter 29: Container Registries and Image Signing

*DevOps Handbook — Part VII, Pages 541–560*

---

## 29.1 Container registries overview

A **container registry** stores and distributes OCI-compatible **images** (manifests + layers). Registries are the artifact hub of the container supply chain—CI pushes images; clusters pull them to run workloads.

| Registry | Provider | Notes |
|----------|----------|-------|
| **Docker Hub** | Docker | Public default; rate limits on anonymous pulls |
| **Amazon ECR** | AWS | IAM auth, image scanning, lifecycle policies |
| **Google Artifact Registry** | GCP | Multi-format (Docker, npm, maven) |
| **Azure ACR** | Azure | Geo-replication, content trust |
| **GitHub Container Registry (GHCR)** | GitHub | `ghcr.io/org/image` |
| **Harbor** | CNCF / self-hosted | RBAC, replication, signing |

Images are referenced by **tag** (`myapp:1.2.3`) or immutable **digest** (`myapp@sha256:abc123...`). Prefer digests in production manifests for immutability.

---

## 29.2 Image naming and tagging strategy

```
<registry>/<namespace>/<repository>:<tag>
ghcr.io/acme-corp/payments-api:v1.4.2
123456789.dkr.ecr.us-east-1.amazonaws.com/web:main-abc1234
```

Tagging conventions:

| Tag pattern | Use |
|-------------|-----|
| `v1.2.3` | Release semver |
| `main-abc1234` | Git SHA from branch |
| `1.2.3-alpine` | Base OS variant |
| `latest` | Dev only—never prod deploy target |

**Never** reuse tags for different content. CI should push unique tags per build; promotion means updating deployment to point at a tested tag/digest.

---

## 29.3 Authenticating to registries

### Amazon ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag myapp:1.0 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:1.0
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:1.0
```

Create repository with Terraform:

```hcl
resource "aws_ecr_repository" "myapp" {
  name                 = "myapp"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "myapp" {
  repository = aws_ecr_repository.myapp.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 30 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}
```

### GHCR

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
docker tag myapp:1.0 ghcr.io/acme-corp/myapp:1.0
docker push ghcr.io/acme-corp/myapp:1.0
```

Use fine-grained PAT or `GITHUB_TOKEN` in Actions with `packages: write` permission.

---

## 29.4 Pull policies in Kubernetes and beyond

```yaml
spec:
  containers:
    - name: api
      image: 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.4.2@sha256:deadbeef...
      imagePullPolicy: IfNotPresent
```

| `imagePullPolicy` | Behavior |
|-------------------|----------|
| `Always` | Pull every pod start (required for `:latest`) |
| `IfNotPresent` | Pull if not cached locally |
| `Never` | Local only (kind/minikube dev) |

Private registries need **imagePullSecrets** or cloud-specific workload identity (EKS, GKE).

---

## 29.5 Vulnerability scanning

Scan on push and on schedule:

```bash
trivy image ghcr.io/acme-corp/myapp:1.0
aws ecr describe-image-scan-findings \
  --repository-name myapp \
  --image-id imageTag=1.0
```

CI gate example:

```yaml
- name: Build and push
  run: |
    docker build -t ghcr.io/acme-corp/myapp:${{ github.sha }} .
    docker push ghcr.io/acme-corp/myapp:${{ github.sha }}

- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/acme-corp/myapp:${{ github.sha }}
    severity: CRITICAL,HIGH
    exit-code: 1
```

Maintain **SBOMs** (Software Bill of Materials) with `syft` or `trivy sbom` for compliance and faster CVE matching.

---

## 29.6 Image signing and verification

Signing proves an image was built by a trusted pipeline and was not tampered with in transit or at rest in the registry.

### Docker Content Trust (Notary v1)

Legacy; being superseded by **Sigstore/cosign** in most ecosystems.

### Cosign (Sigstore)

```bash
# Generate key pair (prefer keyless in CI with OIDC)
cosign generate-key-pair

# Sign after push
cosign sign --key cosign.key ghcr.io/acme-corp/myapp:1.0

# Verify before deploy
cosign verify --key cosign.pub ghcr.io/acme-corp/myapp:1.0
```

**Keyless signing** in GitHub Actions:

```yaml
permissions:
  id-token: write
  contents: read
  packages: write

- uses: sigstore/cosign-installer@main
- run: cosign sign ghcr.io/acme-corp/myapp@${{ steps.build.outputs.digest }}
  env:
    COSIGN_EXPERIMENTAL: "true"
```

Attach **SBOM** as attestation:

```bash
syft ghcr.io/acme-corp/myapp:1.0 -o spdx-json > sbom.spdx.json
cosign attest --predicate sbom.spdx.json --type spdx ghcr.io/acme-corp/myapp:1.0
```

### Policy enforcement

**Kyverno** verifyImages policy:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-signed-images
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-signature
      match:
        any:
          - resources:
              kinds: [Pod]
      verifyImages:
        - imageReferences: ["ghcr.io/acme-corp/*"]
          attestors:
            - entries:
                - keyless:
                    subject: "https://github.com/acme-corp/myapp/.github/workflows/release.yml@refs/heads/main"
                    issuer: "https://token.actions.githubusercontent.com"
```

Unsigned images are rejected at admission.

---

## 29.7 Registry operations

### Mirroring and air-gapped pulls

Harbor and pull-through caches proxy Docker Hub to avoid rate limits and enable offline clusters.

### Replication

Harbor and cloud registries replicate images across regions for disaster recovery and faster pulls.

### Retention and garbage collection

Untagged manifests accumulate storage costs. Lifecycle policies expire old SHAs; run registry GC during maintenance windows.

### RBAC

| Role | Typical permissions |
|------|---------------------|
| CI robot | Push to specific repos |
| Cluster nodes | Pull only |
| Developers | Pull dev; no prod push |
| Security | Scan, quarantine, delete |

---

## 29.8 Supply chain best practices

1. **Pin base images** by digest in Dockerfile
2. **Build in CI** — developers do not push local images to prod registry
3. **Sign every release** artifact
4. **Verify signatures** in deploy pipeline and admission controller
5. **Immutable tags** on production repositories
6. **Separate registries** or repos per environment (dev vs prod)
7. **Audit logs** — who pushed/pulled what and when

---

## 29.9 Chapter summary

- Registries are the **distribution hub** for container images; use structured tagging and immutability.
- Authenticate with **short-lived tokens** (ECR, OIDC) rather than long-lived passwords.
- **Scan** images in CI and block critical CVEs; generate **SBOMs** for traceability.
- **Sign** images with Cosign; **verify** at deploy time and with admission policies.
- Apply **lifecycle policies** to control storage and reduce attack surface from stale images.

---

## 🧪 Lab 29.1

1. Create an ECR or GHCR repository and push an image from CI.
2. Enable scan-on-push and review findings for one image.
3. Tag images with Git SHA and semver; deploy using digest in a K8s manifest.

---

## 🧪 Lab 29.2

1. Sign an image with Cosign (keyless or key pair).
2. Verify the signature in a deploy script before `kubectl apply`.
3. Write a lifecycle policy retaining the last 20 images.

---

## Review questions

1. Why should production deployments reference digests instead of mutable tags?
2. What is the difference between image signing and vulnerability scanning?
3. How does ECR authentication differ from Docker Hub username/password?
4. What does an immutable tag policy prevent?
5. Where in the pipeline should unsigned images be rejected?

---

*Next: [Chapter 30 — Rootless Containers and Podman](./chapter-30-rootless-podman.md)*
