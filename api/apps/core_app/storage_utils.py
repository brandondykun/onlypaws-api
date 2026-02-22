"""
Utilities for cloud storage operations including presigned URL generation.

All environments use remote S3/R2 storage for images; there is no local file storage.
"""

import os
import logging
import uuid
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def is_s3_configured() -> bool:
    """
    Check if S3/R2 storage is configured.
    
    Returns:
        True if AWS credentials are available, False otherwise
    """
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    return bool(access_key and secret_key)


def get_s3_client():
    """
    Get a boto3 S3 client configured for the current environment.
    
    Returns:
        boto3.client: Configured S3 client, or None if not configured
    """
    # Check if S3 settings are configured
    endpoint_url = os.environ.get('AWS_S3_ENDPOINT_URL')
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_S3_REGION_NAME')
    
    if not all([access_key, secret_key]):
        logger.warning("AWS credentials not configured, S3 operations will fail")
        return None
    
    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region or 'auto',
    )


def generate_presigned_upload_url(key: str, expires_in: int = 3600, content_type: Optional[str] = None) -> Optional[dict]:
    """
    Generate a presigned URL for uploading a file to S3/R2.
    
    Args:
        key: The S3 key (path) where the file will be uploaded
        expires_in: URL expiration time in seconds (default 1 hour)
        content_type: Optional content type for the upload
    
    Returns:
        Dict with 'url' and 'key' on success, None on failure
    """
    client = get_s3_client()
    if not client:
        logger.error("Cannot generate presigned URL: S3 client not configured")
        return None
    
    bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        logger.error("Cannot generate presigned URL: AWS_STORAGE_BUCKET_NAME not configured")
        return None
    
    try:
        params = {
            'Bucket': bucket,
            'Key': key,
        }
        if content_type:
            params['ContentType'] = content_type
        
        url = client.generate_presigned_url(
            'put_object',
            Params=params,
            ExpiresIn=expires_in,
        )
        
        logger.debug(f"Generated presigned upload URL for key: {key}")
        return {"url": url, "key": key}
    
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {key}: {str(e)}")
        return None


def get_storage_env_prefix() -> str:
    """Return the environment prefix for storage keys (e.g. images/dev/)."""
    env = os.environ.get("DJANGO_ENV")
    if env == "test":
        return "images/test/"
    if env == "dev":
        return "images/dev/"
    if env == "e2e":
        return "images/e2e/"
    return "images/"


def _env_prefix() -> str:
    """Return the environment prefix for storage keys."""
    return get_storage_env_prefix()


def generate_original_image_key(post_public_id, image_order: int) -> str:
    """
    Generate S3 key for original image uploads (before processing).

    Original images are stored in a separate 'originals' directory and will be
    deleted after processing is complete.

    Args:
        post_public_id: The post's public_id (ULID string or object)
        image_order: The image's order/index in the post

    Returns:
        S3 key string for the original image
    """
    prefix = _env_prefix()
    return f"{prefix}originals/posts/{post_public_id}/{image_order}"


def generate_profile_original_key(profile_public_id) -> str:
    """
    Generate a unique S3 key for profile image original uploads (before processing).

    Each request gets a new UUID so new and update uploads never clash.
    Originals are deleted after processing.

    Args:
        profile_public_id: The profile's public_id (ULID string or object)

    Returns:
        S3 key string for the original image
    """
    prefix = _env_prefix()
    return f"{prefix}originals/profiles/{profile_public_id}/{uuid.uuid4()}"


def delete_s3_object(key: str) -> bool:
    """
    Delete an object from S3/R2.
    
    Args:
        key: The S3 key (path) of the object to delete
    
    Returns:
        True if successful, False otherwise
    """
    client = get_s3_client()
    if not client:
        logger.error("Cannot delete S3 object: S3 client not configured")
        return False
    
    bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        logger.error("Cannot delete S3 object: AWS_STORAGE_BUCKET_NAME not configured")
        return False
    
    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Deleted S3 object: {key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete S3 object {key}: {str(e)}")
        return False


def download_s3_object(key: str) -> Optional[bytes]:
    """
    Download an object from S3/R2.
    
    Args:
        key: The S3 key (path) of the object to download
    
    Returns:
        The file contents as bytes, or None on failure
    """
    client = get_s3_client()
    if not client:
        logger.error("Cannot download S3 object: S3 client not configured")
        return None
    
    bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        logger.error("Cannot download S3 object: AWS_STORAGE_BUCKET_NAME not configured")
        return None
    
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        logger.debug(f"Downloaded S3 object: {key} ({len(content)} bytes)")
        return content
    except ClientError as e:
        logger.error(f"Failed to download S3 object {key}: {str(e)}")
        return None


def download_file(key: str) -> Optional[bytes]:
    """
    Download a file from S3/R2 storage.

    Args:
        key: The storage key (path) of the file to download

    Returns:
        The file contents as bytes, or None on failure
    """
    return download_s3_object(key)


def delete_file(key: str) -> bool:
    """
    Delete a file from S3/R2 storage.

    Args:
        key: The storage key (path) of the file to delete

    Returns:
        True if successful, False otherwise
    """
    return delete_s3_object(key)


def save_local_file(key: str, content: bytes) -> bool:
    """
    Save a file to local storage.

    Args:
        key: The storage key/path where the file will be saved
        content: The file contents as bytes

    Returns:
        True if successful, False otherwise
    """
    try:
        from django.core.files.base import ContentFile

        # Ensure directory exists (default_storage.save handles this)
        saved_name = default_storage.save(key, ContentFile(content))
        logger.info(f"Saved local file: {saved_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save local file {key}: {str(e)}")
        return False


def write_local_file_exact(key: str, content: bytes) -> bool:
    """
    Write content directly to MEDIA_ROOT/key, overwriting if present.
    Bypasses Django storage so the exact key is used (no get_available_name suffix).

    Use for migrations where the destination path must be deterministic.
    """
    try:
        key = key.lstrip("/") if isinstance(key, str) else key
        full_path = Path(settings.MEDIA_ROOT) / key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        logger.info(f"Wrote local file: {key}")
        return True
    except Exception as e:
        logger.error(f"Failed to write local file {key}: {str(e)}")
        return False


def copy_s3_object(source_key: str, dest_key: str) -> bool:
    """
    Copy an object within S3/R2 (same bucket).

    Args:
        source_key: The S3 key of the source object
        dest_key: The S3 key for the destination object

    Returns:
        True if successful, False otherwise
    """
    client = get_s3_client()
    if not client:
        logger.error("Cannot copy S3 object: S3 client not configured")
        return False

    bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        logger.error("Cannot copy S3 object: AWS_STORAGE_BUCKET_NAME not configured")
        return False

    try:
        client.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': source_key},
            Key=dest_key,
        )
        logger.debug(f"Copied S3 object from {source_key} to {dest_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to copy S3 object from {source_key} to {dest_key}: {str(e)}")
        return False


def check_s3_object_exists(key: str) -> bool:
    """
    Check if an object exists in S3/R2.

    Args:
        key: The S3 key (path) to check

    Returns:
        True if the object exists, False otherwise
    """
    client = get_s3_client()
    if not client:
        logger.error("Cannot check S3 object: S3 client not configured")
        return False

    bucket = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        logger.error("Cannot check S3 object: AWS_STORAGE_BUCKET_NAME not configured")
        return False

    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        logger.error(f"Failed to check S3 object {key}: {str(e)}")
        return False


def storage_object_exists(key: str) -> bool:
    """
    Check if an object exists in S3/R2 storage.

    Args:
        key: The storage key (path) to check

    Returns:
        True if the object exists, False otherwise
    """
    return check_s3_object_exists(key)


def copy_storage_object(source_key: str, dest_key: str) -> bool:
    """
    Copy an object within S3/R2 (same bucket).

    Args:
        source_key: The storage key of the source object
        dest_key: The storage key for the destination object

    Returns:
        True if successful, False otherwise
    """
    return copy_s3_object(source_key, dest_key)
