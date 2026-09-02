# Chapter 34: Kubernetes ConfigMaps, Secrets, and Storage (PV/PVC)

*DevOps Handbook — Pages 156–160 of this PDF edition*
---

## 34.1 Separating config from images

Twelve-factor apps store config in the environment, not in images. Kubernetes provides **ConfigMaps** for non-sensitive config and **Secrets** for sensitive data—mounted as files or injected as environment variables.

| Object | Data | Base64 | Encryption at rest |
|--------|------|--------|-------------------|
| ConfigMap | Plain text | No | Optional |
| Secret | Sensitive | Yes (not encryption) | Enable KMS provider |

Never commit plaintext Secrets to Git. Use **Sealed Secrets**, **External Secrets Operator**, or **SOPS**.

---

## 34.2 ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
data:
  LOG_LEVEL: debug
  APP_ENV: staging
  nginx.conf: |
    server {
      listen 80;
      location / { proxy_pass http://127.0.0.1:8080; }
    }
```

Reference in a Deployment:

```yaml
spec:
  containers:
    - name: api
      image: ghcr.io/acme/api:1.0
      envFrom:
        - configMapRef:
            name: api-config
      env:
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: api-config
              key: LOG_LEVEL
      volumeMounts:
        - name: config-vol
          mountPath: /etc/nginx
          readOnly: true
  volumes:
    - name: config-vol
      configMap:
        name: api-config
        items:
          - key: nginx.conf
            path: nginx.conf
```

```bash
kubectl create configmap api-config --from-literal=LOG_LEVEL=info
kubectl create configmap app-config --from-file=./config/
kubectl get configmap api-config -o yaml
```

**Immutable ConfigMaps** (recommended): set `immutable: true` to prevent accidental updates causing rolling reload storms.

---

## 34.3 Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:          # Plain text in manifest — encode on apply
  username: appuser
  password: s3cr3t-db-pwd
```

```bash
kubectl create secret generic db-credentials \
  --from-literal=username=appuser \
  --from-literal=password='s3cr3t'

kubectl create secret docker-registry ghcr-creds \
  --docker-server=ghcr.io \
  --docker-username=user \
  --docker-password=$TOKEN
```

Mount as files (preferred for apps that read credential files):

```yaml
volumeMounts:
  - name: db-secret
    mountPath: /etc/secrets/db
    readOnly: true
volumes:
  - name: db-secret
    secret:
      secretName: db-credentials
      defaultMode: 0400
```

**RBAC** restricts who reads Secrets. Enable **encryption at rest** with KMS (AWS, GCP, Azure integrations).

### External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
    - secretKey: password
      remoteRef:
        key: prod/bookstore/db
        property: password
```

Secrets sync from AWS Secrets Manager, Vault, or Parameter Store into native K8s Secrets.

---

## 34.4 Storage basics — PV, PVC, StorageClass

Pod filesystems are ephemeral. **PersistentVolume (PV)** is cluster storage; **PersistentVolumeClaim (PVC)** is a pod's request for storage.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 20Gi
```

```yaml
spec:
  containers:
    - name: postgres
      image: postgres:16
      volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: data-pvc
```

| Access mode | Meaning |
|-------------|---------|
| **ReadWriteOnce (RWO)** | One node read/write |
| **ReadOnlyMany (ROX)** | Many nodes read |
| **ReadWriteMany (RWX)** | Many nodes read/write (EFS, NFS) |

**WaitForFirstConsumer** delays volume provisioning until pod is scheduled—important for zonal disks.

---

## 34.5 StatefulSet storage pattern

StatefulSets use **volumeClaimTemplates** for per-replica PVCs (`data-postgres-0`, `data-postgres-1`).

Scaling down does **not** delete PVCs by default—data survives for rescheduling. Orphan PVC cleanup must be deliberate.

```bash
kubectl get pvc
kubectl describe pvc data-pvc
kubectl exec postgres-0 -- df -h /var/lib/postgresql/data
```

---

## 34.6 Config reload and updates

Changing a ConfigMap mounted as env var **does not** update running containers—restart required. Mounted **volumes** can refresh (with delay; subPath does not auto-update).

Patterns:

- **Reloader** operator watches ConfigMaps/Secrets and rolls Deployments
- Sidecar **inotify** watcher triggers app reload
- Immutable versions: `api-config-v3` → update deployment reference

For Secrets, prefer short-lived tokens and automatic rotation via External Secrets.

---

## 34.7 Backup and snapshots

CSI **VolumeSnapshot**:

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: data-snap-20250901
spec:
  volumeSnapshotClassName: csi-aws-vsc
  source:
    persistentVolumeClaimName: data-pvc
```

Backup tools: **Velero** (cluster resources + PV snapshots), cloud-native backup services.

Test restores regularly—an untested backup is wishful thinking.

---

## 34.8 Security checklist

- No Secrets in container images or public Git
- Enable **encryption at rest** for etcd Secrets
- Restrict Secret get/list with RBAC
- Use **readOnly** volume mounts where possible
- Prefer **projected volumes** combining multiple sources
- Scan manifests in CI for hardcoded credentials (**gitleaks**, **checkov**)

---

## 34.9 Chapter summary

- **ConfigMaps** hold non-sensitive config; **Secrets** hold sensitive data—neither replaces a secrets manager at scale.
- Mount config as **volumes** for file-based apps; use **env** for simple key-value.
- **PVCs** request storage; **StorageClasses** enable dynamic provisioning.
- Match **access modes** and **StorageClass** topology to workload (RWO for EBS, RWX for shared files).
- Integrate **External Secrets** and **volume snapshots** for production operations.

---

## 🧪 Lab 34.1

1. Create ConfigMap and Secret; deploy an app consuming both via env and volume mounts.
2. Provision a PVC with dynamic StorageClass; verify data survives pod deletion.
3. Expand a PVC if `allowVolumeExpansion` is enabled.

---

## 🧪 Lab 34.2

1. Deploy External Secrets Operator (or Sealed Secrets) syncing one secret from a vault/cloud store.
2. Take a VolumeSnapshot and restore to a new PVC.
3. Add Reloader or manual rollout workflow when ConfigMap changes.

---

## Review questions

1. Why is base64 encoding in Secrets not considered encryption?
2. What happens to a PVC when its pod is deleted?
3. When should you use ReadWriteMany instead of ReadWriteOnce?
4. Why do env-var ConfigMap changes not appear in running pods?
5. What does `volumeBindingMode: WaitForFirstConsumer` prevent?

---

*Next: [Chapter 35 — Helm and GitOps](./chapter-35-helm-gitops.md)*
