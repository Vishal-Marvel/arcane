"""MergeEngine — 3-way merge with conflict markers."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from arcane.core.diff import _flatten_tree, diff_trees
from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.store import ObjectStore


@dataclass
class MergeResult:
    merged_content: str
    has_conflicts: bool


def three_way_merge(base_text: str, ours_text: str, theirs_text: str) -> MergeResult:
    """Perform a 3-way text merge.

    Uses difflib.SequenceMatcher to find changes from base→ours and base→theirs,
    then applies both sets of changes. Emits conflict markers where changes overlap.
    """
    base = base_text.splitlines(keepends=True)
    ours = ours_text.splitlines(keepends=True)
    theirs = theirs_text.splitlines(keepends=True)

    # Extract changed regions as (base_i1, base_i2, replacement_lines)
    ours_changes = _extract_changes(base, ours)
    theirs_changes = _extract_changes(base, theirs)

    merged, has_conflicts = _apply_changes(base, ours_changes, theirs_changes)
    return MergeResult(merged_content="".join(merged), has_conflicts=has_conflicts)


def _extract_changes(
    old: list[str], new: list[str]
) -> list[tuple[int, int, list[str]]]:
    """Return a list of (old_start, old_end, new_lines) for non-equal regions."""
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    changes: list[tuple[int, int, list[str]]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            changes.append((i1, i2, new[j1:j2]))
    return changes


def _apply_changes(
    base: list[str],
    ours_changes: list[tuple[int, int, list[str]]],
    theirs_changes: list[tuple[int, int, list[str]]],
) -> tuple[list[str], bool]:
    """Walk base regions and apply ours/theirs changes, emitting conflict markers."""
    # Build a map from base_start → (base_end, replacement_lines) for fast lookup
    ours_map: dict[int, tuple[int, list[str]]] = {i1: (i2, r) for i1, i2, r in ours_changes}
    theirs_map: dict[int, tuple[int, list[str]]] = {i1: (i2, r) for i1, i2, r in theirs_changes}

    # Also build sets of all base line indices covered by each side's changes
    ours_covered: set[int] = {idx for i1, i2, _ in ours_changes for idx in range(i1, max(i2, i1 + 1))}
    theirs_covered: set[int] = {idx for i1, i2, _ in theirs_changes for idx in range(i1, max(i2, i1 + 1))}

    result: list[str] = []
    has_conflicts = False
    i = 0

    while i <= len(base):
        our_change = ours_map.get(i)
        their_change = theirs_map.get(i)

        if our_change is not None and their_change is not None:
            our_end, our_new = our_change
            their_end, their_new = their_change
            if our_new == their_new:
                result.extend(our_new)
            else:
                has_conflicts = True
                result.append("<<<<<<< ours\n")
                result.extend(our_new)
                result.append("=======\n")
                result.extend(their_new)
                result.append(">>>>>>> theirs\n")
            i = max(our_end, their_end, i + 1)
        elif our_change is not None:
            our_end, our_new = our_change
            result.extend(our_new)
            i = max(our_end, i + 1)
        elif their_change is not None:
            their_end, their_new = their_change
            result.extend(their_new)
            i = max(their_end, i + 1)
        else:
            if i < len(base):
                result.append(base[i])
            i += 1

    return result, has_conflicts


def find_merge_base(
    store: ObjectStore,
    commit_a: str,
    commit_b: str,
) -> str | None:
    """Find the LCA (lowest common ancestor) of two commits via BFS.

    Returns the hash of the merge base, or None if histories diverge completely.
    """
    visited_a: set[str] = set()
    visited_b: set[str] = set()
    queue_a = [commit_a]
    queue_b = [commit_b]

    while queue_a or queue_b:
        if queue_a:
            h = queue_a.pop(0)
            if h in visited_b:
                return h
            if h not in visited_a:
                visited_a.add(h)
                commit = store.read_commit(h)
                queue_a.extend(commit.parents)

        if queue_b:
            h = queue_b.pop(0)
            if h in visited_a:
                return h
            if h not in visited_b:
                visited_b.add(h)
                commit = store.read_commit(h)
                queue_b.extend(commit.parents)

    return None


def merge_trees(
    store: ObjectStore,
    base_tree: str | None,
    ours_tree: str,
    theirs_tree: str,
) -> tuple[str, bool]:
    """Merge two trees relative to a base, writing new blobs/trees to store.

    Returns (new_tree_hash, has_conflicts).
    """
    base_flat = _flatten_tree(store, base_tree, "")
    ours_flat = _flatten_tree(store, ours_tree, "")
    theirs_flat = _flatten_tree(store, theirs_tree, "")

    all_paths = set(base_flat) | set(ours_flat) | set(theirs_flat)
    merged_flat: dict[str, str] = {}
    has_conflicts = False

    for path in sorted(all_paths):
        base_h = base_flat.get(path)
        ours_h = ours_flat.get(path)
        theirs_h = theirs_flat.get(path)

        if ours_h == theirs_h:
            if ours_h:
                merged_flat[path] = ours_h
            # else: both deleted — omit
        elif ours_h == base_h:
            if theirs_h:
                merged_flat[path] = theirs_h
            # else: theirs deleted it
        elif theirs_h == base_h:
            if ours_h:
                merged_flat[path] = ours_h
            # else: ours deleted it
        else:
            # Both changed the file — 3-way text merge
            base_text = store.read_blob(base_h).decode() if base_h else ""
            ours_text = store.read_blob(ours_h).decode() if ours_h else ""
            theirs_text = store.read_blob(theirs_h).decode() if theirs_h else ""

            result = three_way_merge(base_text, ours_text, theirs_text)
            if result.has_conflicts:
                has_conflicts = True

            blob = Blob(result.merged_content.encode())
            blob_hash = store.write(blob)
            merged_flat[path] = blob_hash

    new_tree_hash = _build_tree_from_flat(store, merged_flat)
    return new_tree_hash, has_conflicts


def _build_tree_from_flat(store: ObjectStore, flat: dict[str, str]) -> str:
    """Build nested Tree objects from a flat {path: blob_hash} dict."""
    # Group by top-level directory
    root_entries: dict[str, str | dict] = {}  # type: ignore[type-arg]

    for path, blob_hash in flat.items():
        parts = path.split("/")
        if len(parts) == 1:
            root_entries[parts[0]] = blob_hash
        else:
            top = parts[0]
            rest = "/".join(parts[1:])
            if top not in root_entries:
                root_entries[top] = {}
            subtree = root_entries[top]
            if isinstance(subtree, dict):
                subtree[rest] = blob_hash

    return _write_tree(store, root_entries)


def _write_tree(store: ObjectStore, entries: dict) -> str:  # type: ignore[type-arg]
    tree_entries: list[TreeEntry] = []
    for name, value in entries.items():
        if isinstance(value, str):
            tree_entries.append(TreeEntry(name=name, hash=value, mode=0o100644, object_type="blob"))
        elif isinstance(value, dict):
            subtree_hash = _write_tree(store, value)
            tree_entries.append(TreeEntry(name=name, hash=subtree_hash, mode=0o040000, object_type="tree"))
    tree = Tree(tree_entries)
    return store.write(tree)
