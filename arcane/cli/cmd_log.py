"""arc log — show commit history."""

import time
from collections import defaultdict
from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError
from arcane.utils.hashing import short_hash
from arcane.utils.terminal import console, intent_badge, sparkline, INTENT_COLORS

VALID_INTENTS = ["feat", "fix", "refactor", "perf", "debt", "docs", "test", "chore"]


@click.command("log")
@click.option("-n", "--count", default=0, help="Limit number of commits shown (0 = all).")
@click.option(
    "--intent",
    type=click.Choice(VALID_INTENTS, case_sensitive=False),
    default=None,
    help="Filter commits by intent type.",
)
@click.option("--timeline", is_flag=True, help="Show ASCII sparkline grouped by week.")
@click.option("--oneline", is_flag=True, help="Compact one-line format.")
def log(count: int, intent: str | None, timeline: bool, oneline: bool) -> None:
    """Show commit history from HEAD."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    head = repo.refs.resolve_head()
    if head is None:
        console.print("[dim]No commits yet.[/dim]")
        return

    commits = []
    seen: set[str] = set()
    queue = [head]

    while queue:
        h = queue.pop(0)
        if h in seen:
            continue
        seen.add(h)
        try:
            c = repo.store.read_commit(h)
        except Exception:
            break
        commits.append((h, c))
        queue.extend(c.parents)

    # Filter by intent
    if intent:
        commits = [(h, c) for h, c in commits if c.intent_type == intent]

    if timeline:
        _render_timeline(commits)
        return

    shown = 0
    for h, c in commits:
        if count and shown >= count:
            break

        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(c.author_ts))
        badge = intent_badge(c.intent_type)

        if oneline:
            console.print(
                f"[bold yellow]{h[:8]}[/bold yellow] ",
                badge,
                f" {c.message.splitlines()[0]}",
                sep="",
            )
        else:
            console.print(f"\n[bold yellow]commit {h}[/bold yellow]")
            console.print(f"Author: {c.author}")
            console.print(f"Date:   {date_str}")
            console.print("Intent: ", badge, sep="")
            if c.intent.get("scope"):
                console.print(f"Scope:  {c.intent['scope']}")
            if c.intent.get("breaking"):
                console.print("[bold red]BREAKING CHANGE[/bold red]")
            console.print(f"\n    {c.message}\n")

        shown += 1


def _render_timeline(commits: list[tuple[str, object]]) -> None:  # type: ignore[type-arg]
    """Render an ASCII sparkline of commit activity grouped by ISO week."""
    from arcane.core.objects.commit import Commit as CommitObj

    # Group by (year, week)
    week_intents: dict[tuple[int, int], list[str]] = defaultdict(list)
    for h, c in commits:
        if isinstance(c, CommitObj):
            week = time.strftime("%Y-%W", time.localtime(c.author_ts))
            y, w = int(week[:4]), int(week[5:])
            week_intents[(y, w)].append(c.intent_type)

    if not week_intents:
        console.print("[dim]No data to display.[/dim]")
        return

    sorted_weeks = sorted(week_intents.keys())
    counts = [len(week_intents[wk]) for wk in sorted_weeks]

    console.print("\n[bold]Commit activity by week:[/bold]")
    console.print(sparkline(counts))

    console.print("\n[bold]Intent breakdown:[/bold]")
    for intent_type, color in INTENT_COLORS.items():
        week_counts = [week_intents[wk].count(intent_type) for wk in sorted_weeks]
        if any(week_counts):
            bar = sparkline(week_counts)
            console.print(f"  [{color}]{intent_type:>10}[/{color}]  {bar}")
