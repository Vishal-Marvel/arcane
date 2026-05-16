"""Tests for LLA AnnotationStore."""

import pytest
from pathlib import Path

from arcane.features.lla.store import AnnotationStore


@pytest.fixture
def annotation_store(tmp_path: Path) -> AnnotationStore:
    ann_dir = tmp_path / "annotations"
    ann_dir.mkdir()
    return AnnotationStore(ann_dir)


def test_empty_store_returns_empty_list(annotation_store: AnnotationStore):
    assert annotation_store.list_for_file("foo.py") == []


def test_add_and_list(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "abc123")
    assert annotation_store.list_for_file("foo.py") == ["abc123"]


def test_add_multiple_hashes_for_same_file(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "aaa")
    annotation_store.add("foo.py", "bbb")
    hashes = annotation_store.list_for_file("foo.py")
    assert "aaa" in hashes
    assert "bbb" in hashes
    assert len(hashes) == 2


def test_add_duplicate_hash_is_idempotent(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "abc123")
    annotation_store.add("foo.py", "abc123")
    assert annotation_store.list_for_file("foo.py") == ["abc123"]


def test_add_different_files(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "aaa")
    annotation_store.add("bar.py", "bbb")
    assert annotation_store.list_for_file("foo.py") == ["aaa"]
    assert annotation_store.list_for_file("bar.py") == ["bbb"]


def test_remove_existing_hash(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "aaa")
    annotation_store.add("foo.py", "bbb")
    annotation_store.remove("foo.py", "aaa")
    assert annotation_store.list_for_file("foo.py") == ["bbb"]


def test_remove_nonexistent_hash_is_silent(annotation_store: AnnotationStore):
    annotation_store.add("foo.py", "aaa")
    annotation_store.remove("foo.py", "nonexistent")  # should not raise
    assert annotation_store.list_for_file("foo.py") == ["aaa"]


def test_remove_from_nonexistent_file_is_silent(annotation_store: AnnotationStore):
    annotation_store.remove("ghost.py", "abc")  # should not raise


def test_all_files(annotation_store: AnnotationStore):
    annotation_store.add("a.py", "h1")
    annotation_store.add("b.py", "h2")
    assert set(annotation_store.all_files()) == {"a.py", "b.py"}


def test_all_hashes(annotation_store: AnnotationStore):
    annotation_store.add("a.py", "h1")
    annotation_store.add("a.py", "h2")
    annotation_store.add("b.py", "h3")
    assert set(annotation_store.all_hashes()) == {"h1", "h2", "h3"}


def test_persistence_across_instances(tmp_path: Path):
    ann_dir = tmp_path / "annotations"
    ann_dir.mkdir()

    s1 = AnnotationStore(ann_dir)
    s1.add("foo.py", "abc")

    s2 = AnnotationStore(ann_dir)
    assert s2.list_for_file("foo.py") == ["abc"]
