# Chapter 28: Docker Compose and Local Dev Environments

*DevOps Handbook — Pages 126–130 of this PDF edition*
---

## 28.1 What Docker Compose solves

**Docker Compose** (v2, integrated as `docker compose`) defines multi-container applications in a single YAML file. Developers run `docker compose up` to start databases, caches, APIs, and frontends with consistent networking and volumes—eliminating "works on my machine" setup drift.

Compose is ideal for **local development**, **integration tests**, and **demo stacks**. Production orchestration typically moves to Kubernetes, ECS, or Nomad, but Compose files often inform those definitions.

---

## 28.2 Compose file structure

`compose.yaml`:

```yaml
name: bookstore

services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
      target: dev
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development
      DATABASE_URL: postgres://app:app@db:5432/bookstore
      REDIS_URL: redis://cache:6379/0
    volumes:
      - ./api/src:/app/src:ro
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
    develop:
      watch:
        - action: sync
          path: ./api/src
          target: /app/src
        - action: rebuild
          path: ./api/package.json

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: bookstore
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d bookstore"]
      interval: 5s
      timeout: 5s
      retries: 5

  cache:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no

  adminer:
    image: adminer:4
    ports:
      - "8080:8080"
    profiles:
      - tools

volumes:
  pgdata:
```

Key directives:

| Key | Purpose |
|-----|---------|
| `build` / `image` | Build locally or pull image |
| `ports` | Publish container ports |
| `environment` / `env_file` | Configuration |
| `volumes` | Persistence and dev bind mounts |
| `depends_on` | Startup ordering (with health conditions) |
| `profiles` | Optional services (`--profile tools`) |
| `develop.watch` | File sync / rebuild (Compose 2.22+) |

---

## 28.3 Essential commands

```bash
docker compose up -d              # Detached start
docker compose up --build         # Rebuild images
docker compose ps
docker compose logs -f api
docker compose exec api sh
docker compose run --rm api npm test
docker compose stop
docker compose down               # Stop and remove containers
docker compose down -v            # Also remove named volumes
docker compose config               # Validate and render merged YAML
```

Run one-off commands in the service context:

```bash
docker compose run --rm api npx prisma migrate deploy
```

---

## 28.4 Environment-specific overrides

`compose.yaml` — base stack  
`compose.override.yaml` — auto-loaded local overrides (gitignored secrets)  
`compose.prod.yaml` — production-like settings

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

`compose.override.yaml` example:

```yaml
services:
  api:
    ports:
      - "3000:3000"
      - "9229:9229"    # Node debugger
    environment:
      LOG_LEVEL: debug
```

`.env` file (loaded automatically):

```dotenv
POSTGRES_USER=app
POSTGRES_PASSWORD=localdev
API_PORT=3000
```

Reference in compose: `${API_PORT}:3000`

---

## 28.5 Networking in Compose

Compose creates a **default network** named `{project}_{default}`. All services join it and resolve each other by **service name** (`db`, `cache`, `api`).

Custom network:

```yaml
networks:
  frontend:
  backend:

services:
  web:
    networks: [frontend]
  api:
    networks: [frontend, backend]
  db:
    networks: [backend]
```

`db` is unreachable from `web`—only `api` bridges both networks. Useful for mimicking DMZ patterns locally.

---

## 28.6 Development workflows

### Hot reload with bind mounts

Mount source code read-write; run dev server with file watcher inside container:

```yaml
services:
  api:
    build: .
    command: npm run dev
    volumes:
      - ./api:/app
      - /app/node_modules    # Anonymous volume preserves container node_modules
```

The anonymous volume prevents host `node_modules` from overwriting Linux binaries built in the image.

### Compose Watch

```yaml
develop:
  watch:
    - action: sync+restart
      path: ./config
      target: /app/config
```

`docker compose watch` syncs files and restarts affected services.

### Seed data

```yaml
services:
  db:
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
```

PostgreSQL runs scripts in `docker-entrypoint-initdb.d` on first initialization only.

---

## 28.7 Testing with Compose

`compose.test.yaml`:

```yaml
services:
  api:
    build: .
    environment:
      DATABASE_URL: postgres://test:test@db:5432/test
    command: npm test
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 2s
      retries: 10
```

CI:

```yaml
- run: docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from api
- run: docker compose -f compose.test.yaml down -v
```

`--exit-code-from api` fails the job if tests fail.

---

## 28.8 Compose vs production

| Concern | Local Compose | Production K8s/ECS |
|---------|---------------|-------------------|
| Scaling | `deploy.replicas` (Swarm only); manual | HPA, replica sets |
| Secrets | `.env`, Docker secrets | Vault, K8s Secrets, SSM |
| Health routing | None | Load balancers, probes |
| Rolling updates | Recreate containers | Controlled rollouts |

Translate patterns, not files literally—tools like **Kompose** exist but output usually needs manual refinement.

---

## 28.9 Chapter summary

- **Compose** defines multi-service stacks with networking, volumes, and dependencies in YAML.
- Use **overrides**, `.env`, and **profiles** for flexible local vs CI environments.
- **Healthchecks** and `depends_on` conditions prevent race conditions on startup.
- **Compose Watch** and bind mounts enable fast inner-loop development.
- Run integration tests in CI with `docker compose up --abort-on-container-exit`.

---

## 🧪 Lab 28.1

1. Build a three-service stack: API, PostgreSQL, Redis.
2. Add healthchecks and verify API waits for database readiness.
3. Create a `tools` profile with Adminer or pgAdmin.

---

## 🧪 Lab 28.2

1. Split `compose.yaml` and `compose.override.yaml` for debug ports and log level.
2. Add Compose Watch or a bind mount for live code reload.
3. Write a CI job that runs tests via `compose.test.yaml`.

---

## Review questions

1. How does Compose service discovery differ from linking containers manually?
2. Why use an anonymous volume for `node_modules` in a bind-mounted Node app?
3. What does `depends_on: condition: service_healthy` solve?
4. When should you use `compose down -v` versus `compose down`?
5. How do Compose profiles help keep optional services out of the default stack?

---

*Next: [Chapter 29 — Container Registries and Image Signing](./chapter-29-container-registries-signing.md)*
