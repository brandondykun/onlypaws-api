"""
Tests for the explore cursor pagination class.
"""

from unittest import mock

from django.test import RequestFactory, TestCase
from rest_framework.exceptions import NotFound

from apps.recommendations_app.batch import PAGE_SIZE
from apps.recommendations_app.pagination import (
    CURSOR_QUERY_PARAM,
    ExploreCursorPagination,
    _decode_cursor,
    _encode_cursor,
)


class CursorEncodingTests(TestCase):

    def test_round_trip(self):
        for batch_id, offset in [(0, 0), (3, 24), (7, 96), (100, 288)]:
            encoded = _encode_cursor(batch_id, offset)
            self.assertEqual(_decode_cursor(encoded), (batch_id, offset))

    def test_garbage_raises_notfound(self):
        for value in ["", "not-base64-!!", "ZZZZZ", "eyJiIjotMSwib"]:
            with self.assertRaises(NotFound):
                _decode_cursor(value)

    def test_negative_components_rejected(self):
        # Manually craft a payload with a negative offset and confirm rejection.
        import base64
        import json

        bad = (
            base64.urlsafe_b64encode(json.dumps({"b": 1, "o": -1}).encode())
            .rstrip(b"=")
            .decode()
        )
        with self.assertRaises(NotFound):
            _decode_cursor(bad)


class _StubBatch:
    """Drop-in replacement for batch.get_or_create_batch and record_seen_post_ids."""

    def __init__(self, batches):
        # batches: dict[batch_id, list[post_id]]
        self.batches = batches
        self.recorded = []
        self.requests = []

    def get_or_create_batch(self, profile, batch_id, refresh=False):
        self.requests.append((batch_id, refresh))
        return list(self.batches.get(batch_id, [])), "long+short"

    def record_seen_post_ids(self, profile, post_ids):
        self.recorded.append(
            (profile.id if hasattr(profile, "id") else None, list(post_ids))
        )


class _FakeProfile:
    def __init__(self, pk):
        self.id = pk
        self.pk = pk


class PaginateForProfileTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.profile = _FakeProfile(pk=1)

    def _request(self, cursor=None):
        path = "/api/v1/post/explore/"
        params = f"?{CURSOR_QUERY_PARAM}={cursor}" if cursor else ""
        # DRF wraps Django requests in its own Request; the pagination class only
        # needs query_params, path, build_absolute_uri.
        return self.factory.get(path + params)

    def _patch_batch(self, stub: _StubBatch):
        return mock.patch.multiple(
            "apps.recommendations_app.pagination",
            get_or_create_batch=stub.get_or_create_batch,
            record_seen_post_ids=stub.record_seen_post_ids,
        )

    def test_first_page_returns_first_slice_and_advances_offset(self):
        full_batch = list(range(1, 31))  # 30 IDs
        stub = _StubBatch({0: full_batch})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            req = self._request()
            # Wrap request so query_params is dict-like — use the actual DRF helper.
            from rest_framework.request import Request

            ids = paginator.paginate_for_profile(self.profile, Request(req))

        self.assertEqual(ids, full_batch[:PAGE_SIZE])
        self.assertIsNotNone(paginator._next_cursor)
        self.assertEqual(stub.requests, [(0, True)])
        # Next cursor should still be inside batch 0, advanced by PAGE_SIZE.
        self.assertEqual(_decode_cursor(paginator._next_cursor), (0, PAGE_SIZE))

    def test_cursor_request_is_not_treated_as_refresh(self):
        full_batch = list(range(1, 60))
        stub = _StubBatch({0: full_batch})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            from rest_framework.request import Request

            cursor = _encode_cursor(0, PAGE_SIZE)
            ids = paginator.paginate_for_profile(
                self.profile,
                Request(self._request(cursor)),
            )

        self.assertEqual(ids, full_batch[PAGE_SIZE : PAGE_SIZE * 2])
        self.assertEqual(stub.requests, [(0, False)])

    def test_batch_boundary_advances_to_next_batch(self):
        # Batch 0 has exactly PAGE_SIZE items: page 1 should consume them all
        # and the next cursor should jump to (1, 0).
        stub = _StubBatch({0: list(range(1, PAGE_SIZE + 1))})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            from rest_framework.request import Request

            ids = paginator.paginate_for_profile(self.profile, Request(self._request()))

        self.assertEqual(len(ids), PAGE_SIZE)
        self.assertEqual(_decode_cursor(paginator._next_cursor), (1, 0))

    def test_empty_batch_terminates_feed(self):
        stub = _StubBatch({0: []})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            from rest_framework.request import Request

            ids = paginator.paginate_for_profile(self.profile, Request(self._request()))

        self.assertEqual(ids, [])
        self.assertIsNone(paginator._next_cursor)

    def test_self_heals_when_cached_batch_evicted_mid_scroll(self):
        # batch 0 is empty (Redis lost it), but batch 1 has data.
        # If the request asks for offset=PAGE_SIZE within batch 0, the
        # paginator should jump forward to batch 1 transparently.
        stub = _StubBatch({0: [], 1: list(range(100, 130))})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            from rest_framework.request import Request

            cursor = _encode_cursor(0, PAGE_SIZE)
            ids = paginator.paginate_for_profile(
                self.profile, Request(self._request(cursor))
            )

        self.assertEqual(ids, list(range(100, 130))[:PAGE_SIZE])

    def test_records_seen_post_ids_for_returned_page(self):
        full_batch = list(range(1, 31))
        stub = _StubBatch({0: full_batch})

        with self._patch_batch(stub):
            paginator = ExploreCursorPagination()
            from rest_framework.request import Request

            paginator.paginate_for_profile(self.profile, Request(self._request()))

        self.assertEqual(len(stub.recorded), 1)
        _, recorded_ids = stub.recorded[0]
        self.assertEqual(recorded_ids, full_batch[:PAGE_SIZE])
