from rest_framework import serializers
from .models import Notification
from apps.user_app.serializers import ProfileSerializer
from drf_spectacular.utils import extend_schema_field


def get_extra_data_with_full_urls(obj, context=None):
    """
    Utility function to get extra data with full URLs for images.
    The image URL will be built correctly for both local (dev and test) 
    and S3 URLs (staging and prod).
    """
    extra_data = obj.extra_data.copy() if obj.extra_data else {}
    
    # Convert post_preview_image to full URL if it exists
    if 'post_preview_image' in extra_data:
        preview_image_path = extra_data['post_preview_image']
        if preview_image_path:
            # Check if URL is already absolute (starts with http/https)
            if preview_image_path.startswith(('http://', 'https://')):
                # URL is already absolute, use as-is
                extra_data['post_preview_image'] = preview_image_path
            else:
                # URL is relative, build absolute URL
                request = context.get('request') if context else None
                if request:
                    extra_data['post_preview_image'] = request.build_absolute_uri(preview_image_path)
                else:
                    # Fallback for when no request context (like in Celery tasks)
                    from django.conf import settings
                    media_domain = getattr(settings, 'MEDIA_DOMAIN', 'http://localhost:8000')
                    if preview_image_path.startswith('/'):
                        extra_data['post_preview_image'] = media_domain + preview_image_path
                    else:
                        extra_data['post_preview_image'] = media_domain + '/' + preview_image_path
    
    return extra_data


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""
    
    sender = ProfileSerializer(read_only=True)
    recipient = ProfileSerializer(read_only=True)
    extra_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'sender',
            'notification_type',
            'title',
            'message',
            'is_read',
            'created_at',
            'post',
            'comment',
            'extra_data',
        ]
        read_only_fields = [
            'id',
            'recipient',
            'sender',
            'created_at',
            'post',
            'comment',
            'extra_data',
        ]
    
    @extend_schema_field(serializers.DictField())
    def get_extra_data(self, obj):
        """Get extra data with full URLs for images."""
        return get_extra_data_with_full_urls(obj, self.context)


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications."""
    
    class Meta:
        model = Notification
        fields = [
            'recipient',
            'sender',
            'notification_type',
            'title',
            'message',
            'post',
            'comment',
            'extra_data',
        ]


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating notification read status."""
    
    class Meta:
        model = Notification
        fields = ['is_read']


class WebSocketNotificationSerializer(serializers.ModelSerializer):
    """Lightweight serializer for WebSocket notifications."""
    
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    extra_data = serializers.SerializerMethodField()
    post_id = serializers.SerializerMethodField()
    comment_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'created_at',
            'sender_username',
            'sender_avatar',
            'post_id',
            'comment_id',
            'extra_data'
        ]
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_sender_avatar(self, obj):
        """Get sender's profile image URL safely."""
        try:
            if (obj.sender and 
                hasattr(obj.sender, 'image') and 
                obj.sender.image and 
                obj.sender.image.image):
                image_url = obj.sender.image.image.url
                
                # Check if URL is already absolute (starts with http/https)
                if image_url.startswith(('http://', 'https://')):
                    # URL is already absolute, use as-is
                    return image_url
                else:
                    # URL is relative, build absolute URL
                    request = self.context.get('request')
                    if request:
                        return request.build_absolute_uri(image_url)
                    else:
                        # Fallback for when no request context (like in Celery tasks)
                        from django.conf import settings
                        media_domain = getattr(settings, 'MEDIA_DOMAIN', 'http://localhost:8000')
                        if image_url.startswith('/'):
                            return media_domain + image_url
                        else:
                            return media_domain + '/' + image_url
        except (AttributeError, ValueError):
            pass
        return None

    @extend_schema_field(serializers.DictField())
    def get_extra_data(self, obj):
        """Get extra data with full URLs for images."""
        return get_extra_data_with_full_urls(obj, self.context)
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_post_id(self, obj):
        """Get post ID, returning None if no post."""
        return obj.post.id if obj.post else None
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_comment_id(self, obj):
        """Get comment ID, returning None if no comment."""
        return obj.comment.id if obj.comment else None
