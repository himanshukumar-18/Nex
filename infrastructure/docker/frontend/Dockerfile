# NEX Frontend — Dockerfile
#
# Multi-stage build:
#   deps        -- installs npm dependencies using committed package-lock.json (npm ci)
#   development -- runs Vite dev server with hot module replacement (HMR)
#   builder     -- compiles production React assets to dist/
#   production  -- minimal, hardened Nginx runtime delivering static assets
#
# Base image pin policy:
#   Node.js: node:22-alpine (Active LTS)
#   Nginx:   nginx:1.28.0-alpine (matches infrastructure/nginx)
#   Update tags when upstream CVE advisories are published.
#
# All paths in COPY instructions are relative to the build context (repo root).

# ============================================================================
# Stage 1: Dependencies
# Installs node_modules cleanly via npm ci
# ============================================================================
FROM node:22-alpine AS deps

WORKDIR /app

# Install dependencies using committed lockfile only
COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci --prefer-offline --no-audit

# ============================================================================
# Stage 2: Development
# Lightweight development runtime running Vite dev server with HMR
# ============================================================================
FROM node:22-alpine AS development

WORKDIR /app

ENV NODE_ENV=development

# Copy dependencies with ownership assigned to non-root node user (uid: 1000)
COPY --from=deps --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
COPY --chown=node:node frontend/ ./

# Ensure .vite cache directory can be created by node user
RUN mkdir -p /app/node_modules/.vite /app/node_modules/.vite-temp && \
    chown -R node:node /app

USER node

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

# ============================================================================
# Stage 3: Builder
# Compiles production-optimized client bundle
# ============================================================================
FROM node:22-alpine AS builder

WORKDIR /app

ENV NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/ ./

RUN npm run build

# ============================================================================
# Stage 4: Production Runtime
# Hardened Nginx 1.28 delivering static assets with SPA routing
# ============================================================================
FROM nginx:1.28.0-alpine AS production

# Remove default nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy hardened SPA Nginx configuration
COPY infrastructure/docker/frontend/nginx.conf /etc/nginx/nginx.conf

# Copy production build artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create required temp directories in /tmp for non-root execution
RUN mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /tmp /usr/share/nginx/html

USER nginx

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1

ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
