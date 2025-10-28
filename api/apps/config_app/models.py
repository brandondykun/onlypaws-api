from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class AppConfiguration(models.Model):
    """
    Model for storing application-wide configuration settings.
    Uses key-value pairs with JSON values for flexibility.
    """
    
    key = models.CharField(
        max_length=100,
        unique=True,
        help_text=_('Unique key for the configuration setting')
    )
    value = models.JSONField(
        help_text=_('JSON value for the configuration')
    )
    description = models.TextField(
        blank=True,
        help_text=_('Human-readable description of this configuration')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When the configuration was created')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text=_('When the configuration was last updated')
    )
    
    class Meta:
        ordering = ['key']
        verbose_name = _('App Configuration')
        verbose_name_plural = _('App Configurations')
    
    def __str__(self):
        return f'{self.key}'
    
    def clean(self):
        """Validate model data."""
        if not self.key:
            raise ValidationError({'key': 'Key cannot be empty'})
        
        if self.value is None:
            raise ValidationError({'value': 'Value cannot be null'})

