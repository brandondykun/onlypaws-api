# syntax=docker/dockerfile:1

# ============================
# Builder stage
# ============================
FROM python:3.12.2-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build dependencies (rarely changes — cached as its own layer)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libjpeg-dev \
        build-essential \
        gcc \
        libpq-dev \
        libffi-dev \
        zlib1g-dev

# Create virtual environment
RUN python -m venv /py && /py/bin/pip install --upgrade pip

# Install Python dependencies (cache mount keeps downloaded wheels across rebuilds)
COPY ./requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    /py/bin/pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# ============================
# Final stage
# ============================
FROM python:3.12.2-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/py/bin:$PATH" \
    HF_HOME=/app/models

# Create django user
RUN adduser \
    --disabled-password \
    --no-create-home \
    django-user

# Copy virtual environment from builder
COPY --from=builder /py /py

# Install runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libjpeg62-turbo

# Setup directories and permissions
RUN mkdir -p /api/static /vol/web/media /vol/log && \
    chown -R django-user:django-user /vol && \
    chmod -R 755 /vol

# Copy application code
COPY --chown=django-user:django-user ./api /api

WORKDIR /api
EXPOSE 8000

USER django-user
