"""NEX Developer Approval System & Risk Classification.

Enforces strict developer consent boundaries for all CLI operations.
Automation flags (e.g. --yes) are explicitly restricted from bypassing high-risk
or destructive operations such as code modifications, git push, or PR creation.
"""

import sys
from enum import StrEnum
from typing import Any

from nex.core.exceptions import NexApprovalRequiredError, NexPolicyViolationError


class RiskLevel(StrEnum):
    """Operation risk classification levels."""

    LOW = "low"  # Read-only queries, inspection, config read
    MEDIUM = "medium"  # Diff previews, directory scaffolding, init in empty dir
    HIGH = "high"  # File modifications, script execution, local testing
    CRITICAL = "critical"  # Destructive deletes, git commit, git push, PR creation


class ApprovalPolicy:
    """Governs whether an operation may proceed with or without interactive confirmation."""

    # Operations categorized as HIGH or CRITICAL strictly forbid --yes bypass
    YES_RESTRICTED_LEVELS = {RiskLevel.HIGH, RiskLevel.CRITICAL}

    @classmethod
    def check_yes_flag_eligibility(
        cls,
        operation_name: str,
        risk_level: RiskLevel,
        yes_flag: bool,
    ) -> None:
        """Validate whether the --yes flag is permitted for this operation risk level.

        Raises NexPolicyViolationError if --yes was attempted on a high/critical risk operation.
        """
        if yes_flag and risk_level in cls.YES_RESTRICTED_LEVELS:
            raise NexPolicyViolationError(
                f"Flag '--yes' cannot bypass approval for {risk_level.value.upper()}-risk operation: '{operation_name}'.",
                suggestion=(
                    "High and critical operations (code modifications, destructive changes, "
                    "git push, and PR creation) require explicit interactive confirmation."
                ),
            )

    @classmethod
    def request_approval(
        cls,
        prompt_message: str,
        *,
        operation_name: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        yes_flag: bool = False,
        details: dict[str, Any] | None = None,
        default_yes: bool = False,
    ) -> bool:
        """Request explicit developer approval for an operation.

        Args:
            prompt_message: The prompt displayed to the user.
            operation_name: Identifies the target operation.
            risk_level: The operation's risk classification.
            yes_flag: The value of the CLI --yes option.
            details: Optional metadata to display.
            default_yes: Default value when user presses enter without typing.

        Returns:
            True if approved.

        Raises:
            NexPolicyViolationError: If --yes was used on a restricted operation.
            NexApprovalRequiredError: If user rejects or interactive confirmation is unavailable.
        """
        # 1. Enforce --yes restrictions
        cls.check_yes_flag_eligibility(operation_name, risk_level, yes_flag)

        # 2. If yes_flag is set and permitted for this low/medium risk operation, proceed
        if yes_flag:
            return True

        # 3. Check for non-interactive terminal (piped input, CI/CD without TTY)
        if not sys.stdin.isatty():
            raise NexApprovalRequiredError(
                f"Interactive confirmation required for '{operation_name}', but stdin is not a TTY.",
                suggestion="Run this command in an interactive terminal.",
            )

        # 4. Interactive prompt
        suffix = " [Y/n]: " if default_yes else " [y/N]: "
        try:
            user_response = input(f"{prompt_message}{suffix}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            raise NexApprovalRequiredError(
                f"Operation '{operation_name}' aborted by user.",
            ) from None

        if not user_response:
            approved = default_yes
        else:
            approved = user_response in {"y", "yes"}

        if not approved:
            raise NexApprovalRequiredError(
                f"Operation '{operation_name}' was rejected by user.",
            )

        return True
