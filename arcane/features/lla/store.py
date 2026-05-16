"""LLA — Annotation index store (.arcane/annotations/index.msgpack)."""

from __future__ import annotations

from pathlib import Path

from arcane.utils.fs import atomic_write, locked
from arcane.utils import serialization


class AnnotationStore:
    """Manages the annotation index: maps file_path -> [annotation_hashes].

    The index is stored at .arcane/annotations/index.msgpack.
    All mutations are atomic and lockfile-protected.
    """

    def __init__(self, annotations_dir: Path) -> None:
        self.index_path = annotations_dir / "index.msgpack"
        self.lock_path = annotations_dir / "index.lock"
        self._index: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        raw = self.index_path.read_bytes()
        if not raw:
            return
        data = serialization.decode(raw)
        self._index = {k: list(v) for k, v in data.items()}

    def _save(self) -> None:
        atomic_write(self.index_path, serialization.encode(self._index))

    def add(self, file_path: str, annotation_hash: str) -> None:
        with locked(self.lock_path):
            self._load()
            if file_path not in self._index:
                self._index[file_path] = []
            if annotation_hash not in self._index[file_path]:
                self._index[file_path].append(annotation_hash)
            self._save()

    def remove(self, file_path: str, annotation_hash: str) -> None:
        with locked(self.lock_path):
            self._load()
            if file_path in self._index:
                try:
                    self._index[file_path].remove(annotation_hash)
                except ValueError:
                    pass
            self._save()

    def list_for_file(self, file_path: str) -> list[str]:
        """Return all annotation hashes for a given file."""
        return list(self._index.get(file_path, []))

    def all_files(self) -> list[str]:
        return list(self._index.keys())

    def all_hashes(self) -> list[str]:
        return [h for hashes in self._index.values() for h in hashes]
