"""Blob object — stores raw file content."""

from __future__ import annotations

from arcane.core.objects.base import ArcObject


class Blob(ArcObject):
    """A blob stores the raw bytes of a single file."""

    object_type = "blob"

    def __init__(self, content: bytes) -> None:
        self.content = content

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {"type": "blob", "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> "Blob":  # type: ignore[type-arg]
        return cls(content=d["content"])

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Blob":
        d = cls.deserialize(raw)
        return cls.from_dict(d)

    def decode(self) -> str:
        """Return content as a UTF-8 string (best-effort)."""
        return self.content.decode(errors="replace")
