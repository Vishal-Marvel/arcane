"""arc tag — create or list tags."""

from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.terminal import console


@click.command("tag")
@click.argument("name", required=False)
@click.argument("commit_ref", required=False)
@click.option("-d", "--delete", "delete_name", default=None, metavar="NAME", help="Delete a tag.")
@click.option("-l", "--list", "list_tags", is_flag=True, help="List all tags.")
def tag(
    name: str | None,
    commit_ref: str | None,
    delete_name: str | None,
    list_tags: bool,
) -> None:
    """Create or list tags.

    Without arguments or with -l: list tags.
    With NAME: tag the current HEAD.
    With NAME COMMIT: tag a specific commit.
    -d NAME: delete a tag.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if delete_name:
        try:
            repo.refs.delete_tag(delete_name)
            console.print(f"Deleted tag [bold]{delete_name}[/bold].")
        except ValueError as e:
            raise click.ClickException(str(e))
        return

    if list_tags or not name:
        tags = repo.refs.list_tags()
        if not tags:
            console.print("[dim]No tags.[/dim]")
            return
        for t in tags:
            h = repo.refs.resolve_tag(t) or ""
            console.print(f"  {t}  [dim]{h[:8]}[/dim]")
        return

    # Create tag
    if commit_ref:
        target_hash = repo.refs.resolve(commit_ref)
    else:
        target_hash = repo.refs.resolve_head()

    if not target_hash:
        raise click.ClickException("Could not resolve target commit.")

    try:
        repo.refs.create_tag(name, target_hash)
        console.print(f"Tagged [bold]{target_hash[:8]}[/bold] as [bold green]{name}[/bold green]")
    except ValueError as e:
        raise click.ClickException(str(e))
