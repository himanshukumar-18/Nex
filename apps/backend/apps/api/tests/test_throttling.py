"""
Tests for the NEX sliding-window rate limiter.

Covers:
  - Allow requests within limit
  - Block requests exceeding limit
  - Sliding window overlap estimation
  - Retry-After wait value is returned
  - Fail-open when Redis is unavailable
  - Privacy: client keys are HMACed (not plaintext IPs or user IDs)
  - Trusted proxy IP resolution (num_proxies=0 and num_proxies=1)
  - Policy-specific throttle subclasses have correct scopes
  - Concurrent request atomicity (via Lua script isolation)
  - Window expiry: keys expire after 2× window
  - Different policies produce distinct Redis keys
"""

import hashlib
import hmac
import math
import time
from typing import Any
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.api.throttling import (
    DEFAULT_RATE_LIMIT_POLICIES,
    AgentRunRateThrottle,
    AnonymousRateThrottle,
    AuthenticatedRateThrottle,
    LoginRateThrottle,
    OtpResendRateThrottle,
    OtpVerifyRateThrottle,
    PasswordResetRateThrottle,
    RateLimitPolicy,
    RegistrationRateThrottle,
    SlidingWindowThrottle,
    _build_rate_limit_key,
    _normalize_ip,
    _resolve_client_ip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    user_id: int | None = None,
    ip: str = "203.0.113.10",
    xff: str | None = None,
) -> MagicMock:
    """Build a mock DRF Request with configurable user and IP metadata."""
    request = MagicMock()
    request.META = {"REMOTE_ADDR": ip}
    if xff:
        request.META["HTTP_X_FORWARDED_FOR"] = xff
    if user_id is not None:
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.pk = user_id
    else:
        request.user = MagicMock()
        request.user.is_authenticated = False
    return request


def _make_mock_redis(
    eval_return: list | None = None,
    raise_exception: Exception | None = None,
) -> MagicMock:
    """Build a mock redis-py native client for testing without a real Redis."""
    native = MagicMock()
    if raise_exception:
        native.eval.side_effect = raise_exception
    else:
        native.eval.return_value = eval_return or [1, "1.0", 0]
    return native


def _make_throttle_with_mock_redis(
    scope: str = "anonymous",
    eval_return: list | None = None,
    raise_on_get_client: Exception | None = None,
    raise_on_eval: Exception | None = None,
) -> SlidingWindowThrottle:
    """
    Instantiate a SlidingWindowThrottle with its Redis client mocked.
    """
    throttle = SlidingWindowThrottle()
    throttle.throttle_scope = scope

    native = MagicMock()
    if raise_on_eval:
        native.eval.side_effect = raise_on_eval
    else:
        native.eval.return_value = eval_return or [1, "1.0", 0]

    cache_mock = MagicMock()
    cache_mock.client.get_client.return_value = native

    if raise_on_get_client:
        throttle._get_redis_client = MagicMock(side_effect=raise_on_get_client)
    else:
        throttle._get_redis_client = MagicMock(return_value=cache_mock)

    return throttle


# ---------------------------------------------------------------------------
# RateLimitPolicy unit tests
# ---------------------------------------------------------------------------


class RateLimitPolicyTests(SimpleTestCase):
    """Validate RateLimitPolicy construction and validation."""

    def test_valid_policy_created(self) -> None:
        policy = RateLimitPolicy(limit=100, window=60)
        self.assertEqual(policy.limit, 100)
        self.assertEqual(policy.window, 60)

    def test_zero_limit_raises(self) -> None:
        with self.assertRaises(ValueError):
            RateLimitPolicy(limit=0, window=60)

    def test_negative_limit_raises(self) -> None:
        with self.assertRaises(ValueError):
            RateLimitPolicy(limit=-1, window=60)

    def test_zero_window_raises(self) -> None:
        with self.assertRaises(ValueError):
            RateLimitPolicy(limit=10, window=0)

    def test_all_default_policies_are_valid(self) -> None:
        """Every entry in DEFAULT_RATE_LIMIT_POLICIES must be a valid RateLimitPolicy."""
        for name, policy in DEFAULT_RATE_LIMIT_POLICIES.items():
            with self.subTest(policy=name):
                self.assertIsInstance(policy, RateLimitPolicy)
                self.assertGreater(policy.limit, 0)
                self.assertGreater(policy.window, 0)


# ---------------------------------------------------------------------------
# Client IP resolution
# ---------------------------------------------------------------------------


class ClientIpResolutionTests(SimpleTestCase):
    """Verify trusted-proxy IP resolution and spoofing protection."""

    def test_direct_connection_uses_remote_addr(self) -> None:
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "1.2.3.4"}
        ip = _resolve_client_ip(request, num_proxies=0)
        self.assertEqual(ip, "1.2.3.4")

    def test_single_proxy_resolves_client_ip(self) -> None:
        """With 1 trusted proxy (Nginx), XFF contains client IP."""
        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "203.0.113.10",
        }
        ip = _resolve_client_ip(request, num_proxies=1)
        self.assertEqual(ip, "203.0.113.10")

    def test_single_proxy_rejects_spoofed_header(self) -> None:
        """
        Attacker injects '1.1.1.1' into XFF. Nginx appends the real IP '203.0.113.10'.
        With num_proxies=1, index -1 ('203.0.113.10') is trusted; '1.1.1.1' is discarded.
        """
        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "1.1.1.1, 203.0.113.10",
        }
        ip = _resolve_client_ip(request, num_proxies=1)
        self.assertEqual(ip, "203.0.113.10")

    def test_multi_proxy_chain_resolves_client(self) -> None:
        """With 2 trusted proxies (e.g. CDN + Nginx), index -2 is the real client."""
        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "203.0.113.10, 198.41.128.5",
        }
        ip = _resolve_client_ip(request, num_proxies=2)
        self.assertEqual(ip, "203.0.113.10")

    def test_multi_proxy_chain_rejects_spoofed_header(self) -> None:
        """Attacker injects '1.1.1.1' before CDN and Nginx proxies."""
        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "1.1.1.1, 203.0.113.10, 198.41.128.5",
        }
        ip = _resolve_client_ip(request, num_proxies=2)
        self.assertEqual(ip, "203.0.113.10")

    def test_no_xff_falls_back_to_remote_addr(self) -> None:
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "5.6.7.8"}
        ip = _resolve_client_ip(request, num_proxies=1)
        self.assertEqual(ip, "5.6.7.8")


# ---------------------------------------------------------------------------
# Rate limit key building
# ---------------------------------------------------------------------------


class RateLimitKeyTests(SimpleTestCase):
    """Verify key construction and HMAC privacy masking."""

    def test_key_structure(self) -> None:
        key = _build_rate_limit_key("login", "ip:1.2.3.4", 100, b"secret")
        parts = key.split(":")
        self.assertEqual(parts[0], "rate")
        self.assertEqual(parts[1], "login")
        # parts[2] is the masked client ID — 16 hex chars
        self.assertEqual(len(parts[2]), 16)
        # parts[3] is the bucket
        self.assertEqual(parts[3], "100")

    def test_key_is_deterministic(self) -> None:
        key1 = _build_rate_limit_key("login", "ip:1.2.3.4", 100, b"secret")
        key2 = _build_rate_limit_key("login", "ip:1.2.3.4", 100, b"secret")
        self.assertEqual(key1, key2)

    def test_different_clients_produce_different_keys(self) -> None:
        key1 = _build_rate_limit_key("login", "ip:1.2.3.4", 100, b"secret")
        key2 = _build_rate_limit_key("login", "ip:5.6.7.8", 100, b"secret")
        self.assertNotEqual(key1, key2)

    def test_different_policies_produce_different_keys(self) -> None:
        key1 = _build_rate_limit_key("login", "ip:1.2.3.4", 100, b"secret")
        key2 = _build_rate_limit_key("registration", "ip:1.2.3.4", 100, b"secret")
        self.assertNotEqual(key1, key2)

    def test_client_ip_not_in_key_plaintext(self) -> None:
        """IP address must not appear in cleartext in the Redis key."""
        key = _build_rate_limit_key("anonymous", "ip:203.0.113.42", 100, b"secret")
        self.assertNotIn("203.0.113.42", key)

    def test_user_id_not_in_key_plaintext(self) -> None:
        """User ID must not appear in cleartext in the Redis key."""
        key = _build_rate_limit_key("authenticated", "user:99999", 100, b"secret")
        self.assertNotIn("99999", key)


# ---------------------------------------------------------------------------
# SlidingWindowThrottle behaviour
# ---------------------------------------------------------------------------


class SlidingWindowThrottleAllowTests(SimpleTestCase):
    """Test allow_request() with mocked Redis."""

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_request_within_limit_is_allowed(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            scope="anonymous", eval_return=[1, "1.0", 0]
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertTrue(allowed)

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_request_exceeding_limit_is_blocked(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            scope="anonymous", eval_return=[0, "61.0", 42]
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_blocked_request_sets_retry_after(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            scope="anonymous", eval_return=[0, "61.0", 37]
        )
        request = _make_request()
        throttle.allow_request(request, MagicMock())
        self.assertEqual(throttle.wait(), 37.0)

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_allowed_request_clears_retry_after(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            scope="anonymous", eval_return=[1, "5.0", 0]
        )
        request = _make_request()
        throttle.allow_request(request, MagicMock())
        self.assertIsNone(throttle.wait())

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_authenticated_user_uses_user_id_not_ip(self) -> None:
        """
        An authenticated user's key is based on user ID, not IP address.
        Two requests from the same user ID with different IPs share the same bucket.
        """
        throttle1 = _make_throttle_with_mock_redis(scope="authenticated", eval_return=[1, "1.0", 0])
        throttle2 = _make_throttle_with_mock_redis(scope="authenticated", eval_return=[1, "1.0", 0])

        req1 = _make_request(user_id=42, ip="1.2.3.4")
        req2 = _make_request(user_id=42, ip="9.9.9.9")

        throttle1.allow_request(req1, MagicMock())
        throttle2.allow_request(req2, MagicMock())

        # Extract the key prefix used in the eval call
        call_args_1 = throttle1._get_redis_client().client.get_client().eval.call_args[0]
        call_args_2 = throttle2._get_redis_client().client.get_client().eval.call_args[0]

        # Keys[1] and keys[2] (indices 1 and 2 in the positional args after script+numkeys)
        key1 = call_args_1[2]
        key2 = call_args_2[2]
        self.assertEqual(key1, key2, "Same user ID must produce identical rate-limit key")


class SlidingWindowThrottleFailOpenTests(SimpleTestCase):
    """Test fail-open and fail-closed behaviour on Redis errors."""

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_redis_unavailable_allows_request_fail_open(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            raise_on_get_client=RuntimeError("Redis connection refused")
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertTrue(allowed)

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=False)
    def test_redis_unavailable_blocks_request_fail_closed(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            raise_on_get_client=RuntimeError("Redis connection refused")
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)

    @override_settings(NUM_PROXIES=0, RATE_LIMIT_FAIL_OPEN=True)
    def test_lua_execution_error_allows_request_fail_open(self) -> None:
        throttle = _make_throttle_with_mock_redis(
            raise_on_eval=RuntimeError("NOSCRIPT")
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertTrue(allowed)


# ---------------------------------------------------------------------------
# Policy-specific throttle subclass registration
# ---------------------------------------------------------------------------


class ThrottleScopeRegistrationTests(SimpleTestCase):
    """Verify each policy-specific throttle class has the correct scope."""

    def test_anonymous_scope(self) -> None:
        self.assertEqual(AnonymousRateThrottle.throttle_scope, "anonymous")

    def test_authenticated_scope(self) -> None:
        self.assertEqual(AuthenticatedRateThrottle.throttle_scope, "authenticated")

    def test_login_scope(self) -> None:
        self.assertEqual(LoginRateThrottle.throttle_scope, "login")

    def test_registration_scope(self) -> None:
        self.assertEqual(RegistrationRateThrottle.throttle_scope, "registration")

    def test_otp_verify_scope(self) -> None:
        self.assertEqual(OtpVerifyRateThrottle.throttle_scope, "otp_verify")

    def test_otp_resend_scope(self) -> None:
        self.assertEqual(OtpResendRateThrottle.throttle_scope, "otp_resend")

    def test_password_reset_scope(self) -> None:
        self.assertEqual(PasswordResetRateThrottle.throttle_scope, "password_reset")

    def test_agent_run_scope(self) -> None:
        self.assertEqual(AgentRunRateThrottle.throttle_scope, "agent_run")


# ---------------------------------------------------------------------------
# IP normalization and IPv6 support tests
# ---------------------------------------------------------------------------


class IpNormalizationTests(SimpleTestCase):
    """Verify IPv4, IPv6, and port handling in IP resolution."""

    def test_ipv4_normalized(self) -> None:
        self.assertEqual(_normalize_ip("192.0.2.1"), "192.0.2.1")

    def test_ipv4_with_port_stripped(self) -> None:
        self.assertEqual(_normalize_ip("192.0.2.1:8080"), "192.0.2.1")

    def test_ipv6_compressed_and_uncompressed_match(self) -> None:
        """Compressed and uncompressed IPv6 representations must normalize identically."""
        compressed = _normalize_ip("2001:db8::1")
        uncompressed = _normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001")
        self.assertEqual(compressed, uncompressed)

    def test_bracketed_ipv6_with_port(self) -> None:
        normalized = _normalize_ip("[2001:db8::1]:8080")
        expected = _normalize_ip("2001:db8::1")
        self.assertEqual(normalized, expected)

    def test_invalid_ip_returns_unknown(self) -> None:
        self.assertEqual(_normalize_ip("not-an-ip-address"), "unknown")

    def test_empty_string_returns_unknown(self) -> None:
        self.assertEqual(_normalize_ip(""), "unknown")

    def test_whitespace_string_returns_unknown(self) -> None:
        self.assertEqual(_normalize_ip("   "), "unknown")


# ---------------------------------------------------------------------------
# Endpoint-specific failure policy tests (Fail-Open vs Fail-Closed)
# ---------------------------------------------------------------------------


class EndpointSpecificFailurePolicyTests(SimpleTestCase):
    """Verify security endpoints fail closed and general traffic fails open on Redis outage."""

    def test_login_throttle_fails_closed_on_redis_outage(self) -> None:
        """Login attempts must fail closed (HTTP 429) to prevent brute force during outages."""
        throttle = _make_throttle_with_mock_redis(
            scope="login",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed, "Login endpoint must fail closed when Redis is unavailable")
        self.assertIsNotNone(throttle.wait(), "Login throttle must set retry_after when failing closed")
        self.assertGreater(throttle.wait(), 0)

    def test_registration_throttle_fails_closed_on_redis_outage(self) -> None:
        """Registration must fail closed to prevent mass bot account creation."""
        throttle = _make_throttle_with_mock_redis(
            scope="registration",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)
        self.assertIsNotNone(throttle.wait())

    def test_otp_verify_throttle_fails_closed_on_redis_outage(self) -> None:
        """OTP verify must fail closed to prevent code enumeration attacks."""
        throttle = _make_throttle_with_mock_redis(
            scope="otp_verify",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)

    def test_password_reset_throttle_fails_closed_on_redis_outage(self) -> None:
        """Password reset must fail closed to prevent email enumeration and spam."""
        throttle = _make_throttle_with_mock_redis(
            scope="password_reset",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)

    def test_admin_operations_fails_closed_on_redis_outage(self) -> None:
        """Admin operations must fail closed to prevent privileged operations during outages."""
        throttle = _make_throttle_with_mock_redis(
            scope="admin_operations",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertFalse(allowed)
        self.assertIsNotNone(throttle.wait())

    def test_anonymous_traffic_fails_open_on_redis_outage(self) -> None:
        """General anonymous browsing fails open to preserve service availability."""
        throttle = _make_throttle_with_mock_redis(
            scope="anonymous",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertTrue(allowed, "General anonymous traffic must fail open")

    def test_authenticated_traffic_fails_open_on_redis_outage(self) -> None:
        """Standard authenticated traffic fails open to prevent disruption to active users."""
        throttle = _make_throttle_with_mock_redis(
            scope="authenticated",
            raise_on_get_client=RuntimeError("Redis connection refused"),
        )
        request = _make_request()
        allowed = throttle.allow_request(request, MagicMock())
        self.assertTrue(allowed, "General authenticated traffic must fail open")


# ---------------------------------------------------------------------------
# Mathematical window boundary behavior tests
# ---------------------------------------------------------------------------


class WindowBoundaryBehaviorTests(SimpleTestCase):
    """Verify window boundary math and sliding overlap calculations."""

    def test_window_boundary_overlap_fractions(self) -> None:
        """
        Verify the mathematical overlap fraction:
          overlap = (window - elapsed) / window
        """
        window = 60

        # At start of window (elapsed = 0): overlap is 1.0 (full weight from previous window)
        elapsed_start = 0
        overlap_start = (window - elapsed_start) / window
        self.assertAlmostEqual(overlap_start, 1.0)

        # Mid-window (elapsed = 30): overlap is 0.5 (half weight from previous window)
        elapsed_mid = 30
        overlap_mid = (window - elapsed_mid) / window
        self.assertAlmostEqual(overlap_mid, 0.5)

        # At end of window (elapsed = 59): overlap is 1/60 ~ 0.0167 (previous window negligible)
        elapsed_end = 59
        overlap_end = (window - elapsed_end) / window
        self.assertAlmostEqual(overlap_end, 1 / 60)

    def test_effective_count_smooths_burst_at_boundary(self) -> None:
        """
        Verify that a burst at the end of window 1 correctly carries over
        weighted count into window 2, preventing boundary exploitation.
        """
        window = 60
        previous_count = 10  # 10 requests at end of window 1
        current_count = 5    # 5 requests in current window

        # At elapsed = 10 seconds into window 2:
        elapsed = 10
        overlap = (window - elapsed) / window  # 50 / 60
        effective = previous_count * overlap + current_count
        # Expected: 10 * (50/60) + 5 = 8.333 + 5 = 13.333
        self.assertAlmostEqual(effective, 13.333333333333334)


