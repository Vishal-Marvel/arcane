"""DAC — Impact radius calculator and renderer."""

from __future__ import annotations

from arcane.core.diff import _flatten_tree
from arcane.core.repository import Repository
from arcane.features.dac.snapshot import load_snapshot


def compute_impact(repo: Repository, commit_hash: str) -> dict:  # type: ignore[type-arg]
    """Compute the impact radius of a commit.

    Returns a dict with:
      - changed_files: files directly changed in the commit
      - impacted_files: files transitively affected (import the changed files)
      - graph_available: bool (False if no dep snapshot for this commit)
    """
    commit = repo.store.read_commit(commit_hash)

    # Find changed files vs parent
    changed_files: set[str] = set()
    if commit.parents:
        parent = repo.store.read_commit(commit.parents[0])
        parent_flat = _flatten_tree(repo.store, parent.tree, "")
    else:
        parent_flat = {}

    current_flat = _flatten_tree(repo.store, commit.tree, "")

    all_paths = set(parent_flat) | set(current_flat)
    for path in all_paths:
        if parent_flat.get(path) != current_flat.get(path):
            changed_files.add(path)

    if not commit.dep_snapshot_hash:
        return {
            "changed_files": sorted(changed_files),
            "impacted_files": [],
            "graph_available": False,
        }

    graph = load_snapshot(repo, commit.dep_snapshot_hash)
    impacted = graph.transitive_dependents(changed_files)

    return {
        "changed_files": sorted(changed_files),
        "impacted_files": sorted(impacted),
        "graph_available": True,
    }
