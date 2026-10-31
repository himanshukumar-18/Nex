"""
Tests for the NEX centralized exception handler.

Covers:
  - Validation error normalization
  - Authentication/permission error normalization
  - 404 normalization
  - Throttling response with Retry-After
  - Internal server error (generic safe message + no stack trace)
  - Stable error-code mapping
  - Response envelope structure
"""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.api.exceptions import nex_exception_handler


class ExceptionHandlerEnvelopeTests(SimpleTestCase):
    """Verify the response envelope structure and error codes."""

    def _make_context(self) -> dict:
        factory = RequestFactory()
        request = factory.get("/api/v1/test/")
        return {"request": request, "view": MagicMock()}

    def test_validation_error_returns_400_with_detail(self) -> None:
        exc = ValidationError({"email": ["This field is required."]})
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.data
        self.assertEqual(data["error"], "validation_error")
        self.assertIn("email", data["detail"])
        self.assertIsNotNone(data["message"])

    def test_not_found_returns_404(self) -> None:
        exc = NotFound()
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "not_found")
        self.assertIsNone(response.data["detail"])

    def test_permission_denied_returns_403(self) -> None:
        exc = PermissionDenied()
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "permission_denied")

    def test_not_authenticated_returns_401_generic_message(self) -> None:
        """Authentication failure must not reveal whether the user exists."""
        exc = NotAuthenticated()
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "authentication_required")
        # Message must not mention accounts, users, or passwords
        message: str = response.data["message"]
        for sensitive_word in ["account", "user", "password", "exist"]:
            self.assertNotIn(sensitive_word, message.lower())

    def test_authentication_failed_returns_401_generic_message(self) -> None:
        """AuthenticationFailed must use the same generic message as NotAuthenticated."""
        exc = AuthenticationFailed("Invalid token.")
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Must not echo back the internal "Invalid token." detail
        self.assertNotIn("Invalid token", response.data["message"])

    def test_throttled_returns_429_with_retry_after_header(self) -> None:
        exc = Throttled(wait=45)
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["error"], "rate_limit_exceeded")
        self.assertIn("45", response.data["message"])
        self.assertEqual(response["Retry-After"], "45")

    def test_throttled_without_wait_returns_429(self) -> None:
        exc = Throttled(wait=None)
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertNotIn("Retry-After", response)

    def test_django_http404_converted_to_not_found(self) -> None:
        from django.http import Http404

        exc = Http404()
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "not_found")

    def test_unhandled_exception_returns_500_safe_message(self) -> None:
        """Unhandled exceptions must return a safe generic 500; no stack trace."""
        exc = RuntimeError("Database credentials: password=s3cr3t")
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["error"], "internal_server_error")
        # Must not expose the internal error message
        response_text = json.dumps(response.data)
        self.assertNotIn("password", response_text)
        self.assertNotIn("s3cr3t", response_text)
        # Must include a correlation ID for log tracing
        self.assertIn("correlation_id", response.data)

    def test_unhandled_exception_adopts_request_correlation_id(self) -> None:
        """Unhandled 500 error adopts the correlation ID from request if present."""
        factory = RequestFactory()
        request = factory.get("/api/v1/test/")
        request.correlation_id = "test-req-correlation-id-1234"
        context = {"request": request, "view": MagicMock()}

        exc = RuntimeError("Unexpected boom")
        response = nex_exception_handler(exc, context)
        assert response is not None
        self.assertEqual(response.data.get("correlation_id"), "test-req-correlation-id-1234")

    def test_response_always_has_error_message_detail_keys(self) -> None:
        """Every error response must have exactly error, message, detail keys."""
        exc = NotFound()
        response = nex_exception_handler(exc, self._make_context())
        assert response is not None
        for key in ("error", "message", "detail"):
            self.assertIn(key, response.data)

