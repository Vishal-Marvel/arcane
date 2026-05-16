"""arc branch — list, create, or delete branches."""

from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.terminal import console


@click.command("branch")
@click.argument("name", required=False)
@click.option("-d", "--delete", "delete_name", default=None, metavar="NAME", help="Delete a branch.")
def branch(name: str | None, delete_name: str | None) -> None:
    """List branches, or create/delete one.

    Without arguments: list all branches.
    With NAME: create a new branch at HEAD.
    -d NAME: delete a branch.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if delete_name:
        current = repo.refs.current_branch()
        if delete_name == current:
            raise click.ClickException(f"Cannot delete the currently checked-out branch '{delete_name}'.")
        try:
            repo.refs.delete_branch(delete_name)
            console.print(f"Deleted branch [bold]{delete_name}[/bold].")
        except ValueError as e:
            raise click.ClickException(str(e))
        return

    if name:
        head = repo.refs.resolve_head()
        if not head:
            raise click.ClickException("Cannot create a branch in an empty repository.")
        if repo.refs.branch_exists(name):
            raise click.ClickException(f"Branch '{name}' already exists.")
        repo.refs.update_branch(name, head)
        console.print(f"Created branch [bold cyan]{name}[/bold cyan] at [bold]{head[:8]}[/bold].")
        return

    # List branches
    branches = repo.refs.list_branches()
    current = repo.refs.current_branch()

    if not branches:
        console.print("[dim]No branches yet.[/dim]")
        return

    for b in branches:
        h = repo.refs.resolve_branch(b) or ""
        marker = "* " if b == current else "  "
        style = "bold cyan" if b == current else ""
        console.print(f"{marker}[{style}]{b}[/{style}]  [dim]{h[:8]}[/dim]" if style else f"{marker}{b}  [dim]{h[:8]}[/dim]")
