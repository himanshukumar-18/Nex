"""
NEX Backend — Agent Runtime Internal Client Unit Tests.

Validates Step 6F requirements:
  - Authentication headers (X-Internal-Service-Key).
  - Correlation-ID header propagation.
  - Safe error mapping (Timeouts, Downstream Outages, Auth Failures, Protocol Errors).
  - Schema serialization and response contract parsing.
  - Safe retry behavior (idempotent GET retries; non-idempotent POST does not).
  - SSRF protection and path sanitization.
"""

from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
import httpx

from apps.api.middleware import correlation_id_ctx
from apps.api.runtime_client import (
    AgentRuntimeAuthenticationError,
    AgentRuntimeClient,
    AgentRuntimeMalformedResponseError,
    AgentRuntimeResponseError,
    AgentRuntimeTimeoutError,
    AgentRuntimeUnavailableError,
)
from apps.api.runtime_contracts import (
    AgentTaskResponseContract,
    ServicePingResponseContract,
)


class AgentRuntimeClientTests(SimpleTestCase):
    """Test suite for Django's AgentRuntimeClient."""

    def setUp(self):
        self.secret = "test-sec-key-123456789012345678901234567890"
        self.client = AgentRuntimeClient(
            base_url="http://agent-runtime:8001",
            secret_key=self.secret,
            connect_timeout=2.0,
            read_timeout=5.0,
        )

    def tearDown(self):
        self.client.close()

    def test_ssrf_path_sanitization_rejections(self):
        """Verify that illegal paths, absolute URLs, and path traversal are rejected."""
        with self.assertRaises(ValueError) as ctx:
            self.client.get("api/v1/ping")  # Missing leading slash
        self.assertIn("must start with '/'", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self.client.get("http://evil.com/steal")  # SSRF attempt
        self.assertIn("Illegal or SSRF-prone", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self.client.get("//evil.com/path")
        self.assertIn("Illegal or SSRF-prone", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self.client.get("/api/v1/../../etc/passwd")  # Path traversal
        self.assertIn("Illegal or SSRF-prone", str(ctx.exception))

    @patch("httpx.Client.request")
    def test_correlation_id_propagated_in_headers(self, mock_request):
        """Verify that the active correlation ID is attached to outgoing request headers."""
        token = correlation_id_ctx.set("trace-cid-999")
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b'{"status": "ok"}'
            mock_resp.json.return_value = {"status": "ok"}
            mock_request.return_value = mock_resp

            self.client.get("/api/v1/status")

            mock_request.assert_called_once()
            _, kwargs = mock_request.call_args
            headers = kwargs.get("headers", {})
            self.assertEqual(headers.get("X-Correlation-Id"), "trace-cid-999")
            self.assertEqual(headers.get("X-Internal-Service-Key"), self.secret)
        finally:
            correlation_id_ctx.reset(token)

    @patch("httpx.Client.request")
    def test_successful_ping_contract(self, mock_request):
        """Verify ping() dispatches contract and parses response into ServicePingResponseContract."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"status": "ok", "service": "nex-agent-runtime", "echo_message": "hello", "timestamp": "2026-10-31T12:00:00Z"}'
        mock_resp.json.return_value = {
            "status": "ok",
            "service": "nex-agent-runtime",
            "echo_message": "hello",
            "timestamp": "2026-10-31T12:00:00Z",
        }
        mock_request.return_value = mock_resp

        res = self.client.ping(message="hello")

        self.assertIsInstance(res, ServicePingResponseContract)
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.echo_message, "hello")
        self.assertEqual(res.service, "nex-agent-runtime")

    @patch("httpx.Client.request")
    def test_successful_verify_task_contract(self, mock_request):
        """Verify verify_task() parses response into AgentTaskResponseContract."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"task_id": "task-01", "status": "accepted", "result": {"acknowledged": true}}'
        mock_resp.json.return_value = {
            "task_id": "task-01",
            "status": "accepted",
            "result": {"acknowledged": True},
        }
        mock_request.return_value = mock_resp

        res = self.client.verify_task(task_id="task-01", action="analyze", parameters={"repo": "main"})

        self.assertIsInstance(res, AgentTaskResponseContract)
        self.assertEqual(res.task_id, "task-01")
        self.assertEqual(res.status, "accepted")
        self.assertTrue(res.result.get("acknowledged"))

    @patch("httpx.Client.request")
    def test_authentication_error_handling(self, mock_request):
        """Verify that 401 response raises AgentRuntimeAuthenticationError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.content = b'{"error": {"code": "UNAUTHORIZED", "message": "Invalid service credentials"}}'
        mock_resp.json.return_value = {"error": {"code": "UNAUTHORIZED", "message": "Invalid service credentials"}}
        mock_request.return_value = mock_resp

        with self.assertRaises(AgentRuntimeAuthenticationError) as ctx:
            self.client.get("/api/v1/status")
        self.assertIn("authentication failed", str(ctx.exception))

    @patch("httpx.Client.request")
    def test_service_unavailable_error_handling(self, mock_request):
        """Verify that network disconnect / ConnectError raises AgentRuntimeUnavailableError."""
        mock_request.side_effect = httpx.ConnectError("Connection refused by peer")

        with self.assertRaises(AgentRuntimeUnavailableError):
            self.client.post("/api/v1/ping", json_data={"message": "test"})

    @patch("httpx.Client.request")
    def test_timeout_error_handling(self, mock_request):
        """Verify that httpx ReadTimeout raises AgentRuntimeTimeoutError."""
        mock_request.side_effect = httpx.ReadTimeout("Socket read timed out")

        with self.assertRaises(AgentRuntimeTimeoutError):
            self.client.get("/api/v1/status")

    @patch("httpx.Client.request")
    def test_malformed_response_handling(self, mock_request):
        """Verify that non-JSON response raises AgentRuntimeMalformedResponseError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.content = b"<html>Bad Gateway</html>"
        mock_resp.text = "<html>Bad Gateway</html>"
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_resp

        with self.assertRaises(AgentRuntimeMalformedResponseError):
            self.client.get("/api/v1/status")

    @patch("httpx.Client.request")
    def test_runtime_response_error_normalization(self, mock_request):
        """Verify that non-2xx normalized NEX errors raise AgentRuntimeResponseError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.content = b'{"error": {"code": "VALIDATION_ERROR", "message": "Input failed", "detail": []}}'
        mock_resp.json.return_value = {
            "error": {"code": "VALIDATION_ERROR", "message": "Input failed", "detail": []}
        }
        mock_request.return_value = mock_resp

        with self.assertRaises(AgentRuntimeResponseError) as ctx:
            self.client.post("/api/v1/ping", json_data={})
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertEqual(ctx.exception.message, "Input failed")

    @patch("httpx.Client.request")
    def test_safe_retry_on_get_connection_failure(self, mock_request):
        """Verify that GET requests retry once on transient connection error, then succeed."""
        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.content = b'{"status": "ok"}'
        success_resp.json.return_value = {"status": "ok"}

        # Attempt 1 fails with ConnectError, Attempt 2 succeeds
        mock_request.side_effect = [httpx.ConnectError("Temporary blip"), success_resp]

        res = self.client.get("/api/v1/status")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(mock_request.call_count, 2)

    @patch("httpx.Client.request")
    def test_no_retry_on_post_connection_failure(self, mock_request):
        """Verify that POST requests do NOT retry automatically on connection failure."""
        mock_request.side_effect = httpx.ConnectError("Temporary blip")

        with self.assertRaises(AgentRuntimeUnavailableError):
            self.client.post("/api/v1/tasks/verify", json_data={"task_id": "01"})

        # Strictly called only once!
        self.assertEqual(mock_request.call_count, 1)

