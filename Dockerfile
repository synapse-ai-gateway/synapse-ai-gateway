# syntax=docker/dockerfile:1
# ============================================================================
# Synapse AI Gateway — production container
#
#   Stage 1 (builder)  installs Python dependencies and any required build
#                      toolchain. Nothing from this stage ships to runtime
#                      except the compiled site-packages prefix.
#   Stage 2 (runtime)  minimal python:3.12-slim with the application source,
#                      a non-root user, and a healthcheck. No build tools,
#                      no dev dependencies, no curl.
#
# Build:
#   docker build -t synapse-ai-gateway:dev .
# Build with versioned OCI labels (CI normally supplies these):
#   docker build -t synapse-ai-gateway:1.0.0 \
#     --build-arg VERSION=1.0.0 \
#     --build-arg REVISION=$(git rev-parse HEAD) \
#     --build-arg CREATED=$(date -u +%Y-%m-%dT%H:%M:%SZ) .
# ============================================================================
ARG PYTHON_VERSION=3.12

# ----------------------------------------------------------------------------
# Stage 1 — builder
# ----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential + unixodbc-dev cover sdist fallbacks for the few deps that
# may not ship manylinux wheels (pyodbc historically). These packages stay in
# the builder image and never reach runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
# Two install steps to keep the runtime image lean:
#   1. Strip dev-only or runtime-incompatible deps from requirements.txt:
#        - uvicorn[standard] pulls watchfiles (dev-reload only) and websockets
#          (unused). We add the perf-relevant extras explicitly below.
#        - pyodbc / aioodbc are MSSQL drivers; we don't ship the unixodbc
#          shared libs in runtime, so they would be deadweight here. Users
#          who need MSSQL can install them in a downstream image.
#   2. --no-compile skips .pyc generation (runtime has PYTHONDONTWRITEBYTECODE=1
#      so they would never be used).
RUN sed -E -e '/^uvicorn\[standard\]/d' -e '/^(pyodbc|aioodbc)==/d' requirements.txt \
        > /tmp/req-prod.txt \
    && pip install --no-cache-dir --no-compile --prefix=/install -r /tmp/req-prod.txt \
    && pip install --no-cache-dir --no-compile --prefix=/install \
        uvicorn==0.46.0 \
        uvloop==0.22.1 \
        httptools==0.7.1


# ----------------------------------------------------------------------------
# Stage 2 — runtime
# ----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# ---- OCI image annotations (overridable at build time) ---------------------
# CI's docker/metadata-action injects standard labels and will take precedence;
# the values below are the baseline for a hand-rolled `docker build`.
ARG VERSION="0.0.0-dev"
ARG REVISION=""
ARG CREATED=""
LABEL org.opencontainers.image.title="Synapse AI Gateway" \
      org.opencontainers.image.description="Governance-first AI gateway: per-API-key system prompt enforcement, prompt-layer DLP, hybrid local/cloud routing, immutable audit logging." \
      org.opencontainers.image.vendor="The Synapse AI Gateway Authors" \
      org.opencontainers.image.authors="Synapse AI Gateway maintainers" \
      org.opencontainers.image.source="https://github.com/synapse-ai-gateway/synapse-ai-gateway" \
      org.opencontainers.image.url="https://github.com/synapse-ai-gateway/synapse-ai-gateway" \
      org.opencontainers.image.documentation="https://github.com/synapse-ai-gateway/synapse-ai-gateway#readme" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="docker.io/library/python:3.12-slim" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.created="${CREATED}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

# ca-certificates ship with python:slim; the healthcheck uses urllib from the
# stdlib so no curl install is needed. Only system change: create the app user.
RUN useradd --create-home --uid 1000 synapse

WORKDIR /app

# Python packages from the builder stage land under /usr/local.
COPY --from=builder /install /usr/local

# Application source — ownership is set at copy time to avoid an extra chown
# layer. .env is excluded via .dockerignore; configuration is env-driven.
COPY --chown=synapse:synapse backend/ ./

USER synapse

EXPOSE 8080

# Stdlib healthcheck — no extra binaries in the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys;\
 urllib.request.urlopen('http://localhost:8080/', timeout=4);\
 sys.exit(0)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
