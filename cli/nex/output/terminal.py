"""NEX Cyber Brutalist Terminal Output Formatter.

Renders high-contrast, polished CLI presentations using Rich.
Follows NEX design tokens:
  Primary Accent:    #8B5CF6 (Purple)
  Secondary Accent:  #00D9FF (Cyan)
  Highlight:         #C4B5FD
  Success:           #22C55E
  Warning:           #F59E0B
  Danger:            #EF4444
  Text Secondary:    #A1A1B5
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

NEX_THEME = Theme(
    {
        "accent": "#8B5CF6",
        "cyan": "#00D9FF",
        "highlight": "#C4B5FD",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "dim": "#A1A1B5",
    }
)

console = Console(theme=NEX_THEME)
error_console = Console(theme=NEX_THEME, stderr=True)


class TerminalOutput:
    """Provides structured Cyber Brutalist rendering methods."""

    def __init__(self, is_verbose: bool = False, no_color: bool = False) -> None:
        self.is_verbose = is_verbose
        self.console = Console(theme=NEX_THEME, no_color=no_color)
        self.err_console = Console(theme=NEX_THEME, stderr=True, no_color=no_color)

    def print_banner(self, title: str, subtitle: str | None = None) -> None:
        """Render a top-level Cyber Brutalist section banner."""
        text = Text()
        text.append("■ NEX ", style="bold #00D9FF")
        text.append(f"| {title.upper()}\n", style="bold #8B5CF6")
        if subtitle:
            text.append(f"  {subtitle}", style="#A1A1B5")

        panel = Panel(
            text,
            border_style="#303044",
            padding=(0, 1),
        )
        self.console.print(panel)

    def print_success(self, message: str) -> None:
        """Render a success message with green accent."""
        self.console.print(f"[bold #22C55E]✓[/bold #22C55E] {message}")

    def print_info(self, message: str) -> None:
        """Render an informational message with purple accent."""
        self.console.print(f"[bold #8B5CF6]●[/bold #8B5CF6] {message}")

    def print_warning(self, message: str) -> None:
        """Render a warning message with amber accent."""
        self.console.print(
            f"[bold #F59E0B]▲[/bold #F59E0B] [warning]{message}[/warning]"
        )

    def print_error(self, message: str, suggestion: str | None = None) -> None:
        """Render an error message with red accent to stderr."""
        self.err_console.print(f"[bold #EF4444]✕ ERROR:[/bold #EF4444] {message}")
        if suggestion:
            self.err_console.print(f"  [dim]Suggestion: {suggestion}[/dim]")

    def print_verbose(self, message: str) -> None:
        """Render diagnostic message if verbose mode is active."""
        if self.is_verbose:
            self.err_console.print(f"[dim][VERBOSE] {message}[/dim]")

    def print_table(
        self, title: str, columns: list[str], rows: list[list[str]]
    ) -> None:
        """Render a monospace cyber data table."""
        table = Table(
            title=f"[bold #8B5CF6]{title.upper()}[/bold #8B5CF6]",
            border_style="#303044",
            header_style="bold #00D9FF",
            show_lines=False,
            padding=(0, 2),
        )
        for col in columns:
            table.add_column(col)

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def print_key_value_pairs(self, title: str, items: list[tuple[str, Any]]) -> None:
        """Render aligned key-value properties."""
        self.console.print(f"\n[bold #00D9FF]▸ {title.upper()}[/bold #00D9FF]")
        for key, val in items:
            self.console.print(f"  [dim]{key:.<26}[/dim] [#F5F3FF]{val}[/#F5F3FF]")
