"""arc graph — emit the full commit DAG across all refs (for tooling/editors)."""

import json
from pathlib import Path

import click

from arcane.core.repository import Repository, NotARepositoryError


@click.command("graph")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def graph(as_json: bool) -> None:
    """Print the commit graph reachable from all branches, tags, and HEAD.

    Designed for editor integrations (e.g. the VS Code extension): emits every
    commit with its parent links plus the branch/tag tips, so a client can draw
    a Git-style graph without re-implementing Arcane's object format.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    refs = repo.refs
    store = repo.store

    branches = [{"name": b, "hash": refs.resolve_branch(b)} for b in refs.list_branches()]
    tags = [{"name": t, "hash": refs.resolve_tag(t)} for t in refs.list_tags()]
    head = refs.resolve_head()

    # Collect every commit reachable from any tip.
    tips: set[str] = {b["hash"] for b in branches if b["hash"]}
    tips.update(t["hash"] for t in tags if t["hash"])
    if head:
        tips.add(head)

    visited: dict[str, object] = {}
    queue = list(tips)
    while queue:
        h = queue.pop()
        if not h or h in visited:
            continue
        try:
            commit = store.read_commit(h)
        except Exception:
            continue
        visited[h] = commit
        queue.extend(commit.parents)

    # Newest first — good enough for lane layout on the client.
    ordered = sorted(visited.items(), key=lambda kv: kv[1].author_ts, reverse=True)

    commits = []
    for h, c in ordered:
        intent = c.intent or {}
        commits.append(
            {
                "hash": h,
                "short": h[:8],
                "parents": c.parents,
                "intent": intent.get("type", "chore"),
                "scope": intent.get("scope"),
                "breaking": bool(intent.get("breaking")),
                "message": c.message,
                "subject": c.message.splitlines()[0] if c.message else "",
                "author": c.author,
                "timestamp": c.author_ts,
            }
        )

    payload = {
        "head": head,
        "headShort": head[:8] if head else None,
        "currentBranch": refs.current_branch(),
        "detached": refs.is_detached(),
        "branches": branches,
        "tags": tags,
        "commits": commits,
    }

    if as_json:
        click.echo(json.dumps(payload))
    else:
        # Minimal human fallback so the command is useful on its own.
        for c in commits:
            tip = ""
            label_for = [b["name"] for b in branches if b["hash"] == c["hash"]]
            label_for += [f"tag:{t['name']}" for t in tags if t["hash"] == c["hash"]]
            if label_for:
                tip = f" ({', '.join(label_for)})"
            click.echo(f"{c['short']}  [{c['intent']}]{tip}  {c['subject']}")
