"""Index — the staging area, stored as a lockfile-protected msgpack list."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from arcane.utils.fs import atomic_write, locked
from arcane.utils import serialization


@dataclass
class IndexEntry:
    path: str       # repo-relative, forward slashes
    hash: str       # blob SHA-256 hash
    mode: int       # Unix mode (e.g. 0o100644)
    size: int       # file size in bytes
    mtime: float    # modification time (Unix float, for change detection)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "path": self.path,
            "hash": self.hash,
            "mode": self.mode,
            "size": self.size,
            "mtime": self.mtime,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IndexEntry":  # type: ignore[type-arg]
        return cls(
            path=d["path"],
            hash=d["hash"],
            mode=d["mode"],
            size=d["size"],
            mtime=d["mtime"],
        )


class Index:
    """Manages the staging area at .arcane/index.

    The index is a msgpack-serialized list of IndexEntry dicts, zlib-compressed.
    Writes are protected by a lockfile (.arcane/index.lock).
    """

    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.lock_path = index_path.with_suffix(".lock")
        self._entries: dict[str, IndexEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        raw = self.index_path.read_bytes()
        if not raw:
            return
        data = serialization.decode(raw)
        entries_raw = data.get("entries", [])
        self._entries = {
            e["path"]: IndexEntry.from_dict(e) for e in entries_raw
        }

    def _save(self) -> None:
        data = {"entries": [e.to_dict() for e in self._entries.values()]}
        atomic_write(self.index_path, serialization.encode(data))

    # ── Mutations (all require lock) ─────────────────────────────────────────

    def add(self, path: str, blob_hash: str, file_path: Path) -> None:
        """Stage a file: add or update its IndexEntry."""
        stat = file_path.stat()
        with locked(self.lock_path):
            self._load()
            self._entries[path] = IndexEntry(
                path=path,
                hash=blob_hash,
                mode=0o100644,
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
            self._save()

    def remove(self, path: str) -> None:
        """Unstage a file (remove from index)."""
        with locked(self.lock_path):
            self._load()
            if path not in self._entries:
                raise KeyError(f"'{path}' is not in the index")
            del self._entries[path]
            self._save()

    # ── Reads ────────────────────────────────────────────────────────────────

    def get(self, path: str) -> IndexEntry | None:
        return self._entries.get(path)

    def all_entries(self) -> list[IndexEntry]:
        return list(self._entries.values())

    def paths(self) -> set[str]:
        return set(self._entries.keys())

    def __contains__(self, path: str) -> bool:
        return path in self._entries

    def diff_vs_workdir(self, repo_root: Path) -> dict[str, str]:
        """Return {path: status} for files that differ between index and workdir.

        Status values: 'M' (modified), 'D' (deleted in workdir).
        """
        result: dict[str, str] = {}
        for path, entry in self._entries.items():
            abs_path = repo_root / path.replace("/", "\\")
            if not abs_path.exists():
                result[path] = "D"
            elif abs_path.stat().st_mtime != entry.mtime or abs_path.stat().st_size != entry.size:
                result[path] = "M"
        return result

    def untracked_files(self, repo_root: Path, arcane_dir: Path) -> list[str]:
        """Return repo-relative paths of files in the workdir not in the index."""
        untracked = []
        for abs_path in sorted(repo_root.rglob("*")):
            if abs_path.is_dir():
                continue
            # Skip files inside .arcane/
            try:
                abs_path.relative_to(arcane_dir)
                continue
            except ValueError:
                pass
            rel = abs_path.relative_to(repo_root).as_posix()
            if rel not in self._entries:
                untracked.append(rel)
        return untracked
