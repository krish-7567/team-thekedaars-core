# ─────────────────────────────────────────────────────────────────────────────
# Karigar Backend — Multi-Stage Dockerfile
# Target: IBM Cloud Code Engine (OCI-compliant container image)
# Python 3.11 · FastAPI · IBM Granite + Cloudant
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install to isolated target directory
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install/packages -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root user
RUN groupadd --gid 1001 karigar \
 && useradd  --uid 1001 --gid karigar --shell /bin/sh --create-home karigar

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install/packages /usr/local

# Copy application source
COPY main.py    ./main.py
COPY index.html ./index.html

# Code Engine & IBM Cloud best practice: never bake secrets into the image.
# All secrets are injected at runtime via environment variables or CE secrets.
# See .env.example for required variables.

# Expose the port Code Engine expects
EXPOSE 8080

# Switch to non-root user
USER karigar

# Production entrypoint:
# --workers 2 : 2 Uvicorn worker processes (safe for Code Engine 1-vCPU instances)
# --loop uvloop: faster async event loop (installed via uvicorn[standard])
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--access-log"]
