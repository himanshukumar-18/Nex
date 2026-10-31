"""
Tests for the NEX correlation ID middleware.

Covers:
  - Correlation ID is assigned to every request
  - Valid incoming X-Correlation-Id is preserved
  - Invalid/malformed X-Correlation-Id is replaced with a fresh UUID4
  - Correlation ID is returned in response headers
  - Correlation IDs are valid UUID4 strings
"""

import uuid
from unittest.mock import MagicMock

from django.test import RequestFactory, SimpleTestCase

from apps.api.middleware import (
    CORRELATION_ID_HEADER,
    CORRELATION_ID_META_KEY,
    CorrelationIdMiddleware,
    _is_valid_uuid4,
)


def _make_middleware(response: object = None) -> CorrelationIdMiddleware:
    """Create a middleware instance with a mock response."""
    mock_response = response or MagicMock()
    mock_response.__setitem__ = MagicMock()
    mock_response.__getitem__ = MagicMock(return_value="")
    get_response = MagicMock(return_value=mock_response)
    return CorrelationIdMiddleware(get_response)


class CorrelationIdMiddlewareTests(SimpleTestCase):
    """Verify correlation ID assignment, validation, and response propagation."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def _make_response_with_middleware(
        self,
        incoming_id: str | None = None,
    ) -> tuple[object, object]:
        """Helper: run middleware against a request and return (request, response)."""
        request = self.factory.get("/api/v1/test/")
        if incoming_id is not None:
            request.META[CORRELATION_ID_META_KEY] = incoming_id

        captured_request: list = []

        def get_response(req: object) -> MagicMock:
            captured_request.append(req)
            mock_resp = MagicMock()
            mock_resp.__setitem__ = MagicMock()
            return mock_resp

        middleware = CorrelationIdMiddleware(get_response)
        response = middleware(request)
        return captured_request[0], response

    def test_correlation_id_is_assigned_to_request(self) -> None:
        """Every request must have a correlation_id attribute after middleware."""
        req, _ = self._make_response_with_middleware()
        self.assertTrue(hasattr(req, "correlation_id"))
        self.assertTrue(_is_valid_uuid4(req.correlation_id))

    def test_valid_incoming_id_is_preserved(self) -> None:
        """A valid UUID4 header is reused without modification."""
        valid_id = str(uuid.uuid4())
        req, _ = self._make_response_with_middleware(incoming_id=valid_id)
        self.assertEqual(req.correlation_id, valid_id.lower())

    def test_invalid_incoming_id_is_replaced(self) -> None:
        """A malformed X-Correlation-Id must be replaced with a fresh UUID4."""
        req, _ = self._make_response_with_middleware(incoming_id="not-a-uuid")
        self.assertNotEqual(req.correlation_id, "not-a-uuid")
        self.assertTrue(_is_valid_uuid4(req.correlation_id))

    def test_empty_incoming_id_generates_new_id(self) -> None:
        """An empty X-Correlation-Id header must generate a new ID."""
        req, _ = self._make_response_with_middleware(incoming_id="")
        self.assertTrue(_is_valid_uuid4(req.correlation_id))

    def test_correlation_id_set_on_response_header(self) -> None:
        """The correlation ID must be set in the response X-Correlation-Id header."""
        request = self.factory.get("/")
        mock_response = MagicMock()
        header_values: dict = {}
        mock_response.__setitem__ = lambda self_inner, k, v: header_values.__setitem__(k, v)

        middleware = CorrelationIdMiddleware(lambda req: mock_response)
        middleware(request)

        self.assertIn(CORRELATION_ID_HEADER, header_values)
        self.assertTrue(_is_valid_uuid4(header_values[CORRELATION_ID_HEADER]))

    def test_each_request_gets_unique_id_without_header(self) -> None:
        """Without an incoming header, each request receives a distinct UUID4."""
        req1, _ = self._make_response_with_middleware()
        req2, _ = self._make_response_with_middleware()
        self.assertNotEqual(req1.correlation_id, req2.correlation_id)

    def test_uuid1_rejected_and_replaced(self) -> None:
        """UUID1 is structurally valid but version != 4; must be rejected."""
        uuid1_value = str(uuid.uuid1())
        req, _ = self._make_response_with_middleware(incoming_id=uuid1_value)
        self.assertNotEqual(req.correlation_id, uuid1_value.lower())
        self.assertTrue(_is_valid_uuid4(req.correlation_id))


class IsValidUuid4Tests(SimpleTestCase):
    """Unit tests for the UUID4 validation helper."""

    def test_valid_uuid4_accepted(self) -> None:
        self.assertTrue(_is_valid_uuid4(str(uuid.uuid4())))

    def test_uuid1_rejected(self) -> None:
        self.assertFalse(_is_valid_uuid4(str(uuid.uuid1())))

    def test_random_string_rejected(self) -> None:
        self.assertFalse(_is_valid_uuid4("not-a-uuid-at-all"))

    def test_empty_string_rejected(self) -> None:
        self.assertFalse(_is_valid_uuid4(""))

    def test_uppercase_uuid4_accepted(self) -> None:
        """Uppercase UUID4 should be valid (case-insensitive)."""
        upper = str(uuid.uuid4()).upper()
        self.assertTrue(_is_valid_uuid4(upper))

    def test_oversized_string_rejected_by_length_guard(self) -> None:
        """String longer than 36 characters must be rejected immediately."""
        oversized = "a" * 1000
        self.assertFalse(_is_valid_uuid4(oversized))

    def test_undersized_string_rejected_by_length_guard(self) -> None:
        """String shorter than 36 characters must be rejected immediately."""
        undersized = str(uuid.uuid4())[:30]
        self.assertFalse(_is_valid_uuid4(undersized))


class CorrelationIdLoggingContextTests(SimpleTestCase):
    """Verify contextvars integration with structured logging."""

    def test_log_filter_picks_up_contextvar_during_request(self) -> None:
        """CorrelationIdFilter automatically injects request correlation ID without explicit extra."""
        import logging
        from apps.api.middleware import CorrelationIdFilter, CorrelationIdMiddleware

        factory = RequestFactory()
        request = factory.get("/api/v1/test/")

        captured_records: list[logging.LogRecord] = []
        filter_instance = CorrelationIdFilter()

        def view(req: object) -> MagicMock:
            # Emulate an internal service or view logging without extra
            record = logging.LogRecord(
                name="apps.test",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Operation executed",
                args=(),
                exc_info=None,
            )
            filter_instance.filter(record)
            captured_records.append(record)
            mock_resp = MagicMock()
            mock_resp.__setitem__ = MagicMock()
            return mock_resp

        middleware = CorrelationIdMiddleware(view)
        middleware(request)

        self.assertEqual(len(captured_records), 1)
        # Log record must have the same correlation_id as the request
        self.assertEqual(captured_records[0].correlation_id, request.correlation_id)
        self.assertNotEqual(captured_records[0].correlation_id, "no-request")


