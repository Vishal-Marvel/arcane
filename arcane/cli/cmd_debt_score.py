"""arc debt-score — show the technical debt score for this repository."""

from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.features.cit.scorer import compute_debt_score
from arcane.utils.terminal import console, INTENT_COLORS


@click.command("debt-score")
@click.option("--window", default=50, show_default=True, help="Number of recent commits to analyze.")
def debt_score(window: int) -> None:
    """Show the technical debt score based on commit intent history.

    Score 0–30: healthy (green)
    Score 30–60: moderate debt (yellow)
    Score 60–100: high debt (red)
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    result = compute_debt_score(repo, window=window)
    score = result["score"]
    total = result["total"]

    if score < 30:
        color = "green"
        label = "Healthy"
    elif score < 60:
        color = "yellow"
        label = "Moderate debt"
    else:
        color = "red"
        label = "High debt"

    bar_len = 30
    filled = int(score / 100 * bar_len)
    bar = "#" * filled + "-" * (bar_len - filled)

    console.print(f"\n[bold]Technical Debt Score[/bold] (last {total} commits)")
    console.print(f"  [{color}]{bar}[/{color}]  [{color}]{score}/100 - {label}[/{color}]")

    if "counts" in result:
        console.print("\n[bold]Intent breakdown:[/bold]")
        for intent_type, count in sorted(result["counts"].items()):
            if count == 0:
                continue
            ic = INTENT_COLORS.get(intent_type, "white")
            console.print(f"  [{ic}]{intent_type:>10}[/{ic}]  {count}")
