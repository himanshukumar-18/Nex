"""NEX CLI Exit Code Constants.

Standardized POSIX-compliant exit codes for the NEX command-line interface.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """POSIX exit code enumeration."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    INVALID_INPUT = 2
    CONFIG_ERROR = 3
    AUTH_ERROR = 4
    BACKEND_UNAVAILABLE = 5
    APPROVAL_REQUIRED = 6
    POLICY_VIOLATION = 7
    VERIFICATION_FAILED = 8


# Direct integer constants
SUCCESS: int = ExitCode.SUCCESS
GENERAL_ERROR: int = ExitCode.GENERAL_ERROR
INVALID_INPUT: int = ExitCode.INVALID_INPUT
CONFIG_ERROR: int = ExitCode.CONFIG_ERROR
AUTH_ERROR: int = ExitCode.AUTH_ERROR
BACKEND_UNAVAILABLE: int = ExitCode.BACKEND_UNAVAILABLE
APPROVAL_REQUIRED: int = ExitCode.APPROVAL_REQUIRED
POLICY_VIOLATION: int = ExitCode.POLICY_VIOLATION
VERIFICATION_FAILED: int = ExitCode.VERIFICATION_FAILED
