# Chapter 30: Rootless Containers and Podman

*DevOps Handbook — Part VII, Pages 561–580*

---

## 30.1 Why rootless containers matter

Traditionally, Docker required a **root-owned daemon** (`dockerd`). Any user in the `docker` group effectively had root on the host—container escape or `-v /:/host` mounts could compromise the entire machine.

**Rootless containers** run the container runtime and workloads as an unprivileged user, mapping container UIDs to subordinate UID ranges on the host. Compromise of a container or runtime bug has **reduced blast radius**.

| Mode | Daemon user | Container root maps to |
|------|-------------|------------------------|
| Rootful Docker | root | host root (dangerous) |
| Rootless Podman/Docker | user namespace | unprivileged host UID |
| Kubernetes | varies | depends on PSA/ SCC |

Production clusters still use rootful runtimes on nodes, but developers and CI increasingly adopt rootless tooling.

---

## 30.2 Podman overview

**Podman** (Red Hat / CNCF) is a daemonless OCI container engine. It pulls images, creates containers, and manages pods—compatible with Docker CLI for most workflows.

```bash
podman --version
podman run -d -p 8080:80 --name web docker.io/library/nginx:alpine
podman ps
podman logs web
podman exec -it web sh
podman stop web && podman rm web
```

**Docker-compatible aliases:**

```bash
alias docker=podman
alias docker-compose=podman-compose
```

Podman stores data in `~/.local/share/containers/` for rootless users—no central daemon socket owned by root.

---

## 30.3 Rootless setup

On Fedora/RHEL/Ubuntu with upstream packages:

```bash
# Install
sudo apt install podman slirp4netns fuse-overlayfs

# Enable lingering for systemd user services (servers)
loginctl enable-linger $USER

# Verify rootless
podman info --format '{{.Host.Security.Rootless}}'
```

`/etc/subuid` and `/etc/subgid` must allocate ranges:

```
testuser:100000:65536
```

Podman maps container UID 0 → host UID 100000, etc.

### Limitations of rootless

| Feature | Rootless constraint |
|---------|---------------------|
| Binding ports < 1024 | Needs `sysctl` or rootful helper |
| Some volume mounts | Permission mapping complexity |
| `host` network | Limited compared to rootful |
| cgroup devices | May need delegated cgroup v2 |

Bind privileged ports rootlessly (Linux 5.7+):

```bash
echo "net.ipv4.ip_unprivileged_port_start=80" | \
  sudo tee /etc/sysctl.d/99-unprivileged-ports.conf
sudo sysctl --system
```

---

## 30.4 Pods and systemd integration

Podman groups containers into **pods** (shared network namespace, like a Kubernetes pod):

```bash
podman pod create --name app -p 8080:80
podman run -d --pod app --name web nginx:alpine
podman run -d --pod app --name metrics prom/prometheus
podman pod ps
```

Generate **systemd unit files** for production-like single-host deploys:

```bash
podman generate systemd --new --name web > container-web.service
systemctl --user enable --now container-web.service
journalctl --user -u container-web.service -f
```

`--new` recreates the container on each start from the image definition—closer to immutable infrastructure.

---

## 30.5 Podman Compose and Kubernetes YAML

**podman-compose**:

```bash
podman-compose -f compose.yaml up -d
```

**Play kube** — run Kubernetes manifests locally:

```bash
podman play kube deployment.yaml
podman play kube --down deployment.yaml
```

Useful for validating K8s YAML without a full cluster.

---

## 30.6 Rootless Docker (Moby)

Docker Engine 20.10+ supports **rootless mode** via `dockerd-rootless-setuptool.sh install`.

```bash
dockerd-rootless-setuptool.sh install
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
docker run hello-world
```

Rootless Docker still uses `containerd` and user namespaces but maintains the Docker CLI/API model. Podman is daemonless; choose based on team familiarity and RHEL vs Debian ecosystems.

---

## 30.7 Security comparison

```
Rootful Docker:
  Client → /var/run/docker.sock (group=docker) → root dockerd → container (root in cgroup)

Rootless Podman:
  Client → podman (same UID) → conmon + crun/runc → user namespace → mapped UIDs
```

Hardening tips for rootless dev:

- Do not `sudo podman` routinely—it defeats the model
- Use **SELinux** labels (`:Z` on volume mounts on RHEL)
- Scan images same as production (**Trivy**)
- Prefer **read-only** rootfs and **cap-drop**

```bash
podman run --read-only --tmpfs /tmp --cap-drop=ALL myapp:1.0
```

---

## 30.8 Buildah and Skopeo

The **containers** ecosystem includes:

| Tool | Role |
|------|------|
| **Buildah** | Build OCI images without Dockerfile (or with) |
| **Skopeo** | Copy/sign/inspect images between registries |
| **Podman** | Run containers and pods |
| **crun** | OCI runtime (lightweight) |

Build without daemon:

```bash
buildah bud -t myapp:dev .
buildah push myapp:dev docker://ghcr.io/acme/myapp:dev
```

Skopeo copy (air-gapped mirror):

```bash
skopeo copy docker://docker.io/library/alpine:3.20 \
  docker://registry.internal/alpine:3.20
```

---

## 30.9 When to use Podman vs Docker vs Kubernetes

| Scenario | Recommendation |
|----------|----------------|
| Developer laptop (security-conscious) | Rootless Podman |
| Existing Docker Desktop team | Docker with hardened settings |
| CI build agents | `buildah`/`kaniko`/`docker buildx` |
| Production orchestration | Kubernetes (containerd/CRI-O runtime) |
| Single-node edge | Podman + systemd units |

Kubernetes nodes typically run **CRI-O** or **containerd**—not Podman—though Red Hat OpenShift uses CRI-O with similar roots.

---

## 30.10 Chapter summary

- **Rootless** containers reduce host compromise risk by eliminating a root-owned central daemon.
- **Podman** is daemonless, Docker CLI–compatible, and integrates with **systemd** and **pods**.
- Configure **subuid/subgid** ranges and understand rootless **port and volume** limitations.
- **Buildah** and **Skopeo** complete the toolchain for build and registry operations without Docker.
- Use rootless on workstations; enforce signing, scanning, and orchestrator policies in production.

---

## 🧪 Lab 30.1

1. Install Podman rootless; run nginx publishing port 8080.
2. Create a pod with two containers sharing a network namespace.
3. Generate a systemd user unit and manage the container with `systemctl --user`.

---

## 🧪 Lab 30.2

1. Convert a Docker Compose file to run under `podman-compose`.
2. Build an image with Buildah and push to GHCR with Skopeo or `podman push`.
3. Compare `podman info` security section between rootful and rootless modes.

---

## Review questions

1. Why is membership in the `docker` group considered equivalent to root access?
2. How do user namespaces map container root to the host?
3. What problem do Podman pods solve compared to standalone containers?
4. Name two limitations of rootless mode when binding network ports.
5. When would you choose Buildah over `podman build`?

---

*Next: [Chapter 31 — K8s Architecture](../part-08-kubernetes/chapter-31-k8s-architecture.md)*
