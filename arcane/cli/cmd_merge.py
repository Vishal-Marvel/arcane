"""arc merge — merge a branch into the current branch."""

import time
from pathlib import Path

import click

from arcane.core.diff import _flatten_tree
from arcane.core.merge import find_merge_base, merge_trees
from arcane.core.objects.commit import Commit
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.fs import atomic_write
from arcane.utils.terminal import console, print_warning


@click.command("merge")
@click.argument("branch")
def merge(branch: str) -> None:
    """Merge BRANCH into the current branch."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if repo.is_merging():
        raise click.ClickException(
            "You are already in a merge. Resolve conflicts and commit, or use 'arc merge --abort' (TODO)."
        )

    ours_hash = repo.refs.resolve_head()
    if not ours_hash:
        raise click.ClickException("Cannot merge into empty repository.")

    theirs_hash = repo.refs.resolve(branch)
    if not theirs_hash:
        raise click.ClickException(f"Unknown branch or ref: '{branch}'")

    if ours_hash == theirs_hash:
        console.print("[dim]Already up to date.[/dim]")
        return

    ours_commit = repo.store.read_commit(ours_hash)
    theirs_commit = repo.store.read_commit(theirs_hash)

    # Fast-forward check
    base_hash = find_merge_base(repo.store, ours_hash, theirs_hash)

    if base_hash == theirs_hash:
        console.print("[dim]Already up to date.[/dim]")
        return

    if base_hash == ours_hash:
        # Fast-forward merge
        flat = _flatten_tree(repo.store, theirs_commit.tree, "")
        for rel_path, blob_hash in flat.items():
            abs_path = repo.root / rel_path.replace("/", "\\")
            blob = repo.store.read_blob(blob_hash)
            atomic_write(abs_path, blob.content)
        repo.refs.advance_head(theirs_hash)
        console.print(f"Fast-forward to [bold]{theirs_hash[:8]}[/bold]")
        return

    # 3-way merge
    base_tree = None
    if base_hash:
        base_commit = repo.store.read_commit(base_hash)
        base_tree = base_commit.tree

    new_tree_hash, has_conflicts = merge_trees(
        repo.store, base_tree, ours_commit.tree, theirs_commit.tree
    )

    # Write merged files to workdir
    flat = _flatten_tree(repo.store, new_tree_hash, "")
    for rel_path, blob_hash in flat.items():
        abs_path = repo.root / rel_path.replace("/", "\\")
        blob = repo.store.read_blob(blob_hash)
        atomic_write(abs_path, blob.content)

    if has_conflicts:
        repo.set_merge_head(theirs_hash)
        print_warning("Merge conflict detected. Resolve conflicts, then run 'arc commit'.")
        return

    # Auto-commit the merge
    now = time.time()
    author = repo.get_author()
    current_branch = repo.refs.current_branch() or "HEAD"

    merge_commit = Commit(
        tree=new_tree_hash,
        parents=[ours_hash, theirs_hash],
        author=author,
        author_ts=now,
        committer=author,
        committer_ts=now,
        message=f"Merge branch '{branch}' into {current_branch}",
        intent={"type": "chore", "scope": None, "breaking": False},
    )
    merge_hash = repo.store.write(merge_commit)
    repo.refs.advance_head(merge_hash)
    console.print(f"Merged [bold cyan]{branch}[/bold cyan] → [bold]{merge_hash[:8]}[/bold]")
