"""LLA — Line tracking: compute current line positions via diff replay."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from arcane.core.objects.annotation import Annotation
from arcane.core.repository import Repository


@dataclass
class TrackedAnnotation:
    annotation: Annotation
    annotation_hash: str
    current_line_start: int   # mapped to current HEAD, or -1 if orphaned
    current_line_end: int
    is_orphaned: bool         # True if the line was deleted in history


def track_annotation(
    repo: Repository,
    annotation: Annotation,
    annotation_hash: str,
    target_commit_hash: str | None = None,
) -> TrackedAnnotation:
    """Map an annotation's original line numbers to their positions at target_commit.

    Replays diffs from annotation.commit_hash to target_commit_hash (or HEAD).
    If target_commit_hash is None, uses current HEAD.

    Returns a TrackedAnnotation with updated line numbers.
    """
    if target_commit_hash is None:
        target_commit_hash = repo.refs.resolve_head()

    if target_commit_hash is None or target_commit_hash == annotation.commit_hash:
        return TrackedAnnotation(
            annotation=annotation,
            annotation_hash=annotation_hash,
            current_line_start=annotation.line_start,
            current_line_end=annotation.line_end,
            is_orphaned=False,
        )

    # Build the commit chain from annotation.commit_hash to target_commit_hash
    chain = _build_commit_chain(repo, annotation.commit_hash, target_commit_hash)
    if not chain:
        # Can't trace; return original position
        return TrackedAnnotation(
            annotation=annotation,
            annotation_hash=annotation_hash,
            current_line_start=annotation.line_start,
            current_line_end=annotation.line_end,
            is_orphaned=False,
        )

    line_start = annotation.line_start
    line_end = annotation.line_end
    orphaned = False

    for i in range(len(chain) - 1):
        old_commit = repo.store.read_commit(chain[i])
        new_commit = repo.store.read_commit(chain[i + 1])

        old_blob_hash = _get_blob_hash(repo, old_commit.tree, annotation.file_path)
        new_blob_hash = _get_blob_hash(repo, new_commit.tree, annotation.file_path)

        if old_blob_hash is None and new_blob_hash is None:
            continue
        if new_blob_hash is None:
            orphaned = True
            break
        if old_blob_hash == new_blob_hash:
            continue

        old_text = repo.store.read_blob(old_blob_hash).decode() if old_blob_hash else ""
        new_text = repo.store.read_blob(new_blob_hash).decode()

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        new_start, new_end, is_orphaned = _map_lines(
            old_lines, new_lines, line_start, line_end
        )
        line_start = new_start
        line_end = new_end
        if is_orphaned:
            orphaned = True
            break

    return TrackedAnnotation(
        annotation=annotation,
        annotation_hash=annotation_hash,
        current_line_start=line_start,
        current_line_end=line_end,
        is_orphaned=orphaned,
    )


def _map_lines(
    old_lines: list[str],
    new_lines: list[str],
    line_start: int,
    line_end: int,
) -> tuple[int, int, bool]:
    """Map 1-indexed line numbers from old_lines to new_lines using SequenceMatcher.

    Returns (new_start, new_end, is_orphaned).
    """
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    opcodes = sm.get_opcodes()

    # Convert to 0-indexed for matching
    old_start_0 = line_start - 1
    old_end_0 = line_end - 1

    new_start_0: int | None = None
    new_end_0: int | None = None

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # Lines i1..i2 in old map to j1..j2 in new
            if i1 <= old_start_0 < i2:
                offset = old_start_0 - i1
                new_start_0 = j1 + offset
            if i1 <= old_end_0 < i2:
                offset = old_end_0 - i1
                new_end_0 = j1 + offset
        elif tag in ("replace", "delete"):
            # If our line was in the replaced/deleted region, it's orphaned
            if i1 <= old_start_0 < i2:
                if tag == "delete":
                    return -1, -1, True
                # Replace: try to map to the nearest new line
                new_start_0 = j1

    if new_start_0 is None:
        # Line moved past end or deleted
        return -1, -1, True
    if new_end_0 is None:
        new_end_0 = new_start_0

    return new_start_0 + 1, new_end_0 + 1, False


def _get_blob_hash(repo: Repository, tree_hash: str, file_path: str) -> str | None:
    """Resolve a file path within a tree to its blob hash."""
    parts = file_path.split("/")
    current_tree_hash = tree_hash

    for i, part in enumerate(parts):
        try:
            tree = repo.store.read_tree(current_tree_hash)
        except Exception:
            return None
        entry = tree.get(part)
        if entry is None:
            return None
        if i == len(parts) - 1:
            return entry.hash if entry.object_type == "blob" else None
        if entry.object_type != "tree":
            return None
        current_tree_hash = entry.hash

    return None


def _build_commit_chain(
    repo: Repository,
    from_hash: str,
    to_hash: str,
    max_depth: int = 500,
) -> list[str]:
    """Return an ordered list of commit hashes from from_hash to to_hash.

    Uses BFS to find the path. Returns empty list if not found.
    Assumes linear history (follows first parent only for simplicity).
    """
    # Walk from to_hash back via first-parents until we hit from_hash
    chain: list[str] = [to_hash]
    current = to_hash
    for _ in range(max_depth):
        try:
            commit = repo.store.read_commit(current)
        except Exception:
            return []
        if not commit.parents:
            break
        parent = commit.parents[0]
        chain.append(parent)
        if parent == from_hash:
            break
        current = parent

    chain.reverse()
    if from_hash not in chain:
        return []
    idx = chain.index(from_hash)
    return chain[idx:]
