"""Tree object — stores a directory snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field

from arcane.core.objects.base import ArcObject


@dataclass
class TreeEntry:
    name: str       # basename of the file or subdirectory
    hash: str       # SHA-256 hash of the blob or subtree
    mode: int       # Unix mode (e.g. 0o100644 for regular file, 0o040000 for dir)
    object_type: str  # "blob" or "tree"

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "name": self.name,
            "hash": self.hash,
            "mode": self.mode,
            "object_type": self.object_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TreeEntry":  # type: ignore[type-arg]
        return cls(
            name=d["name"],
            hash=d["hash"],
            mode=d["mode"],
            object_type=d["object_type"],
        )


class Tree(ArcObject):
    """A tree stores a sorted list of TreeEntry records (files + subdirs)."""

    object_type = "tree"

    def __init__(self, entries: list[TreeEntry] | None = None) -> None:
        self.entries: list[TreeEntry] = sorted(
            entries or [], key=lambda e: e.name
        )

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "type": "tree",
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Tree":  # type: ignore[type-arg]
        return cls(entries=[TreeEntry.from_dict(e) for e in d["entries"]])

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Tree":
        d = cls.deserialize(raw)
        return cls.from_dict(d)

    def get(self, name: str) -> TreeEntry | None:
        for e in self.entries:
            if e.name == name:
                return e
        return None
