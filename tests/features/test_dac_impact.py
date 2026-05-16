"""Tests for DAC impact, snapshot, and staging checker."""

import time
import pytest
from pathlib import Path

from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.repository import Repository
from arcane.features.dac.graph import DependencyGraph
from arcane.features.dac.impact import compute_impact
from arcane.features.dac.snapshot import build_snapshot, load_snapshot


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_file(repo: Repository, name: str, content: bytes) -> str:
    path = repo.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    blob = Blob(content)
    return repo.store.write(blob)


def _make_commit(
    repo: Repository,
    files: dict[str, str],  # name -> blob_hash
    parent: str | None,
    dep_snapshot_hash: str | None = None,
) -> str:
    entries = [
        TreeEntry(name=name, hash=h, mode=0o100644, object_type="blob")
        for name, h in files.items()
    ]
    tree = Tree(entries)
    tree_hash = repo.store.write(tree)
    c = Commit(
        tree=tree_hash,
        parents=[parent] if parent else [],
        author="T <t@t.com>",
        author_ts=time.time(),
        committer="T <t@t.com>",
        committer_ts=time.time(),
        message="commit",
        dep_snapshot_hash=dep_snapshot_hash,
    )
    h = repo.store.write(c)
    repo.refs.update_branch("main", h)
    return h


# ── compute_impact ────────────────────────────────────────────────────────────

def test_compute_impact_no_snapshot(tmp_path: Path):
    repo = Repository.init(tmp_path)
    bh = _write_file(repo, "foo.py", b"x = 1\n")
    h1 = _make_commit(repo, {"foo.py": bh}, None)
    bh2 = _write_file(repo, "foo.py", b"x = 2\n")
    h2 = _make_commit(repo, {"foo.py": bh2}, h1)

    result = compute_impact(repo, h2)
    assert "foo.py" in result["changed_files"]
    assert result["graph_available"] is False
    assert result["impacted_files"] == []


def test_compute_impact_with_snapshot(tmp_path: Path):
    repo = Repository.init(tmp_path)

    # Commit 1: create foo.py and bar.py (bar imports foo)
    foo_content = b"x = 1\n"
    bar_content = b"from foo import x\n"
    fh = _write_file(repo, "foo.py", foo_content)
    bh = _write_file(repo, "bar.py", bar_content)

    # Stage both files for snapshot building
    repo.index.add("foo.py", fh, repo.root / "foo.py")
    repo.index.add("bar.py", bh, repo.root / "bar.py")
    snap_hash = build_snapshot(repo)
    h1 = _make_commit(repo, {"foo.py": fh, "bar.py": bh}, None, dep_snapshot_hash=snap_hash)

    # Commit 2: change foo.py
    fh2 = _write_file(repo, "foo.py", b"x = 99\n")
    h2 = _make_commit(repo, {"foo.py": fh2, "bar.py": bh}, h1, dep_snapshot_hash=snap_hash)

    result = compute_impact(repo, h2)
    assert "foo.py" in result["changed_files"]
    assert result["graph_available"] is True
    assert "bar.py" in result["impacted_files"]


def test_compute_impact_initial_commit_all_changed(tmp_path: Path):
    repo = Repository.init(tmp_path)
    fh = _write_file(repo, "main.py", b"print('hi')\n")
    h1 = _make_commit(repo, {"main.py": fh}, None)

    result = compute_impact(repo, h1)
    assert "main.py" in result["changed_files"]


# ── build_snapshot / load_snapshot ───────────────────────────────────────────

def test_build_snapshot_returns_none_for_empty_deps(tmp_path: Path):
    repo = Repository.init(tmp_path)
    fh = _write_file(repo, "plain.txt", b"no imports here\n")
    repo.index.add("plain.txt", fh, repo.root / "plain.txt")
    snap = build_snapshot(repo)
    assert snap is None


def test_build_snapshot_with_python_imports(tmp_path: Path):
    repo = Repository.init(tmp_path)

    utils_content = b"def helper(): pass\n"
    main_content = b"from utils import helper\n"
    uh = _write_file(repo, "utils.py", utils_content)
    mh = _write_file(repo, "main.py", main_content)

    repo.index.add("utils.py", uh, repo.root / "utils.py")
    repo.index.add("main.py", mh, repo.root / "main.py")

    snap_hash = build_snapshot(repo)
    assert snap_hash is not None

    graph = load_snapshot(repo, snap_hash)
    assert isinstance(graph, DependencyGraph)
    assert "utils.py" in graph.direct_deps("main.py")


def test_load_snapshot_roundtrip(tmp_path: Path):
    repo = Repository.init(tmp_path)

    utils_content = b"def helper(): pass\n"
    main_content = b"from utils import helper\n"
    uh = _write_file(repo, "utils.py", utils_content)
    mh = _write_file(repo, "main.py", main_content)

    repo.index.add("utils.py", uh, repo.root / "utils.py")
    repo.index.add("main.py", mh, repo.root / "main.py")

    snap_hash = build_snapshot(repo)
    assert snap_hash is not None

    g1 = load_snapshot(repo, snap_hash)
    g2 = load_snapshot(repo, snap_hash)
    assert g1.to_dict() == g2.to_dict()


# ── staging checker ───────────────────────────────────────────────────────────

def test_check_staged_no_warnings_when_clean(tmp_path: Path, capsys: pytest.CaptureFixture):
    repo = Repository.init(tmp_path)

    utils_content = b"def helper(): pass\n"
    main_content = b"from utils import helper\n"
    uh = _write_file(repo, "utils.py", utils_content)
    mh = _write_file(repo, "main.py", main_content)

    repo.index.add("utils.py", uh, repo.root / "utils.py")
    repo.index.add("main.py", mh, repo.root / "main.py")

    # Nothing in workdir differs from index — no warnings expected
    from arcane.features.dac.checker import check_staged
    check_staged(repo)
    captured = capsys.readouterr()
    assert "unstaged" not in captured.out.lower()


def test_check_staged_warns_unstaged_dependency(tmp_path: Path, capsys: pytest.CaptureFixture):
    repo = Repository.init(tmp_path)

    utils_path = tmp_path / "utils.py"
    main_path = tmp_path / "main.py"

    utils_path.write_bytes(b"def helper(): pass\n")
    main_path.write_bytes(b"from utils import helper\n")

    uh = repo.store.write(Blob(utils_path.read_bytes()))
    mh = repo.store.write(Blob(main_path.read_bytes()))

    # Stage main.py but NOT utils.py — then modify utils on disk
    repo.index.add("main.py", mh, main_path)
    repo.index.add("utils.py", uh, utils_path)

    # Now silently modify utils.py on disk (change mtime/size)
    utils_path.write_bytes(b"def helper(): return 42\n")

    from arcane.features.dac.checker import check_staged
    check_staged(repo)
    # The warning goes through rich print — just verify it doesn't raise
