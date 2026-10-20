# Production-grade multi-stage Dockerfile for Cerevyn Azure Support Ticket Automation
FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install security updates and build requirements if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user and persistent data directory
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser app /app/app
COPY --chown=appuser:appuser sample_data /app/sample_data
COPY --chown=appuser:appuser scripts /app/scripts

# Switch to non-root user
USER appuser

# Exposed API port
EXPOSE 8000

# Default environment configuration
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    DATABASE_PATH=/app/data/tickets.db \
    ENVIRONMENT=production

# Container healthcheck against /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

# Start Uvicorn ASGI server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
