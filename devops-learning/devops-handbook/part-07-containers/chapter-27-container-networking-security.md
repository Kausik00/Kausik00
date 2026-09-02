# Chapter 27: Container Networking, Volumes, and Security

*DevOps Handbook — Pages 121–125 of this PDF edition*
---

## 27.1 Container networking model

Containers share the host Linux kernel but need isolated network namespaces. **Docker** (and containerd/CRI-O underneath) creates virtual interfaces, bridges, and iptables/nftables rules so containers get IPs and can reach each other and the outside world.

| Namespace | Isolates |
|-----------|----------|
| **Network** | Interfaces, routes, ports |
| **PID** | Process tree |
| **Mount** | Filesystem view |
| **UTS** | Hostname |
| **IPC** | Inter-process communication |
| **User** | UID/GID mapping (rootless) |

Understanding namespaces explains why a process in a container sees its own `eth0` and port 80, while the host may map that to port 8080.

---

## 27.2 Docker network drivers

```bash
docker network ls
docker network inspect bridge
docker network create --driver bridge app-net
docker run -d --name api --network app-net nginx:alpine
docker run -d --name cache --network app-net redis:7-alpine
```

| Driver | Scope | Use case |
|--------|-------|----------|
| **bridge** | Single host | Default; container-to-container on one machine |
| **host** | Single host | Container uses host network stack (no NAT) |
| **none** | Isolated | No networking |
| **overlay** | Multi-host (Swarm) | Legacy Swarm clustering |
| **macvlan** | L2 segment | Containers appear as physical NICs on LAN |

### DNS on user-defined bridges

On the default `bridge`, containers resolve each other by IP only. On **user-defined bridge networks**, Docker's embedded DNS resolves **container names**:

```bash
# From api container:
docker exec api ping -c1 cache   # Resolves to cache container IP
```

### Published ports

```bash
docker run -p 127.0.0.1:8080:80 nginx   # Bind host localhost only
docker run -p 8080:80 nginx             # All interfaces (careful in prod)
```

`-p` sets DNAT rules forwarding host port → container port.

---

## 27.3 Container-to-container and host communication

```
┌─────────────────────────────────────────────┐
│ Host (172.17.0.1)                           │
│  ┌──────────────┐      ┌──────────────┐     │
│  │ api          │      │ db           │     │
│  │ 172.18.0.2   │─────▶│ 172.18.0.3   │     │
│  └──────────────┘      └──────────────┘     │
│         ▲ docker0 / br-app-net            │
└─────────┼───────────────────────────────────┘
          │ :8080 published
     External client
```

**Host network mode** (`--network host`): container shares host ports directly—useful for high-performance proxies; breaks port isolation.

**Extra hosts** (`--add-host`): inject static `/etc/hosts` entries for legacy apps.

---

## 27.4 Volumes and persistence

Container filesystems are ephemeral. **Volumes** persist data outside the container lifecycle.

| Mechanism | Location | Best for |
|-----------|----------|----------|
| **Volume** | `/var/lib/docker/volumes/` | Databases, shared data |
| **Bind mount** | Host path | Dev hot-reload, config files |
| **tmpfs** | Memory | Secrets, temp cache |

```bash
docker volume create pgdata
docker run -d \
  --name postgres \
  -v pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=secret \
  postgres:16-alpine

# Bind mount for development
docker run -v $(pwd)/src:/app/src node:20-alpine npm run dev
```

Volume commands:

```bash
docker volume ls
docker volume inspect pgdata
docker run --rm -v pgdata:/data alpine ls /data
```

**Named volumes** are portable across hosts when using volume plugins or orchestrators (Kubernetes PVCs). **Bind mounts** tie data to a specific host path—avoid for production databases on single Docker hosts.

### Read-only root filesystem

```bash
docker run --read-only \
  --tmpfs /tmp \
  -v app-cache:/var/cache \
  myapp:1.0
```

---

## 27.5 Linux capabilities and seccomp

Containers are not VMs. Root in a container may still be dangerous on the host without proper isolation. Docker drops most **Linux capabilities** by default.

```bash
# Drop all, add only what's needed
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE nginx:alpine

# Never do this in production
docker run --privileged myapp   # Near-root on host
```

| Capability | Risk if granted |
|------------|-----------------|
| `SYS_ADMIN` | Mount, cgroup manipulation |
| `NET_RAW` | Packet sniffing, ARP spoofing |
| `DAC_OVERRIDE` | Bypass file permissions |

**seccomp** profiles filter syscalls. Docker uses a default profile; Kubernetes can set `seccompProfile: RuntimeDefault`.

**AppArmor** / **SELinux** add MAC labels:

```bash
docker run --security-opt apparmor=docker-default ...
```

---

## 27.6 Image and runtime security

### Non-root user

```dockerfile
RUN adduser -D -u 10001 appuser
USER appuser
```

### Scanning

```bash
trivy image myapp:1.0
docker scout cves myapp:1.0
grype myapp:1.0
```

Fail CI if CRITICAL CVEs exist without accepted risk ticket.

### Secrets management

| Anti-pattern | Fix |
|--------------|-----|
| `ENV DB_PASSWORD=...` in Dockerfile | Runtime env from vault/SSM |
| Secrets in image layers | BuildKit secrets, multi-stage discard |
| World-readable bind mounts | tmpfs or secret driver |

BuildKit secret mount:

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
```

```bash
docker build --secret id=npmrc,src=$HOME/.npmrc .
```

---

## 27.7 Resource limits and health

```bash
docker run -d \
  --memory=512m \
  --cpus=1.5 \
  --pids-limit=100 \
  --restart=unless-stopped \
  myapp:1.0
```

Without limits, one container can exhaust host memory (**OOM killer** may kill random processes).

**Health checks** (Dockerfile or run flag):

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://localhost:8080/health || exit 1
```

Orchestrators use health status for rolling updates and traffic routing.

---

## 27.8 Debugging networking issues

```bash
docker exec api ip addr
docker exec api cat /etc/resolv.conf
docker exec api wget -qO- http://cache:6379
iptables -t nat -L -n | grep 8080    # Host: inspect port publishing
docker logs api --tail 50
```

Common problems:

- Wrong network → container not on same user-defined bridge
- Published port conflict → another process bound to host port
- DNS failure → using default bridge instead of named network
- Firewall on host blocking forwarded traffic

---

## 27.9 Chapter summary

- Containers use **network namespaces**; user-defined **bridge networks** provide DNS-based service discovery.
- **Volumes** persist data; prefer named volumes over bind mounts for production state.
- Harden with **non-root users**, **cap-drop**, **read-only rootfs**, and **image scanning**.
- Never run `--privileged` in production; inject secrets at runtime, not in images.

---

## 🧪 Lab 27.1

1. Create a user-defined bridge network with `api` and `redis` containers; verify name resolution.
2. Attach a named volume to PostgreSQL; delete and recreate the container without data loss.
3. Run nginx with `--read-only`, `--cap-drop=ALL`, and `--cap-add=NET_BIND_SERVICE`.

---

## 🧪 Lab 27.2

1. Publish a port bound to `127.0.0.1` only; confirm remote access is blocked.
2. Scan an image with Trivy; remediate one CVE by upgrading a base package.
3. Debug a deliberate misconfiguration (wrong network) using `docker inspect` and `exec`.

---

## Review questions

1. Why do containers on the default bridge network not resolve each other by name?
2. What is the difference between a bind mount and a named volume?
3. Which capability allows binding to ports below 1024 without running as root?
4. Why is `--privileged` dangerous compared to adding specific capabilities?
5. How does `-p 8080:80` affect host firewall and NAT rules?

---

*Next: [Chapter 28 — Docker Compose and Local Dev](./chapter-28-docker-compose.md)*
