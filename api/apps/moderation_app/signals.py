"""
Signals for cache invalidation of custom moderation word sets.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.moderation_app.models import CustomBannedWord, WhitelistedWord
from apps.moderation_app.cache import (
    invalidate_banned_words_cache,
    invalidate_whitelisted_words_cache,
)


@receiver(post_save, sender=CustomBannedWord)
@receiver(post_delete, sender=CustomBannedWord)
def invalidate_banned_words(sender, **kwargs):
    invalidate_banned_words_cache()


@receiver(post_save, sender=WhitelistedWord)
@receiver(post_delete, sender=WhitelistedWord)
def invalidate_whitelisted_words(sender, **kwargs):
    invalidate_whitelisted_words_cache()
