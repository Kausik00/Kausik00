# Chapter 26: Docker — Images, Dockerfile, and Multi-stage Builds

*DevOps Handbook — Part VII, Pages 481–505*

---

## 26.1 Containers in one paragraph

A **container** packages an application with its dependencies into an isolated process on a shared Linux kernel. Unlike VMs, containers share the host OS kernel—lightweight and fast to start.

**Docker** is the dominant tooling for building, shipping, and running containers locally and in CI.

---

## 26.2 Core concepts

| Concept | Description |
|---------|-------------|
| **Image** | Read-only template (layers) |
| **Container** | Running instance of an image |
| **Dockerfile** | Recipe to build an image |
| **Registry** | Storage for images (Docker Hub, ECR) |
| **Volume** | Persistent data outside container lifecycle |
| **Network** | Connect containers to each other and the host |

---

## 26.3 Essential commands

```bash
docker pull nginx:1.25-alpine
docker images
docker run -d -p 8080:80 --name web nginx:1.25-alpine
docker ps
docker logs web
docker exec -it web sh
docker stop web && docker rm web
docker build -t myapp:1.0 .
docker tag myapp:1.0 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:1.0
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/myapp:1.0
```

---

## 26.4 Dockerfile best practices

```dockerfile
# Use specific version tags, not :latest in production
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production=false

COPY . .
RUN npm run build

# Multi-stage: smaller final image
FROM node:20-alpine AS runtime

RUN addgroup -g 1001 -S app && adduser -u 1001 -S app -G app
WORKDIR /app
USER app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package.json .

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### Best practices checklist

- Use **multi-stage builds** to shrink images
- Run as **non-root** user
- Minimize layers; combine RUN commands where sensible
- Use `.dockerignore` (exclude `node_modules`, `.git`, etc.)
- Pin base image digests for supply chain security
- Add **HEALTHCHECK** for orchestrators

---

## 26.5 Docker Compose for local development

`docker-compose.yml`:

```yaml
services:
  api:
    build: .
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgres://user:pass@db:5432/app
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d app"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

```bash
docker compose up -d
docker compose logs -f api
docker compose down -v   # Remove volumes too
```

---

## 26.6 Security basics

- Scan images: `docker scout cves` or **Trivy**
- Do not store secrets in images or Dockerfile `ENV`
- Use read-only root filesystem where possible (`--read-only`)
- Drop capabilities: `--cap-drop=ALL`

---

## 26.7 Chapter summary

- Images are built from Dockerfiles; containers are ephemeral runtime instances.
- **Multi-stage builds** and non-root users are production essentials.
- **Docker Compose** orchestrates multi-container local stacks.

---

## 🧪 Lab 26.1

1. Containerize a simple Node or Python web app.
2. Add multi-stage build and health check.
3. Run with Compose alongside PostgreSQL.
4. Scan the image with Trivy.

---

*Next: [Chapter 37 — CI/CD Pipeline Design](../part-09-cicd/chapter-37-cicd-pipeline-design.md)*
