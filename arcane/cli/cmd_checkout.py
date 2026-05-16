"""arc checkout — switch branches or restore files."""

from pathlib import Path

import click

from arcane.core.diff import _flatten_tree
from arcane.core.objects.blob import Blob
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.fs import atomic_write
from arcane.utils.terminal import console


@click.command("checkout")
@click.argument("target")
@click.option("-b", "new_branch", is_flag=True, help="Create and switch to a new branch.")
def checkout(target: str, new_branch: bool) -> None:
    """Switch to a branch or commit, restoring the working tree.

    TARGET can be a branch name, tag, or commit hash.
    Use -b TARGET to create a new branch and switch to it.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if new_branch:
        # Create and switch to new branch
        head = repo.refs.resolve_head()
        if not head:
            raise click.ClickException("Cannot create branch in empty repository.")
        if repo.refs.branch_exists(target):
            raise click.ClickException(f"Branch '{target}' already exists.")
        repo.refs.update_branch(target, head)
        repo.refs.set_head_to_branch(target)
        console.print(f"Switched to new branch [bold cyan]{target}[/bold cyan]")
        return

    # Resolve target to a commit hash
    target_hash = repo.refs.resolve(target)
    if not target_hash:
        raise click.ClickException(f"Unknown branch, tag, or commit: '{target}'")

    try:
        target_commit = repo.store.read_commit(target_hash)
    except Exception:
        raise click.ClickException(f"Could not read commit: {target_hash[:8]}")

    # Restore working tree from target commit's tree
    flat = _flatten_tree(repo.store, target_commit.tree, "")

    # Write files to workdir
    for rel_path, blob_hash in flat.items():
        abs_path = repo.root / rel_path.replace("/", "\\")
        blob = repo.store.read_blob(blob_hash)
        atomic_write(abs_path, blob.content)

    # Remove files that exist in workdir but not in target tree
    current_head = repo.refs.resolve_head()
    if current_head:
        try:
            current_commit = repo.store.read_commit(current_head)
            current_flat = _flatten_tree(repo.store, current_commit.tree, "")
            for rel_path in current_flat:
                if rel_path not in flat:
                    abs_path = repo.root / rel_path.replace("/", "\\")
                    if abs_path.exists():
                        abs_path.unlink()
        except Exception:
            pass

    # Update index to match target tree
    from arcane.core.index import Index, IndexEntry as IE
    index = repo.index
    # Rebuild index from flat tree
    from arcane.utils.fs import locked
    with locked(index.lock_path):
        index._entries = {}
        for rel_path, blob_hash in flat.items():
            abs_path = repo.root / rel_path.replace("/", "\\")
            stat = abs_path.stat() if abs_path.exists() else None
            index._entries[rel_path] = IE(
                path=rel_path,
                hash=blob_hash,
                mode=0o100644,
                size=stat.st_size if stat else 0,
                mtime=stat.st_mtime if stat else 0.0,
            )
        index._save()

    # Update HEAD
    if repo.refs.branch_exists(target):
        repo.refs.set_head_to_branch(target)
        console.print(f"Switched to branch [bold cyan]{target}[/bold cyan]")
    else:
        repo.refs.set_head_detached(target_hash)
        console.print(f"HEAD detached at [bold]{target_hash[:8]}[/bold]")
