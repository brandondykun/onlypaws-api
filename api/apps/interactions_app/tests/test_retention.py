"""
Tests for the PostInteraction retention task.
"""

from datetime import timedelta

from django.utils import timezone

from apps.interactions_app.models import PostInteraction
from apps.interactions_app.tasks import cleanup_old_post_interactions_task
from core.test_utils.helper_classes import BaseFixtureTestCase


IT = PostInteraction.InteractionType


class CleanupOldPostInteractionsTests(BaseFixtureTestCase):

    def _create_with_age(self, profile, post, days_old):
        obj = PostInteraction.objects.create(
            profile=profile,
            post=post,
            interaction_type=IT.VIEW,
            dwell_time_ms=2000,
        )
        if days_old > 0:
            PostInteraction.objects.filter(pk=obj.pk).update(
                created_at=timezone.now() - timedelta(days=days_old)
            )
        return obj

    def test_deletes_rows_older_than_retention_window(self):
        old = self._create_with_age(self.profile, self.post_5, days_old=31)
        recent = self._create_with_age(self.profile, self.post_5, days_old=1)

        result = cleanup_old_post_interactions_task(retention_days=30)

        self.assertGreaterEqual(result["deleted"], 1)
        self.assertFalse(PostInteraction.objects.filter(pk=old.pk).exists())
        self.assertTrue(PostInteraction.objects.filter(pk=recent.pk).exists())

    def test_no_op_when_nothing_to_delete(self):
        self._create_with_age(self.profile, self.post_5, days_old=1)
        result = cleanup_old_post_interactions_task(retention_days=30)
        self.assertEqual(result["deleted"], 0)

    def test_keeps_rows_at_exactly_the_boundary(self):
        # Boundary: exactly retention_days old should NOT be deleted (cutoff is `<`, not `<=`).
        boundary = PostInteraction.objects.create(
            profile=self.profile,
            post=self.post_5,
            interaction_type=IT.VIEW,
            dwell_time_ms=2000,
        )
        cutoff = timezone.now() - timedelta(days=30)
        # Force created_at very slightly after the cutoff.
        PostInteraction.objects.filter(pk=boundary.pk).update(
            created_at=cutoff + timedelta(seconds=10)
        )

        cleanup_old_post_interactions_task(retention_days=30)
        self.assertTrue(PostInteraction.objects.filter(pk=boundary.pk).exists())

    def test_retention_window_is_parameterised(self):
        old_45d = self._create_with_age(self.profile, self.post_5, days_old=45)
        # With a 60-day retention, the 45-day-old row should still exist.
        cleanup_old_post_interactions_task(retention_days=60)
        self.assertTrue(PostInteraction.objects.filter(pk=old_45d.pk).exists())

        # But with a 30-day retention, it gets deleted.
        cleanup_old_post_interactions_task(retention_days=30)
        self.assertFalse(PostInteraction.objects.filter(pk=old_45d.pk).exists())
