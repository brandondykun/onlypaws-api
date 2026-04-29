"""
Tests for popularity helpers.
"""

from django.test import TestCase

from apps.recommendations_app.popularity import (
    _engagement_score,
    _seeded_shuffle,
)


class EngagementScoreTests(TestCase):

    def test_zero_engagement_returns_zero(self):
        self.assertEqual(_engagement_score(0, 0, 0, 0, 1.0), 0.0)

    def test_recency_decay(self):
        new = _engagement_score(10, 5, 3, 100, age_hours=1.0)
        old = _engagement_score(10, 5, 3, 100, age_hours=24.0)
        self.assertGreater(new, old)

    def test_saves_outweigh_likes(self):
        # 0L 1S 0C 0V vs 1L 0S 0C 0V at same age: saves should win.
        self.assertGreater(
            _engagement_score(0, 1, 0, 0, age_hours=1.0),
            _engagement_score(1, 0, 0, 0, age_hours=1.0),
        )

    def test_age_under_one_hour_floors_at_one(self):
        # An age of 0.1h shouldn't divide by anything tiny — it's clamped to 1h.
        clamped = _engagement_score(10, 0, 0, 0, age_hours=0.1)
        at_one = _engagement_score(10, 0, 0, 0, age_hours=1.0)
        self.assertEqual(clamped, at_one)


class SeededShuffleTests(TestCase):

    def test_deterministic_for_same_seed(self):
        ids = list(range(50))
        first = _seeded_shuffle(ids, profile_id=42, batch_id=0)
        second = _seeded_shuffle(ids, profile_id=42, batch_id=0)
        self.assertEqual(first, second)

    def test_different_batch_changes_order(self):
        ids = list(range(50))
        a = _seeded_shuffle(ids, profile_id=42, batch_id=0)
        b = _seeded_shuffle(ids, profile_id=42, batch_id=1)
        self.assertNotEqual(a, b)

    def test_different_shuffle_token_changes_order(self):
        ids = list(range(50))
        a = _seeded_shuffle(ids, profile_id=42, batch_id=0, shuffle_token=1)
        b = _seeded_shuffle(ids, profile_id=42, batch_id=0, shuffle_token=2)
        self.assertNotEqual(a, b)

    def test_different_profile_changes_order(self):
        ids = list(range(50))
        a = _seeded_shuffle(ids, profile_id=42, batch_id=0)
        b = _seeded_shuffle(ids, profile_id=99, batch_id=0)
        self.assertNotEqual(a, b)

    def test_preserves_elements(self):
        ids = list(range(50))
        shuffled = _seeded_shuffle(ids, profile_id=42, batch_id=0)
        self.assertEqual(sorted(shuffled), ids)
