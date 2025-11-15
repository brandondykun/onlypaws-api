from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.profile_app.models import Profile
from apps.posts_app.models import Post
from apps.interactions_app.models import Comment


class NotificationType(models.TextChoices):
    """Types of notifications that can be sent."""
    LIKE_POST = 'like_post', _('Like Post')
    LIKE_COMMENT = 'like_comment', _('Like Comment')
    COMMENT = 'comment', _('Comment')
    COMMENT_REPLY = 'comment_reply', _('Comment Reply')
    FOLLOW = 'follow', _('Follow')
    MENTION = 'mention', _('Mention')
    SYSTEM = 'system', _('System')


class Notification(models.Model):
    """Model for storing notifications."""
    
    recipient = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='notifications_received',
        help_text=_('Profile that receives the notification')
    )
    sender = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='notifications_sent',
        null=True,
        blank=True,
        help_text=_('Profile that triggered the notification (can be null for system notifications)')
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        help_text=_('Type of notification')
    )
    title = models.CharField(
        max_length=255,
        help_text=_('Notification title')
    )
    message = models.TextField(
        help_text=_('Notification message content')
    )
    is_read = models.BooleanField(
        default=False,
        help_text=_('Whether the notification has been read')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When the notification was created')
    )
    
    # Optional references to related objects
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text=_('Related post (if applicable)')
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text=_('Related comment (if applicable)')
    )
    
    # Additional data can be stored as JSON for flexibility
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional data for the notification')
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f'{self.notification_type} notification for {self.recipient.username}'
    
    def clean(self):
        """Validate model data."""
        from django.core.exceptions import ValidationError
        
        if self.title and len(self.title) > 255:
            raise ValidationError({'title': 'Title cannot exceed 255 characters'})
        
        if self.message and len(self.message) > 1000:
            raise ValidationError({'message': 'Message cannot exceed 1000 characters'})
        
        # Validate notification type
        if self.notification_type not in [choice[0] for choice in NotificationType.choices]:
            raise ValidationError({'notification_type': 'Invalid notification type'})
    
    def mark_as_read(self):
        """Mark the notification as read efficiently."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
