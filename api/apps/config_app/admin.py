from django.contrib import admin
from .models import AppConfiguration


@admin.register(AppConfiguration)
class AppConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for AppConfiguration."""
    
    list_display = ['key', 'value', 'updated_at', 'created_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('key', 'value', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

