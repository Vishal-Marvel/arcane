"""Shared pytest fixtures for arcane tests."""

import pytest
from pathlib import Path

from arcane.core.repository import Repository


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Repository:
    """Create and return a fresh arc repository in a temp directory."""
    return Repository.init(tmp_path)


@pytest.fixture
def repo_with_commit(tmp_repo: Repository) -> tuple[Repository, str]:
    """Repo with a single committed file. Returns (repo, commit_hash)."""
    from arcane.core.objects.blob import Blob
    from arcane.core.objects.tree import Tree, TreeEntry
    from arcane.core.objects.commit import Commit
    import time

    blob = Blob(b"hello world\n")
    blob_hash = tmp_repo.store.write(blob)

    tree = Tree([TreeEntry(name="hello.txt", hash=blob_hash, mode=0o100644, object_type="blob")])
    tree_hash = tmp_repo.store.write(tree)

    commit = Commit(
        tree=tree_hash,
        parents=[],
        author="Test User <test@example.com>",
        author_ts=time.time(),
        committer="Test User <test@example.com>",
        committer_ts=time.time(),
        message="Initial commit",
        intent={"type": "feat", "scope": None, "breaking": False},
    )
    commit_hash = tmp_repo.store.write(commit)
    tmp_repo.refs.update_branch("main", commit_hash)

    return tmp_repo, commit_hash
