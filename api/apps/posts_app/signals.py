"""
Django signals for the posts_app.

Uses post_delete signals to ensure files are only deleted AFTER the database
record is successfully removed. This prevents orphaned records that point to
non-existent files. It's better to have orphaned files in storage than broken
database references.
"""

import logging
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PostImage, PostImageScaled
from apps.core_app.storage_utils import delete_file

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=PostImageScaled)
def delete_scaled_image_file_on_delete(sender, instance, **kwargs):
    """
    Delete the scaled image file from storage after the record is deleted.
    
    This fires after the database record is successfully removed, ensuring
    we never have a record pointing to a non-existent file.
    """
    if instance.image and instance.image.name:
        if delete_file(instance.image.name):
            logger.info(f"Deleted scaled image file: {instance.image.name}")
        else:
            logger.warning(f"Failed to delete scaled image file: {instance.image.name}")


@receiver(post_delete, sender=PostImage)
def delete_post_image_files_on_delete(sender, instance, **kwargs):
    """
    Delete associated image files from storage after the PostImage record is deleted.
    
    This fires after the database record is successfully removed, ensuring
    we never have a record pointing to a non-existent file.
    
    Note: PostImageScaled records are cascade-deleted first, and their own
    post_delete signal handles their file cleanup. This signal only handles
    the main image and original_key files.
    """
    deleted_files = []
    failed_files = []
    
    # Delete main processed image
    if instance.image and instance.image.name:
        if delete_file(instance.image.name):
            deleted_files.append(instance.image.name)
        else:
            failed_files.append(instance.image.name)
    
    # Delete original image if it exists (may still exist if processing failed)
    if instance.original_key:
        if delete_file(instance.original_key):
            deleted_files.append(instance.original_key)
        else:
            failed_files.append(instance.original_key)
    
    if deleted_files:
        logger.info(f"Deleted {len(deleted_files)} files for PostImage {instance.id}: {deleted_files}")
    if failed_files:
        logger.warning(f"Failed to delete {len(failed_files)} files for PostImage {instance.id}: {failed_files}")
