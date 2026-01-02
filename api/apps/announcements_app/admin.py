from django.contrib import admin
from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin interface for Announcement."""
    
    list_display = ['title', 'priority', 'announcement_type', 'is_active', 'start_date', 'end_date', 'created_at']
    list_filter = ['priority', 'is_active', 'announcement_type', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']
    list_editable = ['is_active', 'priority']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'message', 'announcement_type')
        }),
        ('Display Settings', {
            'fields': ('priority', 'is_active', 'start_date', 'end_date')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

