"""Tests for arc object types."""

import pytest
from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.objects.commit import Commit
from arcane.core.objects.annotation import Annotation
import time


def test_blob_roundtrip():
    content = b"hello world\n"
    blob = Blob(content)
    raw = blob.serialize()
    restored = Blob.from_bytes(raw)
    assert restored.content == content


def test_blob_hash_is_deterministic():
    blob = Blob(b"same content")
    assert blob.hash() == blob.hash()


def test_tree_roundtrip():
    blob = Blob(b"data")
    blob_hash = blob.hash()
    entry = TreeEntry(name="file.txt", hash=blob_hash, mode=0o100644, object_type="blob")
    tree = Tree([entry])
    raw = tree.serialize()
    restored = Tree.from_bytes(raw)
    assert len(restored.entries) == 1
    assert restored.entries[0].name == "file.txt"
    assert restored.entries[0].hash == blob_hash


def test_tree_entries_are_sorted():
    entries = [
        TreeEntry(name="z.txt", hash="b" * 64, mode=0o100644, object_type="blob"),
        TreeEntry(name="a.txt", hash="a" * 64, mode=0o100644, object_type="blob"),
    ]
    tree = Tree(entries)
    assert tree.entries[0].name == "a.txt"
    assert tree.entries[1].name == "z.txt"


def test_commit_roundtrip():
    now = time.time()
    commit = Commit(
        tree="a" * 64,
        parents=["b" * 64],
        author="Alice <alice@example.com>",
        author_ts=now,
        committer="Alice <alice@example.com>",
        committer_ts=now,
        message="test commit",
        intent={"type": "feat", "scope": "auth", "breaking": False},
    )
    raw = commit.serialize()
    restored = Commit.from_bytes(raw)
    assert restored.message == "test commit"
    assert restored.intent_type == "feat"
    assert restored.parents == ["b" * 64]


def test_annotation_roundtrip():
    now = time.time()
    ann = Annotation(
        file_path="src/main.py",
        line_start=10,
        line_end=10,
        commit_hash="c" * 64,
        annotation_type="warning",
        text="This is dangerous",
        author="Bob <bob@example.com>",
        timestamp=now,
    )
    raw = ann.serialize()
    restored = Annotation.from_bytes(raw)
    assert restored.text == "This is dangerous"
    assert restored.line_start == 10
    assert restored.annotation_type == "warning"
