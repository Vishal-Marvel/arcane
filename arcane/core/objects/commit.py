"""Commit object — stores a snapshot pointer plus metadata."""

from __future__ import annotations

from arcane.core.objects.base import ArcObject


class Commit(ArcObject):
    """A commit points to a root Tree and carries full metadata.

    Extends the standard Git commit model with:
    - intent: CIT structured intent tag
    - dep_snapshot_hash: DAC dependency graph snapshot
    - annotation_refs: LLA annotation object hashes created at this commit
    """

    object_type = "commit"

    def __init__(
        self,
        tree: str,
        parents: list[str],
        author: str,
        author_ts: float,
        committer: str,
        committer_ts: float,
        message: str,
        intent: dict | None = None,  # type: ignore[type-arg]
        dep_snapshot_hash: str | None = None,
        annotation_refs: list[str] | None = None,
    ) -> None:
        self.tree = tree
        self.parents = parents
        self.author = author
        self.author_ts = author_ts
        self.committer = committer
        self.committer_ts = committer_ts
        self.message = message
        self.intent = intent or {"type": "chore", "scope": None, "breaking": False}
        self.dep_snapshot_hash = dep_snapshot_hash
        self.annotation_refs = annotation_refs or []

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "type": "commit",
            "tree": self.tree,
            "parents": self.parents,
            "author": self.author,
            "author_ts": self.author_ts,
            "committer": self.committer,
            "committer_ts": self.committer_ts,
            "message": self.message,
            "intent": self.intent,
            "dep_snapshot_hash": self.dep_snapshot_hash,
            "annotation_refs": self.annotation_refs,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Commit":  # type: ignore[type-arg]
        return cls(
            tree=d["tree"],
            parents=d["parents"],
            author=d["author"],
            author_ts=d["author_ts"],
            committer=d["committer"],
            committer_ts=d["committer_ts"],
            message=d["message"],
            intent=d.get("intent"),
            dep_snapshot_hash=d.get("dep_snapshot_hash"),
            annotation_refs=d.get("annotation_refs", []),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Commit":
        d = cls.deserialize(raw)
        return cls.from_dict(d)

    @property
    def short_hash(self) -> str:
        return self.hash()[:8]

    @property
    def intent_type(self) -> str:
        return self.intent.get("type", "chore")  # type: ignore[union-attr]
