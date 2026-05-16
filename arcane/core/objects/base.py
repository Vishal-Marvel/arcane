"""Base class for all arc object types."""

from __future__ import annotations

from abc import ABC, abstractmethod

from arcane.utils import serialization
from arcane.utils.hashing import sha256_bytes


# 1-byte type prefix written before the msgpack payload on disk.
# Allows fast type dispatch without full deserialization.
OBJECT_TYPE_PREFIX: dict[str, bytes] = {
    "blob": b"\x01",
    "tree": b"\x02",
    "commit": b"\x03",
    "annotation": b"\x04",
    "dep_snapshot": b"\x05",
}

PREFIX_TO_TYPE: dict[bytes, str] = {v: k for k, v in OBJECT_TYPE_PREFIX.items()}


class ArcObject(ABC):
    """Abstract base for all objects stored in the object store."""

    object_type: str  # must be set by subclasses

    @abstractmethod
    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialize to a plain dict for msgpack encoding."""

    def serialize(self) -> bytes:
        """Return the on-disk bytes: 1-byte type prefix + compressed msgpack payload."""
        prefix = OBJECT_TYPE_PREFIX[self.object_type]
        payload = serialization.encode(self.to_dict())
        return prefix + payload

    def hash(self) -> str:
        """Return the SHA-256 hex digest of the serialized bytes."""
        return sha256_bytes(self.serialize())

    @classmethod
    def deserialize(cls, raw: bytes) -> dict:  # type: ignore[type-arg]
        """Strip the type prefix and decode the msgpack payload."""
        return serialization.decode(raw[1:])
