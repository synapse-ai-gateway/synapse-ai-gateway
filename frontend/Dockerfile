# syntax=docker/dockerfile:1
# ============================================================================
# Synapse AI Gateway — admin console (React + Vite)
#
#   Stage 1 (builder)   node:20-alpine builds the SPA bundle.
#   Stage 2 (runtime)   nginx-unprivileged (non-root by default) serves the
#                       static files on :8080 with SPA fallback.
#
# Build:
#   docker build -t synapse-admin:dev frontend/
# Point at a non-default backend:
#   docker build --build-arg VITE_GATEWAY_URL=https://gw.example.com \
#                -t synapse-admin:prod frontend/
# ============================================================================
ARG NODE_VERSION=20
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.27-alpine

# ----------------------------------------------------------------------------
# Stage 1 — builder
# ----------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS builder

ENV CI=true

WORKDIR /app

# Cache-friendly: install deps before copying source.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Build-time configuration. Vite bakes these into the bundle, so they must be
# set at docker build time, not container run time.
ARG VITE_GATEWAY_URL=http://localhost:8080
ARG VITE_USE_MOCK=false
ENV VITE_GATEWAY_URL=${VITE_GATEWAY_URL} \
    VITE_USE_MOCK=${VITE_USE_MOCK}

COPY . .
RUN npm run build


# ----------------------------------------------------------------------------
# Stage 2 — runtime
# ----------------------------------------------------------------------------
FROM ${NGINX_IMAGE} AS runtime

ARG VERSION="0.0.0-dev"
ARG REVISION=""
ARG CREATED=""
LABEL org.opencontainers.image.title="Synapse AI Gateway Admin Console" \
      org.opencontainers.image.description="React/Vite admin UI for Synapse AI Gateway — teams, DLP patterns, audit, incidents." \
      org.opencontainers.image.vendor="The Synapse AI Gateway Authors" \
      org.opencontainers.image.authors="Synapse AI Gateway maintainers" \
      org.opencontainers.image.source="https://github.com/synapse-ai-gateway/synapse-ai-gateway" \
      org.opencontainers.image.url="https://github.com/synapse-ai-gateway/synapse-ai-gateway" \
      org.opencontainers.image.documentation="https://github.com/synapse-ai-gateway/synapse-ai-gateway#readme" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="docker.io/nginxinc/nginx-unprivileged:1.27-alpine" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}"

# SPA-aware nginx config (try_files fallback + asset caching + headers).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Built SPA from the builder stage.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

# Busybox wget ships with the alpine base image.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ > /dev/null || exit 1
