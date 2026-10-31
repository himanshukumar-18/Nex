# NEX

NEX is a proprietary, full-stack AI software engineering platform that helps developers understand, modify, test, review, and ship code through intelligent automation.

> **Project status: Step 5A Core Backend Architecture Implemented & Verified.** Django 5.2 core backend architecture is active with centralized API exception handling, Redis-backed sliding-window rate limiting (atomic Lua scripts, 10-category fail-closed/fail-open policies, anti-spoofing proxy resolution), correlation ID tracking (`X-Correlation-Id`), unified pagination (`NexCursorPagination` with tie-breaking), and a 95-test automated suite (all passing). PostgreSQL 17 with `pgvector` (v0.8.7) and Redis 7.4 are fully operational across all 5 healthy Docker services.

---

## Product Philosophy

- **Agentic by design** — AI is a first-class participant in the engineering workflow, not an add-on.
- **Developer-first** — Accessible through a web interface and a purpose-built CLI.
- **Security from day one** — Secrets management, container hardening, query timeouts, and network segmentation enforced from the start.
- **Production parity** — Development environment mirrors production via Docker from day one.
- **No unnecessary abstractions** — Code stays clean, readable, and maintainable.

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Backend API | Django + Django REST Framework | 5.2.3 / 3.16.0 |
| AI Agent Runtime | FastAPI + uvicorn | 0.115.14 / 0.34.3 |
| Agent Orchestration | LangGraph | Planned |
| Web Frontend | React | Planned |
| CLI | Python | ≥ 3.12 |
| Primary Database | PostgreSQL + pgvector | pg17 (vector 0.8.7) |
| Cache / Queue | Redis | 7.4.4-alpine |
| Reverse Proxy | Nginx | 1.28.0-alpine |
| Containerisation | Docker + Docker Compose | v29 / v5.5.1 |

---

## Architecture

```
  Browser / CLI  →  (TLS LB)  →  Nginx :8080 (dev) / :80 (prod)
                                          │
                                   Django Backend :8000
                                   (internal network only)
                                          │
                             ┌────────────┤
                             │            │
                      PostgreSQL 17    Redis
                      + pgvector       (internal)
                      (internal)

  Agent Runtime :8001  ←──── Django (internal)
  (internal + egress)  ──────────────────────────→  AI Providers (internet)
```

- **Nginx** is the sole public entry point. Agent-runtime is not proxied publicly.
- **`internal: true`** network keeps PostgreSQL and Redis isolated with zero internet access.
- **`egress`** network provides agent-runtime with outbound internet for AI provider calls.
- **FastAPI Agent Runtime (Step 6A & 6F)**: Dedicated internal AI execution runtime with async lifespan connection pooling (Redis DB 1 and backend HTTP client), centralized error envelopes, `X-Correlation-Id` tracking, dynamic streaming request size bounding (413), and decoupled `/health` (liveness) and `/health/ready` (readiness) probes.
- **Inter-Service Communication (Step 6F)**: Resilient communication between Django and FastAPI via dedicated `AgentRuntimeClient` (thread-safe connection pooling, explicit timeout matrix, safe idempotent GET retries, zero non-idempotent retries, SSRF defense) and constant-time mutual secret authentication (`InternalServiceAuthMiddleware` with zero-downtime key rotation).
- **Database Connection Management**: Persistent connections (`CONN_MAX_AGE=60`), connection health checks, and connection-level statement timeouts (`statement_timeout=30s`, `lock_timeout=10s`) prevent denial of service and runaway locks.
- **Abstract Base Models**: All future models inherit from `apps.core.models.BaseModel` (UUIDv4 primary keys and automated timestamp auditing).
- **Distributed Rate Limiting**: Redis-backed sliding-window counter using atomic Lua scripts (O(1) memory, privacy-masked client identifiers, configurable fail-open policy).
- **Centralized Exception Handling & Tracing**: All API errors conform to a unified JSON envelope (`error`, `message`, `detail`), and every request is tracked across workers with a UUID4 `X-Correlation-Id`.
- **Automated Test Coverage**: **140 verified tests passing across the stack** (106 Django backend tests + 34 FastAPI agent-runtime tests), plus live inter-container integration verified.

See [DIRECTORY.md](DIRECTORY.md) for detailed architecture, security decisions, and verification records.

---

## Prerequisites

- **Docker Engine** ≥ 26 (or Docker Desktop)
- **Docker Compose** ≥ 2.24
- **Python** ≥ 3.12 (for local dev tools only — not required to run the stack)

---

## Development Setup

### 1. Configure environment

```bash
cp .env.example .env
```

Set required development variables in `.env`:

```bash
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
POSTGRES_PASSWORD=<strong random password>
# DATABASE_URL is constructed automatically in development from POSTGRES_* vars
```

### 2. Build and start all services

```bash
docker compose up -d --build
```

### 3. Apply database migrations

```bash
docker compose exec backend python manage.py migrate
```

### 4. Verify service health and readiness

```bash
docker compose ps                               # all 5 should report (healthy)
curl http://localhost:8080/health/              # Liveness probe  → {"status":"ok"}
curl http://localhost:8080/health/ready/        # Readiness probe → {"status":"ready","database":"connected"}
curl http://localhost:8080/nginx-health         # Nginx probe     → {"status":"ok"}
```

---

## Database & Development Commands

```bash
# Apply database migrations
docker compose exec backend python manage.py migrate

# Inspect migration status
docker compose exec backend python manage.py showmigrations

# Create new migrations after model changes
docker compose exec backend python manage.py makemigrations

# Run test suite (10 automated tests for DB, vector math, and health checks)
docker compose exec backend python manage.py test apps.core

# Interactive PostgreSQL access (safe inside internal network)
docker compose exec postgres psql -U nex -d nex

# Interactive Redis access
docker compose exec redis redis-cli

# View service logs
docker compose logs -f backend
```

---

## Production Deployment

> **TLS notice:** Production deployments require a TLS-terminating load balancer or Nginx SSL certificates. See [`infrastructure/nginx/README.md`](infrastructure/nginx/README.md).

### Required production secrets

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | 50+ character random key |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated public domain(s) |
| `DATABASE_URL` | `postgres://user:pass@postgres:5432/nex` |
| `POSTGRES_PASSWORD` | Strong random password |
| `REDIS_PASSWORD` | Strong random password |

### Deploy production stack

```bash
# 1. Build hardened production images
docker compose -f docker-compose.prod.yml build

# 2. Start stack (all secrets supplied via environment / secret manager)
docker compose -f docker-compose.prod.yml up -d

# 3. Apply migrations via one-off container
docker compose -f docker-compose.prod.yml run --rm --no-deps backend python manage.py migrate
```

---

## Project Structure

```
apps/backend/       Django REST API service (Core foundation, abstract models, AgentRuntimeClient, health probes)
apps/agent-runtime/ FastAPI agent runtime (Internal AI execution, service auth, Redis DB 1, dynamic 413 limits)
cli/                NEX command-line interface (scaffolded)
frontend/           React web application (scaffolded)
packages/           Shared library code
infrastructure/     Dockerfiles, Nginx reverse proxy, and Redis config template
scripts/            Development automation scripts
tests/              Cross-service test suites
```

See [DIRECTORY.md](DIRECTORY.md) for the complete annotated tree, model standards, and operational guidelines.

---

## Licence

Copyright (c) 2026 Himanshu Kumar. All rights reserved. Proprietary and confidential — see [LICENSE](LICENSE).
