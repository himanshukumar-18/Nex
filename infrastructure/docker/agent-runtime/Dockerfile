# NEX Agent Runtime — Dockerfile
#
# Multi-stage build:
#   builder  -- installs Python dependencies into an isolated prefix
#   runtime  -- copies only installed packages and application source
#
# Base image pin policy:
#   Pin to a specific patch version (e.g. 3.12.11).
#   Update when CVEs are published for the base OS layer.
#   Monitor: https://hub.docker.com/_/python/tags?name=3.12
#   Also run: docker scout cves nex-agent-runtime:dev  (after each build)
#
# OS security updates:
#   Do NOT use apt-get upgrade inside the image — it breaks reproducibility
#   and may silently install untested package versions. Instead, rebuild from
#   a new pinned base image tag when OS updates are required.
#
# To update the base image:
#   1. Change the tag on BOTH FROM lines below.
#   2. Rebuild: docker compose build agent-runtime
#   3. Run tests, then commit the tag change with the reason documented.

# ============================================================================
# Stage 1: builder
# ============================================================================
FROM python:3.12.11-slim-bookworm AS builder

SHELL ["/bin/sh", "-e", "-c"]

WORKDIR /build

# No C extension compilation is required for the current dependency set.
# If LangGraph or future packages require gcc, add it here (builder only).
COPY apps/agent-runtime/requirements.txt ./requirements.txt

RUN pip install \
        --no-cache-dir \
        --timeout 60 \
        --prefix=/install \
        -r requirements.txt

# ============================================================================
# Stage 2: runtime
# ============================================================================
FROM python:3.12.11-slim-bookworm AS runtime

SHELL ["/bin/sh", "-e", "-c"]

# No additional system packages are required for the current implementation.
# The slim-bookworm base already includes essential OS libraries.
# OS security updates are handled by rebuilding from a newer pinned base tag,
# not by running apt-get upgrade inside the image.

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

COPY apps/agent-runtime/ .

RUN chown -R nex:nex /app

USER nex

# ---------------------------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------------------------

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8001

# Exec-form ENTRYPOINT — PID 1 receives OS signals directly.
# uvicorn handles SIGTERM with graceful shutdown via --timeout-graceful-shutdown.
#
# --host 0.0.0.0 binds to all interfaces inside the Docker network.
# The service is only reachable from other containers on the internal network —
# it is not publicly reachable (not proxied by Nginx, not on the public network).
ENTRYPOINT ["uvicorn"]
CMD ["app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1", \
     "--log-level", "info", \
     "--timeout-graceful-shutdown", "10"]
