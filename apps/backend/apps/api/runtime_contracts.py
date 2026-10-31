"""
NEX Backend — FastAPI Agent Runtime Communication Contracts.

Type-safe request and response dataclasses for internal inter-service communication.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ServicePingRequestContract:
    message: str
    client_service: str = "django-backend"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ServicePingResponseContract:
    status: str
    service: str
    echo_message: str
    timestamp: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServicePingResponseContract":
        return cls(
            status=data.get("status", "unknown"),
            service=data.get("service", "unknown"),
            echo_message=data.get("echo_message", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass(frozen=True)
class AgentTaskRequestContract:
    task_id: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentTaskResponseContract:
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTaskResponseContract":
        return cls(
            task_id=data.get("task_id", ""),
            status=data.get("status", "unknown"),
            result=data.get("result"),
        )

