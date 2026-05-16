"""Tests for LLA line tracker."""

import time
import pytest
from pathlib import Path

from arcane.core.objects.annotation import Annotation
from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.repository import Repository
from arcane.features.lla.tracker import track_annotation, _map_lines


# ── Unit tests for _map_lines ────────────────────────────────────────────────

def test_map_lines_unchanged():
    old = ["a\n", "b\n", "c\n"]
    new = ["a\n", "b\n", "c\n"]
    start, end, orphaned = _map_lines(old, new, 2, 2)
    assert start == 2
    assert end == 2
    assert not orphaned


def test_map_lines_line_shifted_down():
    old = ["a\n", "b\n", "c\n"]
    new = ["inserted\n", "a\n", "b\n", "c\n"]
    start, end, orphaned = _map_lines(old, new, 1, 1)
    assert start == 2
    assert not orphaned


def test_map_lines_line_deleted():
    old = ["a\n", "b\n", "c\n"]
    new = ["a\n", "c\n"]
    start, end, orphaned = _map_lines(old, new, 2, 2)
    assert orphaned


def test_map_lines_multi_line_range_preserved():
    old = ["a\n", "b\n", "c\n", "d\n"]
    new = ["x\n", "a\n", "b\n", "c\n", "d\n"]
    start, end, orphaned = _map_lines(old, new, 2, 3)
    assert start == 3
    assert end == 4
    assert not orphaned


# ── Integration tests for track_annotation ───────────────────────────────────

def _make_commit(repo: Repository, files: dict[str, bytes], parent: str | None) -> str:
    """Helper: write files, build a tree+commit, update main branch."""
    entries = []
    for name, content in files.items():
        blob = Blob(content)
        blob_hash = repo.store.write(blob)
        entries.append(TreeEntry(name=name, hash=blob_hash, mode=0o100644, object_type="blob"))

    tree = Tree(entries)
    tree_hash = repo.store.write(tree)
    c = Commit(
        tree=tree_hash,
        parents=[parent] if parent else [],
        author="T <t@t.com>",
        author_ts=time.time(),
        committer="T <t@t.com>",
        committer_ts=time.time(),
        message="test commit",
    )
    h = repo.store.write(c)
    repo.refs.update_branch("main", h)
    return h


def _make_annotation(commit_hash: str, file_path: str, line_start: int, line_end: int) -> Annotation:
    return Annotation(
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        commit_hash=commit_hash,
        annotation_type="note",
        text="test note",
        author="T <t@t.com>",
        timestamp=time.time(),
    )


def test_track_annotation_same_commit(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h = _make_commit(repo, {"foo.py": b"line1\nline2\nline3\n"}, None)
    ann = _make_annotation(h, "foo.py", 2, 2)
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h)
    assert tracked.current_line_start == 2
    assert not tracked.is_orphaned


def test_track_annotation_no_change(tmp_path: Path):
    repo = Repository.init(tmp_path)
    content = b"line1\nline2\nline3\n"
    h1 = _make_commit(repo, {"foo.py": content}, None)
    h2 = _make_commit(repo, {"foo.py": content}, h1)

    ann = _make_annotation(h1, "foo.py", 2, 2)
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.current_line_start == 2
    assert not tracked.is_orphaned


def test_track_annotation_line_shifted(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h1 = _make_commit(repo, {"foo.py": b"a\nb\nc\n"}, None)
    h2 = _make_commit(repo, {"foo.py": b"inserted\na\nb\nc\n"}, h1)

    ann = _make_annotation(h1, "foo.py", 1, 1)  # "a" is on line 1 in h1
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.current_line_start == 2  # "a" moved to line 2
    assert not tracked.is_orphaned


def test_track_annotation_line_deleted_becomes_orphaned(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h1 = _make_commit(repo, {"foo.py": b"a\nb\nc\n"}, None)
    h2 = _make_commit(repo, {"foo.py": b"a\nc\n"}, h1)  # "b" removed

    ann = _make_annotation(h1, "foo.py", 2, 2)  # annotating "b"
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.is_orphaned


def test_track_annotation_file_removed_becomes_orphaned(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h1 = _make_commit(repo, {"foo.py": b"a\nb\nc\n"}, None)
    h2 = _make_commit(repo, {"other.py": b"x\n"}, h1)  # foo.py removed

    ann = _make_annotation(h1, "foo.py", 1, 1)
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.is_orphaned


def test_track_annotation_defaults_to_head(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h1 = _make_commit(repo, {"foo.py": b"a\nb\nc\n"}, None)
    _make_commit(repo, {"foo.py": b"x\na\nb\nc\n"}, h1)  # shifts lines down

    ann = _make_annotation(h1, "foo.py", 1, 1)
    ann_hash = repo.store.write(ann)

    tracked = track_annotation(repo, ann, ann_hash)  # uses HEAD
    assert tracked.current_line_start == 2
    assert not tracked.is_orphaned
