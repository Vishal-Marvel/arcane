"""Tests for MergeEngine."""

import pytest
from arcane.core.merge import three_way_merge, find_merge_base
from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.objects.commit import Commit
from arcane.core.store import ObjectStore
from pathlib import Path
import time


@pytest.fixture
def store(tmp_path: Path) -> ObjectStore:
    objects_dir = tmp_path / "objects"
    objects_dir.mkdir()
    return ObjectStore(objects_dir)


def test_three_way_no_conflict():
    base = "line1\nline2\nline3\n"
    ours = "line1\nline2 modified\nline3\n"
    theirs = "line1\nline2\nline3\nline4\n"
    result = three_way_merge(base, ours, theirs)
    assert not result.has_conflicts


def test_three_way_same_change():
    base = "a\nb\nc\n"
    ours = "a\nb modified\nc\n"
    theirs = "a\nb modified\nc\n"
    result = three_way_merge(base, ours, theirs)
    assert not result.has_conflicts


def test_three_way_conflict():
    base = "a\nb\nc\n"
    ours = "a\nours change\nc\n"
    theirs = "a\ntheirs change\nc\n"
    result = three_way_merge(base, ours, theirs)
    assert result.has_conflicts
    assert "<<<<<<< ours" in result.merged_content
    assert ">>>>>>> theirs" in result.merged_content


def _make_commit(store: ObjectStore, tree_hash: str, parents: list[str]) -> str:
    now = time.time()
    c = Commit(
        tree=tree_hash,
        parents=parents,
        author="A <a@b.com>",
        author_ts=now,
        committer="A <a@b.com>",
        committer_ts=now,
        message="test",
    )
    return store.write(c)


def test_find_merge_base(store: ObjectStore):
    empty_tree = store.write(Tree([]))
    base_hash = _make_commit(store, empty_tree, [])
    branch_a = _make_commit(store, empty_tree, [base_hash])
    branch_b = _make_commit(store, empty_tree, [base_hash])

    result = find_merge_base(store, branch_a, branch_b)
    assert result == base_hash


def test_find_merge_base_no_common(store: ObjectStore):
    empty_tree = store.write(Tree([]))
    a = _make_commit(store, empty_tree, [])
    b = _make_commit(store, empty_tree, [])
    result = find_merge_base(store, a, b)
    assert result is None
