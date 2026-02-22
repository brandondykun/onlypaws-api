"""
Admin configuration for posts app.
"""
from django.contrib import admin
from .models import Post, PostImage, PostImageScaled, SavedPost, PostImageTag


# Inline for PostImageTag in PostImage admin
class PostImageTagInline(admin.TabularInline):
    model = PostImageTag
    extra = 0
    fields = ['tagged_profile', 'tagged_by_profile', 'x_position', 'y_position', 'created_at']
    readonly_fields = ['created_at']
    ordering = ['id']


# Inline for PostImageScaled in PostImage admin
class PostImageScaledInline(admin.TabularInline):
    model = PostImageScaled
    extra = 0
    fields = ['scale', 'image', 'width', 'height', 'created_at']
    readonly_fields = ['image', 'width', 'height', 'created_at']
    ordering = ['scale']


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


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'order', 'image']
    list_filter = ['order']
    search_fields = ['post__id', 'post__caption']
    inlines = [PostImageTagInline, PostImageScaledInline]


@admin.register(PostImageScaled)
class PostImageScaledAdmin(admin.ModelAdmin):
    list_display = ['id', 'image', 'post_image__post__id', 'scale', 'width', 'height', 'created_at']
    list_filter = ['scale', 'created_at']
    search_fields = ['image', 'post_image__post__id', 'post_image__post__caption']
    ordering = ['image', 'post_image', 'scale']
    readonly_fields = ['created_at']


@admin.register(PostImageTag)
class PostImageTagAdmin(admin.ModelAdmin):
    list_display = ['id', 'post_image', 'tagged_profile', 'tagged_by_profile', 'x_position', 'y_position', 'created_at']
    list_filter = ['created_at']
    search_fields = ['tagged_profile__username', 'tagged_by_profile__username', 'post_image__post__id']
    readonly_fields = ['created_at']


admin.site.register(SavedPost)

