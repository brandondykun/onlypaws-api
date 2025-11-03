"""
Admin configuration for posts app.
"""
from django.contrib import admin
from .models import Post, PostImage, SavedPost


# Inline for PostImage in Post admin
class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    fields = ['image', 'order']
    readonly_fields = ['image']
    ordering = ['order', 'id']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'caption', 'profile', 'created_at', 'contains_ai']
    list_filter = ['contains_ai', 'created_at']
    search_fields = ['caption', 'profile__username']
    inlines = [PostImageInline]


admin.site.register(PostImage)
admin.site.register(SavedPost)

