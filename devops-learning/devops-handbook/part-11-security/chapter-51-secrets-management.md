# Chapter 51: Secrets Management — Vault, SOPS, External Secrets

*DevOps Handbook — Pages 247–252 of this PDF edition*
---

## 51.1 The secrets problem

Applications need credentials—database passwords, API keys, TLS certificates, cloud IAM tokens. Storing them in Git, environment files on laptops, or plaintext Kubernetes Secrets violates basic security hygiene and compliance.

Requirements for secrets management:

| Requirement | Description |
|-------------|-------------|
| **Encryption at rest** | Secrets stored encrypted, not plaintext on disk |
| **Encryption in transit** | TLS for all secret API calls |
| **Access control** | Least privilege, audit who read what |
| **Rotation** | Periodic and emergency rotation without downtime |
| **Dynamic secrets** | Short-lived credentials generated on demand |
| **Audit trail** | Immutable log of access events |

This chapter covers **HashiCorp Vault**, **Mozilla SOPS**, and **External Secrets Operator**—common patterns in cloud-native DevOps.

---

## 51.2 HashiCorp Vault architecture

**Vault** is a secrets engine and identity-aware broker.

Components:

```
Clients (apps, CI, humans)
        │
        ▼
   Vault API (TLS)
        │
   ┌────┴────┬──────────┬─────────────┐
   │         │          │             │
 Auth     Secrets    Storage      Audit
 methods  engines    backend      devices
```

| Concept | Role |
|---------|------|
| **Seal/Unseal** | Master key protects data; Shamir shards or auto-unseal (KMS) |
| **Auth methods** | Kubernetes, AWS IAM, OIDC, AppRole, userpass |
| **Secrets engines** | KV, database, PKI, AWS, transit encryption |
| **Policies** | HCL paths controlling read/write |
| **Namespaces** | Multi-tenancy (Enterprise) |

Vault CLI basics:

```bash
export VAULT_ADDR=https://vault.example.com:8200
vault login -method=oidc

# Read static secret
vault kv get secret/data/myapp/database

# Write secret
vault kv put secret/myapp/api key=NEW_VALUE

# Generate dynamic DB creds (TTL 1h)
vault read database/creds/myapp-role
```

Dynamic database credentials: Vault creates temporary DB user, returns username/password, revokes on lease expiry—eliminating long-lived DB passwords in apps.

---

## 51.3 Vault on Kubernetes

**Vault Agent Injector** sidecar mounts secrets into pods:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "api"
    vault.hashicorp.com/agent-inject-secret-db: "secret/data/api/database"
    vault.hashicorp.com/agent-inject-template-db: |
      {{- with secret "secret/data/api/database" -}}
      DATABASE_URL=postgres://{{ .Data.data.username }}:{{ .Data.data.password }}@db:5432/app
      {{- end }}
spec:
  template:
    spec:
      serviceAccountName: api
      containers:
        - name: api
          image: myapp:latest
```

Kubernetes auth binds ServiceAccount → Vault role → policy.

**Vault Secrets Operator** (newer) syncs Vault secrets to Kubernetes Secret objects natively.

Operational concerns:

- **HA deployment** — Raft integrated storage or Consul backend
- **Auto-unseal** — AWS KMS, GCP CKMS, Azure Key Vault
- **Backup** — Snapshot Raft; test restore
- **Upgrade path** — Read release notes; staged rollout

---

## 51.4 Mozilla SOPS — Git-friendly encryption

**SOPS** (Secrets OPerationS) encrypts YAML/JSON/env files **in Git**—only encrypted blobs committed; decryption keys from KMS/PGP/age.

Use case: team wants secrets versioned alongside config with PR review, without plaintext in repo.

Encrypted file example (`secrets.enc.yaml`):

```yaml
db_password: ENC[AES256_GCM,data:xxx,iv:yyy,tag:zzz,type:str]
sops:
  kms:
    - arn: arn:aws:kms:us-east-1:123456789012:key/abc-123
      created_at: "2026-09-01T12:00:00Z
      enc: ...
  lastmodified: "2026-09-01T12:00:00Z
  version: 3.8.1
```

Commands:

```bash
# Encrypt
sops --encrypt --kms arn:aws:kms:us-east-1:123:key/abc secrets.yaml > secrets.enc.yaml

# Edit in place (decrypt-edit-reencrypt)
sops secrets.enc.yaml

# Decrypt to stdout for deploy
sops --decrypt secrets.enc.yaml > /tmp/secrets.yaml
```

CI integration:

```yaml
- name: Decrypt secrets
  env:
    AWS_REGION: us-east-1
  run: |
    sops --decrypt deploy/secrets.enc.yaml > deploy/secrets.yaml
    kubectl apply -f deploy/
```

**age** keys for teams without cloud KMS:

```bash
age-keygen -o key.txt
sops --encrypt --age age1xxx secrets.yaml > secrets.enc.yaml
```

SOPS tradeoffs: secrets in Git history remain encrypted but **key compromise** exposes all; rotate keys periodically.

---

## 51.5 External Secrets Operator (ESO)

**External Secrets Operator** syncs secrets from external providers into Kubernetes Secrets—bridging Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Parameter Store.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-db-credentials
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-db-credentials
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: production/api/database
        property: url
```

ClusterSecretStore for AWS:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

Benefits:

- No secrets in Git
- Central rotation in AWS/Vault propagates to K8s on refresh interval
- IRSA (IAM Roles for Service Accounts) for authentication—no static AWS keys

---

## 51.6 Cloud-native secret managers

| Provider | Service | Integration |
|----------|---------|-------------|
| AWS | Secrets Manager, SSM Parameter Store | ESO, Lambda rotation |
| GCP | Secret Manager | ESO, GKE workload identity |
| Azure | Key Vault | ESO, managed identity |

AWS Secrets Manager rotation Lambda template rotates RDS passwords automatically.

Compare Vault vs cloud-native:

| Factor | Vault | Cloud SM |
|--------|-------|----------|
| Multi-cloud | Yes | Per-cloud |
| Dynamic secrets | Rich engines | Limited |
| Operational load | Higher | Managed |
| Cost | Self-host + HCP option | Per-secret pricing |

Many orgs: Vault for dynamic/complex; cloud SM for simple static secrets.

---

## 51.7 CI/CD secrets patterns

| Anti-pattern | Better approach |
|--------------|-----------------|
| Long-lived cloud keys in GitHub Secrets | OIDC federation to IAM role |
| Same secret all environments | Separate secrets per env |
| Manual rotation | Automated rotation + ESO refresh |
| Echo secrets in CI logs | Mask variables; use secret refs |

GitHub OIDC → AWS (no static key):

```yaml
permissions:
  id-token: write
steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/GHA-Deploy
      aws-region: us-east-1
  - run: aws secretsmanager get-secret-value --secret-id prod/api
```

Short-lived tokens reduce blast radius of CI compromise.

---

## 51.8 Rotation and emergency response

Rotation checklist:

1. Generate new secret in manager
2. Dual-write period (app accepts old + new) if applicable
3. Update consumers via ESO refresh or redeploy
4. Revoke old secret after validation
5. Audit access logs for anomalies

Emergency: leaked secret → revoke immediately, rotate, scan Git history, review Vault/AWS audit logs for unauthorized access.

---

## 51.9 Chapter summary

- Vault provides dynamic secrets, fine-grained policies, and audit for enterprise secret management.
- SOPS enables encrypted secrets in Git with KMS/age keys for reviewable configuration.
- External Secrets Operator syncs cloud/Vault secrets into Kubernetes without plaintext in repos.
- Prefer OIDC and short-lived credentials in CI; automate rotation and maintain audit trails.

---

## 🧪 Lab 51.1 — SOPS with age

1. Generate age key pair; encrypt a YAML file with DB credentials.
2. Commit encrypted file to Git; verify plaintext never appears in history.
3. Decrypt in CI script simulating deploy.

---

## 🧪 Lab 51.2 — External Secrets on Kubernetes

1. Store secret in AWS Secrets Manager (or LocalStack for local test).
2. Install ESO; configure ClusterSecretStore and ExternalSecret.
3. Mount synced K8s Secret in pod; verify app reads value.

---

## Review questions

1. Compare static secrets in K8s Secrets vs Vault dynamic database credentials.
2. When is SOPS appropriate vs External Secrets Operator?
3. What is Vault seal/unseal, and why use auto-unseal with KMS?
4. How does IRSA enable ESO to access AWS Secrets Manager without static keys?
5. Describe a safe secret rotation procedure for a database password.
6. Why use OIDC in GitHub Actions instead of storing AWS access keys?
7. What audit capabilities should a secrets platform provide?

---

*Continue: Chapter 52 — Supply Chain, SBOM, Sigstore, SLSA*
