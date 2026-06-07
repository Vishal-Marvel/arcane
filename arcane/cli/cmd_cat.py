"""arc cat — print the content of a tracked file at a given commit."""

import sys
from pathlib import Path

import click

from arcane.core.diff import _flatten_tree
from arcane.core.repository import Repository, NotARepositoryError


@click.command("cat")
@click.argument("ref")
@click.argument("file")
def cat(ref: str, file: str) -> None:
    """Write FILE's content as of REF to stdout.

    REF may be a branch, tag, commit hash, or HEAD. FILE is a repo-relative path
    (forward slashes). Exits non-zero if the file does not exist at that commit —
    editor integrations rely on this to render diffs against a prior version.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    target = repo.refs.resolve(ref)
    if not target:
        raise click.ClickException(f"Unknown ref: '{ref}'")

    try:
        commit = repo.store.read_commit(target)
    except Exception:
        raise click.ClickException(f"Could not read commit: {target[:8]}")

    flat = _flatten_tree(repo.store, commit.tree, "")
    file_posix = file.replace("\\", "/")
    blob_hash = flat.get(file_posix)
    if blob_hash is None:
        # Not an error message to stdout — keep stdout clean for piping.
        raise click.ClickException(f"'{file_posix}' not found at {target[:8]}")

    blob = repo.store.read_blob(blob_hash)
    sys.stdout.buffer.write(blob.content)
