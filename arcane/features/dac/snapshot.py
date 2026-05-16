"""DAC — Build and store DependencySnapshot objects."""

from __future__ import annotations

import time
import zlib
from pathlib import Path

import msgpack

from arcane.core.objects.base import OBJECT_TYPE_PREFIX
from arcane.core.repository import Repository
from arcane.features.dac.graph import DependencyGraph
from arcane.features.dac.parser import parse_dependencies
from arcane.utils.hashing import sha256_bytes


def build_graph_from_workdir(repo: Repository) -> DependencyGraph:
    """Scan all tracked files in the repo workdir and build a DependencyGraph."""
    graph = DependencyGraph()
    for entry in repo.index.all_entries():
        abs_path = repo.root / entry.path.replace("/", "\\")
        if not abs_path.exists():
            continue
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            continue
        deps = parse_dependencies(abs_path, content, repo.root)
        for dep in deps:
            graph.add_edge(entry.path, dep)
    return graph


def build_snapshot(repo: Repository) -> str | None:
    """Build a DependencySnapshot, write it to the object store, return its hash.

    Returns None if no dependencies were found (avoids storing empty snapshots).
    """
    head = repo.refs.resolve_head()
    graph = build_graph_from_workdir(repo)

    if not graph.edges:
        return None

    data = {
        "type": "dep_snapshot",
        "commit_hash": head or "",
        "timestamp": time.time(),
        "edges": graph.to_dict(),
    }
    packed = msgpack.packb(data, use_bin_type=True)
    compressed = zlib.compress(packed)
    prefix = OBJECT_TYPE_PREFIX["dep_snapshot"]
    raw = prefix + compressed
    obj_hash = sha256_bytes(raw)
    repo.store.write_raw("dep_snapshot", raw, obj_hash)
    return obj_hash


def load_snapshot(repo: Repository, snapshot_hash: str) -> DependencyGraph:
    """Load a DependencyGraph from a stored dep_snapshot object."""
    raw = repo.store.read_raw(snapshot_hash)
    compressed = raw[1:]  # strip type prefix
    data = msgpack.unpackb(zlib.decompress(compressed), raw=False)
    return DependencyGraph.from_dict(data.get("edges", {}))
