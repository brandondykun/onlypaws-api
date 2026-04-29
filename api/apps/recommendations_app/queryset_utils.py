"""
Shared queryset predicates for the recommendations engine.

Centralising the recommendable-posts filter keeps every code path that surfaces
posts to a viewer (vector search, popularity refresh + revalidation, recency
fallback) in agreement on which posts are eligible. Skipping this filter in any
one path lets reported content leak into Explore until the next batch turn over.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.moderation_app.models import INAPPROPRIATE_REPORT_REASON_NAME
from apps.posts_app.models import Post


def recommendable_posts_qs() -> QuerySet[Post]:
    """
    Base queryset for posts eligible to surface in the personalised Explore feed.

    Policy: hide posts whose reports include INAPPROPRIATE_REPORT_REASON_NAME.
    This matches the filter used by RetrieveFeedView, ListProfilePostsView, and
    ListSimilarPostsView, so Explore is no stricter than the followed feed.

    Profile-level exclusions (own / blocked / heavily-reported) and ranking are
    caller-specific and applied on top of this queryset.
    """
    return (
        Post.objects.filter(
            status=Post.Status.READY,
            profile__is_private=False,
        ).exclude(reports__reason__name=INAPPROPRIATE_REPORT_REASON_NAME)
    )
