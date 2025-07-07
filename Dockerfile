# ===============================
# Stage 1: Builder
# ===============================
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY ./requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ===============================
# Stage 2: Final Production Image
# ===============================
FROM python:3.10-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# App setup
WORKDIR /app

COPY src/ ./src/
COPY service-account.json /app/service-account.json
COPY zoko_templates.json /app/zoko_templates.json
COPY templates.json /app/templates.json

# Create logs and set permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Expose port
EXPOSE 8080

# Set ENV VARS
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/service-account.json"

# Run the app with Gunicorn, preload, and 1 worker for easier debugging and lower memory usage on Cloud Run
CMD ["gunicorn", "src.main:app", "-c", "src/gunicorn_conf.py"]
