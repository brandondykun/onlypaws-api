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
