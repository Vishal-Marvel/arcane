"""ObjectStore — SHA-256 content-addressed storage for all arc objects."""

from __future__ import annotations

from pathlib import Path

from arcane.core.objects.base import PREFIX_TO_TYPE, ArcObject
from arcane.core.objects.annotation import Annotation
from arcane.core.objects.blob import Blob
from arcane.core.objects.commit import Commit
from arcane.core.objects.tree import Tree
from arcane.utils.fs import atomic_write
from arcane.utils.hashing import object_path_parts

_TYPE_MAP = {
    "blob": Blob,
    "tree": Tree,
    "commit": Commit,
    "annotation": Annotation,
}


class ObjectNotFoundError(Exception):
    pass


class ObjectStore:
    """Reads and writes arc objects to .arcane/objects/ using fan-out layout.

    Layout: .arcane/objects/AB/CDEF... (first 2 hex chars as directory).
    All objects are stored as: 1-byte type prefix + zlib-compressed msgpack.
    """

    def __init__(self, objects_dir: Path) -> None:
        self.objects_dir = objects_dir

    def _path(self, full_hash: str) -> Path:
        prefix, rest = object_path_parts(full_hash)
        return self.objects_dir / prefix / rest

    def exists(self, full_hash: str) -> bool:
        return self._path(full_hash).exists()

    def write(self, obj: ArcObject) -> str:
        """Serialize and store an object. Returns its SHA-256 hash."""
        data = obj.serialize()
        full_hash = obj.hash()
        path = self._path(full_hash)
        if not path.exists():
            atomic_write(path, data)
        return full_hash

    def read_raw(self, full_hash: str) -> bytes:
        path = self._path(full_hash)
        if not path.exists():
            raise ObjectNotFoundError(f"Object not found: {full_hash}")
        return path.read_bytes()

    def read(self, full_hash: str) -> Blob | Tree | Commit | Annotation:
        """Read and deserialize an object by hash. Returns a typed object."""
        raw = self.read_raw(full_hash)
        type_byte = raw[:1]
        obj_type = PREFIX_TO_TYPE.get(type_byte)
        if obj_type is None:
            raise ValueError(f"Unknown object type prefix: {type_byte!r}")
        klass = _TYPE_MAP.get(obj_type)
        if klass is None:
            raise ValueError(f"No class registered for type: {obj_type}")
        return klass.from_bytes(raw)  # type: ignore[union-attr]

    def read_blob(self, full_hash: str) -> Blob:
        obj = self.read(full_hash)
        if not isinstance(obj, Blob):
            raise TypeError(f"Expected Blob, got {type(obj).__name__}")
        return obj

    def read_tree(self, full_hash: str) -> Tree:
        obj = self.read(full_hash)
        if not isinstance(obj, Tree):
            raise TypeError(f"Expected Tree, got {type(obj).__name__}")
        return obj

    def read_commit(self, full_hash: str) -> Commit:
        obj = self.read(full_hash)
        if not isinstance(obj, Commit):
            raise TypeError(f"Expected Commit, got {type(obj).__name__}")
        return obj

    def read_annotation(self, full_hash: str) -> Annotation:
        obj = self.read(full_hash)
        if not isinstance(obj, Annotation):
            raise TypeError(f"Expected Annotation, got {type(obj).__name__}")
        return obj

    def write_raw(self, obj_type: str, data: bytes, full_hash: str) -> None:
        """Write pre-built raw bytes under a known hash (used for dep_snapshot)."""
        path = self._path(full_hash)
        if not path.exists():
            atomic_write(path, data)
