"""DAC — Staging checker: warns when staged files have unstaged dependencies."""

from __future__ import annotations

from pathlib import Path

from arcane.core.repository import Repository
from arcane.features.dac.parser import parse_dependencies
from arcane.utils.terminal import print_warning


def check_staged(repo: Repository) -> None:
    """Warn if any staged file imports a file that has unstaged workdir changes.

    This is advisory only — it never blocks the add operation.
    """
    staged_paths = repo.index.paths()
    unstaged_changes = repo.index.diff_vs_workdir(repo.root)

    warned: set[tuple[str, str]] = set()

    for staged_path in staged_paths:
        abs_path = repo.root / staged_path.replace("/", "\\")
        if not abs_path.exists():
            continue
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue

        deps = parse_dependencies(abs_path, content, repo.root)
        for dep in deps:
            if dep in unstaged_changes and (staged_path, dep) not in warned:
                print_warning(
                    f"[bold]{staged_path}[/bold] imports [bold]{dep}[/bold] "
                    f"which has unstaged changes ({unstaged_changes[dep]})"
                )
                warned.add((staged_path, dep))
