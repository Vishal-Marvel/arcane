"""arc annotate — manage line-level annotations."""

import time
from pathlib import Path

import click

from arcane.core.objects.annotation import Annotation
from arcane.core.repository import Repository, NotARepositoryError
from arcane.features.lla.store import AnnotationStore
from arcane.features.lla.tracker import track_annotation
from arcane.utils.terminal import console, annotation_gutter

ANNOTATION_TYPES = ["note", "warning", "todo", "link"]


def _get_annotation_store(repo: Repository) -> AnnotationStore:
    return AnnotationStore(repo.arcane_dir / "annotations")


@click.group("annotate")
def annotate() -> None:
    """Manage line-level annotations on source files."""


@annotate.command("add")
@click.argument("file")
@click.argument("line", type=int)
@click.argument("text")
@click.option(
    "--type", "annotation_type",
    type=click.Choice(ANNOTATION_TYPES, case_sensitive=False),
    default="note",
    show_default=True,
    help="Type of annotation.",
)
def annotate_add(file: str, line: int, text: str, annotation_type: str) -> None:
    """Add an annotation to FILE at LINE.

    The annotation is anchored to the current HEAD commit.
    It will track line movements as the file changes over time.
    """
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    head = repo.refs.resolve_head()
    if head is None:
        raise click.ClickException("No commits yet. Make a commit before adding annotations.")

    # Validate that the file and line exist
    abs_path = repo.root / file.replace("/", "\\")
    if not abs_path.exists():
        raise click.ClickException(f"File not found: {file}")

    lines = abs_path.read_text(errors="replace").splitlines()
    if line < 1 or line > len(lines):
        raise click.ClickException(f"Line {line} is out of range (file has {len(lines)} lines).")

    ann = Annotation(
        file_path=file.replace("\\", "/"),
        line_start=line,
        line_end=line,
        commit_hash=head,
        annotation_type=annotation_type.lower(),
        text=text,
        author=repo.get_author(),
        timestamp=time.time(),
        parent_id=None,
    )
    ann_hash = repo.store.write(ann)

    ann_store = _get_annotation_store(repo)
    ann_store.add(ann.file_path, ann_hash)

    gutter = annotation_gutter(annotation_type.lower())
    console.print(
        f"[bold green]Added[/bold green] [{annotation_type}] annotation on "
        f"[bold]{file}[/bold]:{line}  ",
        gutter,
        f" {text[:60]}{'…' if len(text) > 60 else ''}",
        sep="",
    )
    console.print(f"[dim]{ann_hash[:8]}[/dim]")


@annotate.command("list")
@click.argument("file")
def annotate_list(file: str) -> None:
    """List all annotations on FILE, with current line numbers tracked."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    file_posix = file.replace("\\", "/")
    ann_store = _get_annotation_store(repo)
    hashes = ann_store.list_for_file(file_posix)

    if not hashes:
        console.print(f"[dim]No annotations on {file}.[/dim]")
        return

    head = repo.refs.resolve_head()
    tracked = []
    for ann_hash in hashes:
        try:
            ann = repo.store.read_annotation(ann_hash)
            ta = track_annotation(repo, ann, ann_hash, head)
            tracked.append(ta)
        except Exception:
            continue

    # Sort by current line
    tracked.sort(key=lambda t: (t.is_orphaned, t.current_line_start))

    # Load file content for inline display
    abs_path = repo.root / file.replace("/", "\\")
    file_lines: list[str] = []
    if abs_path.exists():
        file_lines = abs_path.read_text(errors="replace").splitlines()

    console.print(f"\n[bold]Annotations on[/bold] [bold cyan]{file}[/bold cyan]\n")

    for ta in tracked:
        ann = ta.annotation
        gutter = annotation_gutter(ann.annotation_type)
        import time as _time
        date_str = _time.strftime("%Y-%m-%d", _time.localtime(ann.timestamp))

        if ta.is_orphaned:
            line_display = "[dim](orphaned)[/dim]"
            context = ""
        else:
            line_display = f":{ta.current_line_start}"
            if 0 < ta.current_line_start <= len(file_lines):
                context = f"  [dim]{file_lines[ta.current_line_start - 1].strip()[:50]}[/dim]"
            else:
                context = ""

        console.print(
            f"  {gutter} [bold]{file}{line_display}[/bold]{context}"
        )
        console.print(f"     [cyan]{ann.annotation_type}[/cyan]  {ann.text}")
        console.print(f"     [dim]{ann.author} · {date_str} · {ta.annotation_hash[:8]}[/dim]\n")


@annotate.command("history")
@click.argument("file")
@click.argument("line", type=int)
def annotate_history(file: str, line: int) -> None:
    """Show all annotations that ever touched LINE in FILE."""
    try:
        repo = Repository.discover(Path.cwd())
    except NotARepositoryError as e:
        raise click.ClickException(str(e))

    file_posix = file.replace("\\", "/")
    ann_store = _get_annotation_store(repo)
    hashes = ann_store.list_for_file(file_posix)

    if not hashes:
        console.print(f"[dim]No annotations on {file}.[/dim]")
        return

    head = repo.refs.resolve_head()
    relevant = []

    for ann_hash in hashes:
        try:
            ann = repo.store.read_annotation(ann_hash)
        except Exception:
            continue

        # Check if this annotation's tracked line range covers the requested line
        ta = track_annotation(repo, ann, ann_hash, head)
        original_covers = ann.line_start <= line <= ann.line_end
        current_covers = not ta.is_orphaned and ta.current_line_start <= line <= ta.current_line_end

        if original_covers or current_covers:
            relevant.append((ann, ann_hash, ta))

    if not relevant:
        console.print(f"[dim]No annotations found for {file}:{line}[/dim]")
        return

    relevant.sort(key=lambda x: x[0].timestamp)

    console.print(f"\n[bold]Annotation history for[/bold] [bold cyan]{file}:{line}[/bold cyan]\n")
    for ann, ann_hash, ta in relevant:
        gutter = annotation_gutter(ann.annotation_type)
        import time as _time
        date_str = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(ann.timestamp))
        status = "[dim](orphaned)[/dim]" if ta.is_orphaned else f"now at line {ta.current_line_start}"

        console.print(f"  {gutter} [dim]{date_str}[/dim]  [{ann.annotation_type}]  {ann.text}")
        console.print(f"     [dim]{ann.author} · original line {ann.line_start} · {status} · {ann_hash[:8]}[/dim]\n")
