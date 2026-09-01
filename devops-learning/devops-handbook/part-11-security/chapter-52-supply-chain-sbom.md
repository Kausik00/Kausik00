# Chapter 52: Supply Chain Security — SBOM, Sigstore, SLSA

*DevOps Handbook — Part XI, Pages 1021–1040*

---

## 52.1 Software supply chain threats

Modern software is assembled from thousands of components—open-source libraries, base images, CI plugins, Terraform modules. Attackers target the **supply chain** because compromising one dependency affects thousands of downstream users.

Notable incidents:

| Incident | Mechanism |
|----------|-----------|
| **SolarWinds (2020)** | Build system compromise, trojanized updates |
| **Log4Shell (2021)** | Ubiquitous vulnerable dependency |
| **Codecov (2021)** | CI script compromise exfiltrating secrets |
| **npm package typosquatting** | Malicious packages mimicking popular names |
| **3CX (2023)** | Signed malware in legitimate software update |

**Supply chain security** verifies **provenance** (where artifacts came from), **integrity** (unchanged since build), and **trust** (who built and signed).

---

## 52.2 SBOM — Software Bill of Materials

An **SBOM** is a machine-readable inventory of components in a software artifact—like nutrition labels for code.

| Format | Maintainer |
|--------|------------|
| **CycloneDX** | OWASP / ECMA standard |
| **SPDX** | Linux Foundation ISO standard |

SBOM enables:

- Rapid CVE response ("are we affected by CVE-2024-XXXX?")
- License compliance audits
- Vendor risk assessment
- Regulatory requirements (US EO 14028, EU CRA)

Generate SBOM with **Syft**:

```bash
# Filesystem
syft dir:. -o cyclonedx-json > sbom.json

# Container image
syft registry.example.com/myapp:v1.2.3 -o spdx-json > sbom.spdx.json

# Attach to image attestation
syft attest registry.example.com/myapp:v1.2.3 -o cyclonedx-json
```

CI integration:

```yaml
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    image: myapp:${{ github.sha }}
    format: cyclonedx-json
    output-file: sbom.cdx.json

- name: Upload SBOM artifact
  uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.cdx.json
```

Store SBOMs alongside artifacts in registry (OCI referrer) or artifact repository—queryable when new CVEs emerge.

**VEX** (Vulnerability Exploitability eXchange) documents why listed CVEs are not exploitable in context—reduces false panic.

---

## 52.3 SLSA — supply chain levels

**SLSA** (Supply-chain Levels for Software Artifacts) defines progressive security levels for build pipelines.

| Level | Requirements (summary) |
|-------|------------------------|
| **SLSA 1** | Provenance exists (build documented) |
| **SLSA 2** | Hosted build service, signed provenance |
| **SLSA 3** | Hardened build platform, non-falsifiable provenance |
| **SLSA 4** | Two-person review, reproducible builds |

Provenance attestation (conceptual):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{"name": "myapp:v1.2.3", "digest": {"sha256": "abc..."}}],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://github.com/Attestations/GitHubActionsWorkflow@v1",
      "externalParameters": {
        "workflow": {"ref": "refs/heads/main", "repository": "https://github.com/org/myapp"}
      }
    },
    "runDetails": {
      "builder": {"id": "https://github.com/org/myapp/.github/workflows/build.yml@refs/heads/main"},
      "metadata": {"invocationId": "1234567890"}
    }
  }
}
```

GitHub Actions can generate SLSA provenance with **slsa-github-generator** workflow.

---

## 52.4 Sigstore and cosign

**Sigstore** provides free, automated code signing and verification—**cosign** signs container images and blobs; **Fulcio** issues short-lived certificates bound to OIDC identity; **Rekor** is transparency log.

Sign image after build:

```bash
# Keyless signing (OIDC identity from CI)
cosign sign registry.example.com/myapp:v1.2.3

# Verify
cosign verify registry.example.com/myapp:v1.2.3 \
  --certificate-identity-regexp="https://github.com/myorg/myapp/.github/workflows/.*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

GitHub Actions:

```yaml
- name: Install cosign
  uses: sigstore/cosign-installer@v3

- name: Sign image
  run: cosign sign --yes registry.example.com/myapp:${{ github.sha }}
  env:
    COSIGN_EXPERIMENTAL: "true"
```

**Kubernetes admission** — Verify signatures before deploy:

```yaml
# Policy Controller / Kyverno verifyImages
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-signed-images
spec:
  validationFailureAction: Enforce
  rules:
    - name: verify-cosign-signature
      match:
        any:
          - resources:
              kinds: [Pod]
      verifyImages:
        - imageReferences:
            - "registry.example.com/myapp:*"
          attestors:
            - count: 1
              entries:
                - keyless:
                    subject: "https://github.com/myorg/myapp/.github/workflows/*"
                    issuer: "https://token.actions.githubusercontent.com"
```

Only signed images from trusted CI workflows deploy to production.

---

## 52.5 Dependency and build hardening

| Control | Implementation |
|---------|----------------|
| **Pin dependencies** | Lock files, digest-pinned base images |
| **Verify checksums** | npm/yarn integrity, Go sum |
| **Private registry proxy** | Pull-through cache, vulnerability gate |
| **Minimal CI permissions** | `permissions: contents: read` default |
| **Signed commits/tags** | GPG or Sigstore gitsign |
| **Branch protection** | Required reviews, status checks |
| **Hermetic builds** | Reproducible, no network in compile (Bazel, Nix) |

**Dependabot/Renovate** with grouped updates and CI validation before merge.

Block unpinned actions in CI:

```yaml
# Policy: actions must use SHA pin
# Semgrep or custom linter on workflow files
uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
```

---

## 52.6 in-toto and attestations

**in-toto** framework chains attestations through supply chain steps: design → source → build → test → deploy.

Each step produces signed metadata; final deployment verifies entire chain.

**GitHub Artifact Attestations** (2024+) attach build provenance to artifacts in GitHub UI and API.

OCI **referrers** attach SBOM and signatures to container images in registry—Cosign, ORAS CLI.

```bash
oras attach registry.example.com/myapp:v1.2.3 \
  --artifact-type application/vnd.cyclonedx+json \
  --file sbom.json
```

---

## 52.7 Organizational supply chain program

1. **Inventory** — SBOM for every production artifact
2. **Sign** — cosign keyless in CI for all release images
3. **Verify** — Admission policy in K8s clusters
4. **Monitor** — Alert on new CVEs affecting SBOM components
5. **Respond** — Playbook linking CVE → affected services via SBOM query
6. **Vendor** — Require SBOM + SLSA level from third-party software

Metrics:

- % artifacts with SBOM + signature
- Mean time to identify affected services for new CVE
- % deployments blocked by unsigned image policy (should be 0 in prod bypass)

---

## 52.8 Chapter summary

- SBOMs inventory software components for CVE response and compliance.
- SLSA defines progressive build hardening levels with provenance attestations.
- Sigstore/cosign enables keyless signing and Kubernetes verification policies.
- Pin dependencies, harden CI, and maintain organizational SBOM + signing program.

---

## 🧪 Lab 52.1 — SBOM generation and CVE lookup

1. Build Docker image for sample app; generate CycloneDX SBOM with Syft.
2. Scan SBOM with Grype; document findings.
3. Upgrade vulnerable package; regenerate SBOM; confirm clean scan.

---

## 🧪 Lab 52.2 — Sign and verify with cosign

1. Build and push image to registry (GHCR or local).
2. Sign with cosign keyless in GitHub Actions (or local key).
3. Configure Kyverno or conftest policy rejecting unsigned images.
4. Attempt deploy unsigned image; confirm rejection.

---

## Review questions

1. What is an SBOM, and why generate it for every release?
2. Compare CycloneDX and SPDX formats.
3. Explain SLSA Level 2 vs Level 3 requirements at high level.
4. How does cosign keyless signing bind identity to CI workflow?
5. What is VEX, and when use it?
6. Name three supply chain attacks and their mechanisms.
7. How do Kubernetes admission policies enforce signed images?

---

*Continue: Chapter 53 — Runtime Security*
