import os
from urllib.parse import urlparse

# Proxy/HTTPS Configuration
# Trust X-Forwarded-Proto header from proxy to generate correct HTTPS URLs
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

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

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "apps.core_app.exceptions.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth": "30/minute",
        "auth_sensitive": "5/minute",
        "explore_feed": "60/minute",
    },
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Ensure webp mimetype is registered (may not be in default mimetypes db)
import mimetypes

mimetypes.add_type("image/webp", ".webp")

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_QUERYSTRING_EXPIRE = 600
# Endpoint for uploads and signed operations (boto3 client)
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
# Public base URL for read-only image URLs (no signing, no expiry)
AWS_S3_ENDPOINT_PUBLIC_URL = os.environ.get("AWS_S3_ENDPOINT_PUBLIC_URL")

if AWS_S3_ENDPOINT_PUBLIC_URL:
    _public = urlparse(AWS_S3_ENDPOINT_PUBLIC_URL)
    AWS_S3_CUSTOM_DOMAIN = _public.netloc or None
    AWS_QUERYSTRING_AUTH = False
    MEDIA_DOMAIN = (
        f"{_public.scheme or 'https'}://{_public.netloc}/"
        if _public.netloc
        else f"https://{AWS_STORAGE_BUCKET_NAME}.r2.cloudflarestorage.com/"
    )
else:
    AWS_S3_CUSTOM_DOMAIN = None
    MEDIA_DOMAIN = f"https://{AWS_STORAGE_BUCKET_NAME}.r2.cloudflarestorage.com/"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Celery Configuration for Staging
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
