"""RefsManager — manages branches, HEAD, and tags as plain text files."""

from __future__ import annotations

from pathlib import Path

from arcane.utils.fs import atomic_write_text


class RefsManager:
    """Manages all refs in .arcane/refs/ and .arcane/HEAD.

    Branches: .arcane/refs/heads/<name>  (plain UTF-8 hex hash)
    Tags:     .arcane/refs/tags/<name>   (plain UTF-8 hex hash)
    HEAD:     .arcane/HEAD               (either "ref: refs/heads/<name>" or raw hash)
    """

    def __init__(self, arcane_dir: Path) -> None:
        self.arcane_dir = arcane_dir
        self.heads_dir = arcane_dir / "refs" / "heads"
        self.tags_dir = arcane_dir / "refs" / "tags"
        self.head_path = arcane_dir / "HEAD"

    # ── HEAD ────────────────────────────────────────────────────────────────

    def read_head_raw(self) -> str:
        """Return the raw content of HEAD (may be a ref or a hash)."""
        return self.head_path.read_text().strip()

    def is_detached(self) -> bool:
        return not self.read_head_raw().startswith("ref:")

    def current_branch(self) -> str | None:
        """Return the current branch name, or None if HEAD is detached."""
        raw = self.read_head_raw()
        if raw.startswith("ref: refs/heads/"):
            return raw[len("ref: refs/heads/"):]
        return None

    def resolve_head(self) -> str | None:
        """Resolve HEAD to a commit hash. Returns None for an empty repo."""
        raw = self.read_head_raw()
        if raw.startswith("ref:"):
            ref_path_str = raw[len("ref: "):].strip()
            ref_path = self.arcane_dir / ref_path_str
            if not ref_path.exists():
                return None
            return ref_path.read_text().strip()
        return raw  # detached HEAD

    def set_head_to_branch(self, branch_name: str) -> None:
        atomic_write_text(self.head_path, f"ref: refs/heads/{branch_name}\n")

    def set_head_detached(self, commit_hash: str) -> None:
        atomic_write_text(self.head_path, f"{commit_hash}\n")

    # ── Branches ────────────────────────────────────────────────────────────

    def update_branch(self, name: str, commit_hash: str) -> None:
        path = self.heads_dir / name
        atomic_write_text(path, f"{commit_hash}\n")

    def update_current_branch(self, commit_hash: str) -> None:
        branch = self.current_branch()
        if branch is None:
            raise RuntimeError("HEAD is detached; cannot update current branch")
        self.update_branch(branch, commit_hash)

    def advance_head(self, commit_hash: str) -> None:
        """Update whatever HEAD points at (branch or detached) to commit_hash."""
        if self.is_detached():
            self.set_head_detached(commit_hash)
        else:
            self.update_current_branch(commit_hash)

    def resolve_branch(self, name: str) -> str | None:
        path = self.heads_dir / name
        if not path.exists():
            return None
        return path.read_text().strip()

    def list_branches(self) -> list[str]:
        if not self.heads_dir.exists():
            return []
        return sorted(
            p.relative_to(self.heads_dir).as_posix()
            for p in self.heads_dir.rglob("*")
            if p.is_file()
        )

    def delete_branch(self, name: str) -> None:
        path = self.heads_dir / name
        if not path.exists():
            raise ValueError(f"Branch '{name}' does not exist")
        path.unlink()

    def branch_exists(self, name: str) -> bool:
        return (self.heads_dir / name).exists()

    # ── Tags ────────────────────────────────────────────────────────────────

    def create_tag(self, name: str, commit_hash: str) -> None:
        path = self.tags_dir / name
        if path.exists():
            raise ValueError(f"Tag '{name}' already exists")
        atomic_write_text(path, f"{commit_hash}\n")

    def resolve_tag(self, name: str) -> str | None:
        path = self.tags_dir / name
        if not path.exists():
            return None
        return path.read_text().strip()

    def list_tags(self) -> list[str]:
        if not self.tags_dir.exists():
            return []
        return sorted(p.name for p in self.tags_dir.iterdir() if p.is_file())

    def delete_tag(self, name: str) -> None:
        path = self.tags_dir / name
        if not path.exists():
            raise ValueError(f"Tag '{name}' does not exist")
        path.unlink()

    # ── Generic resolution ──────────────────────────────────────────────────

    def resolve(self, name: str) -> str | None:
        """Resolve a name that could be HEAD, a branch, a tag, or a raw hash.

        Returns a commit hash or None.
        """
        if name == "HEAD":
            return self.resolve_head()
        h = self.resolve_branch(name)
        if h:
            return h
        h = self.resolve_tag(name)
        if h:
            return h
        # Treat as a raw hash (full or short — caller validates)
        return name if len(name) >= 4 else None
