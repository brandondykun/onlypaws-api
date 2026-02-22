import os
from datetime import timedelta
from urllib.parse import urlparse

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 3,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "apps.core_app.exceptions.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "HOST": os.environ.get("DB_HOST"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "PORT": os.environ.get("DB_PORT"),
    }
}

# S3/R2 Storage Configuration for E2E (same as dev/staging - no local image storage)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

import mimetypes

mimetypes.add_type("image/webp", ".webp")

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "auto")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_QUERYSTRING_EXPIRE = 600
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
AWS_S3_ENDPOINT_PUBLIC_URL = os.environ.get("AWS_S3_ENDPOINT_PUBLIC_URL")

if AWS_S3_ENDPOINT_PUBLIC_URL:
    _public = urlparse(AWS_S3_ENDPOINT_PUBLIC_URL)
    AWS_S3_CUSTOM_DOMAIN = _public.netloc or None
    AWS_QUERYSTRING_AUTH = False
    MEDIA_DOMAIN = (
        f"{_public.scheme or 'https'}://{_public.netloc}/"
        if _public.netloc
        else os.environ.get("MEDIA_DOMAIN", "http://localhost:8000")
    )
else:
    AWS_S3_CUSTOM_DOMAIN = None
    MEDIA_DOMAIN = os.environ.get("MEDIA_DOMAIN", "http://localhost:8000")

# Celery Configuration for Tests
# Run tasks synchronously during testing to avoid Redis dependency
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Fixed verification code for e2e create-user flow (tests cannot read email).
# Use this value when calling the verify-email endpoint after creating a user during e2e tests.
E2E_VERIFICATION_CODE = "123456"

# JWT Cookie settings for e2e testing
# These override the production settings to allow cookies in test environment
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("ACCESS_TOKEN_LIFETIME", 5))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("REFRESH_TOKEN_LIFETIME", 7))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    # Cookie settings relaxed for e2e testing
    "AUTH_COOKIE": "refresh_token",
    "AUTH_COOKIE_DOMAIN": None,
    "AUTH_COOKIE_SECURE": False,  # Allow cookies over HTTP
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_PATH": "/",
    "AUTH_COOKIE_SAMESITE": "Lax",
}
