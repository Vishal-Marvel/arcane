"""Integration tests: CIT, DAC, and LLA working through the full commit flow."""

import time
from pathlib import Path

import pytest

from arcane.core.objects.annotation import Annotation
from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree, TreeEntry
from arcane.core.repository import Repository
from arcane.features.cit.scorer import compute_debt_score
from arcane.features.dac.impact import compute_impact
from arcane.features.dac.snapshot import build_snapshot, load_snapshot
from arcane.features.lla.store import AnnotationStore
from arcane.features.lla.tracker import track_annotation


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_file(repo: Repository, name: str, content: bytes) -> str:
    path = repo.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    blob = Blob(content)
    return repo.store.write(blob)


def _commit(
    repo: Repository,
    files: dict[str, str],
    parent: str | None,
    intent_type: str = "feat",
    dep_snapshot_hash: str | None = None,
) -> str:
    entries = [
        TreeEntry(name=n, hash=h, mode=0o100644, object_type="blob")
        for n, h in files.items()
    ]
    tree_hash = repo.store.write(Tree(entries))
    c = Commit(
        tree=tree_hash,
        parents=[parent] if parent else [],
        author="T <t@t.com>",
        author_ts=time.time(),
        committer="T <t@t.com>",
        committer_ts=time.time(),
        message=f"[{intent_type}]",
        intent={"type": intent_type, "scope": None, "breaking": False},
        dep_snapshot_hash=dep_snapshot_hash,
    )
    h = repo.store.write(c)
    repo.refs.update_branch("main", h)
    return h


# ── CIT integration ───────────────────────────────────────────────────────────

def test_cit_debt_rises_with_debt_commits(tmp_path: Path):
    repo = Repository.init(tmp_path)

    fh = _write_file(repo, "a.py", b"x=1\n")
    h = _commit(repo, {"a.py": fh}, None, "feat")
    for _ in range(6):
        fh2 = _write_file(repo, "a.py", b"x=2\n")
        h = _commit(repo, {"a.py": fh2}, h, "debt")

    result = compute_debt_score(repo)
    assert result["score"] > 30
    assert result["total"] == 7


def test_cit_healthy_repo_low_debt(tmp_path: Path):
    repo = Repository.init(tmp_path)
    fh = _write_file(repo, "a.py", b"x=1\n")
    h = _commit(repo, {"a.py": fh}, None, "feat")
    for intent in ["feat", "feat", "refactor", "docs"]:
        fh2 = _write_file(repo, "a.py", b"x=2\n")
        h = _commit(repo, {"a.py": fh2}, h, intent)

    result = compute_debt_score(repo)
    assert result["score"] < 20


# ── DAC integration ───────────────────────────────────────────────────────────

def test_dac_impact_propagates_through_chain(tmp_path: Path):
    """A → B → C: changing A should flag B and C as impacted."""
    repo = Repository.init(tmp_path)

    a_content = b"def func_a(): pass\n"
    b_content = b"from a import func_a\ndef func_b(): func_a()\n"
    c_content = b"from b import func_b\nfunc_b()\n"

    ah = _write_file(repo, "a.py", a_content)
    bh = _write_file(repo, "b.py", b_content)
    ch = _write_file(repo, "c.py", c_content)

    repo.index.add("a.py", ah, repo.root / "a.py")
    repo.index.add("b.py", bh, repo.root / "b.py")
    repo.index.add("c.py", ch, repo.root / "c.py")

    snap = build_snapshot(repo)
    assert snap is not None

    h1 = _commit(repo, {"a.py": ah, "b.py": bh, "c.py": ch}, None, dep_snapshot_hash=snap)

    # Change a.py in second commit
    ah2 = _write_file(repo, "a.py", b"def func_a(): return 42\n")
    h2 = _commit(repo, {"a.py": ah2, "b.py": bh, "c.py": ch}, h1, dep_snapshot_hash=snap)

    result = compute_impact(repo, h2)
    assert "a.py" in result["changed_files"]
    assert result["graph_available"] is True
    assert "b.py" in result["impacted_files"]
    assert "c.py" in result["impacted_files"]


def test_dac_no_impact_for_leaf_file(tmp_path: Path):
    """Changing a file that nothing depends on has zero impacted files."""
    repo = Repository.init(tmp_path)

    ah = _write_file(repo, "a.py", b"x = 1\n")
    bh = _write_file(repo, "b.py", b"from a import x\n")

    repo.index.add("a.py", ah, repo.root / "a.py")
    repo.index.add("b.py", bh, repo.root / "b.py")
    snap = build_snapshot(repo)

    h1 = _commit(repo, {"a.py": ah, "b.py": bh}, None, dep_snapshot_hash=snap)

    # Change b.py — nothing imports b.py
    bh2 = _write_file(repo, "b.py", b"from a import x\nprint(x)\n")
    h2 = _commit(repo, {"a.py": ah, "b.py": bh2}, h1, dep_snapshot_hash=snap)

    result = compute_impact(repo, h2)
    assert "b.py" in result["changed_files"]
    assert "a.py" not in result["impacted_files"]


# ── LLA integration ───────────────────────────────────────────────────────────

def test_lla_annotation_survives_prepend(tmp_path: Path):
    """An annotation on line 1 should shift to line 2 after a line is prepended."""
    repo = Repository.init(tmp_path)
    ann_dir = repo.root / ".arcane" / "annotations"
    ann_store = AnnotationStore(ann_dir)

    fh1 = _write_file(repo, "foo.py", b"target_line\nother\n")
    h1 = _commit(repo, {"foo.py": fh1}, None)

    ann = Annotation(
        file_path="foo.py",
        line_start=1,
        line_end=1,
        commit_hash=h1,
        annotation_type="note",
        text="watch this",
        author="T <t@t.com>",
        timestamp=time.time(),
    )
    ann_hash = repo.store.write(ann)
    ann_store.add("foo.py", ann_hash)

    fh2 = _write_file(repo, "foo.py", b"new_first_line\ntarget_line\nother\n")
    h2 = _commit(repo, {"foo.py": fh2}, h1)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.current_line_start == 2
    assert not tracked.is_orphaned


def test_lla_annotation_orphaned_when_line_deleted(tmp_path: Path):
    repo = Repository.init(tmp_path)
    ann_dir = repo.root / ".arcane" / "annotations"
    ann_store = AnnotationStore(ann_dir)

    fh1 = _write_file(repo, "foo.py", b"keep\ndelete_me\nkeep2\n")
    h1 = _commit(repo, {"foo.py": fh1}, None)

    ann = Annotation(
        file_path="foo.py",
        line_start=2,
        line_end=2,
        commit_hash=h1,
        annotation_type="note",
        text="this line will vanish",
        author="T <t@t.com>",
        timestamp=time.time(),
    )
    ann_hash = repo.store.write(ann)
    ann_store.add("foo.py", ann_hash)

    fh2 = _write_file(repo, "foo.py", b"keep\nkeep2\n")
    h2 = _commit(repo, {"foo.py": fh2}, h1)

    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h2)
    assert tracked.is_orphaned


def test_lla_store_and_tracker_round_trip(tmp_path: Path):
    """Add annotation to store, track it, verify we get back the original object."""
    repo = Repository.init(tmp_path)
    ann_dir = repo.root / ".arcane" / "annotations"
    ann_store = AnnotationStore(ann_dir)

    fh = _write_file(repo, "notes.py", b"alpha\nbeta\ngamma\n")
    h1 = _commit(repo, {"notes.py": fh}, None)

    ann = Annotation(
        file_path="notes.py",
        line_start=2,
        line_end=2,
        commit_hash=h1,
        annotation_type="todo",
        text="clean this up",
        author="T <t@t.com>",
        timestamp=time.time(),
    )
    ann_hash = repo.store.write(ann)
    ann_store.add("notes.py", ann_hash)

    # Reload the annotation from store
    hashes = ann_store.list_for_file("notes.py")
    assert ann_hash in hashes

    loaded_ann = repo.store.read_annotation(ann_hash)
    assert loaded_ann.text == "clean this up"
    assert loaded_ann.line_start == 2

    tracked = track_annotation(repo, loaded_ann, ann_hash, target_commit_hash=h1)
    assert tracked.current_line_start == 2
    assert not tracked.is_orphaned


# ── Cross-feature integration ─────────────────────────────────────────────────

def test_commit_carries_intent_and_dep_snapshot(tmp_path: Path):
    """A commit should record both CIT intent and DAC snapshot hash."""
    repo = Repository.init(tmp_path)

    ah = _write_file(repo, "a.py", b"x = 1\n")
    bh = _write_file(repo, "b.py", b"from a import x\n")

    repo.index.add("a.py", ah, repo.root / "a.py")
    repo.index.add("b.py", bh, repo.root / "b.py")
    snap = build_snapshot(repo)

    h = _commit(repo, {"a.py": ah, "b.py": bh}, None, intent_type="feat", dep_snapshot_hash=snap)

    loaded = repo.store.read_commit(h)
    assert loaded.intent_type == "feat"
    assert loaded.dep_snapshot_hash == snap


def test_multi_commit_workflow(tmp_path: Path):
    """Simulate a realistic multi-commit workflow and verify all features."""
    repo = Repository.init(tmp_path)

    # Commit 1: initial feature
    ah = _write_file(repo, "api.py", b"def get(): pass\n")
    mh = _write_file(repo, "main.py", b"from api import get\nget()\n")
    repo.index.add("api.py", ah, repo.root / "api.py")
    repo.index.add("main.py", mh, repo.root / "main.py")
    snap1 = build_snapshot(repo)
    h1 = _commit(repo, {"api.py": ah, "main.py": mh}, None, "feat", dep_snapshot_hash=snap1)

    # Commit 2: debt commit
    ah2 = _write_file(repo, "api.py", b"def get(): return None  # hack\n")
    h2 = _commit(repo, {"api.py": ah2, "main.py": mh}, h1, "debt", dep_snapshot_hash=snap1)

    # Commit 3: fix
    ah3 = _write_file(repo, "api.py", b"def get(): return {}\n")
    h3 = _commit(repo, {"api.py": ah3, "main.py": mh}, h2, "fix", dep_snapshot_hash=snap1)

    # Annotate a line in api.py at h1
    ann = Annotation(
        file_path="api.py",
        line_start=1,
        line_end=1,
        commit_hash=h1,
        annotation_type="review",
        text="check this endpoint",
        author="T <t@t.com>",
        timestamp=time.time(),
    )
    ann_hash = repo.store.write(ann)

    # CIT: should show low-ish debt (1 debt out of 3)
    score_result = compute_debt_score(repo)
    assert score_result["total"] == 3

    # DAC: changing api.py should impact main.py
    impact = compute_impact(repo, h2)
    assert "api.py" in impact["changed_files"]
    assert "main.py" in impact["impacted_files"]

    # LLA: annotation still tracks to line 1 (content changed but line exists)
    tracked = track_annotation(repo, ann, ann_hash, target_commit_hash=h3)
    assert not tracked.is_orphaned
