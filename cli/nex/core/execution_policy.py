"""NEX Hybrid Execution Architecture & Policy.

Enforces clear separation between safe local operations and untrusted code execution.
Untrusted or AI-generated commands must never execute directly in the local environment;
they must route through remote isolated sandboxes.
"""

from enum import StrEnum
from typing import Any

from nex.core.exceptions import NexPolicyViolationError


class ExecutionTarget(StrEnum):
    """Permitted execution target environments."""

    LOCAL = "local"  # Read-only inspection, git query, local diff
    REMOTE_SANDBOX = (
        "remote_sandbox"  # AI code execution, build harnesses, untrusted scripts
    )


class ExecutionPolicy:
    """Validates and routes commands according to safety constraints."""

    # Disallowed commands in local environment
    LOCAL_DISALLOWED_PATTERNS = {
        "rm -rf",
        "sudo",
        "chmod",
        "curl | sh",
        "wget | sh",
        ":(){ :|:& };:",
    }

    @classmethod
    def validate_local_execution(cls, command: str) -> None:
        """Validate whether a command is safe for local execution.

        Arbitrary or destructive shell commands are strictly blocked locally.
        """
        lower_cmd = command.lower()
        for disallowed in cls.LOCAL_DISALLOWED_PATTERNS:
            if disallowed in lower_cmd:
                raise NexPolicyViolationError(
                    f"Execution of potentially destructive command '{command}' is forbidden locally.",
                    suggestion="Route operations requiring shell modifications through an isolated sandbox.",
                )

    @classmethod
    def require_sandbox(
        cls, operation: str, context: dict[str, Any] | None = None
    ) -> None:
        """Raise policy error if an untrusted execution is attempted without sandbox."""
        raise NexPolicyViolationError(
            f"Operation '{operation}' requires an isolated remote sandbox environment.",
            suggestion="Sandbox infrastructure will be connected in subsequent execution phases.",
        )
