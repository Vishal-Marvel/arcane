"""arc status — show working tree status."""

import json
from pathlib import Path

import click
from rich.text import Text

from arcane.core.diff import diff_index_vs_head
from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.terminal import console

STATUS_COLORS = {"A": "green", "M": "yellow", "D": "red"}


@click.command("status")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON (for tooling/editors).")
def status(as_json: bool) -> None:
    """Show the status of files in the index and working directory."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    if as_json:
        _emit_json(repo)
        return

    branch = repo.refs.current_branch()
    if branch:
        console.print(f"On branch [bold cyan]{branch}[/bold cyan]")
    else:
        head = repo.refs.resolve_head()
        console.print(f"HEAD detached at [bold]{head[:8] if head else 'unknown'}[/bold]")

    if repo.is_merging():
        console.print("[bold yellow]You are in the middle of a merge.[/bold yellow]")

    # Staged changes (index vs HEAD)
    staged = diff_index_vs_head(repo.store, repo.refs, repo.index)

    # Unstaged changes (workdir vs index)
    unstaged_map = repo.index.diff_vs_workdir(repo.root)

    # Untracked files
    untracked = repo.index.untracked_files(repo.root, repo.arcane_dir)

    if not staged and not unstaged_map and not untracked:
        console.print("[dim]nothing to commit, working tree clean[/dim]")
        return

    if staged:
        console.print("\n[bold]Changes staged for commit:[/bold]")
        for fd in staged:
            color = STATUS_COLORS.get(fd.status, "white")
            label = {"A": "new file", "M": "modified", "D": "deleted"}.get(fd.status, fd.status)
            console.print(f"  [{color}]{label:>10}:[/{color}]  {fd.path}")

    if unstaged_map:
        console.print("\n[bold]Changes not staged for commit:[/bold]")
        for path, st in sorted(unstaged_map.items()):
            color = STATUS_COLORS.get(st, "white")
            label = {"M": "modified", "D": "deleted"}.get(st, st)
            console.print(f"  [{color}]{label:>10}:[/{color}]  {path}")

    if untracked:
        console.print("\n[bold]Untracked files:[/bold]")
        for path in untracked:
            console.print(f"  [dim]{path}[/dim]")


def _emit_json(repo: Repository) -> None:
    """Print a stable JSON snapshot of repository status to stdout (no Rich markup)."""
    branch = repo.refs.current_branch()
    head = repo.refs.resolve_head()

    staged = diff_index_vs_head(repo.store, repo.refs, repo.index)
    unstaged_map = repo.index.diff_vs_workdir(repo.root)
    untracked = repo.index.untracked_files(repo.root, repo.arcane_dir)

    payload = {
        "branch": branch,
        "detached": repo.refs.is_detached(),
        "head": head,
        "headShort": head[:8] if head else None,
        "merging": repo.is_merging(),
        "staged": [{"status": fd.status, "path": fd.path} for fd in staged],
        "unstaged": [
            {"status": st, "path": path} for path, st in sorted(unstaged_map.items())
        ],
        "untracked": list(untracked),
    }
    click.echo(json.dumps(payload))
