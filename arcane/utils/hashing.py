"""SHA-256 content-addressing helpers."""

import hashlib


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_str(text: str) -> str:
    """Return the hex SHA-256 digest of a UTF-8 string."""
    return sha256_bytes(text.encode())


def short_hash(full_hash: str, length: int = 8) -> str:
    """Return the first `length` characters of a hash for display."""
    return full_hash[:length]


def object_path_parts(full_hash: str) -> tuple[str, str]:
    """Split a hash into (directory_prefix, filename) for fan-out storage.

    e.g. 'abcdef1234...' -> ('ab', 'cdef1234...')
    Mirrors Git's .git/objects/AB/CDEF... layout.
    """
    return full_hash[:2], full_hash[2:]
