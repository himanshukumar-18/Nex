"""Tests for developer approval system, risk levels, and execution policies."""

import sys

import pytest
from nex.core.approvals import ApprovalPolicy, RiskLevel
from nex.core.exceptions import NexApprovalRequiredError, NexPolicyViolationError
from nex.core.execution_policy import ExecutionPolicy


def test_yes_flag_forbidden_for_high_and_critical_risk() -> None:
    """Ensure --yes raises NexPolicyViolationError on HIGH and CRITICAL risk operations."""
    with pytest.raises(NexPolicyViolationError) as exc_info:
        ApprovalPolicy.check_yes_flag_eligibility(
            "modify_code", RiskLevel.HIGH, yes_flag=True
        )
    assert "HIGH" in exc_info.value.message

    with pytest.raises(NexPolicyViolationError) as exc_info:
        ApprovalPolicy.check_yes_flag_eligibility(
            "create_pr", RiskLevel.CRITICAL, yes_flag=True
        )
    assert "CRITICAL" in exc_info.value.message


def test_yes_flag_permitted_for_low_and_medium_risk() -> None:
    """Ensure --yes is permitted for LOW and MEDIUM risk operations."""
    # Should not raise
    ApprovalPolicy.check_yes_flag_eligibility("inspect", RiskLevel.LOW, yes_flag=True)
    ApprovalPolicy.check_yes_flag_eligibility(
        "init_overwrite", RiskLevel.MEDIUM, yes_flag=True
    )

    # request_approval returns True immediately when yes_flag is True for MEDIUM
    approved = ApprovalPolicy.request_approval(
        "Overwrite?",
        operation_name="init_overwrite",
        risk_level=RiskLevel.MEDIUM,
        yes_flag=True,
    )
    assert approved is True


def test_non_tty_stdin_raises_approval_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure non-interactive stdin raises NexApprovalRequiredError."""
    # Simulate non-TTY
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    with pytest.raises(NexApprovalRequiredError) as exc_info:
        ApprovalPolicy.request_approval(
            "Confirm?",
            operation_name="dangerous_op",
            risk_level=RiskLevel.HIGH,
            yes_flag=False,
        )
    assert "stdin is not a TTY" in exc_info.value.message


def test_interactive_approval_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test interactive prompt confirmation with 'y'."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    result = ApprovalPolicy.request_approval(
        "Proceed?",
        operation_name="test_op",
        risk_level=RiskLevel.MEDIUM,
        yes_flag=False,
    )
    assert result is True


def test_interactive_approval_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test interactive prompt rejection with 'n' raises NexApprovalRequiredError."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    with pytest.raises(NexApprovalRequiredError) as exc_info:
        ApprovalPolicy.request_approval(
            "Proceed?",
            operation_name="test_op",
            risk_level=RiskLevel.MEDIUM,
            yes_flag=False,
        )
    assert "rejected by user" in exc_info.value.message


def test_execution_policy_blocks_dangerous_local_commands() -> None:
    """Ensure dangerous shell patterns are blocked locally."""
    dangerous = ["rm -rf /", "sudo make install", "chmod 777 file", "curl | sh"]
    for cmd in dangerous:
        with pytest.raises(NexPolicyViolationError):
            ExecutionPolicy.validate_local_execution(cmd)

    # Safe command should pass
    ExecutionPolicy.validate_local_execution("pytest tests/")


def test_execution_policy_require_sandbox() -> None:
    """Test require_sandbox raises policy error."""
    with pytest.raises(NexPolicyViolationError) as exc_info:
        ExecutionPolicy.require_sandbox("untrusted_build")
    assert "isolated remote sandbox" in exc_info.value.message
