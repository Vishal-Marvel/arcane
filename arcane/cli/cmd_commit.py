"""arc commit — record staged changes as a new commit."""

import time
from pathlib import Path

import click

from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.terminal import console, intent_badge

VALID_INTENTS = ["feat", "fix", "refactor", "perf", "debt", "docs", "test", "chore"]


def _build_tree_from_index(repo: Repository) -> str:
    """Recursively build Tree objects from all index entries. Returns root tree hash."""
    entries = repo.index.all_entries()
    if not entries:
        raise click.ClickException("Nothing staged. Use 'arc add' to stage files.")

    # Group entries by directory structure
    flat: dict[str, str] = {e.path: e.hash for e in entries}
    return _write_tree_recursive(repo, flat)


def _write_tree_recursive(repo: Repository, flat: dict[str, str]) -> str:
    """Build nested Tree objects from a flat {posix_path: blob_hash} dict."""
    tree_entries: list[TreeEntry] = []
    dirs: dict[str, dict[str, str]] = {}

    for path, blob_hash in flat.items():
        parts = path.split("/", 1)
        if len(parts) == 1:
            tree_entries.append(TreeEntry(name=parts[0], hash=blob_hash, mode=0o100644, object_type="blob"))
        else:
            top, rest = parts
            if top not in dirs:
                dirs[top] = {}
            dirs[top][rest] = blob_hash

    for dirname, sub_flat in dirs.items():
        subtree_hash = _write_tree_recursive(repo, sub_flat)
        tree_entries.append(TreeEntry(name=dirname, hash=subtree_hash, mode=0o040000, object_type="tree"))

    tree = Tree(tree_entries)
    return repo.store.write(tree)


@click.command("commit")
@click.option("-m", "--message", required=True, help="Commit message.")
@click.option(
    "-i", "--intent",
    type=click.Choice(VALID_INTENTS, case_sensitive=False),
    default=None,
    help="Commit intent type (required; will prompt if omitted).",
)
@click.option("--scope", default=None, help="Optional scope label (e.g. 'auth', 'parser').")
@click.option("--breaking", is_flag=True, default=False, help="Mark as a breaking change.")
def commit(message: str, intent: str | None, scope: str | None, breaking: bool) -> None:
    """Record staged changes as a new commit."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    # CIT: enforce intent
    if intent is None:
        intent = click.prompt(
            "Intent",
            type=click.Choice(VALID_INTENTS, case_sensitive=False),
            default="chore",
        )

    intent_meta = {"type": intent.lower(), "scope": scope, "breaking": breaking}

    # DAC: build dependency snapshot
    dep_snapshot_hash: str | None = None
    try:
        from arcane.features.dac.snapshot import build_snapshot
        dep_snapshot_hash = build_snapshot(repo)
    except Exception:
        pass  # DAC is non-blocking

    # Build tree from index
    tree_hash = _build_tree_from_index(repo)

    # Determine parent commits
    parents: list[str] = []
    head_hash = repo.refs.resolve_head()
    if head_hash:
        parents.append(head_hash)
    if repo.is_merging():
        merge_head = repo.merge_head_path.read_text().strip()
        parents.append(merge_head)

    now = time.time()
    author = repo.get_author()

    commit_obj = Commit(
        tree=tree_hash,
        parents=parents,
        author=author,
        author_ts=now,
        committer=author,
        committer_ts=now,
        message=message,
        intent=intent_meta,
        dep_snapshot_hash=dep_snapshot_hash,
        annotation_refs=[],
    )

    commit_hash = repo.store.write(commit_obj)
    repo.refs.advance_head(commit_hash)

    if repo.is_merging():
        repo.clear_merge_head()

    badge = intent_badge(intent)
    console.print(
        f"[bold]{commit_hash[:8]}[/bold] ",
        badge,
        f" {message}",
        sep="",
    )
