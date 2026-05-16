"""Integration test: full init → add → commit → log flow."""

import time
from pathlib import Path

import pytest

from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.repository import Repository
from arcane.core.diff import diff_index_vs_head


def test_init_creates_arcane_dir(tmp_path: Path):
    repo = Repository.init(tmp_path)
    assert (tmp_path / ".arcane").is_dir()
    assert (tmp_path / ".arcane" / "HEAD").exists()
    assert (tmp_path / ".arcane" / "refs" / "heads").is_dir()
    assert (tmp_path / ".arcane" / "objects").is_dir()


def test_full_commit_flow(tmp_path: Path):
    repo = Repository.init(tmp_path)

    # Write a file
    (tmp_path / "hello.txt").write_bytes(b"hello world\n")

    # Stage it
    blob = Blob(b"hello world\n")
    blob_hash = repo.store.write(blob)
    repo.index.add("hello.txt", blob_hash, tmp_path / "hello.txt")

    assert "hello.txt" in repo.index.paths()

    # Build tree and commit
    tree = Tree([TreeEntry(name="hello.txt", hash=blob_hash, mode=0o100644, object_type="blob")])
    tree_hash = repo.store.write(tree)

    now = time.time()
    commit = Commit(
        tree=tree_hash,
        parents=[],
        author="Test <test@test.com>",
        author_ts=now,
        committer="Test <test@test.com>",
        committer_ts=now,
        message="Add hello.txt",
        intent={"type": "feat", "scope": None, "breaking": False},
    )
    commit_hash = repo.store.write(commit)
    repo.refs.update_branch("main", commit_hash)

    # Verify HEAD resolves
    assert repo.refs.resolve_head() == commit_hash

    # Verify commit is readable
    loaded = repo.store.read_commit(commit_hash)
    assert loaded.message == "Add hello.txt"
    assert loaded.intent_type == "feat"

    # Verify no staged diffs after commit (index matches HEAD)
    # (index still has the entry, HEAD now also has it — so diff should be empty)
    diffs = diff_index_vs_head(repo.store, repo.refs, repo.index)
    assert diffs == []


def test_second_commit_has_parent(tmp_path: Path):
    repo = Repository.init(tmp_path)

    def make_commit(msg: str, parent: str | None) -> str:
        tree = Tree([])
        tree_hash = repo.store.write(tree)
        now = time.time()
        c = Commit(
            tree=tree_hash,
            parents=[parent] if parent else [],
            author="T <t@t.com>",
            author_ts=now,
            committer="T <t@t.com>",
            committer_ts=now,
            message=msg,
        )
        h = repo.store.write(c)
        repo.refs.update_branch("main", h)
        return h

    h1 = make_commit("first", None)
    h2 = make_commit("second", h1)

    c2 = repo.store.read_commit(h2)
    assert c2.parents == [h1]


def test_branch_creation_and_resolution(tmp_path: Path):
    repo = Repository.init(tmp_path)
    tree = Tree([])
    tree_hash = repo.store.write(tree)
    now = time.time()
    c = Commit(
        tree=tree_hash, parents=[], author="T <t@t.com>",
        author_ts=now, committer="T <t@t.com>", committer_ts=now, message="init"
    )
    main_hash = repo.store.write(c)
    repo.refs.update_branch("main", main_hash)

    # Create feature branch
    repo.refs.update_branch("feature/auth", main_hash)
    assert repo.refs.resolve_branch("feature/auth") == main_hash
    assert "feature/auth" in repo.refs.list_branches()
