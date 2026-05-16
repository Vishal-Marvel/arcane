"""arc rm — remove files from the index."""

from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.fs import repo_relative


@click.command("rm")
@click.argument("paths", nargs=-1, required=True, type=click.Path())
@click.option("--cached", is_flag=True, help="Remove from index only, keep file in workdir.")
def rm(paths: tuple[str, ...], cached: bool) -> None:
    """Remove files from the index (and optionally from the workdir)."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    for raw_path in paths:
        abs_path = Path(raw_path).resolve()
        rel = repo_relative(repo.root, abs_path)

        try:
            repo.index.remove(rel)
        except KeyError:
            raise click.ClickException(f"'{rel}' is not tracked in the index")

        if not cached and abs_path.exists():
            abs_path.unlink()
            click.echo(f"removed: {rel}")
        else:
            click.echo(f"unstaged: {rel}")
