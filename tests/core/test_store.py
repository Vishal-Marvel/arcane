"""Tests for ObjectStore."""

import pytest
from pathlib import Path

from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.store import ObjectStore, ObjectNotFoundError


@pytest.fixture
def store(tmp_path: Path) -> ObjectStore:
    objects_dir = tmp_path / "objects"
    objects_dir.mkdir()
    return ObjectStore(objects_dir)


def test_write_and_read_blob(store: ObjectStore):
    blob = Blob(b"hello")
    h = store.write(blob)
    assert len(h) == 64  # SHA-256 hex
    restored = store.read_blob(h)
    assert restored.content == b"hello"


def test_write_is_idempotent(store: ObjectStore):
    blob = Blob(b"same content")
    h1 = store.write(blob)
    h2 = store.write(blob)
    assert h1 == h2


def test_read_nonexistent_raises(store: ObjectStore):
    with pytest.raises(ObjectNotFoundError):
        store.read("a" * 64)


def test_fan_out_layout(store: ObjectStore):
    blob = Blob(b"test")
    h = store.write(blob)
    expected = store.objects_dir / h[:2] / h[2:]
    assert expected.exists()


def test_exists(store: ObjectStore):
    blob = Blob(b"exists test")
    h = store.write(blob)
    assert store.exists(h)
    assert not store.exists("0" * 64)
