from .models import PostImage
from django.dispatch import receiver
from django.db.models.signals import pre_delete


@receiver(pre_delete, sender=PostImage)
def delete_s3_image(sender, instance, **kwargs):
    """Delete the Post images from S3 when an Image instance is deleted."""
    try:
        instance.image.delete(save=False)
    except Exception as e:
        print(f"Error deleting S3 file: {e}")
