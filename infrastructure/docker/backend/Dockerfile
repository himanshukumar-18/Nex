# NEX Backend — Dockerfile
#
# Multi-stage build:
#   builder  -- installs Python dependencies into an isolated prefix
#   runtime  -- copies only installed packages and application source
#
# Base image pin policy:
#   Pin to a specific patch version (e.g. 3.12.11).
#   Update when CVEs are published for the base OS layer.
#   Monitor: https://hub.docker.com/_/python/tags?name=3.12
#   Also run: docker scout cves nex-backend:dev  (after each build)
#
# To update the base image:
#   1. Change the tag on BOTH FROM lines below to the new patch version.
#   2. Rebuild: docker compose build backend
#   3. Run tests, then commit the tag change with the reason documented.

# ============================================================================
# Stage 1: builder
# Installs Python dependencies into /install so the runtime stage receives
# only the compiled packages without build tooling.
# ============================================================================
FROM python:3.12.11-slim-bookworm AS builder

# Fail immediately on any shell error.
SHELL ["/bin/sh", "-e", "-c"]

WORKDIR /build

# System packages needed only to compile Python C extensions.
# libpq-dev provides headers required to build psycopg from source.
# psycopg[binary] ships pre-compiled wheels that bundle libpq, so libpq-dev
# is only needed here (builder) to satisfy any source-build fallback, and
# is NOT copied into the runtime stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to maximise Docker layer cache reuse.
# The dep-install layer is only invalidated when requirements change.
COPY apps/backend/requirements/base.txt ./requirements.txt

# Install to an isolated prefix so the runtime stage can copy cleanly
# without inheriting the full builder filesystem.
RUN pip install \
        --no-cache-dir \
        --timeout 60 \
        --prefix=/install \
        -r requirements.txt

# ============================================================================
# Stage 2: runtime
# Minimal image — only what is needed to run the application.
# ============================================================================
FROM python:3.12.11-slim-bookworm AS runtime

SHELL ["/bin/sh", "-e", "-c"]

# psycopg[binary] bundles its own libpq — no system libpq packages are needed
# at runtime. The runtime stage installs no additional system packages,
# minimising the attack surface.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage only.
COPY --from=builder /install /usr/local

# ---------------------------------------------------------------------------
# Non-root application user
# ---------------------------------------------------------------------------
RUN groupadd --system --gid 1001 nex \
    && useradd --system --uid 1001 --gid nex --no-create-home --shell /sbin/nologin nex

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
WORKDIR /app

# .dockerignore prevents .env, __pycache__, .venv, tests etc. from being
# included in the build context.
COPY apps/backend/ .

# Ensure the non-root user owns the application directory before switching.
# staticfiles/ is created here so the directory exists even before collectstatic.
RUN mkdir -p staticfiles \
    && chown -R nex:nex /app

USER nex

# ---------------------------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------------------------

# DJANGO_SETTINGS_MODULE and DJANGO_SECRET_KEY are intentionally NOT set here.
# They must be supplied by the orchestration layer (Docker Compose / Kubernetes
# secrets) to prevent any insecure default being baked into the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# Exec-form ENTRYPOINT ensures the process is PID 1 and receives OS signals
# (SIGTERM / SIGINT) directly. Gunicorn handles SIGTERM with graceful shutdown.
#
# Worker tuning:
#   Start with 2 workers for the container sizing in docker-compose.prod.yml.
#   A reasonable default is (2 × vCPU) + 1.
#   Timeout: 30 s — request handling must complete within this window.
ENTRYPOINT ["gunicorn"]
CMD ["config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
