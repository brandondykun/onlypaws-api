from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.User)
admin.site.register(models.Profile)
admin.site.register(models.Post)
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
