from django.db import models
from django.utils.translation import gettext_lazy as _


class AnnouncementPriority(models.TextChoices):
    """Priority levels for announcements."""
    LOW = 'low', _('Low')
    NORMAL = 'normal', _('Normal')
    HIGH = 'high', _('High')


class Announcement(models.Model):
    """Model for storing system-wide announcements."""
    
    title = models.CharField(
        max_length=200,
        help_text=_('Announcement title')
    )
    message = models.TextField(
        help_text=_('Announcement message content')
    )
    priority = models.CharField(
        max_length=10,
        choices=AnnouncementPriority.choices,
        default=AnnouncementPriority.NORMAL,
        help_text=_('Priority level of the announcement')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether the announcement is active')
    )
    start_date = models.DateTimeField(
        help_text=_('When the announcement should start being displayed')
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the announcement should stop being displayed (null = no end date)')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When the announcement was created')
    )
    announcement_type = models.CharField(
        max_length=50,
        default='general',
        help_text=_('Type of announcement (e.g., general, welcome, maintenance)')
    )
    
    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
            models.Index(fields=['announcement_type']),
            models.Index(fields=['-priority', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.title} ({self.priority})'

