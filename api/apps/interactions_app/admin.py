"""
Admin configuration for interactions app.
"""
from django.contrib import admin
from .models import Like, Comment, CommentLike, Follow

admin.site.register(Like)
admin.site.register(Comment)
admin.site.register(CommentLike)
admin.site.register(Follow)
