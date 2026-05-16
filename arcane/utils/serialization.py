"""msgpack + zlib serialization for arc objects."""

import zlib

import msgpack


def encode(data: dict) -> bytes:  # type: ignore[type-arg]
    """Serialize a dict to zlib-compressed msgpack bytes."""
    packed = msgpack.packb(data, use_bin_type=True)
    return zlib.compress(packed)


def decode(raw: bytes) -> dict:  # type: ignore[type-arg]
    """Deserialize zlib-compressed msgpack bytes to a dict."""
    unpacked = zlib.decompress(raw)
    result = msgpack.unpackb(unpacked, raw=False)
    if not isinstance(result, dict):
        raise ValueError(f"Expected dict from msgpack, got {type(result)}")
    return result  # type: ignore[return-value]
