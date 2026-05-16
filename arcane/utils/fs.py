"""Safe filesystem helpers: atomic writes and lockfiles."""

import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def atomic_write(path: Path, data: bytes) -> None:
    """Write `data` to `path` atomically using a temp file + rename.

    Prevents partial writes from corrupting files on crash.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            os.replace(tmp_path_str, path)
        except PermissionError:
            # Windows fallback: unlink destination first then rename
            try:
                os.unlink(path)
            except OSError:
                pass
            os.rename(tmp_path_str, path)
    except Exception:
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Write a UTF-8 string to `path` atomically."""
    atomic_write(path, text.encode())


@contextmanager
def locked(lock_path: Path) -> Generator[None, None, None]:
    """Context manager that acquires an exclusive lockfile.

    Creates `lock_path`, yields, then removes it.
    Raises RuntimeError if the lock is already held.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_TEMPORARY", 0))
        os.close(fd)
    except FileExistsError:
        raise RuntimeError(
            f"Lock file exists: {lock_path}\n"
            "Another arc process may be running. If not, delete the lock file manually."
        ) from None
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_relative(repo_root: Path, abs_path: Path) -> str:
    """Return a repo-relative path string with forward slashes."""
    return abs_path.relative_to(repo_root).as_posix()
