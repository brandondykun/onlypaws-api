import logging
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Notification, NotificationType
from .serializers import WebSocketNotificationSerializer
from apps.core_app.models import Profile, Post

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def send_notification_task(self, notification_id):
    """
    Send a notification via WebSocket to the recipient.
    
    Args:
        notification_id (int): ID of the notification to send
    """
    try:
        notification = Notification.objects.select_related(
            'recipient', 'sender', 'post', 'comment'
        ).get(id=notification_id)
        
        # Serialize notification for WebSocket
        serializer = WebSocketNotificationSerializer(notification)
        notification_data = serializer.data
        
        # Send to WebSocket group
        channel_layer = get_channel_layer()
        group_name = f'profile_{notification.recipient.id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )
        
        logger.info(f"Notification {notification_id} sent to profile {notification.recipient.id}")
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
    except Exception as e:
        logger.error(f"Error sending notification {notification_id}: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def create_post_like_notification_task(self, post_id, liker_profile_id):
    """
    Create and send a like notification with security checks.
    
    Args:
        post_id (int): ID of the post that was liked
        liker_profile_id (int): ID of the profile that liked the post
    """
    try:
        # Validate input parameters
        if not isinstance(post_id, int) or not isinstance(liker_profile_id, int):
            logger.error(f"Invalid parameter types: post_id={type(post_id)}, liker_profile_id={type(liker_profile_id)}")
            return
            
        post = Post.objects.select_related('profile').get(id=post_id)
        liker_profile = Profile.objects.get(id=liker_profile_id)
        
        # Security: Don't send notification if user liked their own post
        if post.profile.id == liker_profile.id:
            return
        
        # Get post preview image URL (let serializer handle URL construction)
        post_preview_image = None
        if post.images.first():
            preview_image_path = post.images.first().image.url
            if preview_image_path:
                # Store the URL as-is from Django's ImageField
                # The serializer will handle proper URL construction
                post_preview_image = preview_image_path
        
        # Get or update existing notification to prevent spam
        notification, created = Notification.objects.get_or_create(
            recipient=post.profile,
            sender=liker_profile,
            notification_type=NotificationType.LIKE_POST,
            post=post,
            comment=None,
            defaults={
                'title': "liked your post",
                'message': f"{liker_profile.username} liked your post: \"{post.caption[:50]}{'...' if len(post.caption) > 50 else ''}\"",
                'extra_data': {
                    'post_caption': post.caption[:100],  # Limit data size
                    'post_id': post.id,
                    'liker_username': liker_profile.username,
                    'liker_id': liker_profile.id,
                    'post_preview_image': post_preview_image
                }
            }
        )
        
        # If notification already exists, mark as unread
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=['is_read'])
        
        # Send via WebSocket
        send_notification_task.delay(notification.id)
        
        logger.info(f"Like notification {'created' if created else 'updated'} for post {post_id}")
        
    except (Post.DoesNotExist, Profile.DoesNotExist) as e:
        logger.error(f"Object not found for like notification: {e}")
    except Exception as e:
        logger.error(f"Error creating like notification: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def send_system_message_task(self, profile_id, message, data=None):
    """
    Send a system message to a specific profile via WebSocket.
    
    Args:
        profile_id (int): ID of the profile to send message to
        message (str): System message content (max 500 chars)
        data (dict, optional): Additional data to send
    """
    try:
        # Input validation
        if not isinstance(profile_id, int) or profile_id <= 0:
            logger.error(f"Invalid profile_id: {profile_id}")
            return
            
        if not isinstance(message, str) or len(message) > 500:
            logger.error(f"Invalid message: length={len(message) if isinstance(message, str) else 'not string'}")
            return
            
        # Verify profile exists
        if not Profile.objects.filter(id=profile_id).exists():
            logger.error(f"Profile {profile_id} does not exist")
            return
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'profile_{profile_id}',
            {
                'type': 'system_message',
                'message': message,
                'data': data or {}
            }
        )
        
        logger.info(f"System message sent to profile {profile_id}")
        
    except Exception as e:
        logger.error(f"Error sending system message to profile {profile_id}: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def cleanup_old_notifications_task(self, days=30):
    """
    Clean up old read notifications to prevent database bloat.
    
    Args:
        days (int): Number of days after which to delete read notifications
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = Notification.objects.filter(
            is_read=True,
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        
    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {e}")
        raise self.retry(countdown=3600, max_retries=3)  # Retry in 1 hour
