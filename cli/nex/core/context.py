"""NEX CLI Execution Context.

Aggregates active command configuration, output formatting targets,
repository root discovery, correlation tracking, and API clients.
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from nex.client.django import NexDjangoClient
from nex.config.schema import NexConfig
from nex.output.terminal import TerminalOutput


@dataclass
class CLIContext:
    """Execution context passed through command callbacks."""

    config: NexConfig
    output: TerminalOutput
    repo_root: Path
    correlation_id: str = field(default_factory=lambda: f"nex-cli-{uuid.uuid4()}")
    verbose: bool = False
    json_mode: bool = False
    dry_run: bool = False
    yes: bool = False
    _client: NexDjangoClient | None = None

    @property
    def client(self) -> NexDjangoClient:
        """Lazily initialize Django HTTP client configured with active context."""
        if self._client is None:
            self._client = NexDjangoClient(
                base_url=self.config.api.base_url,
                timeout_seconds=self.config.api.timeout_seconds,
                retry_attempts=self.config.api.retry_attempts,
            )
        return self._client

    def close(self) -> None:
        """Clean up network and system resources."""
        if self._client is not None:
            self._client.close()
            self._client = None
