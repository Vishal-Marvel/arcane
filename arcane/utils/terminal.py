"""Terminal display helpers using rich."""

from rich.console import Console
from rich.text import Text

console = Console()
err_console = Console(stderr=True)

# Intent type → color mapping
INTENT_COLORS: dict[str, str] = {
    "feat": "green",
    "fix": "red",
    "refactor": "blue",
    "perf": "cyan",
    "debt": "yellow",
    "docs": "magenta",
    "test": "white",
    "chore": "bright_black",
}

# Annotation type → color/symbol mapping
ANNOTATION_SYMBOLS: dict[str, tuple[str, str]] = {
    "note": ("*", "cyan"),
    "warning": ("!", "yellow"),
    "todo": ("~", "green"),
    "link": ("->", "blue"),
}

SPARKLINE_CHARS = "_.,:-=+|#"


def intent_badge(intent_type: str) -> Text:
    """Return a colored rich Text badge for an intent type."""
    color = INTENT_COLORS.get(intent_type, "white")
    return Text(f"[{intent_type}]", style=f"bold {color}")


def annotation_gutter(annotation_type: str) -> Text:
    """Return a colored gutter symbol for an annotation."""
    symbol, color = ANNOTATION_SYMBOLS.get(annotation_type, ("●", "white"))
    return Text(symbol, style=color)


def sparkline(values: list[int]) -> str:
    """Render a list of counts as a sparkline string using block chars."""
    if not values:
        return ""
    max_val = max(values) or 1
    return "".join(
        SPARKLINE_CHARS[min(int(v / max_val * (len(SPARKLINE_CHARS) - 1)), len(SPARKLINE_CHARS) - 1)]
        for v in values
    )


def print_error(msg: str) -> None:
    err_console.print(f"[bold red]error:[/bold red] {msg}")


def print_warning(msg: str) -> None:
    err_console.print(f"[bold yellow]warning:[/bold yellow] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")
