"""Tests for DiffEngine."""

import pytest
from pathlib import Path

from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.diff import diff_blobs, diff_trees
from arcane.core.store import ObjectStore


@pytest.fixture
def store(tmp_path: Path) -> ObjectStore:
    objects_dir = tmp_path / "objects"
    objects_dir.mkdir()
    return ObjectStore(objects_dir)


def test_diff_blobs_modified(store: ObjectStore):
    old = Blob(b"line1\nline2\n")
    new = Blob(b"line1\nline2 modified\n")
    old_h = store.write(old)
    new_h = store.write(new)
    result = diff_blobs(store, old_h, new_h, "test.txt")
    assert "line2 modified" in result
    assert "@@" in result


def test_diff_blobs_new_file(store: ObjectStore):
    new = Blob(b"new content\n")
    new_h = store.write(new)
    result = diff_blobs(store, None, new_h, "new.txt")
    assert "new content" in result


def test_diff_trees_added_file(store: ObjectStore):
    old_tree = Tree([])
    new_blob = Blob(b"new\n")
    new_blob_hash = store.write(new_blob)
    new_tree = Tree([TreeEntry(name="new.txt", hash=new_blob_hash, mode=0o100644, object_type="blob")])

    old_hash = store.write(old_tree)
    new_hash = store.write(new_tree)

    diffs = diff_trees(store, old_hash, new_hash)
    assert len(diffs) == 1
    assert diffs[0].status == "A"
    assert diffs[0].path == "new.txt"


def test_diff_trees_deleted_file(store: ObjectStore):
    blob = Blob(b"content\n")
    blob_hash = store.write(blob)
    old_tree = Tree([TreeEntry(name="file.txt", hash=blob_hash, mode=0o100644, object_type="blob")])
    new_tree = Tree([])

    old_hash = store.write(old_tree)
    new_hash = store.write(new_tree)

    diffs = diff_trees(store, old_hash, new_hash)
    assert len(diffs) == 1
    assert diffs[0].status == "D"


def test_diff_trees_no_changes(store: ObjectStore):
    blob = Blob(b"same\n")
    blob_hash = store.write(blob)
    tree = Tree([TreeEntry(name="f.txt", hash=blob_hash, mode=0o100644, object_type="blob")])
    tree_hash = store.write(tree)
    diffs = diff_trees(store, tree_hash, tree_hash)
    assert diffs == []
