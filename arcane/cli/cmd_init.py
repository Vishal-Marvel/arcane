"""arc init — initialize a new repository."""

import click
from pathlib import Path

from arcane.core.repository import Repository
from arcane.utils.terminal import console


@click.command("init")
@click.argument("path", default=".", type=click.Path())
def init(path: str) -> None:
    """Initialize a new arc repository at PATH (default: current directory)."""
    target = Path(path).resolve()
    try:
        repo = Repository.init(target)
        console.print(f"[bold green]Initialized empty arc repository in[/bold green] {repo.arcane_dir}")
    except FileExistsError as e:
        raise click.ClickException(str(e))
