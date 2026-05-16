"""arc diff — show changes between commits, index, and workdir."""

from pathlib import Path

import click

from arcane.core.diff import diff_blobs, diff_index_vs_head, diff_trees, diff_workdir_vs_index
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.terminal import console

STATUS_COLORS = {"A": "green", "M": "yellow", "D": "red"}


@click.command("diff")
@click.argument("commit_a", required=False)
@click.argument("commit_b", required=False)
@click.option("--staged", is_flag=True, help="Show staged changes (index vs HEAD).")
@click.option("--stat", is_flag=True, help="Show only file names and change summary.")
def diff(
    commit_a: str | None,
    commit_b: str | None,
    staged: bool,
    stat: bool,
) -> None:
    """Show changes.

    Without arguments: workdir vs index (unstaged changes).
    --staged: index vs HEAD (staged changes).
    <commit>: workdir vs that commit.
    <commit_a> <commit_b>: diff between two commits.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if commit_a and commit_b:
        # Tree-to-tree diff
        hash_a = repo.refs.resolve(commit_a)
        hash_b = repo.refs.resolve(commit_b)
        if not hash_a:
            raise click.ClickException(f"Unknown ref: {commit_a}")
        if not hash_b:
            raise click.ClickException(f"Unknown ref: {commit_b}")
        c_a = repo.store.read_commit(hash_a)
        c_b = repo.store.read_commit(hash_b)
        diffs = diff_trees(repo.store, c_a.tree, c_b.tree)
    elif staged:
        diffs = diff_index_vs_head(repo.store, repo.refs, repo.index)
    else:
        # Unstaged: workdir vs index (show diff content by re-hashing workdir file)
        diffs = diff_workdir_vs_index(repo.index, repo.root)
        # Enrich with actual unified diff from workdir
        enriched = []
        for fd in diffs:
            abs_path = repo.root / fd.path.replace("/", "\\")
            if abs_path.exists():
                new_content = abs_path.read_bytes().decode(errors="replace")
                old_content = ""
                if fd.old_hash:
                    old_content = repo.store.read_blob(fd.old_hash).decode()
                old_lines = old_content.splitlines(keepends=True)
                new_lines = new_content.splitlines(keepends=True)
                import difflib
                udiff = "".join(
                    difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{fd.path}", tofile=f"b/{fd.path}")
                )
                from arcane.core.diff import FileDiff
                enriched.append(FileDiff(path=fd.path, status=fd.status, old_hash=fd.old_hash, new_hash=None, unified_diff=udiff))
            else:
                enriched.append(fd)
        diffs = enriched

    if not diffs:
        console.print("[dim]No changes.[/dim]")
        return

    for fd in diffs:
        color = STATUS_COLORS.get(fd.status, "white")
        if stat:
            console.print(f"  [{color}]{fd.status}[/{color}]  {fd.path}")
        else:
            console.print(fd.unified_diff, end="")
