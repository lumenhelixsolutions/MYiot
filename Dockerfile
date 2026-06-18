# =============================================================================
# MYiot — Universal Smart Home Hub
# Multi-Stage Production Dockerfile
# =============================================================================
# Brand Colors: #081021 (Deep Space Slate) | #6366F1 (Electric Indigo)
#               #06B6D4 (Cyan Glow) | #F59E0B (Warm Amber)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Frontend Build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

# Set working directory
WORKDIR /app/frontend

# Copy package files first for better layer caching
COPY frontend/package*.json ./

# Install dependencies (clean install for deterministic builds)
RUN npm ci --ignore-scripts

# Copy frontend source code
COPY frontend/ ./

# Build production assets
ENV NODE_ENV=production
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Backend Build
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS backend-builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/backend

# Copy dependency files
COPY backend/pyproject.toml backend/requirements*.txt ./

# Create virtual environment and install dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir -e "."

# Copy backend source code
COPY backend/ ./

# Pre-compile Python bytecode for faster startup
RUN python -m compileall app/

# ---------------------------------------------------------------------------
# Stage 3: Production Runner (Nginx + Uvicorn)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Metadata labels (OCI-compliant)
LABEL org.opencontainers.image.title="MYiot"
LABEL org.opencontainers.image.description="Universal Smart Home Hub"
LABEL org.opencontainers.image.source="https://github.com/myiot/myiot"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="1.0.0"

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from backend builder
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy backend application
COPY --from=backend-builder /app/backend /app/backend

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy Nginx configuration
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy startup script
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create non-root user for security
RUN groupadd -r myiot && useradd -r -g myiot myiot && \
    mkdir -p /var/cache/nginx /var/run/nginx /app/data && \
    chown -R myiot:myiot /app/data /var/cache/nginx /var/run/nginx /usr/share/nginx/html

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Expose ports
# 80   — Nginx (static frontend + API proxy)
# 8000 — Uvicorn (FastAPI backend, direct access)
EXPOSE 80 8000

# Volume for persistent data
VOLUME ["/app/data"]

# Use the entrypoint script to start services
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
