# NEX — Repository Directory

> **Status: Step 6F Django ↔ FastAPI Backend Communication Implemented & Verified** — Secure, resilient inter-service communication between Django Core Backend and FastAPI Agent Runtime is established. Implements Django-side dedicated `AgentRuntimeClient` (thread-safe connection pooling via `httpx.Client`, explicit timeout matrix, safe idempotent GET retries, zero non-idempotent retries, SSRF/traversal protection, and `X-Correlation-Id` propagation), FastAPI constant-time service authentication (`InternalServiceAuthMiddleware` using `secrets.compare_digest` with zero-downtime key rotation via primary and fallback keys), true dynamic streaming request body size enforcement (HTTP 413 on chunked/streamed transfers), typed request/response contracts, and centralized normalized error responses. Combined platform test suite: **140/140 passing tests** (106 Django backend + 34 FastAPI agent-runtime) plus live end-to-end container integration verified. All 5 Docker development services are healthy.

---

## 1. Project Overview

NEX is a proprietary, full-stack AI software engineering platform designed to help developers understand, modify, test, review, and ship code through intelligent automation. The platform is built around an agentic core: an AI runtime that can reason over codebases, execute multi-step engineering workflows, and surface results through a web interface and a command-line tool.

---

## 2. Repository Directory Tree

```
nex - ai software engineer/
├── .dockerignore                        # Docker build exclusion rules
├── .env.example                         # Environment variable template (no secrets)
├── .gitignore                           # Git exclusion rules
├── LICENSE                              # Proprietary licence (Himanshu Kumar, 2026)
├── Makefile                             # Developer quality-check commands
├── README.md                            # Project overview and quick-start reference
├── DIRECTORY.md                         # This file — detailed repository documentation
├── pyproject.toml                       # Root Python project config (Ruff, mypy, pytest)
├── docker-compose.yml                   # Development Docker Compose (all services healthy)
├── docker-compose.prod.yml              # Production Docker Compose (hardened)
│
├── apps/
│   ├── backend/                         # Django REST API service
│   │   ├── manage.py                    # Django management entry-point
│   │   ├── config/
│   │   │   ├── __init__.py              # Config package marker
│   │   │   ├── health.py                # Liveness (/health/) & Readiness (/health/ready/) probes
│   │   │   ├── urls.py                  # URL routing
│   │   │   ├── wsgi.py                  # WSGI entry-point for Gunicorn
│   │   │   └── settings/
│   │   │       ├── __init__.py          # Settings package marker
│   │   │       ├── base.py              # Shared settings + DB pooling & timeout options
│   │   │       ├── development.py       # Development overrides (DEBUG=True)
│   │   │       └── production.py        # Production overrides + strict startup validation
│   │   ├── requirements/
│   │   │   ├── base.txt                 # Pinned shared Python dependencies
│   │   │   ├── development.txt          # Dev-only dependencies (pytest-django, httpx)
│   │   │   └── production.txt           # Production dependencies (extends base)
│   │   └── apps/
│   │       ├── __init__.py              # Applications package marker
│   │       ├── core/                    # Core foundation application
│   │       │   ├── __init__.py          # Core package marker
│   │       │   ├── apps.py              # AppConfig (apps.core)
│   │       │   ├── models.py            # Abstract BaseModel & TimeStampedModel (UUIDv4 PK, timestamps)
│   │       │   ├── tests.py             # Database connectivity, vector math, and health tests
│   │       │   └── migrations/
│   │       │       ├── __init__.py      # Migrations package marker
│   │       │       └── 0001_enable_pgvector.py  # Idempotent CreateExtension("vector") migration
│   │       ├── api/                     # Shared REST API foundation & infrastructure
│   │       │   ├── __init__.py          # API package marker
│   │       │   ├── apps.py              # AppConfig (apps.api)
│   │       │   ├── exceptions.py        # Centralized DRF exception handler (normalized envelopes)
│   │       │   ├── middleware.py        # CorrelationIdMiddleware & structured logging filter
│   │       │   ├── pagination.py        # NexPageNumberPagination & NexCursorPagination
│   │       │   ├── permissions.py       # IsAuthenticatedUser & IsReadOnly base permissions
│   │       │   ├── runtime_client.py    # Dedicated thread-safe AgentRuntimeClient (timeouts, retries, SSRF defense)
│   │       │   ├── runtime_contracts.py # Typed inter-service communication dataclass contracts
│   │       │   ├── throttling.py        # Distributed Redis sliding-window limiter (Lua scripts)
│   │       │   ├── urls.py              # /api/v1/ versioned URL routing
│   │       │   └── tests/               # API architecture test suite (96 tests)
│   │       │       ├── __init__.py
│   │       │       ├── test_exceptions.py
│   │       │       ├── test_middleware.py
│   │       │       ├── test_pagination.py
│   │       │       ├── test_runtime_client.py # Inter-service communication & reliability test suite (11 tests)
│   │       │       └── test_throttling.py
│   │       ├── accounts/                # User and organisation management (empty placeholder)
│   │       ├── agent_runs/              # Agent execution records (empty placeholder)
│   │       ├── audit_logs/              # Security and activity audit trail (empty placeholder)
│   │       ├── projects/                # Project management (empty placeholder)
│   │       └── repositories/            # Git repository integration (empty placeholder)
│   │
│   └── agent-runtime/                   # FastAPI AI agent service
│       ├── requirements.txt             # Pinned Python dependencies (FastAPI, Redis, Uvicorn, httpx, pytest)
│       ├── pytest.ini                   # Asyncio test configuration
│       ├── app/
│       │   ├── main.py                  # ASGI factory create_app() & lifespan context manager
│       │   ├── core/
│       │   │   ├── __init__.py          # Settings export marker
│       │   │   ├── auth.py              # Constant-time internal service authentication middleware (rotation support)
│       │   │   ├── config.py            # Pydantic Settings & strict validation
│       │   │   ├── exceptions.py        # Centralized error handlers & normalized JSON envelopes
│       │   │   ├── http_client.py       # Async httpx client pool with correlation header propagation
│       │   │   ├── logging.py           # Single-line JSON logger with ContextVar correlation & scrubbing
│       │   │   ├── middleware.py        # CorrelationIdMiddleware & streaming RequestBodyLimitMiddleware
│       │   │   └── redis.py             # redis.asyncio connection pool lifecycle & health checks
│       │   ├── api/
│       │   │   ├── __init__.py          # API routers export
│       │   │   ├── health.py            # Decoupled /health (liveness) and /health/ready (readiness)
│       │   │   └── v1/
│       │   │       ├── __init__.py      # V1 API package marker
│       │   │       ├── router.py        # Versioned router prefix /api/v1 & /status, /ping, /tasks endpoints
│       │   │       └── schemas.py       # Strict Pydantic communication contracts (ping, task execution)
│       │   ├── agents/                  # LangGraph agent definitions (future Step 6B+)
│       │   ├── services/                # Business-logic services (future Step 6B+)
│       │   ├── tools/                   # Agent tool implementations (future Step 6B+)
│       │   └── workflows/               # Multi-step agent workflows (future Step 6B+)
│       └── tests/                       # Agent-runtime test suite (34 tests)
│           ├── __init__.py
│           ├── conftest.py              # Async test fixtures & ASGITransport client
│           ├── test_api_v1.py           # Versioned API status endpoint tests
│           ├── test_body_limit.py       # Actual streaming body limit & chunked transfer tests (4 tests)
│           ├── test_config.py           # Settings validation & constraint tests
│           ├── test_exceptions.py       # Normalized error envelope tests (404, 405, 422, 500, custom)
│           ├── test_health.py           # Liveness & readiness dependency failure tests
│           ├── test_middleware.py       # Correlation ID propagation & 413 payload limit tests
│           ├── test_redis.py            # Async Redis connection pool lifecycle tests
│           └── test_service_auth.py     # Shared-secret verification & rotation fallback tests (6 tests)
│
├── cli/
│   └── nex/                             # NEX CLI (scaffolded, not implemented)
│       ├── __init__.py
│       ├── main.py
│       ├── client/
│       ├── commands/
│       ├── config/
│       └── ui/
│   └── tests/
│
├── frontend/                            # React web application (dirs only, no source)
│   ├── public/
│   └── src/
│       ├── components/
│       ├── features/
│       ├── hooks/
│       ├── layouts/
│       ├── lib/
│       ├── pages/
│       ├── services/
│       └── store/
│
├── packages/
│   └── shared/                          # Shared code across services (empty)
│
├── infrastructure/
│   ├── docker/
│   │   ├── backend/
│   │   │   └── Dockerfile               # Multi-stage Django backend image
│   │   ├── agent-runtime/
│   │   │   └── Dockerfile               # Multi-stage FastAPI agent-runtime image
│   │   ├── cli/                         # CLI Dockerfile (not yet needed)
│   │   └── frontend/                    # Frontend Dockerfile (not yet needed)
│   ├── nginx/
│   │   ├── nginx.conf                   # Nginx reverse-proxy configuration
│   │   └── README.md                    # Production TLS deployment checklist
│   └── redis/
│       └── redis.conf.template          # Redis config template (password via file, not CLI args)
│
├── scripts/                             # Development and automation scripts (empty)
└── tests/                               # Cross-service integration tests (empty)
```

---

## 3. Technology Stack

| Layer | Technology | Pinned Version | Status |
|---|---|---|---|
| **Primary Database** | PostgreSQL + pgvector | pg17 (vector 0.8.7) | **Operational & Verified** |
| **Backend API** | Django | 5.2.3 | **Operational & Verified** |
| **Backend Framework** | Django REST Framework | 3.16.0 | **Operational & Verified** |
| **Database Driver** | psycopg (v3 binary) | 3.2.9 | **Operational & Verified** |
| **Redis Cache / Driver** | django-redis | 5.4.0 (redis 8.1.0) | **Operational & Verified** |
| **Settings Management**| django-environ | 0.12.0 | **Operational & Verified** |
| **Static Files** | whitenoise | 6.9.0 | Configured |
| **WSGI Server** | gunicorn | 23.0.0 | **Operational & Verified** |
| **AI Agent Runtime** | FastAPI | 0.115.14 | **Operational & Verified** |
| **ASGI Server** | uvicorn[standard] | 0.34.3 | **Operational & Verified** |
| **Agent Settings** | pydantic-settings | 2.10.1 | Configured |
| **Cache / Queue** | Redis | 7.4.4-alpine | **Operational & Verified** |
| **Reverse Proxy** | Nginx | 1.28.0-alpine | **Operational & Verified** |
| **Python Base Image** | python:3.12.11-slim-bookworm | 3.12.11 | Pinned in both Dockerfiles |
| **Linter/Formatter** | Ruff | ≥ 0.11, < 1.0 | Configured in pyproject.toml |
| **Type Checker** | mypy | ≥ 1.15, < 2.0 | Configured in pyproject.toml |
| **Test Runner** | pytest / Django test runner | ≥ 8.3 / Django 5.2 | **95/95 Tests Passed** |

---

## 4. Database Architecture & Standards

### 4.1 Database Engine & Extension

- **Engine:** PostgreSQL 17 via official `pgvector/pgvector:pg17` image.
- **Vector Extension:** `vector` v0.8.7 enabled via Django migration `apps/backend/apps/core/migrations/0001_enable_pgvector.py`.
- **Driver:** `psycopg[binary]==3.2.9` (psycopg 3 native C-wheel bundle).
- **Driver Integration:** Django's `django.db.backends.postgresql` natively utilizes psycopg 3.

### 4.2 Connection Management & Session Timeouts

Configured in `apps/backend/config/settings/base.py`:

```python
# Persistent connections avoid per-request handshake overhead
CONN_MAX_AGE = env.int("DB_CONN_MAX_AGE", default=60)
CONN_HEALTH_CHECKS = env.bool("DB_CONN_HEALTH_CHECKS", default=True)

# Connection parameters & safety limits
OPTIONS = {
    "connect_timeout": env.int("DB_CONNECT_TIMEOUT", default=10),
    "options": (
        "-c statement_timeout=30000 "                     # 30s query timeout (anti-DoS)
        "-c lock_timeout=10000 "                          # 10s lock timeout (prevents deadlocks)
        "-c idle_in_transaction_session_timeout=60000"    # 60s idle transaction cleanup
    ),
}
```

### 4.3 Model Architecture Conventions

All persistent application models must inherit from `apps.core.models.BaseModel` or `TimeStampedModel`:

| Standard | Rule | Implementation in `BaseModel` |
|---|---|---|
| **Primary Key** | Non-sequential UUIDv4 | `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` |
| **Created Timestamp**| Immutable ISO UTC timestamp | `created_at = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)` |
| **Updated Timestamp**| Automatic update on save | `updated_at = models.DateTimeField(auto_now=True, editable=False, db_index=True)` |
| **Default Ordering** | Reverse chronological | `ordering = ["-created_at"]` |
| **Foreign Keys** | Always explicit `on_delete` | Prefer `models.PROTECT` or `models.CASCADE` strictly based on lifecycle ownership. |
| **Indexes** | Explicit `db_index` or `indexes` | Composite indexes on frequently queried pairs; avoid redundant single-column indexes. |
| **Nullability** | Avoid `null=True` on CharField/TextField | Use `blank=True, default=""` for string fields to avoid dual-null states. |

---

## 5. Django Core Backend Architecture & Standards (Step 5A)

### 5.1 Shared API Foundation (`apps.api`)

`apps.api` provides shared infrastructure for all future REST API modules:

| Component | Module | Responsibility |
|---|---|---|
| **Exception Handling** | `exceptions.py` | Centralized DRF `EXCEPTION_HANDLER` normalizing all errors into `{"error": "...", "message": "...", "detail": ...}`. Conceals stack traces and returns correlation IDs on HTTP 500. |
| **Correlation Tracking**| `middleware.py` | `CorrelationIdMiddleware` assigns or validates UUID4 `X-Correlation-Id` on requests and injects into structured logs and response headers. |
| **Rate Limiting** | `throttling.py` | Distributed Redis sliding-window counter via atomic Lua script. O(1) memory, HMAC-masked client keys, 10 distinct policies with endpoint-specific fail-closed/fail-open resilience. |
| **Pagination** | `pagination.py` | `NexPageNumberPagination` (default, offset-based) & `NexCursorPagination` (keyset cursor for high-volume collections). Max page size 100. |
| **Permissions** | `permissions.py` | `IsAuthenticatedUser` (verifies authentication & `is_active`) and `IsReadOnly` (allows safe methods). |
| **API Versioning** | `urls.py` | Versioned route mounting under `/api/v1/` with namespace `api_v1`. |

### 5.2 Distributed Sliding-Window Rate Limiter Architecture

```
Client Request  ──►  CorrelationIdMiddleware (attaches UUID4)
                            │
                     SlidingWindowThrottle
                            │
               Resolve Client ID: user:{id} or ip:{resolved_ip}
                            │
               HMAC-SHA256 Mask: rate:<policy>:<masked_16_hex>:<bucket>
                            │
                     Redis Lua Script (Atomic)
               - Fetch previous & current window counts
               - effective = previous * overlap + current
               - If effective >= limit: return {0, count, retry_after}
               - If effective < limit: INCR current, EXPIRE (2*window), return {1, count, 0}
                            │
               ┌────────────┴────────────┐
             Allowed                  Exceeded
               │                         │
          Continue View          HTTP 429 Too Many Requests
                                 Retry-After: <seconds>
                                 {"error": "rate_limit_exceeded"}
```

### 5.2 Distributed Sliding-Window Rate Limiter Architecture

```
Client Request  ──►  CorrelationIdMiddleware (attaches UUID4)
                            │
                     SlidingWindowThrottle
                            │
               Resolve Client ID: user:{id} or ip:{resolved_ip}
               (canonicalizes IPv4/IPv6, strips proxy ports, takes XFF[-num_proxies])
                            │
               HMAC-SHA256 Mask: rate:<policy>:<masked_16_hex>:<bucket>
                            │
                     Redis Lua Script (Atomic)
               - Fetch previous & current window counts
               - effective = previous * overlap + current
               - If effective >= limit: return {0, count, retry_after}
               - If effective < limit: INCR current, EXPIRE (2*window), return {1, count, 0}
                            │
               ┌────────────┴────────────┐
             Allowed                  Exceeded
               │                         │
          Continue View          HTTP 429 Too Many Requests
                                 Retry-After: <seconds>
                                 {"error": "rate_limit_exceeded"}
```

#### 5.2.1 Algorithm Justification: Sliding Window Counter vs. Log

NEX explicitly implements an **atomic Sliding Window Counter** approximation (using two bucket keys and overlap fraction interpolation) rather than an exact **Sliding Window Log**:

- **Memory Efficiency:** A sliding window log requires a Redis sorted set (`ZADD`) storing individual millisecond timestamps for every request. Under high traffic or DDoS attacks, memory consumption scales linearly with request volume ($O(N)$ memory). The sliding window counter uses exactly 2 scalar integer keys per client ($O(1)$ constant memory), completely preventing memory exhaustion.
- **Atomicity & Latency:** The check-and-increment runs inside a single atomic Redis Lua script in sub-millisecond execution time, avoiding multiple round-trips.
- **Accuracy:** The counter provides ~99% accuracy compared to an exact log, eliminating the $2\times$ burst-at-boundary vulnerability of fixed-window counters while maintaining constant memory overhead.

#### 5.2.2 Explicit Failure-Policy Matrix (All 10 Categories)

NEX separates policies into availability-first (fail-open) and security-first (fail-closed) categories when Redis is unreachable:

| Policy Scope | Limit / Window | Failure Mode | Trade-off & Engineering Rationale |
|---|:---:|:---:|---|
| `anonymous` | 60 / 60s | **FAIL-OPEN** | Availability-first. Preserves public browsing and API health checks during transient Redis outages. |
| `authenticated` | 300 / 60s | **FAIL-OPEN** | Availability-first. Prevents Redis hiccups from breaking active, authenticated developer sessions. |
| `agent_run` | 20 / 60s | **FAIL-OPEN** | Availability-first. Allows ongoing AI agent execution requests; downstream API limits handle provider quota. |
| `admin_operations` | 30 / 60s | **FAIL-CLOSED** | Security-first. Prevents abuse of sensitive administrative and configuration operations during outages. |
| `login` | 10 / 60s | **FAIL-CLOSED** | Security-first. Prevents brute-force credential stuffing and password guessing during Redis downtime. |
| `registration` | 5 / 60s | **FAIL-CLOSED** | Security-first. Blocks automated bot account creation and registration spam during outages. |
| `otp_verify` | 5 / 300s | **FAIL-CLOSED** | Security-first. Prevents brute-forcing short-lived OTP codes during outages. |
| `otp_resend` | 3 / 300s | **FAIL-CLOSED** | Security-first. Blocks SMS/email flooding and cost-exhaustion attacks during outages. |
| `password_reset` | 5 / 300s | **FAIL-CLOSED** | Security-first. Prevents account enumeration and email inbox spamming during outages. |
| `account_sensitive` | 10 / 300s | **FAIL-CLOSED** | Security-first. Protects email changes, 2FA modifications, and security-critical account updates. |

*Global Override:* Operators can set `RATE_LIMIT_FAIL_OPEN=False` in environment settings to enforce universal fail-closed behavior across all endpoints during security incidents.

#### 5.2.3 HMAC Secret Rotation Operational Procedure

Rate-limit keys are derived using `HMAC-SHA256(client_id, RATE_LIMIT_HMAC_SECRET)[:16]`. Raw user IDs and IP addresses are never written to Redis.

**Operational Rotation Steps:**
1. Generate a new cryptographically random 32+ character secret:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update `RATE_LIMIT_HMAC_SECRET` in production configuration / secret store.
3. Deploy update via zero-downtime rolling restart of backend workers.
4. **Security & System Impact during Rotation:**
   - Existing Redis keys use the old HMAC hash and naturally expire within $2 \times \text{window}$ (maximum 10 minutes).
   - Requests arriving immediately after rotation compute the new HMAC hash, giving clients a fresh counter starting at 0 for at most one window cycle.
   - No data corruption occurs and zero client identities are leaked.
   - If an immediate reset of all counters is desired, run: `redis-cli --scan --pattern "rate:*" | xargs redis-cli del`.

#### 5.2.4 Trusted Proxy Topology & Anti-Spoofing Architecture

NEX assumes the standard production topology:
`Client -> Proxy_1 (e.g. Cloudflare) -> ... -> Proxy_N (Nginx) -> Django`

- Nginx appends `$remote_addr` to `X-Forwarded-For`.
- The real client IP is strictly extracted from `addresses[-num_proxies]`.
- Any values injected by the client to the left of `-num_proxies` are completely discarded, preventing IP spoofing.
- The resolved IP is canonicalized using `ipaddress` (standardizing IPv4, bracketed IPv6, and compressed/uncompressed IPv6) before HMAC hashing.

---

## 6. Health Checks & Reliability

### 6.1 Endpoint Classification

| Endpoint | Type | Target | Query Executed | Failure Code |
|---|---|---|---|---|
| `GET /health/` | **Liveness** | Django Worker | None (process alive) | 500 |
| `GET /health/live/`| **Liveness** | Django Worker | None (process alive) | 500 |
| `GET /health/ready/`| **Readiness** | Database | `SELECT 1;` | 503 Service Unavailable |
| `GET /nginx-health`| **Liveness** | Nginx Proxy | None (Nginx alive) | 502/503 |
| `docker healthcheck`| **Container** | Postgres/Redis | `pg_isready` / `redis-cli ping` | Container Unhealthy |

### 6.2 Failure Isolation

- When the database is offline, `/health/` continues to return HTTP 200 (process alive).
- When the database is offline, `/health/ready/` returns HTTP 503 `{"error": "service_unavailable", ...}` without leaking passwords, IP addresses, or stack traces.

---

## 7. Migration Management & Operational Procedures

### 6.1 Principles

1. Migrations are strictly version-controlled inside each app (`migrations/` directory).
2. Migrations must be idempotent and non-destructive.
3. Destructive database commands (`migrate --fake`, `flush`, `reset_db`) must **never** be run automatically during container startup.

### 6.2 Development Migration Workflow

```bash
# 1. Create migrations after modifying models
docker compose exec backend python manage.py makemigrations

# 2. Inspect generated SQL before applying
docker compose exec backend python manage.py sqlmigrate <app_name> <migration_number>

# 3. Apply migrations explicitly
docker compose exec backend python manage.py migrate

# 4. Check migration status
docker compose exec backend python manage.py showmigrations
```

### 6.3 Production Migration Workflow

1. Perform database backup prior to migration deployment:
   ```bash
   docker compose -f docker-compose.prod.yml exec postgres \
     pg_dump -U nex -d nex -Fc > "backup_$(date +%Y%m%d_%H%M%S).dump"
   ```
2. Run migration task as a dedicated one-shot job:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps backend python manage.py migrate
   ```
3. Verify readiness endpoint:
   ```bash
   curl -f http://localhost:80/health/ready/
   ```

---

## 7. Backup and Restoration Strategy

### 7.1 Logical Backups (`pg_dump`)

- **Format:** Custom compressed format (`-Fc`) allows selective table restore and parallel restoration.
- **Command:**
  ```bash
  pg_dump -U nex -d nex -Fc -f /backups/nex_backup.dump
  ```
- **Restoration:**
  ```bash
  pg_restore -U nex -d nex --clean --if-exists /backups/nex_backup.dump
  ```

### 7.2 Storage Persistence

- Data directory `/var/lib/postgresql/data` is mounted to named volume `postgres_data`.
- Persistent across container teardowns (`docker compose down`).
- Only deleted if explicitly instructed with `-v` (`docker compose down -v`).

---

## 8. Database Security Controls

| Security Control | Implementation | Verification Status |
|---|---|---|
| **No Public Port Exposure** | `5432/tcp: null` in container port bindings. Accessible only on internal Docker network. | **PASSED** |
| **Network Segmentation** | Postgres is on `internal` bridge network (`internal: true`). No outbound internet access. | **PASSED** (`Network is unreachable`) |
| **Credential Isolation** | Passwords injected exclusively via environment variables; never hardcoded or committed. | **PASSED** |
| **Non-Superuser Capability** | Application queries and vector distance calculations verified working under non-superuser role `nex_app`. | **PASSED** |
| **Query Timeout Protection** | `statement_timeout=30s` prevents rogue queries from exhausting connection pools. | **PASSED** |
| **Transaction Leak Protection** | `idle_in_transaction_session_timeout=60s` drops orphaned locks automatically. | **PASSED** |
| **Sanitized Logging** | Nginx access logs `$uri` (no query strings); Django health endpoints log warnings without connection details. | **PASSED** |
| **Startup Secret Validation** | `production.py` aborts startup if `SECRET_KEY`, `ALLOWED_HOSTS`, or `DATABASE_URL` are missing or insecure. | **PASSED** |

---

## 9. FastAPI Agent Runtime Core Architecture (Step 6A)

### 9.1 Architectural Boundaries & Responsibility Separation

NEX enforces a strict architectural boundary between the Django web backend and the FastAPI agent runtime:

| Dimension | Django Core Backend (`apps/backend`) | FastAPI Agent Runtime (`apps/agent-runtime`) |
|---|---|---|
| **Primary Domain** | User accounts, auth/authz, project ownership, billing, audit trail | AI execution runtime, LangGraph workflows, tool orchestration, code analysis |
| **External Reachability** | Accessible via Nginx reverse proxy on port 8080 (public network) | Strictly internal service; not mapped to host ports; not proxied by Nginx |
| **Docker Networks** | `internal` (Postgres, Redis) | `internal` (Backend, Redis) + `egress` (Outbound AI provider APIs) |
| **Redis Database** | DB 0 (`redis://redis:6379/0`) for rate-limiting and cache | DB 1 (`redis://redis:6379/1`) for agent state and execution coordination |
| **Authentication Authority** | Authoritative user model, JWT/session issuance | Internal service caller verification; accepts `X-Correlation-Id` |
| **Public API Gateway** | Primary entry point for web frontend and CLI | Inter-service target invoked exclusively by Django backend |

### 9.2 Application Lifecycle & Connection Pooling

- **Modern Async Lifespan:** Bootstrapped via Starlette/FastAPI `@asynccontextmanager lifespan(app: FastAPI)` in [main.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/main.py), superseding deprecated `@app.on_event`.
- **Async Redis Pool:** Managed via `redis.asyncio.ConnectionPool.from_url` in [redis.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/redis.py) with bounded timeouts (`socket_connect_timeout=2.0s`, `socket_timeout=2.0s`) and max 50 connections.
- **Inter-Service HTTP Pool:** Managed via `httpx.AsyncClient` in [http_client.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/http_client.py) with automatic outbound `X-Correlation-Id` header injection hook and graceful teardown.

### 9.3 Observability, Correlation Tracking & Security Middlewares

- **Correlation ID Middleware:** [middleware.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/middleware.py) captures incoming `X-Correlation-Id` (sanitizing to 1–64 alphanumeric, `-`, `_` characters) or generates a clean 32-character UUIDv4 hex identifier. The ID is stored in a `ContextVar[str]` and returned in response headers alongside `X-Process-Time-Ms`.
- **Structured JSON Logging:** [logging.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/logging.py) emits single-line JSON records to `stdout` containing `timestamp`, `level`, `logger`, `message`, `correlation_id`, and `environment`. Sensitive patterns (`password`, `token`, `secret`, `authorization`, credentials in Redis URLs) are scrubbed automatically.
- **Payload Boundary Enforcement:** `RequestBodyLimitMiddleware` inspects `Content-Length` headers, rejecting payloads exceeding `max_request_body_size_bytes` (10 MB default) with HTTP 413 `PAYLOAD_TOO_LARGE`.
- **Centralized Normalized Error Envelopes:** [exceptions.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/exceptions.py) formats all error responses (`RequestValidationError`, `HTTPException`, custom `NexRuntimeError`, and unhandled `Exception`) into the uniform NEX JSON envelope. Unhandled 500 exceptions conceal stack traces when `app_debug=False`.

### 9.4 Health Probes & Versioned API

- **Decoupled Health Architecture:** [health.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/api/health.py) provides:
  - `GET /health` and `GET /health/live`: Pure liveness check returning HTTP 200 without downstream I/O.
  - `GET /health/ready`: Readiness check probing Redis DB 1 (`PING`) and Django backend reachability (`GET /health/`). Returns HTTP 200 `{"status": "ready"}` or HTTP 503 `{"status": "degraded"}`.
- **Versioned Router:** Mounted at `/api/v1/` in [router.py](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/api/v1/router.py) with `/api/v1/status`, `/api/v1/ping`, and `/api/v1/tasks/verify`.

---

## 10. Django ↔ FastAPI Backend Communication (Step 6F)

### 10.1 Communication Architecture

The NEX platform strictly enforces the following inter-service communication path:

```
Frontend / CLI  ──(HTTP/TLS)──>  Nginx Reverse Proxy  ──(Internal)──>  Django Backend  ──(Internal)──>  FastAPI Runtime
(Public Users)                    (Port 8080)                           (Port 8000)                      (Port 8001)
```

1. **Django as API Gateway:** Django remains the authoritative public boundary responsible for user authentication, organizations, repository ownership, permissions, and business models.
2. **FastAPI as Internal Execution Engine:** FastAPI is an isolated runtime reachable strictly within the Docker `internal` network. It has no published host ports and cannot be reached directly by external clients.
3. **Dedicated Internal Client:** All communication from Django to FastAPI must route through [`AgentRuntimeClient`](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/backend/apps/api/runtime_client.py). Django views and domain logic never execute ad-hoc HTTP requests.

### 10.2 Service Authentication & Key Rotation

- **Mutual Service Secret:** Inter-service requests carry `X-Internal-Service-Key` (or `Authorization: Bearer <secret>`).
- **Constant-Time Verification:** [`InternalServiceAuthMiddleware`](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/auth.py) uses `secrets.compare_digest` to prevent timing attacks.
- **Zero-Downtime Key Rotation:** Both Django and FastAPI support `INTERNAL_SERVICE_SECRET` (primary) and `INTERNAL_SERVICE_SECRET_FALLBACK` (secondary). Operational rotation steps:
  1. Generate new 32+ character random hex secret `NEW_SECRET`.
  2. Set `INTERNAL_SERVICE_SECRET_FALLBACK` to the current active secret across both services.
  3. Set `INTERNAL_SERVICE_SECRET` to `NEW_SECRET` across both services.
  4. Deploy both services. FastAPI accepts both primary and fallback keys.
  5. Once all Django workers are upgraded, clear `INTERNAL_SERVICE_SECRET_FALLBACK`.
- **Exempt Routes:** Container health probes (`/health`, `/health/live`) are exempt from service key requirements.

### 10.3 Dynamic Streaming Request Body Size Enforcement

- **ASGI-Level Protection:** [`RequestBodyLimitMiddleware`](file:///Users/himanshukumar/Developer/GenAi%20Projects/nex%20-%20ai%20software%20engineer/apps/agent-runtime/app/core/middleware.py) enforces body size limits on both:
  1. **Stated Content-Length:** Rejects requests with `Content-Length > max_bytes` immediately without buffering.
  2. **Streaming / Chunked Bodies:** Dynamically accumulates byte counts across streamed chunks (`request.stream()`). If received bytes exceed `max_bytes` (10 MB default), stream reading is aborted immediately and HTTP 413 `PAYLOAD_TOO_LARGE` is returned.
  3. **Malformed Headers:** Non-integer `Content-Length` headers return HTTP 400 `BAD_REQUEST`.

### 10.4 Resilient Client Policies & SSRF Defense

- **Explicit Timeout Matrix:**
  - Connect Timeout: 3.0s
  - Read Timeout: 15.0s
  - Write Timeout: 10.0s
  - Pool Timeout: 5.0s
- **Idempotent Retry Policy:**
  - Idempotent methods (`GET`, `HEAD`) retry exactly once on transient `ConnectError` with backoff (0.1s).
  - Non-idempotent methods (`POST`, `PUT`, `DELETE`) NEVER retry automatically, preventing accidental duplicate task triggers or race conditions.
- **SSRF & Traversal Protection:** Request paths are validated before dispatch; paths missing `/`, containing scheme specifiers (`://`), protocol-relative URLs (`//`), or directory traversal (`..`) are rejected immediately with `ValueError`.
- **Correlation Propagation:** Outgoing requests automatically inject `X-Correlation-Id: get_correlation_id()`, enabling unified tracing across Django and FastAPI structured JSON logs.
- **Domain Exception Normalization:** Downstream outages map to `AgentRuntimeUnavailableError`, timeouts map to `AgentRuntimeTimeoutError`, and auth rejections map to `AgentRuntimeAuthenticationError`.

---

## 11. Comprehensive Verification Results (Steps 4, 5A, 6A & 6F)

All checks directly verified against running containers:

| # | Check | Target | Execution Method | Result | Notes |
|---|---|---|---|---|---|
| 1 | Development Compose Config | `docker-compose.yml` | `docker compose config --quiet` | **PASSED** | Valid syntax with internal/egress networks |
| 2 | Production Compose Config | `docker-compose.prod.yml` | `docker compose -f ... config` | **PASSED** | Strictly enforces required secrets (`REDIS_PASSWORD`, `INTERNAL_SERVICE_SECRET`) |
| 3 | Application Image Build | `backend`, `agent-runtime` | `docker compose build` | **PASSED** | Multi-stage Dockerfiles + pinned dependencies (`httpx`, `redis`) |
| 4 | Service Startup | 5 Services | `docker compose up -d` | **PASSED** | All 5 services running |
| 5 | Container Health Checks | All 5 containers | `docker compose ps` | **PASSED** | All 5 containers report `(healthy)` |
| 6 | Nginx → Django Communication | Nginx Port 8080 | `curl http://localhost:8080/health/` | **PASSED** | HTTP 200 `{"status": "ok"}` |
| 7 | Internal Agent-Runtime Probe | Agent Runtime Port 8001 | `docker compose exec backend urllib.request` | **PASSED** | HTTP 200 `{"status": "ok"}` |
| 8 | Unpublished Database Ports | Ports 5432 & 6379 | `docker inspect --format '{{json .NetworkSettings.Ports}}'` | **PASSED** | Both ports `null` (no host binding) |
| 9 | DB External Network Isolation| Postgres & Redis | Outbound socket test to external IP | **PASSED** | `Network is unreachable` |
| 10| Agent-Runtime Outbound Access| Agent-Runtime | Outbound HTTPS request via `egress` network | **PASSED** | Outbound access enabled on egress network |
| 11| Production Settings Rejection | `production.py` & prod Compose | Run with missing/insecure secrets | **PASSED** | Rejects missing secrets at configuration/startup |
| 12| Redis Password Hardening | Redis Service | Inspect config template vs compose args | **PARTIAL** | Health check uses `REDISCLI_AUTH`; template provided |
| 13| Container Hardening & Non-Root| Backend & Agent-Runtime | `docker compose exec ... id` | **PASSED** | Both run as `uid=1001(nex)` |
| 14| Query String Log Exclusion | Nginx Access Log | Request with sensitive query tokens | **PASSED** | URI query parameters omitted from logs |
| 15| Django Backend Automated Tests| `apps` test suite (106 tests)| `manage.py test apps` | **PASSED** | **106/106 tests passed** (10 core + 85 api + 11 runtime_client) |
| 16| Live Redis Rate Limiter | `LoginRateThrottle` | 12 sequential requests via live Redis | **PASSED** | 10 allowed, 11th/12th blocked (HTTP 429) |
| 17| Correlation ID In Header | Nginx → Django | `curl -sI http://localhost:8080/health/` | **PASSED** | Response contains `X-Correlation-Id: <uuid4>` |
| 18| Correlation ID Sanitization | Request with invalid header | Send `X-Correlation-Id: invalid-payload` | **PASSED** | Malformed header replaced with clean UUID4 |
| 19| ContextVar Logging | View/Service log tracing | `test_middleware.py` | **PASSED** | Logs automatically inherit request correlation ID |
| 20| Centralized Error Envelope | DRF Exception Handler | `test_exceptions.py` (11 tests) | **PASSED** | Normalized `error`, `message`, `detail` envelope |
| 21| 10-Category Failure Policy | Rate limit outage suite | `test_throttling.py` (outage tests) | **PASSED** | Sensitive endpoints fail closed; general traffic fails open |
| 22| Anti-Spoofing IP Resolution | XFF extraction (`-num_proxies`) | `test_throttling.py` (proxy suite) | **PASSED** | Correctly resolves real client IP; discards spoofed values |
| 23| IPv4 & IPv6 Normalization | IP Resolution | `test_throttling.py` (normalization suite) | **PASSED** | Port stripping + compressed IPv6 canonicalized |
| 24| Keyset Cursor Determinism | Duplicate timestamps test | `NexCursorPagination` (`-created_at`, `-id`) | **PASSED** | Zero duplicate/omitted records across pages |
| 25| Production Secret Validation | `production.py` | Missing/insecure `RATE_LIMIT_HMAC_SECRET` | **PASSED** | Aborts startup with `FATAL` error |
| 26| Agent-Runtime Unit Test Suite| `agent-runtime` (34 tests) | `docker compose exec agent-runtime pytest` | **PASSED** | **34/34 tests passed** (0 warnings, 0.15s) |
| 27| Service Auth: Valid Secret | FastAPI internal auth | `test_service_auth.py` | **PASSED** | HTTP 200 on valid primary secret |
| 28| Service Auth: Missing Secret | FastAPI internal auth | `test_service_auth.py` | **PASSED** | HTTP 401 UNAUTHORIZED on missing credentials |
| 29| Service Auth: Invalid Secret | FastAPI internal auth | `test_service_auth.py` | **PASSED** | HTTP 401 UNAUTHORIZED on invalid secret |
| 30| Service Auth: Fallback Rotation | FastAPI internal auth | `test_service_auth.py` | **PASSED** | HTTP 200 on fallback rotation key |
| 31| Service Auth: Bearer Header | FastAPI internal auth | `test_service_auth.py` | **PASSED** | HTTP 200 on `Authorization: Bearer <secret>` |
| 32| Streaming Body Limit (413) | Chunked transfer without header | `test_body_limit.py` | **PASSED** | HTTP 413 `PAYLOAD_TOO_LARGE` when streamed bytes > 1MB |
| 33| Streaming Body Within Limit | Chunked transfer within bound | `test_body_limit.py` | **PASSED** | HTTP 200 when chunked bytes within limit |
| 34| Malformed Content-Length | Invalid header format | `test_body_limit.py` | **PASSED** | HTTP 400 `BAD_REQUEST` |
| 35| Django Client SSRF Defense | Path traversal & absolute URLs | `test_runtime_client.py` | **PASSED** | Rejects `http://...` and `..` paths with `ValueError` |
| 36| Django Client Safe Retries | Network drop on GET vs POST | `test_runtime_client.py` | **PASSED** | GET retries once; POST strictly fails without retry |
| 37| Django Client Correlation Tracing| ContextVar propagation | `test_runtime_client.py` | **PASSED** | Attaches active `X-Correlation-Id` to request headers |
| 38| Live Container Round-Trip | Django → FastAPI client | Live container execution script | **PASSED** | `ping`, `get_status`, and `verify_task` succeeded; invalid auth rejected |
| 39| Live Inter-Service Log Tracing| Agent-Runtime structured logs | `docker compose logs agent-runtime` | **PASSED** | Log record tagged with Django's `live-e2e-trace-id-777` |

---

## 12. Known Limitations & Remaining Work

1. **Authentication Classes (Step 5B):** DRF `DEFAULT_AUTHENTICATION_CLASSES` and `DEFAULT_PERMISSION_CLASSES` are prepared and will be activated once the custom user and authentication service are implemented in Step 5B.
2. **Agent Workflows & Tool Execution (Step 6B+):** LangGraph workflow definitions, prompt execution pipelines, repository analyzers, and disposable sandbox runners will be integrated onto the Step 6A/6F foundation.
3. **mTLS for Inter-Service Communication:** In high-security multi-host deployments, mutual TLS (mTLS) with short-lived X.509 client certificates can supplement or supersede shared-secret authentication.
4. **Redis Config Deployment Automation:** While `redis.conf.template` exists and `REDISCLI_AUTH` is used for health checks, automated generation and mounting of `redis.conf` in production environments remains a deployment orchestration task.
5. **TLS Termination:** Nginx is prepared for TLS reverse proxying, but production SSL certificate provisioning (via Let's Encrypt or Cloud Load Balancer) must be configured prior to public launch.

---

*Last updated: 2026-10-31*
