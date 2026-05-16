"""Repository — the central context object for an arc repository."""

from __future__ import annotations

from pathlib import Path

from arcane.core.index import Index
from arcane.core.refs import RefsManager
from arcane.core.store import ObjectStore
from arcane.utils.fs import ensure_dir, atomic_write_text

ARCANE_DIR = ".arcane"


class NotARepositoryError(Exception):
    pass


class Repository:
    """Holds references to all core subsystems for an arc repository.

    All CLI commands obtain a Repository via Repository.discover() and pass
    it down to plumbing functions — no subsystem is accessed directly from CLI.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.arcane_dir = root / ARCANE_DIR
        self.store = ObjectStore(self.arcane_dir / "objects")
        self.refs = RefsManager(self.arcane_dir)
        self.index = Index(self.arcane_dir / "index")

    # ── Discovery ────────────────────────────────────────────────────────────

    @classmethod
    def discover(cls, start: Path) -> "Repository":
        """Walk up from `start` until a .arcane directory is found.

        Raises NotARepositoryError if no repository is found.
        """
        current = start.resolve()
        while True:
            candidate = current / ARCANE_DIR
            if candidate.is_dir():
                return cls(current)
            parent = current.parent
            if parent == current:
                raise NotARepositoryError(
                    "Not an arc repository (no .arcane directory found). "
                    "Run 'arc init' to create one."
                )
            current = parent

    # ── Initialisation ───────────────────────────────────────────────────────

    @classmethod
    def init(cls, path: Path) -> "Repository":
        """Create a new repository at `path`. Raises if one already exists."""
        arcane_dir = path / ARCANE_DIR
        if arcane_dir.exists():
            raise FileExistsError(f"Repository already exists at {arcane_dir}")

        ensure_dir(arcane_dir / "objects")
        ensure_dir(arcane_dir / "refs" / "heads")
        ensure_dir(arcane_dir / "refs" / "tags")
        ensure_dir(arcane_dir / "annotations")

        atomic_write_text(arcane_dir / "HEAD", "ref: refs/heads/main\n")

        return cls(path)

    # ── Config helpers ───────────────────────────────────────────────────────

    @property
    def config_path(self) -> Path:
        return self.arcane_dir / "config"

    def get_author(self) -> str:
        """Return 'Name <email>' from config, or a sensible default."""
        if self.config_path.exists():
            for line in self.config_path.read_text().splitlines():
                if line.startswith("author="):
                    return line[len("author="):].strip()
        import os
        name = os.environ.get("ARC_AUTHOR_NAME", os.environ.get("USER", "unknown"))
        email = os.environ.get("ARC_AUTHOR_EMAIL", f"{name}@localhost")
        return f"{name} <{email}>"

    # ── Merge state ──────────────────────────────────────────────────────────

    @property
    def merge_head_path(self) -> Path:
        return self.arcane_dir / "MERGE_HEAD"

    def is_merging(self) -> bool:
        return self.merge_head_path.exists()

    def set_merge_head(self, commit_hash: str) -> None:
        atomic_write_text(self.merge_head_path, f"{commit_hash}\n")

    def clear_merge_head(self) -> None:
        if self.merge_head_path.exists():
            self.merge_head_path.unlink()
