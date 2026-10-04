# ---------------------------------------------------------------------------
# SANGYAN Production Multi-Stage Hardened Dockerfile
# Base: python:3.13-slim (Debian Bookworm minimal)
# Security: Non-root user (UID 10001), read-only rootfs compatible, CIS hardened
# ---------------------------------------------------------------------------

# Stage 1: Build & Wheel Compiler
FROM python:3.13-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install minimal build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY sangyan ./sangyan

# Build wheels for application and postgres optional dependencies
RUN pip wheel --wheel-dir=/wheels .[postgres]


# Stage 2: Hardened Production Runtime
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="SANGYAN" \
      org.opencontainers.image.description="Investor Safety & Content Intelligence Platform" \
      org.opencontainers.image.version="0.7.0" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/usr/local/bin:$PATH" \
    SANGYAN_ENV=production \
    SANGYAN_HOST=0.0.0.0 \
    SANGYAN_PORT=8000 \
    SANGYAN_DATABASE_URL=sqlite:////app/data/sangyan.db \
    SANGYAN_CHECKPOINT_DB_PATH=/app/checkpoints/workflow_checkpoints.db \
    SANGYAN_KEY_DIR=/app/keys \
    SANGYAN_BACKUP_DIR=/app/backups

# Create dedicated non-root user and group with explicit UID:GID 10001:10001
RUN groupadd -g 10001 -r sangyan && \
    useradd -u 10001 -r -g sangyan -s /sbin/nologin -d /app sangyan

# Install wheels from builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

WORKDIR /app

# Copy application source code (owned by root, read-only to sangyan)
COPY --chown=root:root sangyan /app/sangyan

# Setup explicit writable directories for state persistence with strict permissions
RUN mkdir -p /app/data /app/checkpoints /app/keys /app/backups /tmp && \
    chown -R 10001:10001 /app/data /app/checkpoints /app/keys /app/backups /tmp && \
    chmod 0750 /app/data /app/checkpoints /app/backups && \
    chmod 0700 /app/keys && \
    chmod 1777 /tmp && \
    chmod -R 0555 /app/sangyan

# Switch to non-root user
USER 10001:10001

EXPOSE 8000

# Operational liveness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).read()" || exit 1

# Exec-form entrypoint for proper signal propagation (SIGTERM/SIGINT)
ENTRYPOINT ["python", "-m", "sangyan.cli"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
