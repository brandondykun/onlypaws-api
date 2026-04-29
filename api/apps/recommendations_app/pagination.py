"""
Cursor pagination for the personalised explore feed.

A cursor encodes (batch_id, offset_in_batch). Each batch holds up to BATCH_SIZE
post IDs in Redis; pagination just slices the cached list. When the offset
reaches the end of the current batch, the next cursor advances to the next
batch_id, which will be lazily generated on the following request.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Optional, Tuple

from rest_framework.exceptions import NotFound
from rest_framework.pagination import BasePagination
from rest_framework.response import Response

from .batch import (
    BATCH_SIZE,
    PAGE_SIZE,
    get_or_create_batch,
    record_seen_post_ids,
)

logger = logging.getLogger(__name__)

CURSOR_QUERY_PARAM = "cursor"


def _encode_cursor(batch_id: int, offset: int) -> str:
    payload = json.dumps({"b": batch_id, "o": offset}, separators=(",", ":")).encode(
        "utf-8"
    )
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> Tuple[int, int]:
    """Returns (batch_id, offset). Raises NotFound on garbage input."""
    try:
        padding = "=" * (-len(value) % 4)
        payload = base64.urlsafe_b64decode(value + padding)
        data = json.loads(payload.decode("utf-8"))
        batch_id = int(data["b"])
        offset = int(data["o"])
        if batch_id < 0 or offset < 0:
            raise ValueError("negative cursor component")
        return batch_id, offset
    except (
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        logger.warning(f"Invalid cursor: {value!r} ({exc})")
        raise NotFound("Invalid cursor.")


class ExploreCursorPagination(BasePagination):
    """
    DRF pagination class for the personalised explore feed.

    Diverges from typical DRF pagination in that it does NOT operate on the
    queryset passed via paginate_queryset. Instead the view calls
    `paginate_for_profile(profile, request)` which returns the post IDs for
    the current page; the view then constructs a real queryset for those IDs
    and serializes it.
    """

    page_size = PAGE_SIZE

    def __init__(self):
        self._next_cursor: Optional[str] = None
        self._source: Optional[str] = None
        self._request = None

    def paginate_for_profile(self, profile, request) -> list[int]:
        self._request = request
        cursor_value = request.query_params.get(CURSOR_QUERY_PARAM)
        if cursor_value:
            batch_id, offset = _decode_cursor(cursor_value)
            refresh = False
        else:
            batch_id, offset = 0, 0
            refresh = True

        batch_ids, source = get_or_create_batch(profile, batch_id, refresh=refresh)
        self._source = source

        # Self-heal: if the cached batch came back empty AND we asked for a
        # mid-batch slice, jump to the next batch immediately so the user's
        # scroll doesn't dead-end mid-feed because of a Redis eviction.
        if not batch_ids and offset > 0:
            batch_id += 1
            offset = 0
            batch_ids, source = get_or_create_batch(profile, batch_id)
            self._source = source

        if not batch_ids:
            self._next_cursor = None
            return []

        page = batch_ids[offset : offset + self.page_size]
        record_seen_post_ids(profile, page)

        if offset + self.page_size < len(batch_ids):
            self._next_cursor = _encode_cursor(batch_id, offset + self.page_size)
        else:
            # End of this batch; signal the next batch even though we haven't
            # generated it yet. The next request will lazily build it.
            self._next_cursor = _encode_cursor(batch_id + 1, 0)

        return page

    # ----- DRF protocol shims -----------------------------------------------
    # These satisfy the BasePagination interface even though the view drives
    # pagination explicitly via paginate_for_profile.

    def paginate_queryset(self, queryset, request, view=None):  # pragma: no cover
        raise NotImplementedError(
            "ExploreCursorPagination is driven via paginate_for_profile; "
            "the view should not call paginate_queryset."
        )

    def get_paginated_response(self, data) -> Response:
        next_url = None
        if self._next_cursor and self._request is not None:
            next_url = self._request.build_absolute_uri(
                self._request.path + f"?{CURSOR_QUERY_PARAM}={self._next_cursor}"
            )
        return Response(
            {
                "next": next_url,
                "previous": None,
                "results": data,
                "source": self._source,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "next": {"type": "string", "nullable": True, "format": "uri"},
                "previous": {"type": "string", "nullable": True},
                "results": schema,
                "source": {"type": "string", "nullable": True},
            },
        }
