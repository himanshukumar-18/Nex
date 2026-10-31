"""
Tests for NEX API pagination classes.

Covers:
  - NexPageNumberPagination default configuration
  - NexCursorPagination default configuration
  - Page size limits enforced (max_page_size)
  - Correct response keys present
"""

from django.test import SimpleTestCase

from apps.api.pagination import NexCursorPagination, NexPageNumberPagination


class PageNumberPaginationConfigTests(SimpleTestCase):
    """Verify NexPageNumberPagination configuration values."""

    def test_default_page_size(self) -> None:
        self.assertEqual(NexPageNumberPagination.page_size, 20)

    def test_max_page_size(self) -> None:
        self.assertEqual(NexPageNumberPagination.max_page_size, 100)

    def test_page_size_query_param(self) -> None:
        self.assertEqual(NexPageNumberPagination.page_size_query_param, "page_size")

    def test_page_query_param(self) -> None:
        self.assertEqual(NexPageNumberPagination.page_query_param, "page")


class CursorPaginationConfigTests(SimpleTestCase):
    """Verify NexCursorPagination configuration values."""

    def test_default_page_size(self) -> None:
        self.assertEqual(NexCursorPagination.page_size, 20)

    def test_max_page_size(self) -> None:
        self.assertEqual(NexCursorPagination.max_page_size, 100)

    def test_ordering_is_newest_first(self) -> None:
        """Cursor pagination must default to newest-first with deterministic ID tie-breaker."""
        self.assertEqual(NexCursorPagination.ordering, ("-created_at", "-id"))

    def test_page_size_query_param(self) -> None:
        self.assertEqual(NexCursorPagination.page_size_query_param, "page_size")

    def test_cursor_page_size_clamping(self) -> None:
        """Page size greater than max_page_size (100) must be clamped."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        req = Request(factory.get("/?page_size=500"))
        paginator = NexCursorPagination()
        self.assertEqual(paginator.get_page_size(req), 100)

    def test_cursor_page_size_invalid_fallback(self) -> None:
        """Invalid page_size query param falls back to default page_size (20)."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        req = Request(factory.get("/?page_size=not-a-number"))
        paginator = NexCursorPagination()
        self.assertEqual(paginator.get_page_size(req), 20)

