from django.contrib import admin
from . import models


# Inline for PostImage in Post admin
class PostImageInline(admin.TabularInline):
    model = models.PostImage
    extra = 0
    fields = ['image', 'order']
    readonly_fields = ['image']
    ordering = ['order', 'id']


@admin.register(models.Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'caption', 'profile', 'created_at', 'contains_ai']
    list_filter = ['contains_ai', 'created_at']
    search_fields = ['caption', 'profile__username']
    inlines = [PostImageInline]


admin.site.register(models.User)
admin.site.register(models.Profile)
admin.site.register(models.PostImage)
admin.site.register(models.Comment)
admin.site.register(models.Like)
admin.site.register(models.Follow)
admin.site.register(models.ProfileImage)
admin.site.register(models.CommentLike)
admin.site.register(models.PetType)
admin.site.register(models.PostImageStaged)
admin.site.register(models.SavedPost)
admin.site.register(models.ReportReason)
admin.site.register(models.PostReport)
admin.site.register(models.VerifyEmailToken)
admin.site.register(models.ResetPasswordToken)
admin.site.register(models.PendingEmailChange)
admin.site.register(models.RegularProfile)
admin.site.register(models.BusinessProfile)
admin.site.register(models.Address)
