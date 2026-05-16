"""Annotation object — a line-level note stored in the object store."""

from __future__ import annotations

from arcane.core.objects.base import ArcObject


class Annotation(ArcObject):
    """Stores a user-authored note attached to a line range in a file.

    The line numbers (line_start, line_end) refer to the file at commit_hash.
    Current line positions are computed at read time by the LLA tracker.
    """

    object_type = "annotation"

    def __init__(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        commit_hash: str,
        annotation_type: str,
        text: str,
        author: str,
        timestamp: float,
        parent_id: str | None = None,
    ) -> None:
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.commit_hash = commit_hash
        self.annotation_type = annotation_type
        self.text = text
        self.author = author
        self.timestamp = timestamp
        self.parent_id = parent_id

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "type": "annotation",
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "commit_hash": self.commit_hash,
            "annotation_type": self.annotation_type,
            "text": self.text,
            "author": self.author,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":  # type: ignore[type-arg]
        return cls(
            file_path=d["file_path"],
            line_start=d["line_start"],
            line_end=d["line_end"],
            commit_hash=d["commit_hash"],
            annotation_type=d["annotation_type"],
            text=d["text"],
            author=d["author"],
            timestamp=d["timestamp"],
            parent_id=d.get("parent_id"),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Annotation":
        d = cls.deserialize(raw)
        return cls.from_dict(d)
