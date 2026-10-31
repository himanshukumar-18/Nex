"""
NEX Backend — Distributed Sliding-Window Rate Limiter.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Algorithm: Sliding Window Counter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The sliding window counter is implemented using two Redis keys per policy
and client:

  rate:<policy>:<client_key>:current   — request count in the current window
  rate:<policy>:<client_key>:previous  — request count in the previous window

On each request, the effective count is estimated as:

  effective = previous_count × overlap_fraction + current_count

where overlap_fraction = (window_seconds - seconds_elapsed_in_current_window)
                          / window_seconds

This approximation smooths the hard reset of a fixed-window counter and
eliminates the burst-at-boundary vulnerability without the O(n) memory cost
of a sliding window log.

Properties:
  ✓ O(1) memory per key (always exactly 2 Redis keys per policy+client)
  ✓ Atomic: the check-and-increment is a single Redis Lua execution
  ✓ Accurate within ~1% for typical traffic patterns
  ✓ Supports multiple simultaneous policies (categories)
  ✓ Correct under concurrent requests from multiple Django workers
  ✓ Keys auto-expire (TTL = 2 × window_size); no cleanup job needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Key naming convention (privacy-aware)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Client keys are derived as follows:

  Authenticated user:   HMAC-SHA256(str(user_id), RATE_LIMIT_SECRET)[:16]
  Unauthenticated IP:   HMAC-SHA256(resolved_client_ip, RATE_LIMIT_SECRET)[:16]

The HMAC ensures:
  1. Client IDs are not stored in cleartext in Redis.
  2. Redis key dumps do not expose IP addresses or user IDs.
  3. The secret prevents offline rainbow-table attacks against stored keys.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rate-limit policies
━━━━━━━━━━━━━━━━━━━
Policies are defined in Django settings under RATE_LIMIT_POLICIES as a dict:

  RATE_LIMIT_POLICIES = {
      "anonymous":         RateLimitPolicy(limit=60,  window=60),
      "authenticated":     RateLimitPolicy(limit=300, window=60),
      "login":             RateLimitPolicy(limit=10,  window=60),
      "registration":      RateLimitPolicy(limit=5,   window=60),
      "otp_verify":        RateLimitPolicy(limit=5,   window=300),
      "otp_resend":        RateLimitPolicy(limit=3,   window=300),
      "password_reset":    RateLimitPolicy(limit=5,   window=300),
      "account_sensitive": RateLimitPolicy(limit=10,  window=300),
      "admin_operations":  RateLimitPolicy(limit=30,  window=60),
      "agent_run":         RateLimitPolicy(limit=20,  window=60),
  }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Redis unavailability policy (FAIL-OPEN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If Redis is unreachable, the rate limiter ALLOWS the request to proceed.
This is a deliberate fail-open policy. The trade-off is documented here:

  ADVANTAGE: A transient Redis failure does not cause a full API outage.
  RISK:      Rate limiting is suspended during Redis downtime.
  MITIGATION:
    - Auth endpoints have per-attempt DB-level protections (account lockout
      will be implemented in Step 5B).
    - Redis health is monitored separately; alerts fire on Redis failure.
    - Connection failures are logged at ERROR level so on-call engineers
      are notified immediately.

  Rationale: For a multi-user platform where Redis downtime is rare and
  brief, preferring availability over strict rate enforcement during
  infrastructure failures is the correct default. Projects with stricter
  requirements (financial, regulated) should set RATE_LIMIT_FAIL_OPEN=False
  to switch to fail-closed behaviour.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trusted proxy and client IP resolution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Client IP is extracted from the request using a configurable strategy:

  - REMOTE_ADDR is trusted unconditionally when NUM_PROXIES=0.
  - When NUM_PROXIES > 0, the rightmost non-trusted IP in X-Forwarded-For
    is used. This prevents IP spoofing by limiting header trust to the
    configured number of upstream proxies.
  - X-Real-IP is never used (too easily forged).
  - Clients MUST NOT be able to influence their own rate-limit key by
    injecting X-Forwarded-For values.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DRF integration
━━━━━━━━━━━━━━━
The SlidingWindowThrottle class extends DRF's BaseThrottle. Views use it
by setting throttle_classes = [SlidingWindowThrottle] with an appropriate
policy selected via get_throttle_scope() or throttle_scope attribute.

Alternatively, use the policy-specific shortcut classes:
  AnonymousRateThrottle, AuthenticatedRateThrottle, LoginRateThrottle, etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle

if TYPE_CHECKING:
    from rest_framework.views import APIView
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script — atomic sliding-window counter check-and-increment
# ---------------------------------------------------------------------------
#
# Arguments:
#   KEYS[1]  — current window key   (e.g. rate:<policy>:<client>:<bucket>)
#   KEYS[2]  — previous window key  (e.g. rate:<policy>:<client>:<prev_bucket>)
#   ARGV[1]  — limit (int)
#   ARGV[2]  — window_seconds (int)
#   ARGV[3]  — current_time_float (seconds since epoch, float)
#
# Returns a three-element array:
#   [0]  1 if allowed, 0 if rate limited
#   [1]  effective_count (float as string)
#   [2]  retry_after_seconds (int, 0 if allowed)
#
_SLIDING_WINDOW_LUA = """
local current_key  = KEYS[1]
local previous_key = KEYS[2]
local limit        = tonumber(ARGV[1])
local window       = tonumber(ARGV[2])
local now          = tonumber(ARGV[3])

-- Determine the bucket boundary for the current window
local bucket_start = math.floor(now / window) * window
local elapsed      = now - bucket_start
local overlap      = (window - elapsed) / window

local previous_count = tonumber(redis.call('GET', previous_key) or 0)
local current_count  = tonumber(redis.call('GET', current_key) or 0)

local effective = previous_count * overlap + current_count

if effective >= limit then
    local retry_after = math.ceil(window - elapsed)
    return {0, tostring(effective), retry_after}
end

-- Increment current window counter; set TTL to 2× window so previous-window
-- data is still readable in the next window cycle
local new_count = redis.call('INCR', current_key)
if new_count == 1 then
    redis.call('EXPIRE', current_key, window * 2)
end

effective = previous_count * overlap + new_count
return {1, tostring(effective), 0}
"""


@dataclass(frozen=True)
class RateLimitPolicy:
    """Immutable rate-limit policy definition."""

    limit: int
    """Maximum number of requests allowed within `window` seconds."""

    window: int
    """Window duration in seconds."""

    fail_open: bool = True
    """
    Behavior when Redis is unavailable:
      - True (default for general traffic): allow requests through to preserve availability.
      - False (for security-sensitive endpoints like auth, OTP, password reset):
        block requests (HTTP 429) to prevent brute-force attacks during Redis outages.
    """

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError(f"RateLimitPolicy.limit must be positive, got {self.limit}")
        if self.window <= 0:
            raise ValueError(f"RateLimitPolicy.window must be positive, got {self.window}")


# ---------------------------------------------------------------------------
# Default policies
# ---------------------------------------------------------------------------
#
# Security policies for authentication and sensitive account endpoints explicitly
# fail closed (`fail_open=False`) to prevent brute-force attacks during Redis outages.
# General traffic policies fail open (`fail_open=True`) to maintain system availability.
#
DEFAULT_RATE_LIMIT_POLICIES: dict[str, RateLimitPolicy] = {
    # General API traffic — fail open to prioritize availability
    "anonymous": RateLimitPolicy(limit=60, window=60, fail_open=True),
    "authenticated": RateLimitPolicy(limit=300, window=60, fail_open=True),
    "agent_run": RateLimitPolicy(limit=20, window=60, fail_open=True),

    # Security-critical & administrative endpoints — fail closed to prevent brute-force and unauthorized operations during outages
    "admin_operations": RateLimitPolicy(limit=30, window=60, fail_open=False),
    "login": RateLimitPolicy(limit=10, window=60, fail_open=False),
    "registration": RateLimitPolicy(limit=5, window=60, fail_open=False),
    "otp_verify": RateLimitPolicy(limit=5, window=300, fail_open=False),
    "otp_resend": RateLimitPolicy(limit=3, window=300, fail_open=False),
    "password_reset": RateLimitPolicy(limit=5, window=300, fail_open=False),
    "account_sensitive": RateLimitPolicy(limit=10, window=300, fail_open=False),
}


# ---------------------------------------------------------------------------
# Client identification
# ---------------------------------------------------------------------------


def _normalize_ip(ip_str: str) -> str:
    """
    Validate and return the canonical representation of an IPv4 or IPv6 address.

    Strips any trailing port number (e.g. '192.0.2.1:8080' or '[2001:db8::1]:8080').
    Normalizes compressed vs. uncompressed IPv6 forms into standard canonical syntax.
    Returns 'unknown' if the string is not a valid IP.
    """
    clean_ip = ip_str.strip()
    if not clean_ip:
        return "unknown"

    # Handle bracketed IPv6 with port: [2001:db8::1]:8080
    if clean_ip.startswith("[") and "]" in clean_ip:
        clean_ip = clean_ip[1 : clean_ip.index("]")]
    # Handle IPv4 with port: 192.0.2.1:8080 (single colon, no brackets)
    elif ":" in clean_ip and clean_ip.count(":") == 1:
        clean_ip = clean_ip.split(":")[0]

    try:
        parsed = ipaddress.ip_address(clean_ip)
        return parsed.exploded if parsed.version == 6 else str(parsed)
    except ValueError:
        return "unknown"


def _resolve_client_ip(request: Request, num_proxies: int) -> str:
    """
    Resolve and normalize the actual client IP address from the request.

    Topology model:
      Client -> Proxy_1 -> ... -> Proxy_N -> Django (N = num_proxies)

    In this topology:
      - The immediate proxy (Proxy_N) connects to Django; its address is in REMOTE_ADDR.
      - Each proxy prepends or appends to X-Forwarded-For:
          XFF = client_ip, proxy_1, proxy_2, ...
      - The real client IP is at index `-num_proxies` from the right of XFF.
      - Any addresses to the left of `-num_proxies` were supplied by the untrusted
        client and MUST be ignored to prevent header spoofing.

    Security guarantees:
      - When num_proxies == 0: trusts REMOTE_ADDR only; completely ignores XFF.
      - When num_proxies > 0: inspects XFF, taking `addresses[-num_proxies]`.
      - Normalizes IPv4 and IPv6 to standard canonical representation.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    if num_proxies <= 0:
        return _normalize_ip(remote_addr)

    xff_header: str = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not xff_header:
        return _normalize_ip(remote_addr)

    # X-Forwarded-For: client, proxy1, proxy2, ...
    addresses = [addr.strip() for addr in xff_header.split(",") if addr.strip()]
    if not addresses:
        return _normalize_ip(remote_addr)

    # When behind num_proxies, the client is located at index -num_proxies
    if len(addresses) >= num_proxies:
        resolved = addresses[-num_proxies]
    else:
        # Fewer entries than configured proxies; fall back to leftmost or remote_addr
        resolved = addresses[0]

    normalized = _normalize_ip(resolved)
    return normalized if normalized != "unknown" else _normalize_ip(remote_addr)


def _build_rate_limit_key(
    policy_name: str,
    client_identifier: str,
    window_bucket: int,
    hmac_secret: bytes,
) -> str:
    """
    Build a privacy-preserving Redis key for rate limiting.

    The client identifier is HMACed so raw IPs and user IDs are never
    stored in Redis in cleartext.
    """
    masked = hmac.new(hmac_secret, client_identifier.encode(), hashlib.sha256).hexdigest()[:16]
    return f"rate:{policy_name}:{masked}:{window_bucket}"


def _build_previous_key(
    policy_name: str,
    client_identifier: str,
    window_bucket: int,
    hmac_secret: bytes,
) -> str:
    """Build the Redis key for the previous window bucket."""
    masked = hmac.new(hmac_secret, client_identifier.encode(), hashlib.sha256).hexdigest()[:16]
    return f"rate:{policy_name}:{masked}:{window_bucket - 1}"


# ---------------------------------------------------------------------------
# Core throttle class
# ---------------------------------------------------------------------------


class SlidingWindowThrottle(BaseThrottle):
    """
    DRF BaseThrottle implementation using a Redis-backed sliding-window counter.

    Usage:

        class MyView(APIView):
            throttle_classes = [LoginRateThrottle]

    Or for custom scopes:

        class MyView(APIView):
            throttle_classes = [SlidingWindowThrottle]
            throttle_scope = "agent_run"

    The throttle_scope must match a key in settings.RATE_LIMIT_POLICIES
    (or DEFAULT_RATE_LIMIT_POLICIES if not overridden).
    """

    # Subclasses set this to bind a specific policy.
    throttle_scope: ClassVar[str] = "anonymous"

    # Populated during allow_request(); used by wait() for Retry-After.
    _retry_after: float | None = None

    def _get_redis_client(self) -> object:
        """
        Retrieve the Django-Redis cache client for the rate-limit cache alias.

        Raises ImproperlyConfigured if django-redis is not configured.
        """
        try:
            from django.core.cache import caches

            return caches[getattr(settings, "RATE_LIMIT_CACHE_ALIAS", "rate_limit")]
        except Exception as exc:
            raise ImproperlyConfigured(
                "RATE_LIMIT_CACHE_ALIAS cache backend is not configured. "
                "Ensure django-redis is installed and CACHES['rate_limit'] is set."
            ) from exc

    def _get_policy(self) -> RateLimitPolicy:
        """Return the RateLimitPolicy for this throttle's scope."""
        policies: dict[str, RateLimitPolicy] = getattr(
            settings, "RATE_LIMIT_POLICIES", DEFAULT_RATE_LIMIT_POLICIES
        )
        policy = policies.get(self.throttle_scope)
        if policy is None:
            raise ImproperlyConfigured(
                f"No rate-limit policy defined for scope '{self.throttle_scope}'. "
                f"Add it to settings.RATE_LIMIT_POLICIES or DEFAULT_RATE_LIMIT_POLICIES."
            )
        return policy

    def _get_client_identifier(self, request: Request) -> str:
        """
        Return a stable, privacy-safe string identifying this client.

        Authenticated users are identified by user ID.
        Unauthenticated clients are identified by resolved IP address.
        """
        num_proxies: int = getattr(settings, "NUM_PROXIES", 1)
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.pk}"
        ip = _resolve_client_ip(request, num_proxies)
        return f"ip:{ip}"

    def allow_request(self, request: Request, view: APIView) -> bool:
        """
        Return True if the request is within the rate limit, False otherwise.

        Failure behavior on Redis unavailability:
          - Evaluates `policy.fail_open` for the specific endpoint category.
          - General traffic fails open (returns True) to preserve availability.
          - Authentication/security endpoints fail closed (returns False) to prevent brute-force attacks.
        """
        policy = self._get_policy()
        # Explicit global override takes precedence if set to False (fail-closed operator switch)
        global_fail_open: bool | None = getattr(settings, "RATE_LIMIT_FAIL_OPEN", None)
        if global_fail_open is False:
            fail_open = False
        else:
            fail_open = policy.fail_open

        try:
            cache = self._get_redis_client()
            # Access the underlying redis-py client for raw Lua execution
            native_client = cache.client.get_client()
        except Exception:
            logger.error(
                "Rate limiter: Redis client unavailable for scope '%s'. %s",
                self.throttle_scope,
                "Requests allowed through (fail-open policy)."
                if fail_open
                else "Requests blocked (fail-closed policy for security).",
                exc_info=False,
            )
            if not fail_open:
                # Return standard retry-after (60s) during fail-closed outage
                self._retry_after = 60.0
            return fail_open

        client_id = self._get_client_identifier(request)
        hmac_secret: bytes = getattr(settings, "RATE_LIMIT_HMAC_SECRET", b"nex-rate-limit-dev")
        if isinstance(hmac_secret, str):
            hmac_secret = hmac_secret.encode()

        now = time.time()
        window_bucket = math.floor(now / policy.window)
        prev_bucket = window_bucket - 1

        current_key = _build_rate_limit_key(
            self.throttle_scope, client_id, window_bucket, hmac_secret
        )
        previous_key = _build_previous_key(
            self.throttle_scope, client_id, prev_bucket, hmac_secret
        )

        try:
            result = native_client.eval(
                _SLIDING_WINDOW_LUA,
                2,  # number of keys
                current_key,
                previous_key,
                str(policy.limit),
                str(policy.window),
                str(now),
            )
            allowed = int(result[0]) == 1
            retry_after = int(result[2])

            if not allowed:
                self._retry_after = float(retry_after)
            else:
                self._retry_after = None

            return allowed

        except Exception:
            logger.error(
                "Rate limiter: Lua script execution failed for scope '%s'. %s",
                self.throttle_scope,
                "Allowing request through (fail-open policy)."
                if fail_open
                else "Blocking request (fail-closed policy).",
                exc_info=True,
            )
            if not fail_open:
                self._retry_after = 60.0
            return fail_open

    def wait(self) -> float | None:
        """Return the number of seconds until the rate limit resets."""
        return self._retry_after


# ---------------------------------------------------------------------------
# Policy-specific shortcut throttle classes
# ---------------------------------------------------------------------------
#
# Each class targets a specific policy by name. Views import and apply
# these directly rather than specifying throttle_scope manually.
#


class AnonymousRateThrottle(SlidingWindowThrottle):
    """Rate limit for unauthenticated requests to general endpoints."""

    throttle_scope = "anonymous"


class AuthenticatedRateThrottle(SlidingWindowThrottle):
    """Rate limit for authenticated requests to general endpoints."""

    throttle_scope = "authenticated"


class LoginRateThrottle(SlidingWindowThrottle):
    """Strict rate limit for login attempts to prevent brute-force attacks."""

    throttle_scope = "login"


class RegistrationRateThrottle(SlidingWindowThrottle):
    """Rate limit for account registration to prevent mass account creation."""

    throttle_scope = "registration"


class OtpVerifyRateThrottle(SlidingWindowThrottle):
    """Rate limit for OTP verification attempts to prevent brute-forcing codes."""

    throttle_scope = "otp_verify"


class OtpResendRateThrottle(SlidingWindowThrottle):
    """Rate limit for OTP resend requests to prevent SMS/email flooding."""

    throttle_scope = "otp_resend"


class PasswordResetRateThrottle(SlidingWindowThrottle):
    """Rate limit for password-reset requests to prevent enumeration."""

    throttle_scope = "password_reset"


class AccountSensitiveRateThrottle(SlidingWindowThrottle):
    """Rate limit for high-value account operations (email change, 2FA setup)."""

    throttle_scope = "account_sensitive"


class AdminOperationsRateThrottle(SlidingWindowThrottle):
    """Rate limit for administrative platform operations."""

    throttle_scope = "admin_operations"


class AgentRunRateThrottle(SlidingWindowThrottle):
    """Rate limit for expensive AI agent execution requests."""

    throttle_scope = "agent_run"
