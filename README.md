# NEX

NEX is a proprietary, full-stack AI software engineering platform that helps developers understand, modify, test, review, and ship code through intelligent automation.

> **Project status: Step 11 Completed & Frontend Fully Integrated.** Unified identity system powered by Firebase Authentication across React, Django, and CLI. Step 11 adds complete local Git repository inspection (`nex git *`), production-grade GitHub App authorization (`nex auth github`), comprehensive repository discovery, pagination, PostgreSQL persistence with safe tombstoning, REST API (`/api/v1/repositories/`), safe Git mutations, Pull Request automation (`nex pr`), and end-to-end React frontend integration (`frontend/src/`). Combined platform automated test coverage: **490/490 verified tests passing** (195 Django backend + 34 FastAPI agent-runtime + 125 React frontend + 136 Python CLI). All Docker services operational and healthy.

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
| Web Frontend | React 18 + Vite 6 + Tailwind CSS | 18.3.1 / 6.2.0 |
| Frontend State | Redux Toolkit | 2.6.0 |
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
- **Automated Test Coverage**: **315 verified tests passing across the stack** (139 Django backend tests + 34 FastAPI agent-runtime tests + 83 React frontend tests + 59 Python CLI tests), plus live inter-container integration verified.

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
docker compose ps                               # all 6 services should report (healthy)
curl http://localhost:8080/health/              # Backend liveness probe   → {"status":"ok"}
curl http://localhost:8080/health/ready/        # Backend readiness probe  → {"status":"ready","database":"connected"}
curl http://localhost:8080/nginx-health         # Nginx proxy probe        → {"status":"ok"}
curl http://localhost:3000/                     # Frontend UI probe        → HTTP 200 (HTML)
```

---

## Frontend Development Commands

```bash
# Navigate to frontend directory
cd frontend

# Start Vite development server (port 3000, proxies /api to port 8080)
npm run dev

# Run Vitest automated component and unit test suite
npm test

# Run tests in watch mode
npm run test:watch

# Build production bundle to dist/
npm run build

# Preview production build locally
npm run preview
```

---

## Command-Line Interface (CLI) Commands

The `nex` executable is installed via standard Python packaging (`pyproject.toml`):

```bash
# View all available CLI commands and global options
./.venv/bin/nex --help

# Display CLI version (supports both terminal and machine-readable JSON)
./.venv/bin/nex --version
./.venv/bin/nex --version --json

# Initialize a project configuration (.nex/config.toml)
./.venv/bin/nex init

# Inspect local repository structure, detected languages, manifests, and Git status
./.venv/bin/nex inspect
./.venv/bin/nex inspect --json

# Review working tree or staged code changes
./.venv/bin/nex review
./.venv/bin/nex review --staged

# Plan targeted issue fixes with dry-run preview (HIGH risk requires interactive approval)
./.venv/bin/nex fix "Fix memory leak in auth middleware" --dry-run
./.venv/bin/nex fix "Fix memory leak in auth middleware"

# Run tests under hybrid sandbox execution policy
./.venv/bin/nex test
./.venv/bin/nex test --local

# Scan workspace for exposed credentials, private keys, and loose permissions
./.venv/bin/nex security
./.venv/bin/nex security --strict

# Prepare and submit pull requests (CRITICAL risk requires interactive approval)
./.venv/bin/nex pr --title "Fix authentication token issue" --draft

# Inspect and safely mutate configuration settings (secrets automatically masked)
./.venv/bin/nex config show
./.venv/bin/nex config path
./.venv/bin/nex config get general.default_model
./.venv/bin/nex config set general.default_model "gemini-2.0-flash"

# Local Git inspection and repository diagnostics (Step 11 Phase 1)
./.venv/bin/nex git status                       # Working tree status, merge/rebase state, staged/unstaged
./.venv/bin/nex git status --json                # Machine-readable JSON output
./.venv/bin/nex git branches                     # List local branches and tracking status
./.venv/bin/nex git branches -a                  # Include remote-tracking branches
./.venv/bin/nex git log -n 5                     # View recent commit history
./.venv/bin/nex git diff                         # Inspect unified diffs (sensitive files/tokens redacted)
./.venv/bin/nex git diff --staged                # Inspect staged changes only
./.venv/bin/nex git diff --stat                  # Summary of file additions/deletions
./.venv/bin/nex git remotes                      # Configured remote repository URLs
./.venv/bin/nex git inspect                      # Complete repository health audit and diagnostic

# Inspect historical agent execution runs from Django backend
./.venv/bin/nex runs list
./.venv/bin/nex runs get <run-uuid>

# Inspect and manage authorized GitHub App installations (Step 11 Phase 2)
./.venv/bin/nex auth github                      # Display connected GitHub account and installations
./.venv/bin/nex auth github --connect            # Initiate browser-based GitHub App authorization
./.venv/bin/nex auth github --json               # Machine-readable JSON output

# Discover, sync, and inspect GitHub repositories (Step 11 Phase 3)
./.venv/bin/nex repos list                       # List synchronized repositories (formatted table)
./.venv/bin/nex repos list --visibility private  # Filter by private or public repositories
./.venv/bin/nex repos list --search "core"       # Search repositories by name or description
./.venv/bin/nex repos list --json                # Machine-readable JSON repository list
./.venv/bin/nex repos sync                       # Trigger manual sync across active installations
./.venv/bin/nex repos show <owner/repo>          # Display repository details, clone URLs, and metadata

# Safe Git operations with approval policy & stale-plan detection (Step 11 Phase 4)
./.venv/bin/nex git branch list                  # List local and remote branches
./.venv/bin/nex git branch create <name>         # Safely create branch with validation (--dry-run supported)
./.venv/bin/nex git branch switch <name>         # Safely switch branch (enforces clean working tree)
./.venv/bin/nex git stage <files...>             # Selectively stage files (blocks wildcards & sensitive files)
./.venv/bin/nex git unstage <files...>           # Selectively unstage files from Git index
./.venv/bin/nex git staged                       # Inspect staged metrics and redacted diff preview
./.venv/bin/nex git commit -m "<message>"        # Commit staged changes with preview & developer approval
./.venv/bin/nex git push [--remote] [--branch]   # Push approved branch via secure GIT_ASKPASS token helper

# Pull Request integration with preview fingerprinting & approval (Step 11 Phase 5)
./.venv/bin/nex pr [--base main] [--title "..."] # Preview & publish PR with CRITICAL-risk approval
./.venv/bin/nex pr --dry-run                     # Preview commit/file comparison without publishing
./.venv/bin/nex pr list [--state open|all]       # List repository pull requests with status badges
./.venv/bin/nex pr view <number> [--sync]        # Inspect PR details and sync live GitHub status

# Run CLI automated unit and integration test suite (136 tests)
./.venv/bin/pytest cli/tests/

# Run CLI linting and type checking
./.venv/bin/ruff check cli/
./.venv/bin/mypy cli/
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

### GitHub App Configuration & Setup URL Reference

- **GitHub App Setup URL (Backend Callback)**: `http://localhost:8080/api/v1/repositories/github/callback/`
  - Configured in the GitHub App settings under **Setup URL** (redirect on install).
  - GitHub redirects here on both fresh installations and configuration updates (`github.com/settings/installations/<id>`).
  - Fresh installs are validated with single-use Redis cryptographic state tokens (anti-replay defense).
  - Updates from existing installations without state are safely reconciled for verified existing users (unbound installations are rejected with `UNVERIFIED_INSTALLATION`).
  - Note: **OAuth Callback URL** is **not required** for the installation-only flow because authorization relies on the GitHub App Setup URL and installation tokens.
- **Frontend Redirect Destination (`GITHUB_APP_CALLBACK_URL`)**: `http://localhost:3000/settings`
  - Once the backend processes the installation callback, it redirects the browser to this frontend URL with query parameters (`?github=connected` or `?github=connected&sync=failed`).
- **Webhook Endpoint**: `http://localhost:8080/api/v1/repositories/github/webhook/`
  - Receives installation, repository, and pull request lifecycle events.
  - Payloads are verified via constant-time HMAC-SHA256 against `GITHUB_WEBHOOK_SECRET`.
- **Private Key Configuration & Docker Mount**:
  - Store your 2048-bit RSA PEM key on the host at `./secrets/github-app-private-key.pem`.
  - The key is mounted read-only into the Django backend container at `/run/secrets/github-app-private-key.pem:ro`.
  - Configured via `GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github-app-private-key.pem`.
  - The key is validated with strict cryptographic checks (rejecting SHA256 fingerprints, public keys, or non-PEM strings).
- **Required Minimum Permissions (Repository)**:
  - `Metadata`: Read-only (mandatory for all GitHub Apps)
  - `Contents`: Read and write (for repository inspection, file staging, branch creation, commit creation, and git push)
  - `Pull requests`: Read and write (for pull request creation, listing, inspection, and live sync)
- **Required Webhook Events**:
  - `Installation` (installation lifecycle: created, deleted, suspend)
  - `Installation target` / `Installation repositories` (repository access changes: added, removed)
  - `Repository` (repository lifecycle: created, deleted, archived, renamed)
  - `Pull request` (PR lifecycle: opened, closed, synchronized, edited)
- **Local Webhook Testing (HTTPS Tunnel)**:
  - GitHub webhooks require a publicly accessible HTTPS endpoint. For local development, establish an HTTPS tunnel:
    ```bash
    # Option A: ngrok
    ngrok http 8080

    # Option B: Cloudflare Tunnel
    cloudflared tunnel --url http://localhost:8080
    ```
  - In your GitHub App settings, set **Webhook URL** to:
    `https://<your-tunnel-subdomain>/api/v1/repositories/github/webhook/`
  - Set **Webhook secret** to match `GITHUB_WEBHOOK_SECRET` in `.env`.
- **Security Notice on Installation Linking**:
  - Insecure manual linking by Installation ID has been completely removed to prevent unauthorized installation hijacking. All installation bindings require verified cryptographic state tokens or Setup URL owner verification.
- **Frontend Development Proxy**:
  - In `frontend/vite.config.js`, both `/api` and `/health` are proxied to `http://localhost:8080`.

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
cli/                NEX command-line interface (Typer, Rich, HTTPX, Pydantic, POSIX exit codes)
frontend/           React web application (Cyber Brutalist, Redux Toolkit, containerized)
packages/           Shared library code
infrastructure/     Dockerfiles (backend, agent-runtime, frontend), Nginx proxy, Redis template
scripts/            Development automation scripts
tests/              Cross-service test suites
```

See [DIRECTORY.md](DIRECTORY.md) for the complete annotated tree, model standards, and operational guidelines.

---

## Licence

Copyright (c) 2026 Himanshu Kumar. All rights reserved. Proprietary and confidential — see [LICENSE](LICENSE).
