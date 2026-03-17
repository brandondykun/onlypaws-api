"""
Cache helpers for moderation word sets.
"""

from django.core.cache import cache

CUSTOM_BANNED_WORDS_KEY = "moderation:custom_banned_words"
WHITELISTED_WORDS_KEY = "moderation:whitelisted_words"
CACHE_TIMEOUT = 3600  # 1 hour


def get_custom_banned_words() -> set[str]:
    """Fetch custom banned words from cache, falling back to DB."""
    words = cache.get(CUSTOM_BANNED_WORDS_KEY)
    if words is None:
        from apps.moderation_app.models import CustomBannedWord

        words = set(CustomBannedWord.objects.values_list("word", flat=True))
        cache.set(CUSTOM_BANNED_WORDS_KEY, words, CACHE_TIMEOUT)
    return words


def get_whitelisted_words() -> set[str]:
    """Fetch whitelisted words from cache, falling back to DB."""
    words = cache.get(WHITELISTED_WORDS_KEY)
    if words is None:
        from apps.moderation_app.models import WhitelistedWord

        words = set(WhitelistedWord.objects.values_list("word", flat=True))
        cache.set(WHITELISTED_WORDS_KEY, words, CACHE_TIMEOUT)
    return words


def invalidate_banned_words_cache():
    cache.delete(CUSTOM_BANNED_WORDS_KEY)


def invalidate_whitelisted_words_cache():
    cache.delete(WHITELISTED_WORDS_KEY)
