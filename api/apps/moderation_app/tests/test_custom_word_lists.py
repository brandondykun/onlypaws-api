"""
Tests for CustomBannedWord and WhitelistedWord integration with ProfanityService.

Tests verify that:
- Words flagged by the default word list can be whitelisted to pass
- Clean words can be added as custom banned words to be flagged
- Cache invalidation works correctly when words are added/removed
- Both check_text() and check_username() respect custom word lists
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from apps.core_app.profanity_service import (
    ProfanityService,
    check_and_log_text,
    check_and_log_username,
)
from apps.moderation_app.models import CustomBannedWord, WhitelistedWord
from apps.moderation_app.cache import (
    get_custom_banned_words,
    get_whitelisted_words,
    invalidate_banned_words_cache,
    invalidate_whitelisted_words_cache,
)

CACHES_SETTING = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-custom-words",
    }
}


@override_settings(CACHES=CACHES_SETTING)
class CustomBannedWordModelTests(TestCase):
    """Tests for the CustomBannedWord model."""

    def test_word_is_lowercased_on_save(self):
        word = CustomBannedWord.objects.create(word="BADTERM")
        self.assertEqual(word.word, "badterm")

    def test_word_is_stripped_on_save(self):
        word = CustomBannedWord.objects.create(word="  badterm  ")
        self.assertEqual(word.word, "badterm")

    def test_word_unique_constraint(self):
        CustomBannedWord.objects.create(word="badterm")
        with self.assertRaises(Exception):
            CustomBannedWord.objects.create(word="badterm")

    def test_str_representation(self):
        word = CustomBannedWord.objects.create(word="badterm")
        self.assertEqual(str(word), "badterm")


@override_settings(CACHES=CACHES_SETTING)
class WhitelistedWordModelTests(TestCase):
    """Tests for the WhitelistedWord model."""

    def test_word_is_lowercased_on_save(self):
        word = WhitelistedWord.objects.create(word="GOODWORD")
        self.assertEqual(word.word, "goodword")

    def test_word_is_stripped_on_save(self):
        word = WhitelistedWord.objects.create(word="  goodword  ")
        self.assertEqual(word.word, "goodword")

    def test_word_unique_constraint(self):
        WhitelistedWord.objects.create(word="goodword")
        with self.assertRaises(Exception):
            WhitelistedWord.objects.create(word="goodword")

    def test_str_representation(self):
        word = WhitelistedWord.objects.create(word="goodword")
        self.assertEqual(str(word), "goodword")


@override_settings(CACHES=CACHES_SETTING)
class CacheHelperTests(TestCase):
    """Tests for the cache helper functions."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()

    def test_get_custom_banned_words_returns_set(self):
        CustomBannedWord.objects.create(word="badterm")
        CustomBannedWord.objects.create(word="anotherbad")
        words = get_custom_banned_words()
        self.assertEqual(words, {"badterm", "anotherbad"})

    def test_get_custom_banned_words_empty(self):
        words = get_custom_banned_words()
        self.assertEqual(words, set())

    def test_get_whitelisted_words_returns_set(self):
        WhitelistedWord.objects.create(word="safeword")
        WhitelistedWord.objects.create(word="anothersafe")
        words = get_whitelisted_words()
        self.assertEqual(words, {"safeword", "anothersafe"})

    def test_get_whitelisted_words_empty(self):
        words = get_whitelisted_words()
        self.assertEqual(words, set())

    def test_cache_invalidation_on_banned_word_create(self):
        """Cache is invalidated via signal when a banned word is created."""
        # Prime the cache
        words = get_custom_banned_words()
        self.assertEqual(words, set())

        # Create a new word — signal should invalidate cache
        CustomBannedWord.objects.create(word="newbad")

        # Next fetch should reflect the new word
        words = get_custom_banned_words()
        self.assertIn("newbad", words)

    def test_cache_invalidation_on_banned_word_delete(self):
        """Cache is invalidated via signal when a banned word is deleted."""
        word = CustomBannedWord.objects.create(word="tempbad")
        # Prime cache
        words = get_custom_banned_words()
        self.assertIn("tempbad", words)

        # Delete — signal should invalidate cache
        word.delete()

        words = get_custom_banned_words()
        self.assertNotIn("tempbad", words)

    def test_cache_invalidation_on_whitelisted_word_create(self):
        """Cache is invalidated via signal when a whitelisted word is created."""
        words = get_whitelisted_words()
        self.assertEqual(words, set())

        WhitelistedWord.objects.create(word="newsafe")

        words = get_whitelisted_words()
        self.assertIn("newsafe", words)

    def test_cache_invalidation_on_whitelisted_word_delete(self):
        """Cache is invalidated via signal when a whitelisted word is deleted."""
        word = WhitelistedWord.objects.create(word="tempsafe")
        words = get_whitelisted_words()
        self.assertIn("tempsafe", words)

        word.delete()

        words = get_whitelisted_words()
        self.assertNotIn("tempsafe", words)


@override_settings(CACHES=CACHES_SETTING)
class WhitelistCheckTextTests(TestCase):
    """
    Tests that whitelisting a word causes check_text() to no longer flag it.

    Flow: verify the word IS flagged → whitelist it → verify it is NOT flagged.
    """

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_default_bad_word_is_flagged_then_whitelisted(self, mock_predict):
        """A word from the default bad list is flagged, then passes after whitelisting."""
        # Mock ML to always return low probability so we isolate word-level detection
        mock_predict.side_effect = lambda texts: [0.01] * len(texts)

        # Pick a word deterministically — find one that is purely alphabetic and
        # won't be split by _split_sentences or cause normalize edge cases
        bad_word = None
        for w in sorted(self.service._bad_words):
            if w.isalpha() and len(w) >= 4:
                bad_word = w
                break
        self.assertIsNotNone(bad_word, "Need at least one alpha bad word >= 4 chars")

        # Step 1: Verify it IS flagged via WORD_MATCH
        result = self.service.check_text(bad_word)
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "WORD_MATCH")

        # Step 2: Whitelist it
        WhitelistedWord.objects.create(word=bad_word)

        # Step 3: Verify it is NOT flagged anymore
        result = self.service.check_text(bad_word)
        self.assertFalse(result.is_profane)

    def test_whitelist_does_not_affect_ml_detection(self):
        """ML-based detection should NOT be overridden by whitelisting."""
        # We mock the ML layer to return a high probability for a sentence
        with patch("apps.core_app.profanity_service.predict_prob") as mock_predict:
            mock_predict.return_value = [0.95]

            # Even if every word is whitelisted, ML detection should still trigger
            WhitelistedWord.objects.create(word="testword")
            result = self.service.check_text("testword")
            self.assertTrue(result.is_profane)
            self.assertEqual(result.detection_method, "ML")


@override_settings(CACHES=CACHES_SETTING)
class CustomBannedCheckTextTests(TestCase):
    """
    Tests that adding a custom banned word causes check_text() to flag it.

    Flow: verify the word is NOT flagged → add to banned list → verify it IS flagged.
    """

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_clean_word_passes_then_banned(self, mock_predict):
        """A clean word passes, then fails after being added as a custom banned word."""
        mock_predict.return_value = [0.01]

        # Step 1: Verify the word is NOT flagged
        result = self.service.check_text("fluffernutter")
        self.assertFalse(result.is_profane)

        # Step 2: Add it as a custom banned word
        CustomBannedWord.objects.create(word="fluffernutter")

        # Step 3: Verify it IS now flagged
        result = self.service.check_text("fluffernutter")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "WORD_MATCH")
        self.assertEqual(result.detection_details["matched_word"], "fluffernutter")

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_removing_custom_banned_word_allows_it_again(self, mock_predict):
        """Removing a custom banned word makes it pass again."""
        mock_predict.return_value = [0.01]

        word = CustomBannedWord.objects.create(word="fluffernutter")

        result = self.service.check_text("fluffernutter")
        self.assertTrue(result.is_profane)

        # Remove the banned word
        word.delete()

        result = self.service.check_text("fluffernutter")
        self.assertFalse(result.is_profane)


@override_settings(CACHES=CACHES_SETTING)
class WhitelistCheckUsernameTests(TestCase):
    """
    Tests that whitelisting a word causes check_username() to no longer flag it.

    Covers SUBSTRING, SHORT_MATCH, and FUZZY detection methods.
    """

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    def test_substring_match_flagged_then_whitelisted(self):
        """A custom banned word in a username is flagged via SUBSTRING, then passes after whitelisting."""
        # Use a custom banned word to avoid interference from other default bad words
        CustomBannedWord.objects.create(word="fluffernutter")

        username = "fluffernutterpaws"

        # Step 1: Verify it IS flagged
        result = self.service.check_username(username)
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "SUBSTRING")
        self.assertEqual(result.detection_details["matched_word"], "fluffernutter")

        # Step 2: Whitelist the matched word
        WhitelistedWord.objects.create(word="fluffernutter")

        # Step 3: Verify it is NOT flagged anymore
        result = self.service.check_username(username)
        self.assertFalse(result.is_profane)

    def test_short_match_flagged_then_whitelisted(self):
        """A 3-char custom banned word at the start of a username is flagged, then passes after whitelisting."""
        # Use a custom banned word to avoid non-determinism from default word set ordering
        CustomBannedWord.objects.create(word="zqx")

        username = "zqxpawlover"

        # Step 1: Verify it IS flagged via SHORT_MATCH at start
        result = self.service.check_username(username)
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "SHORT_MATCH")
        self.assertEqual(result.detection_details["matched_word"], "zqx")

        # Step 2: Whitelist
        WhitelistedWord.objects.create(word="zqx")

        # Step 3: Verify no longer flagged
        result = self.service.check_username(username)
        self.assertFalse(result.is_profane)


@override_settings(CACHES=CACHES_SETTING)
class CustomBannedCheckUsernameTests(TestCase):
    """
    Tests that adding a custom banned word causes check_username() to flag it.

    Flow: verify the username passes → add custom banned word → verify it is flagged.
    """

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    def test_clean_username_passes_then_banned_substring(self):
        """A clean username passes, then is flagged via SUBSTRING after adding a custom banned word."""
        # Step 1: Verify the username is NOT flagged
        result = self.service.check_username("fluffernutterpaws")
        self.assertFalse(result.is_profane)

        # Step 2: Add "fluffernutter" as a custom banned word (>= 4 chars → SUBSTRING detection)
        CustomBannedWord.objects.create(word="fluffernutter")

        # Step 3: Verify it IS now flagged
        result = self.service.check_username("fluffernutterpaws")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "SUBSTRING")
        self.assertEqual(result.detection_details["matched_word"], "fluffernutter")

    def test_clean_username_passes_then_banned_short_match(self):
        """A clean username passes, then is flagged via SHORT_MATCH after adding a 3-char custom banned word."""
        # Step 1: Verify the username is NOT flagged
        result = self.service.check_username("zqxlover")
        self.assertFalse(result.is_profane)

        # Step 2: Add "zqx" as a custom banned word (3 chars → SHORT_MATCH detection)
        CustomBannedWord.objects.create(word="zqx")

        # Step 3: Verify it IS now flagged at start
        result = self.service.check_username("zqxlover")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "SHORT_MATCH")
        self.assertEqual(result.detection_details["matched_word"], "zqx")
        self.assertEqual(result.detection_details["match_position"], "start")

    def test_removing_custom_banned_word_allows_username_again(self):
        """Removing a custom banned word makes the username pass again."""
        result = self.service.check_username("fluffernutterpaws")
        self.assertFalse(result.is_profane)

        word = CustomBannedWord.objects.create(word="fluffernutter")

        result = self.service.check_username("fluffernutterpaws")
        self.assertTrue(result.is_profane)

        # Remove the banned word
        word.delete()

        result = self.service.check_username("fluffernutterpaws")
        self.assertFalse(result.is_profane)


@override_settings(CACHES=CACHES_SETTING)
class CombinedBannedAndWhitelistTests(TestCase):
    """Tests for interactions between custom banned words and whitelisted words."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_custom_banned_word_can_be_whitelisted(self, mock_predict):
        """A custom banned word that is also whitelisted should NOT be flagged."""
        mock_predict.return_value = [0.01]

        CustomBannedWord.objects.create(word="fluffernutter")

        # Flagged as banned
        result = self.service.check_text("fluffernutter")
        self.assertTrue(result.is_profane)

        # Now whitelist it
        WhitelistedWord.objects.create(word="fluffernutter")

        # No longer flagged
        result = self.service.check_text("fluffernutter")
        self.assertFalse(result.is_profane)

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_whitelist_only_affects_whitelisted_word(self, mock_predict):
        """Whitelisting one word does not affect detection of other words."""
        mock_predict.return_value = [0.01]

        CustomBannedWord.objects.create(word="badtermone")
        CustomBannedWord.objects.create(word="badtermtwo")
        WhitelistedWord.objects.create(word="badtermone")

        # "badtermone" is whitelisted — should pass
        result = self.service.check_text("badtermone")
        self.assertFalse(result.is_profane)

        # "badtermtwo" is NOT whitelisted — should still be flagged
        result = self.service.check_text("badtermtwo")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_details["matched_word"], "badtermtwo")

    def test_username_custom_banned_then_whitelisted(self):
        """A custom banned word in a username is flagged, then passes after whitelisting."""
        CustomBannedWord.objects.create(word="fluffernutter")

        result = self.service.check_username("fluffernutterpaws")
        self.assertTrue(result.is_profane)

        WhitelistedWord.objects.create(word="fluffernutter")

        result = self.service.check_username("fluffernutterpaws")
        self.assertFalse(result.is_profane)


@override_settings(CACHES=CACHES_SETTING)
class ContainsProfanityHelperTests(TestCase):
    """Tests for the _contains_* boolean helper methods on ProfanityService."""

    def setUp(self):
        self.service = ProfanityService()

    def test_contains_long_profanity_true(self):
        """_contains_long_profanity returns True when a long bad word is a substring."""
        long_word = next(w for w in self.service._long_bad if len(w) >= 4)
        self.assertTrue(self.service._contains_long_profanity(f"abc{long_word}xyz"))

    def test_contains_long_profanity_false(self):
        """_contains_long_profanity returns False for clean text."""
        self.assertFalse(self.service._contains_long_profanity("fluffernutterpaws"))

    def test_contains_short_profanity_true(self):
        """_contains_short_profanity returns True when text starts/ends with a 3-char bad word."""
        short_word = next(w for w in self.service._short_bad if len(w) == 3)
        self.assertTrue(
            self.service._contains_short_profanity(f"{short_word}puppylover")
        )

    def test_contains_short_profanity_false(self):
        """_contains_short_profanity returns False for clean text."""
        self.assertFalse(self.service._contains_short_profanity("fluffypaws"))

    def test_contains_fuzzy_profanity_true(self):
        """_contains_fuzzy_profanity returns True for a near-match of a long bad word."""
        # Need a word long enough that one char swap stays >= 88% similar
        # For an 8-char word, 1 swap = 87.5% (7/8), so use >= 9 chars
        long_word = next((w for w in self.service._long_bad if len(w) >= 9), None)
        if long_word is None:
            # Fallback: use the exact word (100% match is always >= 88%)
            long_word = next(w for w in self.service._long_bad if len(w) >= 5)
            self.assertTrue(self.service._contains_fuzzy_profanity(long_word))
            return
        mid = len(long_word) // 2
        fuzzy_variant = long_word[:mid] + "z" + long_word[mid + 1 :]
        self.assertTrue(self.service._contains_fuzzy_profanity(fuzzy_variant))

    def test_contains_fuzzy_profanity_false(self):
        """_contains_fuzzy_profanity returns False for clean text."""
        self.assertFalse(self.service._contains_fuzzy_profanity("fluffypaws"))


@override_settings(CACHES=CACHES_SETTING)
class ShortMatchEndPositionTests(TestCase):
    """Tests for SHORT_MATCH detection at the end of a username."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    def test_short_match_end_position(self):
        """A 3-char custom banned word at the end of a username is detected as SHORT_MATCH end."""
        CustomBannedWord.objects.create(word="zqx")

        # Username ending with the short word (not starting)
        result = self.service.check_username("loverzqx")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "SHORT_MATCH")
        self.assertEqual(result.detection_details["matched_word"], "zqx")
        self.assertEqual(result.detection_details["match_position"], "end")


@override_settings(CACHES=CACHES_SETTING)
class FuzzyMatchUsernameTests(TestCase):
    """Tests for FUZZY detection in check_username with custom banned words."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    def test_fuzzy_match_detects_near_spelling(self):
        """A username with a near-spelling of a custom banned word triggers FUZZY detection."""
        CustomBannedWord.objects.create(word="fluffernutter")

        # Swap one character — "fluffernuttor" should fuzzy-match "fluffernutter"
        result = self.service.check_username("fluffernuttor")
        self.assertTrue(result.is_profane)
        self.assertEqual(result.detection_method, "FUZZY")
        self.assertEqual(result.detection_details["matched_word"], "fluffernutter")

    def test_fuzzy_match_whitelisted(self):
        """A fuzzy-matched custom banned word that is whitelisted should NOT be flagged."""
        CustomBannedWord.objects.create(word="fluffernutter")
        WhitelistedWord.objects.create(word="fluffernutter")

        result = self.service.check_username("fluffernuttor")
        self.assertFalse(result.is_profane)


@override_settings(CACHES=CACHES_SETTING)
class BoolWrapperMethodTests(TestCase):
    """Tests for the is_profane_text and is_profane_username boolean wrapper methods."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_is_profane_text_returns_true_for_banned_word(self, mock_predict):
        mock_predict.return_value = [0.01]
        CustomBannedWord.objects.create(word="fluffernutter")
        self.assertTrue(self.service.is_profane_text("fluffernutter"))

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_is_profane_text_returns_false_for_clean_text(self, mock_predict):
        mock_predict.return_value = [0.01]
        self.assertFalse(self.service.is_profane_text("cute puppy"))

    def test_is_profane_username_returns_true_for_banned_word(self):
        CustomBannedWord.objects.create(word="fluffernutter")
        self.assertTrue(self.service.is_profane_username("fluffernutterpaws"))

    def test_is_profane_username_returns_false_for_clean_username(self):
        self.assertFalse(self.service.is_profane_username("fluffypaws"))


@override_settings(CACHES=CACHES_SETTING)
class CheckAndLogTests(TestCase):
    """Tests for the check_and_log_text and check_and_log_username module-level functions."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()

    @patch("apps.moderation_app.tasks.log_profanity_detection_task")
    @patch("apps.core_app.profanity_service.predict_prob")
    def test_check_and_log_text_logs_when_profane(self, mock_predict, mock_task):
        """check_and_log_text dispatches a logging task when profanity is detected."""
        mock_predict.return_value = [0.01]
        CustomBannedWord.objects.create(word="fluffernutter")

        result = check_and_log_text("fluffernutter", "COMMENT", profile_id=42)

        self.assertTrue(result)
        mock_task.delay.assert_called_once()
        call_kwargs = mock_task.delay.call_args[1]
        self.assertEqual(call_kwargs["original_text"], "fluffernutter")
        self.assertEqual(call_kwargs["content_type"], "COMMENT")
        self.assertEqual(call_kwargs["detection_method"], "WORD_MATCH")
        self.assertEqual(call_kwargs["profile_id"], 42)

    @patch("apps.moderation_app.tasks.log_profanity_detection_task")
    @patch("apps.core_app.profanity_service.predict_prob")
    def test_check_and_log_text_no_log_when_clean(self, mock_predict, mock_task):
        """check_and_log_text does not dispatch a task for clean text."""
        mock_predict.return_value = [0.01]

        result = check_and_log_text("cute puppy", "COMMENT")

        self.assertFalse(result)
        mock_task.delay.assert_not_called()

    @patch("apps.moderation_app.tasks.log_profanity_detection_task")
    def test_check_and_log_username_logs_when_profane(self, mock_task):
        """check_and_log_username dispatches a logging task when profanity is detected."""
        CustomBannedWord.objects.create(word="fluffernutter")

        result = check_and_log_username("fluffernutterpaws", "USERNAME", profile_id=99)

        self.assertTrue(result)
        mock_task.delay.assert_called_once()
        call_kwargs = mock_task.delay.call_args[1]
        self.assertEqual(call_kwargs["original_text"], "fluffernutterpaws")
        self.assertEqual(call_kwargs["content_type"], "USERNAME")
        self.assertEqual(call_kwargs["detection_method"], "SUBSTRING")
        self.assertEqual(call_kwargs["profile_id"], 99)

    @patch("apps.moderation_app.tasks.log_profanity_detection_task")
    def test_check_and_log_username_no_log_when_clean(self, mock_task):
        """check_and_log_username does not dispatch a task for clean usernames."""
        result = check_and_log_username("fluffypaws", "USERNAME")

        self.assertFalse(result)
        mock_task.delay.assert_not_called()


@override_settings(CACHES=CACHES_SETTING)
class CleanInputReturnsFalseTests(TestCase):
    """Tests that clean inputs return is_profane=False through all detection stages."""

    def setUp(self):
        invalidate_banned_words_cache()
        invalidate_whitelisted_words_cache()
        self.service = ProfanityService()

    @patch("apps.core_app.profanity_service.predict_prob")
    def test_check_text_clean_returns_false(self, mock_predict):
        """check_text returns is_profane=False for completely clean text."""
        mock_predict.return_value = [0.01]
        result = self.service.check_text("what a lovely day for a walk with my dog")
        self.assertFalse(result.is_profane)
        self.assertIsNone(result.detection_method)

    def test_check_username_clean_returns_false(self):
        """check_username returns is_profane=False for a clean username after all checks."""
        result = self.service.check_username("fluffypaws")
        self.assertFalse(result.is_profane)
        self.assertIsNone(result.detection_method)

    def test_check_username_empty_normalized_returns_false(self):
        """check_username returns is_profane=False when normalized text is empty."""
        # All-numeric username normalizes to empty after leet-speak + alpha filter
        result = self.service.check_username("12345")
        self.assertFalse(result.is_profane)
