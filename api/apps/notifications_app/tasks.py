import logging
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db.models import Prefetch

from .models import Notification, NotificationType
from .serializers import WebSocketNotificationSerializer
from apps.profile_app.models import Profile, ProfileImageScaled
from apps.posts_app.models import Post, PostImage, PostImageScaled, PostImageTag
from apps.interactions_app.models import Comment, FollowRequest

logger = logging.getLogger(__name__)


def build_full_media_url(relative_path):
    """
    Build a full URL for media files.
    
    In production/staging with S3, the URL is already complete.
    In development, we need to prepend the MEDIA_DOMAIN.
    
    Args:
        relative_path (str): The relative path or full URL to the media file
        
    Returns:
        str: The full URL to the media file, or None if relative_path is None/empty
    """
    if not relative_path:
        return None
    
    # If already a full URL (S3), return as-is
    if relative_path.startswith('http://') or relative_path.startswith('https://'):
        return relative_path
    
    # Build full URL using MEDIA_DOMAIN
    media_domain = getattr(settings, 'MEDIA_DOMAIN', '')
    if media_domain:
        # Ensure no double slashes
        if media_domain.endswith('/') and relative_path.startswith('/'):
            return f"{media_domain[:-1]}{relative_path}"
        elif not media_domain.endswith('/') and not relative_path.startswith('/'):
            return f"{media_domain}/{relative_path}"
        return f"{media_domain}{relative_path}"
    
    return relative_path


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
            
        post = Post.objects.select_related('profile').prefetch_related(
            Prefetch(
                'images',
                queryset=PostImage.objects.prefetch_related(
                    Prefetch(
                        'scaled_images',
                        queryset=PostImageScaled.objects.filter(
                            scale=PostImageScaled.Scale.SMALL
                        ),
                    )
                ),
            )
        ).get(id=post_id)
        liker_profile = Profile.objects.get(id=liker_profile_id)
        
        # Security: Don't send notification if user liked their own post
        if post.profile.id == liker_profile.id:
            return
        
        # Get post preview image URL (prefer small scaled for notifications)
        post_preview_image = None
        first_image = post.images.first()
        if first_image:
            small_scaled = next(
                (s for s in first_image.scaled_images.all() if s.image and s.image.url),
                None,
            )
            if small_scaled:
                post_preview_image = small_scaled.image.url
            elif first_image.image and first_image.image.url:
                post_preview_image = first_image.image.url
        
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
                    'post_public_id': str(post.public_id),
                    'liker_username': liker_profile.username,
                    'liker_id': liker_profile.id,
                    'liker_public_id': str(liker_profile.public_id),
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
def create_comment_like_notification_task(self, comment_id, liker_profile_id):
    """
    Create and send a comment like notification with security checks.
    
    Args:
        comment_id (int): ID of the comment that was liked
        liker_profile_id (int): ID of the profile that liked the comment
    """
    try:
        # Validate input parameters
        if not isinstance(comment_id, int) or not isinstance(liker_profile_id, int):
            logger.error(f"Invalid parameter types: comment_id={type(comment_id)}, liker_profile_id={type(liker_profile_id)}")
            return
            
        comment = Comment.objects.select_related('profile', 'post').prefetch_related(
            Prefetch(
                'post__images',
                queryset=PostImage.objects.prefetch_related(
                    Prefetch(
                        'scaled_images',
                        queryset=PostImageScaled.objects.filter(
                            scale=PostImageScaled.Scale.SMALL
                        ),
                    )
                ),
            )
        ).get(id=comment_id)
        liker_profile = Profile.objects.get(id=liker_profile_id)
        
        # Security: Don't send notification if user liked their own comment
        if comment.profile.id == liker_profile.id:
            return
        
        # Get post preview image URL (prefer small scaled for notifications)
        post_preview_image = None
        first_image = comment.post.images.first()
        if first_image:
            small_scaled = next(
                (s for s in first_image.scaled_images.all() if s.image and s.image.url),
                None,
            )
            if small_scaled:
                post_preview_image = small_scaled.image.url
            elif first_image.image and first_image.image.url:
                post_preview_image = first_image.image.url
        
        # Get or update existing notification to prevent spam
        notification, created = Notification.objects.get_or_create(
            recipient=comment.profile,
            sender=liker_profile,
            notification_type=NotificationType.LIKE_COMMENT,
            post=comment.post,
            comment=comment,
            defaults={
                'title': "liked your comment",
                'message': f"{liker_profile.username} liked your comment: \"{comment.text[:50]}{'...' if len(comment.text) > 50 else ''}\"",
                'extra_data': {
                    'comment_text': comment.text[:100],  # Limit data size
                    'comment_id': comment.id,
                    'post_id': comment.post.id,
                    'post_public_id': str(comment.post.public_id),
                    'post_caption': comment.post.caption[:100],
                    'liker_username': liker_profile.username,
                    'liker_id': liker_profile.id,
                    'liker_public_id': str(liker_profile.public_id),
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
        
        logger.info(f"Comment like notification {'created' if created else 'updated'} for comment {comment_id}")
        
    except (Comment.DoesNotExist, Profile.DoesNotExist) as e:
        logger.error(f"Object not found for comment like notification: {e}")
    except Exception as e:
        logger.error(f"Error creating comment like notification: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def create_comment_notification_task(self, comment_id, post_id, commenter_profile_id):
    """
    Create and send a comment notification with security checks.
    Handles both top-level comments (notify post owner) and replies (notify comment owner).
    
    Args:
        comment_id (int): ID of the comment that was created
        post_id (int): ID of the post that was commented on
        commenter_profile_id (int): ID of the profile that created the comment
    """
    try:
        # Validate input parameters
        if not isinstance(comment_id, int) or not isinstance(post_id, int) or not isinstance(commenter_profile_id, int):
            logger.error(f"Invalid parameter types: comment_id={type(comment_id)}, post_id={type(post_id)}, commenter_profile_id={type(commenter_profile_id)}")
            return
            
        comment = Comment.objects.select_related(
            'profile', 
            'post', 
            'post__profile',
            'reply_to_comment',
            'reply_to_comment__profile'
        ).get(id=comment_id)
        post = Post.objects.select_related('profile').prefetch_related(
            Prefetch(
                'images',
                queryset=PostImage.objects.prefetch_related(
                    Prefetch(
                        'scaled_images',
                        queryset=PostImageScaled.objects.filter(
                            scale=PostImageScaled.Scale.SMALL
                        ),
                    )
                ),
            )
        ).get(id=post_id)
        commenter_profile = Profile.objects.get(id=commenter_profile_id)
        
        # Get post preview image URL (prefer small scaled for notifications)
        post_preview_image = None
        first_image = post.images.first()
        if first_image:
            small_scaled = next(
                (s for s in first_image.scaled_images.all() if s.image and s.image.url),
                None,
            )
            if small_scaled:
                post_preview_image = small_scaled.image.url
            elif first_image.image and first_image.image.url:
                post_preview_image = first_image.image.url
        
        # Determine if this is a reply or a top-level comment
        if comment.reply_to_comment:
            # This is a reply to another comment
            replied_to_comment = comment.reply_to_comment
            recipient = replied_to_comment.profile
            
            # Security: Don't send notification if user replied to their own comment
            if recipient.id == commenter_profile.id:
                return
            
            # Get or update existing notification to prevent spam
            notification, created = Notification.objects.get_or_create(
                recipient=recipient,
                sender=commenter_profile,
                notification_type=NotificationType.COMMENT_REPLY,
                post=post,
                comment=comment,
                defaults={
                    'title': "replied to your comment",
                    'message': f"{commenter_profile.username} replied to your comment: \"{comment.text[:50]}{'...' if len(comment.text) > 50 else ''}\"",
                    'extra_data': {
                        'comment_text': comment.text[:100],  # Limit data size
                        'comment_id': comment.id,
                        'replied_to_comment_id': replied_to_comment.id,
                        'replied_to_comment_text': replied_to_comment.text[:100],
                        'post_id': post.id,
                        'post_public_id': str(post.public_id),
                        'post_caption': post.caption[:100],
                        'commenter_username': commenter_profile.username,
                        'commenter_id': commenter_profile.id,
                        'commenter_public_id': str(commenter_profile.public_id),
                        'post_preview_image': post_preview_image,
                        'is_reply': True
                    }
                }
            )
            
            logger.info(f"Comment reply notification {'created' if created else 'updated'} for comment {replied_to_comment.id}")
            
        else:
            # This is a top-level comment on the post
            recipient = post.profile
            
            # Security: Don't send notification if user commented on their own post
            if recipient.id == commenter_profile.id:
                return
            
            # Get or update existing notification to prevent spam
            notification, created = Notification.objects.get_or_create(
                recipient=recipient,
                sender=commenter_profile,
                notification_type=NotificationType.COMMENT,
                post=post,
                comment=comment,
                defaults={
                    'title': "commented on your post",
                    'message': f"{commenter_profile.username} commented on your post: \"{comment.text[:50]}{'...' if len(comment.text) > 50 else ''}\"",
                    'extra_data': {
                        'comment_text': comment.text[:100],  # Limit data size
                        'comment_id': comment.id,
                        'post_id': post.id,
                        'post_public_id': str(post.public_id),
                        'post_caption': post.caption[:100],
                        'commenter_username': commenter_profile.username,
                        'commenter_id': commenter_profile.id,
                        'commenter_public_id': str(commenter_profile.public_id),
                        'post_preview_image': post_preview_image,
                        'is_reply': False
                    }
                }
            )
            
            logger.info(f"Comment notification {'created' if created else 'updated'} for post {post_id}")
        
        # If notification already exists, mark as unread
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=['is_read'])
        
        # Send via WebSocket
        send_notification_task.delay(notification.id)
        
    except (Comment.DoesNotExist, Post.DoesNotExist, Profile.DoesNotExist) as e:
        logger.error(f"Object not found for comment notification: {e}")
    except Exception as e:
        logger.error(f"Error creating comment notification: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def create_follow_notification_task(self, followed_profile_id, follower_profile_id):
    """
    Create and send a follow notification with security checks.
    
    Args:
        followed_profile_id (int): ID of the profile being followed
        follower_profile_id (int): ID of the profile doing the following
    """
    try:
        # Validate input parameters
        if not isinstance(followed_profile_id, int) or not isinstance(follower_profile_id, int):
            logger.error(f"Invalid parameter types: followed_profile_id={type(followed_profile_id)}, follower_profile_id={type(follower_profile_id)}")
            return
        
        # Security: Don't send notification if someone somehow followed themselves
        if followed_profile_id == follower_profile_id:
            logger.warning(f"Attempted to create self-follow notification for profile {followed_profile_id}")
            return
            
        followed_profile = Profile.objects.get(id=followed_profile_id)
        follower_profile = Profile.objects.select_related('image').get(id=follower_profile_id)
        
        # Get the specific profile (RegularProfile or BusinessProfile)
        specific_follower = follower_profile.get_specific_profile()
        
        # Get follower's avatar URL
        follower_avatar = None
        if hasattr(follower_profile, 'image') and follower_profile.image:
            avatar_path = follower_profile.image.image.url
            if avatar_path:
                # Store the URL as-is from Django's ImageField
                # The serializer will handle proper URL construction
                follower_avatar = avatar_path
        
        # Get about snippet (first 150 characters)
        about_snippet = ""
        if hasattr(specific_follower, 'about') and specific_follower.about:
            about_snippet = specific_follower.about[:150]
            if len(specific_follower.about) > 150:
                about_snippet += "..."
        
        # Build extra data based on profile type
        extra_data = {
            'follower_username': follower_profile.username,
            'follower_id': follower_profile.id,
            'follower_public_id': str(follower_profile.public_id),
            'follower_avatar': follower_avatar,
            'follower_about': about_snippet,
        }
        
        # Add profile-type-specific fields
        if follower_profile.is_regular_profile():
            extra_data.update({
                'follower_name': specific_follower.name if specific_follower.name else "",
                'follower_pet_type': specific_follower.pet_type.name if specific_follower.pet_type else None,
                'follower_breed': specific_follower.breed if specific_follower.breed else "",
            })
        elif follower_profile.is_business_profile():
            extra_data.update({
                'follower_name': specific_follower.business_name if hasattr(specific_follower, 'business_name') else "",
                'follower_business_category': specific_follower.business_category if hasattr(specific_follower, 'business_category') else None,
            })
        
        # Get or update existing notification to prevent spam
        notification, created = Notification.objects.get_or_create(
            recipient=followed_profile,
            sender=follower_profile,
            notification_type=NotificationType.FOLLOW,
            post=None,
            comment=None,
            defaults={
                'title': "started following you",
                'message': f"{follower_profile.username} started following you",
                'extra_data': extra_data
            }
        )
        
        # If notification already exists, mark as unread
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=['is_read'])
        
        # Send via WebSocket
        send_notification_task.delay(notification.id)
        
        logger.info(f"Follow notification {'created' if created else 'updated'} for profile {followed_profile_id} (followed by {follower_profile_id})")
        
    except Profile.DoesNotExist as e:
        logger.error(f"Profile not found for follow notification: {e}")
    except Exception as e:
        logger.error(f"Error creating follow notification: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def create_tagged_post_notification_task(self, post_image_tag_id):
    """
    Create and send a notification when a profile is tagged in a post image.
    
    Args:
        post_image_tag_id (int): ID of the PostImageTag that was created
    """
    try:
        # Validate input parameters
        if not isinstance(post_image_tag_id, int):
            logger.error(f"Invalid parameter type: post_image_tag_id={type(post_image_tag_id)}")
            return
            
        post_image_tag = PostImageTag.objects.select_related(
            'post_image',
            'post_image__post',
            'post_image__post__profile',
            'tagged_profile',
            'tagged_by_profile'
        ).prefetch_related(
            Prefetch(
                'post_image__scaled_images',
                queryset=PostImageScaled.objects.filter(
                    scale=PostImageScaled.Scale.SMALL
                ),
            )
        ).get(id=post_image_tag_id)
        
        post = post_image_tag.post_image.post
        tagged_profile = post_image_tag.tagged_profile
        tagger_profile = post_image_tag.tagged_by_profile
        
        # Security: Don't send notification if user tagged themselves
        if tagged_profile.id == tagger_profile.id:
            return
        
        # Get post preview image URL (prefer small scaled; use the image where they were tagged)
        post_preview_image = None
        post_image = post_image_tag.post_image
        if post_image:
            small_scaled = next(
                (s for s in post_image.scaled_images.all() if s.image and s.image.url),
                None,
            )
            if small_scaled:
                post_preview_image = small_scaled.image.url
            elif post_image.image and post_image.image.url:
                post_preview_image = post_image.image.url
        
        # Get or update existing notification to prevent spam
        # Use the post as the unique identifier (one notification per post, not per image tag)
        notification, created = Notification.objects.get_or_create(
            recipient=tagged_profile,
            sender=tagger_profile,
            notification_type=NotificationType.TAGGED_POST,
            post=post,
            comment=None,
            defaults={
                'title': "tagged you in a post", # this is displayed in the notification list item
                'message': f"{tagger_profile.username} tagged you in a post", # this is displayed in the toast notification
                'extra_data': {
                    'post_caption': post.caption[:100],  # Limit data size
                    'post_id': post.id,
                    'post_public_id': str(post.public_id),
                    'post_image_id': post_image_tag.post_image.id,
                    'post_image_public_id': str(post_image_tag.post_image.public_id),
                    'tagger_username': tagger_profile.username,
                    'tagger_id': tagger_profile.id,
                    'tagger_public_id': str(tagger_profile.public_id),
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
        
        logger.info(f"Tagged post notification {'created' if created else 'updated'} for post {post.id}, tagged profile {tagged_profile.id}")
        
    except PostImageTag.DoesNotExist as e:
        logger.error(f"PostImageTag not found for tagged post notification: {e}")
    except Exception as e:
        logger.error(f"Error creating tagged post notification: {e}")
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


@shared_task(bind=True, ignore_result=True)
def create_follow_request_notification_task(self, follow_request_id):
    """
    Send a real-time WebSocket notification for a follow request.
    
    Note: This does NOT create a Notification database object. Follow requests
    are fetched separately by the frontend via FollowRequest endpoints, so we
    only send a real-time WebSocket notification to alert the user.
    
    Args:
        follow_request_id (int): ID of the FollowRequest that was created
    """
    try:
        # Validate input parameters
        if not isinstance(follow_request_id, int):
            logger.error(f"Invalid parameter type: follow_request_id={type(follow_request_id)}")
            return
            
        follow_request = FollowRequest.objects.select_related(
            'requester', 'requester__image', 'target'
        ).prefetch_related(
            Prefetch(
                'requester__image__scaled_images',
                queryset=ProfileImageScaled.objects.filter(scale=ProfileImageScaled.Scale.SMALL),
            )
        ).get(id=follow_request_id)
        
        requester_profile = follow_request.requester
        target_profile = follow_request.target
        
        # Get the specific profile (RegularProfile or BusinessProfile)
        specific_requester = requester_profile.get_specific_profile()
        
        # Get requester's avatar URL (prefer small scaled for notifications)
        requester_avatar = None
        if hasattr(requester_profile, 'image') and requester_profile.image:
            small_scaled = next(
                (s for s in requester_profile.image.scaled_images.all() if s.image and s.image.url),
                None,
            )
            if small_scaled:
                requester_avatar = build_full_media_url(small_scaled.image.url)
            else:
                avatar_path = requester_profile.image.image.url if requester_profile.image.image else None
                if avatar_path:
                    requester_avatar = build_full_media_url(avatar_path)
        
        # Get about snippet (first 150 characters)
        about_snippet = ""
        if hasattr(specific_requester, 'about') and specific_requester.about:
            about_snippet = specific_requester.about[:150]
            if len(specific_requester.about) > 150:
                about_snippet += "..."
        
        # Build extra data based on profile type
        extra_data = {
            'requester_username': requester_profile.username,
            'requester_id': requester_profile.id,
            'requester_avatar': requester_avatar,
            'requester_about': about_snippet,
            'follow_request_id': follow_request_id,
            "requester_public_id": str(requester_profile.public_id),
            "target_public_id": str(target_profile.public_id),
        }
        
        # Add profile-type-specific fields
        if requester_profile.is_regular_profile():
            extra_data.update({
                'requester_name': specific_requester.name if specific_requester.name else "",
                'requester_pet_type': specific_requester.pet_type.name if specific_requester.pet_type else None,
                'requester_breed': specific_requester.breed if specific_requester.breed else "",
            })
        elif requester_profile.is_business_profile():
            extra_data.update({
                'requester_name': specific_requester.business_name if hasattr(specific_requester, 'business_name') else "",
                'requester_business_category': specific_requester.business_category if hasattr(specific_requester, 'business_category') else None,
            })
        
        # Build notification data matching WebSocketNotificationSerializer format
        # Note: We don't create a Notification object for follow requests since
        # they are fetched separately by the frontend via the FollowRequest endpoints
        notification_data = {
            'id': None,  # No Notification object
            'notification_type': NotificationType.FOLLOW_REQUEST,
            'title': "wants to follow you",
            'message': f"{requester_profile.username} wants to follow you",
            'created_at': follow_request.created_at.isoformat(),
            'sender_username': requester_profile.username,
            'sender_avatar': requester_avatar,
            'sender_public_id': str(requester_profile.public_id),
            'post_id': None,
            'post_public_id': None,
            'comment_id': None,
            'extra_data': extra_data
        }
        
        # Send directly via WebSocket (no Notification object created)
        channel_layer = get_channel_layer()
        group_name = f'profile_{target_profile.id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )
        
        logger.info(f"Follow request WebSocket notification sent to profile {target_profile.id} (from {requester_profile.id})")
        
    except FollowRequest.DoesNotExist as e:
        logger.error(f"FollowRequest not found for follow request notification: {e}")
    except Exception as e:
        logger.error(f"Error creating follow request notification: {e}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, ignore_result=True)
def create_follow_request_accepted_notification_task(self, followed_profile_id, follower_profile_id):
    """
    Create and send a notification when a follow request is accepted.
    Notifies the requester that their follow request was accepted.
    
    Args:
        followed_profile_id (int): ID of the profile that accepted the request (the followed)
        follower_profile_id (int): ID of the profile whose request was accepted (the follower)
    """
    try:
        # Validate input parameters
        if not isinstance(followed_profile_id, int) or not isinstance(follower_profile_id, int):
            logger.error(f"Invalid parameter types: followed_profile_id={type(followed_profile_id)}, follower_profile_id={type(follower_profile_id)}")
            return
        
        followed_profile = Profile.objects.select_related('image').get(id=followed_profile_id)
        follower_profile = Profile.objects.get(id=follower_profile_id)
        
        # Get the specific profile (RegularProfile or BusinessProfile)
        specific_followed = followed_profile.get_specific_profile()
        
        # Get followed's avatar URL
        followed_avatar = None
        if hasattr(followed_profile, 'image') and followed_profile.image:
            avatar_path = followed_profile.image.image.url
            if avatar_path:
                followed_avatar = avatar_path
        
        # Get about snippet (first 150 characters)
        about_snippet = ""
        if hasattr(specific_followed, 'about') and specific_followed.about:
            about_snippet = specific_followed.about[:150]
            if len(specific_followed.about) > 150:
                about_snippet += "..."
        
        # Build extra data
        extra_data = {
            'followed_username': followed_profile.username,
            'followed_id': followed_profile.id,
            'followed_public_id': str(followed_profile.public_id),
            'followed_avatar': followed_avatar,
            'followed_about': about_snippet,
            'follower_public_id': str(follower_profile.public_id),
        }
        
        # Add profile-type-specific fields
        if followed_profile.is_regular_profile():
            extra_data.update({
                'followed_name': specific_followed.name if specific_followed.name else "",
                'followed_pet_type': specific_followed.pet_type.name if specific_followed.pet_type else None,
                'followed_breed': specific_followed.breed if specific_followed.breed else "",
            })
        elif followed_profile.is_business_profile():
            extra_data.update({
                'followed_name': specific_followed.business_name if hasattr(specific_followed, 'business_name') else "",
                'followed_business_category': specific_followed.business_category if hasattr(specific_followed, 'business_category') else None,
            })
        
        # Create notification (recipient is the follower who made the request)
        notification, created = Notification.objects.get_or_create(
            recipient=follower_profile,
            sender=followed_profile,
            notification_type=NotificationType.FOLLOW_REQUEST_ACCEPTED,
            post=None,
            comment=None,
            defaults={
                'title': "accepted your follow request",
                'message': f"{followed_profile.username} accepted your follow request",
                'extra_data': extra_data
            }
        )
        
        # If notification already exists, mark as unread
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=['is_read'])
        
        # Send via WebSocket
        send_notification_task.delay(notification.id)
        
        logger.info(f"Follow request accepted notification {'created' if created else 'updated'} for profile {follower_profile_id} (accepted by {followed_profile_id})")
        
    except Profile.DoesNotExist as e:
        logger.error(f"Profile not found for follow request accepted notification: {e}")
    except Exception as e:
        logger.error(f"Error creating follow request accepted notification: {e}")
        raise self.retry(countdown=60, max_retries=3)
