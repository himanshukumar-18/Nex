"""NEX CLI Domain Exceptions.

Provides structured, typed exceptions mapping directly to standardized exit codes
and error presentation envelopes.
"""

from typing import Any

from nex.core import exit_codes


class NexError(Exception):
    """Base exception for all NEX CLI errors."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = exit_codes.GENERAL_ERROR,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "GENERAL_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.detail = detail
        self.suggestion = suggestion
        self.code = code


class NexInvalidInputError(NexError):
    """Raised when user input, flags, or command arguments are invalid."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "INVALID_INPUT",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.INVALID_INPUT,
            detail=detail,
            suggestion=suggestion,
            code=code,
        )


class NexConfigError(NexError):
    """Raised when configuration loading, schema validation, or parsing fails."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "CONFIG_ERROR",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.CONFIG_ERROR,
            detail=detail,
            suggestion=suggestion,
            code=code,
        )


class NexAuthError(NexError):
    """Raised when authentication credentials are missing, expired, or invalid."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "AUTHENTICATION_REQUIRED",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.AUTH_ERROR,
            detail=detail,
            suggestion=suggestion
            or "Run 'nex config' or check your NEX_API_KEY environment variable.",
            code=code,
        )


class NexBackendUnavailableError(NexError):
    """Raised when the Django API gateway is unreachable, timed out, or down."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "BACKEND_UNAVAILABLE",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.BACKEND_UNAVAILABLE,
            detail=detail,
            suggestion=suggestion
            or "Verify that the NEX backend service is running and accessible.",
            code=code,
        )


class NexApprovalRequiredError(NexError):
    """Raised when an operation requires explicit approval that was not granted."""

    def __init__(
        self,
        message: str = "Operation was cancelled or rejected by user.",
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "APPROVAL_REQUIRED",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.APPROVAL_REQUIRED,
            detail=detail,
            suggestion=suggestion
            or "Review the proposed changes before granting approval.",
            code=code,
        )


class NexPolicyViolationError(NexError):
    """Raised when a security policy or boundary is violated (e.g., path traversal)."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "POLICY_VIOLATION",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.POLICY_VIOLATION,
            detail=detail,
            suggestion=suggestion
            or "Operations are restricted to approved repository boundaries.",
            code=code,
        )


class NexVerificationFailedError(NexError):
    """Raised when a verification step or test harness assertion fails."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "VERIFICATION_FAILED",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.VERIFICATION_FAILED,
            detail=detail,
            suggestion=suggestion or "Review failure logs and re-run verification.",
            code=code,
        )


class NexRepositoryError(NexError):
    """Raised when repository discovery, Git inspection, or path resolution fails."""

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        suggestion: str | None = None,
        code: str = "REPOSITORY_ERROR",
    ) -> None:
        super().__init__(
            message,
            exit_code=exit_codes.INVALID_INPUT,
            detail=detail,
            suggestion=suggestion
            or "Ensure you are inside a valid Git repository or specify --path.",
            code=code,
        )
