"""Tests for RefsManager."""

import pytest
from pathlib import Path

from arcane.core.refs import RefsManager
from arcane.utils.fs import ensure_dir


@pytest.fixture
def refs(tmp_path: Path) -> RefsManager:
    arcane_dir = tmp_path / ".arcane"
    ensure_dir(arcane_dir / "refs" / "heads")
    ensure_dir(arcane_dir / "refs" / "tags")
    (arcane_dir / "HEAD").write_text("ref: refs/heads/main\n")
    return RefsManager(arcane_dir)


def test_resolve_head_empty(refs: RefsManager):
    assert refs.resolve_head() is None


def test_update_and_resolve_branch(refs: RefsManager):
    h = "a" * 64
    refs.update_branch("main", h)
    assert refs.resolve_branch("main") == h
    assert refs.resolve_head() == h


def test_current_branch(refs: RefsManager):
    assert refs.current_branch() == "main"


def test_create_and_resolve_tag(refs: RefsManager):
    refs.update_branch("main", "b" * 64)
    refs.create_tag("v1.0", "b" * 64)
    assert refs.resolve_tag("v1.0") == "b" * 64


def test_duplicate_tag_raises(refs: RefsManager):
    refs.create_tag("v1.0", "a" * 64)
    with pytest.raises(ValueError):
        refs.create_tag("v1.0", "b" * 64)


def test_list_branches(refs: RefsManager):
    refs.update_branch("main", "a" * 64)
    refs.update_branch("dev", "b" * 64)
    assert "main" in refs.list_branches()
    assert "dev" in refs.list_branches()


def test_detached_head(refs: RefsManager):
    refs.set_head_detached("c" * 64)
    assert refs.is_detached()
    assert refs.current_branch() is None
    assert refs.resolve_head() == "c" * 64
