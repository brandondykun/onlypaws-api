"""
Service for detecting profanity in user-generated content.
"""

import re
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Optional
from better_profanity import profanity
from profanity_check import predict_prob
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class ProfanityCheckResult:
    is_profane: bool
    detection_method: Optional[str] = (
        None  # "ML", "WORD_MATCH", "SUBSTRING", "SHORT_MATCH", "FUZZY"
    )
    detection_details: dict = field(default_factory=dict)


class ProfanityService:
    """
    Service for detecting profanity in user-generated content.

    Designed for reuse across different content types (usernames, captions, etc.)
    with content-type-specific public methods.
    """

    def __init__(self):
        profanity.load_censor_words()
        custom_words = []
        profanity.add_censor_words(custom_words)

        self._bad_words = {str(word).lower() for word in profanity.CENSOR_WORDSET}
        self._short_bad = {w for w in self._bad_words if len(w) == 3}
        self._long_bad = {w for w in self._bad_words if len(w) >= 4}

        self._leet_map = str.maketrans(
            {
                "0": "o",
                "1": "i",
                "3": "e",
                "4": "a",
                "5": "s",
                "7": "t",
                "@": "a",
                "$": "s",
                "!": "i",
            }
        )

    def _normalize_username(self, username: str) -> str:
        """Normalize username for profanity detection."""
        username = unicodedata.normalize("NFKD", username)
        username = username.encode("ascii", "ignore").decode("ascii")
        username = username.lower()
        username = username.translate(self._leet_map)
        username = re.sub(r"[^a-z]", "", username)
        return username

    def _get_custom_banned_words(self) -> set[str]:
        """Fetch custom banned words from cache/DB."""
        from apps.moderation_app.cache import get_custom_banned_words

        return get_custom_banned_words()

    def _get_whitelisted_words(self) -> set[str]:
        """Fetch whitelisted words from cache/DB."""
        from apps.moderation_app.cache import get_whitelisted_words

        return get_whitelisted_words()

    def _contains_long_profanity(self, normalized: str) -> bool:
        """Check for substring matches of profane words >= 4 chars."""
        for word in self._long_bad:
            if word in normalized:
                return True
        return False

    def _find_long_profanity(
        self, normalized: str, word_set: Optional[set] = None
    ) -> Optional[str]:
        """Find first substring match of profane words >= 4 chars."""
        for word in word_set if word_set is not None else self._long_bad:
            if word in normalized:
                return word
        return None

    def _contains_short_profanity(self, normalized: str) -> bool:
        """Check for start/end matches of 3-char profane words."""
        for word in self._short_bad:
            if normalized.startswith(word) or normalized.endswith(word):
                return True
        return False

    def _find_short_profanity(
        self, normalized: str, word_set: Optional[set] = None
    ) -> Optional[tuple]:
        """Find first start/end match of 3-char profane words. Returns (word, position) or None."""
        for word in word_set if word_set is not None else self._short_bad:
            if normalized.startswith(word):
                return (word, "start")
            if normalized.endswith(word):
                return (word, "end")
        return None

    def _contains_fuzzy_profanity(self, normalized: str, threshold: int = 88) -> bool:
        """Check for fuzzy matches using sliding window."""
        for word in self._long_bad:
            window_size = len(word)
            for i in range(len(normalized) - window_size + 1):
                window = normalized[i : i + window_size]
                if fuzz.ratio(window, word) >= threshold:
                    return True
        return False

    def _find_fuzzy_profanity(
        self, normalized: str, threshold: int = 88, word_set: Optional[set] = None
    ) -> Optional[dict]:
        """Find first fuzzy match. Returns details dict or None."""
        for word in word_set if word_set is not None else self._long_bad:
            window_size = len(word)
            for i in range(len(normalized) - window_size + 1):
                window = normalized[i : i + window_size]
                score = fuzz.ratio(window, word)
                if score >= threshold:
                    return {
                        "matched_word": word,
                        "matched_window": window,
                        "fuzzy_score": round(score, 1),
                        "threshold": threshold,
                    }
        return None

    def _normalize_word(self, word: str) -> str:
        """Normalize a single word for profanity detection (reuses leet-speak map)."""
        word = unicodedata.normalize("NFKD", word)
        word = word.encode("ascii", "ignore").decode("ascii")
        word = word.lower()
        word = word.translate(self._leet_map)
        word = re.sub(r"[^a-z]", "", word)
        return word

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for ML analysis."""
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def check_text(self, text: str) -> ProfanityCheckResult:
        """
        Check if longer-form text contains profanity, returning detailed result.

        Uses ML-based sentence-level detection combined with word-level
        exact matching using leet-speak normalization.
        """
        if not text or not text.strip():
            return ProfanityCheckResult(is_profane=False)

        # ML check: sentence-level probability
        threshold = 0.80
        sentences = self._split_sentences(text)
        if sentences:
            probabilities = predict_prob(sentences)
            for i, p in enumerate(probabilities):
                if p >= threshold:
                    return ProfanityCheckResult(
                        is_profane=True,
                        detection_method="ML",
                        detection_details={
                            "sentences": sentences,
                            "probabilities": [
                                round(float(prob), 4) for prob in probabilities
                            ],
                            "threshold": threshold,
                            "flagged_sentence": sentences[i],
                            "flagged_sentence_index": i,
                            "flagged_probability": round(float(p), 4),
                        },
                    )

        # Word-level exact match with leet-speak normalization
        custom_banned = self._get_custom_banned_words()
        whitelist = self._get_whitelisted_words()
        all_bad_words = self._bad_words | custom_banned

        words = re.split(r"\s+", text.strip())
        for word in words:
            normalized = self._normalize_word(word)
            if (
                normalized
                and normalized in all_bad_words
                and normalized not in whitelist
            ):
                return ProfanityCheckResult(
                    is_profane=True,
                    detection_method="WORD_MATCH",
                    detection_details={
                        "matched_word": normalized,
                        "original_word": word,
                        "normalized_text": " ".join(
                            self._normalize_word(w)
                            for w in words
                            if self._normalize_word(w)
                        ),
                    },
                )

        return ProfanityCheckResult(is_profane=False)

    def check_username(self, username: str) -> ProfanityCheckResult:
        """
        Check if a username contains profanity, returning detailed result.

        Uses normalization (leet-speak, unicode), substring matching,
        start/end matching for short words, and fuzzy matching.
        """
        normalized = self._normalize_username(username)

        if not normalized:
            return ProfanityCheckResult(is_profane=False)

        custom_banned = self._get_custom_banned_words()
        whitelist = self._get_whitelisted_words()
        all_long = self._long_bad | {w for w in custom_banned if len(w) >= 4}
        all_short = self._short_bad | {w for w in custom_banned if len(w) == 3}

        # Substring match (long words)
        matched = self._find_long_profanity(normalized, word_set=all_long)
        if matched and matched not in whitelist:
            return ProfanityCheckResult(
                is_profane=True,
                detection_method="SUBSTRING",
                detection_details={
                    "matched_word": matched,
                    "normalized_text": normalized,
                },
            )

        # Short word start/end match
        short_match = self._find_short_profanity(normalized, word_set=all_short)
        if short_match and short_match[0] not in whitelist:
            return ProfanityCheckResult(
                is_profane=True,
                detection_method="SHORT_MATCH",
                detection_details={
                    "matched_word": short_match[0],
                    "match_position": short_match[1],
                    "normalized_text": normalized,
                },
            )

        # Fuzzy match
        fuzzy_match = self._find_fuzzy_profanity(normalized, word_set=all_long)
        if fuzzy_match and fuzzy_match["matched_word"] not in whitelist:
            return ProfanityCheckResult(
                is_profane=True,
                detection_method="FUZZY",
                detection_details={**fuzzy_match, "normalized_text": normalized},
            )

        return ProfanityCheckResult(is_profane=False)

    def is_profane_text(self, text: str) -> bool:
        """
        Check if longer-form text (captions, about text) contains profanity.

        Uses ML-based sentence-level detection (alt-profanity-check) combined
        with word-level exact matching using leet-speak normalization.
        """
        return self.check_text(text).is_profane

    def is_profane_username(self, username: str) -> bool:
        """
        Check if a username contains profanity.

        Uses normalization (leet-speak, unicode), substring matching,
        start/end matching for short words, and fuzzy matching.
        """
        return self.check_username(username).is_profane


_profanity_service = None


def get_profanity_service() -> ProfanityService:
    """Get a singleton instance of the profanity service."""
    global _profanity_service
    if _profanity_service is None:
        _profanity_service = ProfanityService()
    return _profanity_service


def check_and_log_text(text, content_type, profile_id=None):
    """Check text for profanity and log asynchronously if detected. Returns bool."""
    result = get_profanity_service().check_text(text)
    if result.is_profane:
        from apps.moderation_app.tasks import log_profanity_detection_task

        log_profanity_detection_task.delay(
            original_text=text,
            content_type=content_type,
            detection_method=result.detection_method,
            detection_details=result.detection_details,
            profile_id=profile_id,
        )
    return result.is_profane


def check_and_log_username(text, content_type, profile_id=None):
    """Check short text for profanity and log asynchronously if detected. Returns bool."""
    result = get_profanity_service().check_username(text)
    if result.is_profane:
        from apps.moderation_app.tasks import log_profanity_detection_task

        log_profanity_detection_task.delay(
            original_text=text,
            content_type=content_type,
            detection_method=result.detection_method,
            detection_details=result.detection_details,
            profile_id=profile_id,
        )
    return result.is_profane
