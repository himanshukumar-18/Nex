"""Tests for exit codes and domain exceptions."""

from nex.core.exceptions import (
    NexApprovalRequiredError,
    NexAuthError,
    NexBackendUnavailableError,
    NexConfigError,
    NexError,
    NexInvalidInputError,
    NexPolicyViolationError,
    NexRepositoryError,
    NexVerificationFailedError,
)
from nex.core.exit_codes import (
    APPROVAL_REQUIRED,
    AUTH_ERROR,
    BACKEND_UNAVAILABLE,
    CONFIG_ERROR,
    GENERAL_ERROR,
    INVALID_INPUT,
    POLICY_VIOLATION,
    SUCCESS,
    VERIFICATION_FAILED,
    ExitCode,
)


def test_exit_codes_values() -> None:
    """Verify exit code values align with POSIX conventions."""
    assert SUCCESS == 0
    assert GENERAL_ERROR == 1
    assert INVALID_INPUT == 2
    assert CONFIG_ERROR == 3
    assert AUTH_ERROR == 4
    assert BACKEND_UNAVAILABLE == 5
    assert APPROVAL_REQUIRED == 6
    assert POLICY_VIOLATION == 7
    assert VERIFICATION_FAILED == 8

    assert ExitCode.SUCCESS == 0
    assert ExitCode.GENERAL_ERROR == 1
    assert ExitCode.INVALID_INPUT == 2
    assert ExitCode.CONFIG_ERROR == 3
    assert ExitCode.AUTH_ERROR == 4
    assert ExitCode.BACKEND_UNAVAILABLE == 5
    assert ExitCode.APPROVAL_REQUIRED == 6
    assert ExitCode.POLICY_VIOLATION == 7
    assert ExitCode.VERIFICATION_FAILED == 8


def test_nex_error_defaults() -> None:
    """Test base NexError attributes."""
    err = NexError("Something went wrong", code="GENERIC", exit_code=1)
    assert str(err) == "Something went wrong"
    assert err.message == "Something went wrong"
    assert err.code == "GENERIC"
    assert err.exit_code == 1
    assert err.detail is None
    assert err.suggestion is None


def test_typed_exceptions_exit_codes() -> None:
    """Verify that each domain exception carries its correct exit code and code string."""
    cases = [
        (NexInvalidInputError("bad arg"), INVALID_INPUT, "INVALID_INPUT"),
        (NexConfigError("bad toml"), CONFIG_ERROR, "CONFIG_ERROR"),
        (NexAuthError("bad token"), AUTH_ERROR, "AUTHENTICATION_REQUIRED"),
        (
            NexBackendUnavailableError("offline"),
            BACKEND_UNAVAILABLE,
            "BACKEND_UNAVAILABLE",
        ),
        (NexApprovalRequiredError("denied"), APPROVAL_REQUIRED, "APPROVAL_REQUIRED"),
        (NexPolicyViolationError("traversal"), POLICY_VIOLATION, "POLICY_VIOLATION"),
        (
            NexVerificationFailedError("test failed"),
            VERIFICATION_FAILED,
            "VERIFICATION_FAILED",
        ),
        (NexRepositoryError("not a repo"), INVALID_INPUT, "REPOSITORY_ERROR"),
    ]

    for err, expected_exit_code, expected_code in cases:
        assert err.exit_code == expected_exit_code
        assert err.code == expected_code
        assert err.message is not None
