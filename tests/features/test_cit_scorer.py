"""Tests for CIT debt scorer."""

import pytest
import time
from pathlib import Path

from arcane.core.objects.blob import Blob
from arcane.core.objects.tree import Tree
from arcane.core.objects.commit import Commit
from arcane.core.repository import Repository
from arcane.features.cit.scorer import compute_debt_score


def _make_commit(repo: Repository, intent_type: str, parent: str | None = None) -> str:
    empty_tree = Tree([])
    tree_hash = repo.store.write(empty_tree)
    parents = [parent] if parent else []
    c = Commit(
        tree=tree_hash,
        parents=parents,
        author="T <t@t.com>",
        author_ts=time.time(),
        committer="T <t@t.com>",
        committer_ts=time.time(),
        message=f"commit [{intent_type}]",
        intent={"type": intent_type, "scope": None, "breaking": False},
    )
    h = repo.store.write(c)
    repo.refs.update_branch("main", h)
    return h


def test_empty_repo_score(tmp_path: Path):
    repo = Repository.init(tmp_path)
    result = compute_debt_score(repo)
    assert result["score"] == 0


def test_healthy_repo(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h = _make_commit(repo, "feat")
    h = _make_commit(repo, "feat", h)
    h = _make_commit(repo, "refactor", h)
    result = compute_debt_score(repo)
    assert result["score"] < 30


def test_high_debt_repo(tmp_path: Path):
    repo = Repository.init(tmp_path)
    h = _make_commit(repo, "fix")
    for _ in range(8):
        h = _make_commit(repo, "debt", h)
    result = compute_debt_score(repo)
    assert result["score"] > 30
