# ============================
# Builder stage
# ============================
FROM python:3.12.2-slim as builder

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy requirements
COPY ./requirements.txt /tmp/requirements.txt
COPY ./requirements.dev.txt /tmp/requirements.dev.txt

# Create python virtual environment and install dependencies
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libjpeg-dev \
        build-essential \
        gcc \
        libpq-dev \
        libffi-dev \
        zlib1g-dev && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    if [ "$DEV" = "true" ]; \
    then /py/bin/pip install -r /tmp/requirements.dev.txt ; \
    fi && \
    apt-get purge -y --auto-remove build-essential gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/requirements.txt /tmp/requirements.dev.txt

# Pre-download the sentence-transformers model into /app/models
RUN mkdir -p /app/models && \
    HF_HOME=/app/models /py/bin/python - <<'EOF'
from sentence_transformers import SentenceTransformer
SentenceTransformer("sentence-transformers/clip-ViT-B-32")
EOF

# ============================
# Final stage
# ============================
FROM python:3.12.2-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/py/bin:$PATH" \
    HF_HOME=/app/models

# Create django user
RUN adduser \
    --disabled-password \
    --no-create-home \
    django-user

# Copy virtual environment and pre-downloaded models from builder
COPY --from=builder /py /py
COPY --from=builder /app/models /app/models

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libjpeg62-turbo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Setup directories and permissions
RUN mkdir -p /api/static /vol/web/media /vol/log && \
    chown -R django-user:django-user /api /vol /app/models && \
    chmod -R 755 /api /vol /app/models

# Copy application code
COPY --chown=django-user:django-user ./api /api

WORKDIR /api
EXPOSE 8000

USER django-user