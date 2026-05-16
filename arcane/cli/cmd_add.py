"""arc add — stage files."""

from pathlib import Path

import click

from arcane.core.objects.blob import Blob
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.fs import repo_relative
from arcane.utils.terminal import print_error


@click.command("add")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
def add(paths: tuple[str, ...]) -> None:
    """Stage files for the next commit."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    for raw_path in paths:
        abs_path = Path(raw_path).resolve()
        if abs_path.is_dir():
            # Recursively add all files in the directory
            files = [f for f in abs_path.rglob("*") if f.is_file()]
        else:
            files = [abs_path]

        for file_path in files:
            # Skip files inside .arcane/
            try:
                file_path.relative_to(repo.arcane_dir)
                continue
            except ValueError:
                pass

            rel = repo_relative(repo.root, file_path)
            content = file_path.read_bytes()
            blob = Blob(content)
            blob_hash = repo.store.write(blob)
            repo.index.add(rel, blob_hash, file_path)
            click.echo(f"staged: {rel}")

    # DAC check — warn about unstaged dependencies (Phase 3 hook, imported lazily)
    try:
        from arcane.features.dac.checker import check_staged
        check_staged(repo)
    except Exception:
        pass  # DAC is advisory; never block add
