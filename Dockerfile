# Builder stage
FROM python:3.12.2-alpine3.19 as builder

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy requirements files
COPY ./requirements.txt /tmp/requirements.txt
COPY ./requirements.dev.txt /tmp/requirements.dev.txt

# Create python virtual environment
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    apk add --update --no-cache postgresql-client jpeg-dev && \
    apk add --update --no-cache --virtual .tmp-build-deps \
    build-base gcc postgresql-dev musl-dev libffi-dev zlib zlib-dev && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    if [ "$DEV" = "true" ]; \
    then /py/bin/pip install -r /tmp/requirements.dev.txt ; \
    fi && \
    rm -rf /tmp && \
    apk del .tmp-build-deps

# Final stage
FROM python:3.12.2-alpine3.19

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/py/bin:$PATH"

# Create django user
RUN adduser \
    --disabled-password \
    --no-create-home \
    django-user

# Copy virtual environment from builder
COPY --from=builder /py /py

# Install runtime dependencies
RUN apk add --no-cache postgresql-client jpeg-dev

# Setup directories and permissions
RUN mkdir -p /api/static && \
    mkdir -p /vol/web/media && \
    mkdir -p /vol/log && \
    chown -R django-user:django-user /api && \
    chown -R django-user:django-user /vol && \
    chmod -R 755 /api && \
    chmod -R 755 /vol

# Copy application code
COPY --chown=django-user:django-user ./api /api

WORKDIR /api
EXPOSE 8000

USER django-user