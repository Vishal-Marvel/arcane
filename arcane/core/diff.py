"""DiffEngine — unified diffs between blobs, trees, index, and workdir."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from arcane.core.index import Index
from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree
from arcane.core.refs import RefsManager
from arcane.core.store import ObjectStore


@dataclass
class FileDiff:
    """Represents a change to a single file."""
    path: str
    status: str          # 'A' added, 'D' deleted, 'M' modified
    old_hash: str | None
    new_hash: str | None
    unified_diff: str    # empty string for binary files or pure adds/deletes with no content


def diff_blobs(
    store: ObjectStore,
    old_hash: str | None,
    new_hash: str | None,
    path: str = "",
) -> str:
    """Return a unified diff string between two blob hashes.

    Pass None for old_hash (new file) or new_hash (deleted file).
    """
    old_lines: list[str] = []
    new_lines: list[str] = []

    if old_hash:
        old_blob = store.read_blob(old_hash)
        old_lines = old_blob.decode().splitlines(keepends=True)

    if new_hash:
        new_blob = store.read_blob(new_hash)
        new_lines = new_blob.decode().splitlines(keepends=True)

    old_label = f"a/{path}" if old_hash else "/dev/null"
    new_label = f"b/{path}" if new_hash else "/dev/null"

    return "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile=old_label, tofile=new_label)
    )


def diff_trees(
    store: ObjectStore,
    old_tree_hash: str | None,
    new_tree_hash: str | None,
) -> list[FileDiff]:
    """Recursively diff two trees, returning a flat list of FileDiff records."""
    old_flat = _flatten_tree(store, old_tree_hash, "")
    new_flat = _flatten_tree(store, new_tree_hash, "")

    all_paths = set(old_flat) | set(new_flat)
    result: list[FileDiff] = []

    for path in sorted(all_paths):
        old_hash = old_flat.get(path)
        new_hash = new_flat.get(path)

        if old_hash == new_hash:
            continue

        if old_hash is None:
            status = "A"
        elif new_hash is None:
            status = "D"
        else:
            status = "M"

        udiff = diff_blobs(store, old_hash, new_hash, path)
        result.append(FileDiff(path=path, status=status, old_hash=old_hash, new_hash=new_hash, unified_diff=udiff))

    return result


def _flatten_tree(store: ObjectStore, tree_hash: str | None, prefix: str) -> dict[str, str]:
    """Recursively flatten a tree into {repo_relative_path: blob_hash}."""
    if tree_hash is None:
        return {}
    tree = store.read_tree(tree_hash)
    result: dict[str, str] = {}
    for entry in tree.entries:
        full_path = f"{prefix}{entry.name}" if not prefix else f"{prefix}/{entry.name}"
        if entry.object_type == "blob":
            result[full_path] = entry.hash
        elif entry.object_type == "tree":
            result.update(_flatten_tree(store, entry.hash, full_path))
    return result


def diff_index_vs_head(
    store: ObjectStore,
    refs: RefsManager,
    index: Index,
) -> list[FileDiff]:
    """Return staged changes: what's in the index vs what's in HEAD."""
    head_hash = refs.resolve_head()
    head_flat: dict[str, str] = {}
    if head_hash:
        head_commit = store.read_commit(head_hash)
        head_flat = _flatten_tree(store, head_commit.tree, "")

    result: list[FileDiff] = []
    index_paths = index.paths()
    all_paths = set(head_flat) | index_paths

    for path in sorted(all_paths):
        old_hash = head_flat.get(path)
        entry = index.get(path)
        new_hash = entry.hash if entry else None

        if old_hash == new_hash:
            continue

        if old_hash is None:
            status = "A"
        elif new_hash is None:
            status = "D"
        else:
            status = "M"

        udiff = diff_blobs(store, old_hash, new_hash, path)
        result.append(FileDiff(path=path, status=status, old_hash=old_hash, new_hash=new_hash, unified_diff=udiff))

    return result


def diff_workdir_vs_index(index: Index, repo_root: Path) -> list[FileDiff]:
    """Return unstaged changes: workdir files vs what's in the index."""
    result: list[FileDiff] = []
    changes = index.diff_vs_workdir(repo_root)
    for path, status in sorted(changes.items()):
        entry = index.get(path)
        old_hash = entry.hash if entry else None
        result.append(FileDiff(path=path, status=status, old_hash=old_hash, new_hash=None, unified_diff=""))
    return result
