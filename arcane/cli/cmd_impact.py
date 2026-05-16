"""arc impact — show the transitive impact radius of a commit."""

from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.features.dac.impact import compute_impact
from arcane.utils.terminal import console


@click.command("impact")
@click.argument("commit_ref", default="HEAD")
def impact(commit_ref: str) -> None:
    """Show which files are transitively affected by changes in COMMIT_REF.

    Uses the dependency graph snapshot stored at commit time to trace
    which files import the changed files (directly or transitively).
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    target_hash = repo.refs.resolve(commit_ref)
    if not target_hash:
        raise click.ClickException(f"Unknown ref: '{commit_ref}'")

    result = compute_impact(repo, target_hash)

    console.print(f"\n[bold]Impact analysis for[/bold] [bold yellow]{target_hash[:8]}[/bold yellow]")

    changed = result["changed_files"]
    impacted = result["impacted_files"]

    if not changed:
        console.print("[dim]No file changes in this commit.[/dim]")
        return

    console.print(f"\n[bold green]Directly changed[/bold green] ({len(changed)} file{'s' if len(changed) != 1 else ''}):")
    for f in changed:
        console.print(f"  [green]+[/green] {f}")

    if not result["graph_available"]:
        console.print(
            "\n[dim]No dependency snapshot available for this commit. "
            "Impact radius requires commits made with arcane >= 0.1.[/dim]"
        )
        return

    if impacted:
        console.print(f"\n[bold yellow]Transitively affected[/bold yellow] ({len(impacted)} file{'s' if len(impacted) != 1 else ''}):")
        for f in impacted:
            console.print(f"  [yellow]>[/yellow] {f}")
    else:
        console.print("\n[dim]No other files depend on the changed files.[/dim]")
