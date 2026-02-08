"""
Django signals for the profile_app.

Deletes storage files on ProfileImage and ProfileImageScaled deletion.
"""

import logging
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProfileImage, ProfileImageScaled
from apps.core_app.storage_utils import delete_file

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=ProfileImageScaled)
def delete_profile_scaled_image_file_on_delete(sender, instance, **kwargs):
    """Delete the scaled image file from storage after the record is deleted."""
    if instance.image and instance.image.name:
        if delete_file(instance.image.name):
            logger.info(f"Deleted scaled profile image file: {instance.image.name}")
        else:
            logger.warning(f"Failed to delete scaled profile image file: {instance.image.name}")


@receiver(post_delete, sender=ProfileImage)
def delete_profile_image_files_on_delete(sender, instance, **kwargs):
    """
    Delete profile image files from storage after the ProfileImage record is deleted.
    Handles main image, original_key (if still present), and relies on cascade
    for ProfileImageScaled (their post_delete handles scaled files).
    """
    deleted = []
    failed = []
    if instance.image and instance.image.name:
        if delete_file(instance.image.name):
            deleted.append(instance.image.name)
        else:
            failed.append(instance.image.name)
    if instance.original_key:
        if delete_file(instance.original_key):
            deleted.append(instance.original_key)
        else:
            failed.append(instance.original_key)
    if deleted:
        logger.info(f"Deleted {len(deleted)} files for ProfileImage {instance.id}: {deleted}")
    if failed:
        logger.warning(f"Failed to delete {len(failed)} files for ProfileImage {instance.id}: {failed}")
