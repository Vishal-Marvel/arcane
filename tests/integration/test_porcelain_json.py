"""Integration tests for the JSON porcelain commands used by editor tooling.

Covers `arc status --json`, `arc graph --json`, and `arc cat` — the interface the
VS Code extension consumes.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from arcane.cli.main import cli


def _run(args: list[str]) -> "object":
    runner = CliRunner()
    return runner.invoke(cli, args, catch_exceptions=False)


def _commit_file(name: str, content: str, message: str, intent: str) -> None:
    Path(name).write_text(content)
    assert _run(["add", name]).exit_code == 0
    assert _run(["commit", "-m", message, "-i", intent]).exit_code == 0


@pytest.fixture
def in_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    assert _run(["init"]).exit_code == 0
    return tmp_path


def test_status_json_reports_staged_unstaged_untracked(in_repo: Path) -> None:
    _commit_file("a.py", "x = 1\n", "add a", "feat")

    # One tracked file modified (unstaged) and one brand-new untracked file.
    Path("a.py").write_text("x = 1\n# edit\n")
    Path("b.py").write_text("y = 2\n")

    result = _run(["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)

    assert data["branch"] == "main"
    assert data["detached"] is False
    assert data["merging"] is False
    assert data["staged"] == []
    assert {"status": "M", "path": "a.py"} in data["unstaged"]
    assert "b.py" in data["untracked"]


def test_graph_json_has_parent_links_and_refs(in_repo: Path) -> None:
    _commit_file("a.py", "x = 1\n", "first", "feat")
    _commit_file("a.py", "x = 2\n", "second", "refactor")
    assert _run(["tag", "v1"]).exit_code == 0
    assert _run(["checkout", "-b", "feature"]).exit_code == 0
    _commit_file("c.py", "z = 3\n", "feature work", "feat")

    result = _run(["graph", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)

    # Three commits total, newest first.
    subjects = [c["subject"] for c in data["commits"]]
    assert subjects[0] == "feature work"
    assert {"first", "second", "feature work"} == set(subjects)

    by_subject = {c["subject"]: c for c in data["commits"]}
    # 'second' is the parent of 'feature work'.
    assert by_subject["second"]["hash"] in by_subject["feature work"]["parents"]
    # 'first' has no parents (root).
    assert by_subject["first"]["parents"] == []

    branch_names = {b["name"] for b in data["branches"]}
    assert {"main", "feature"} <= branch_names
    assert data["currentBranch"] == "feature"
    assert any(t["name"] == "v1" for t in data["tags"])


def test_cat_returns_content_at_head_and_errors_when_missing(in_repo: Path) -> None:
    _commit_file("a.py", "hello\nworld\n", "add a", "feat")

    # Unstaged edit must NOT appear in `cat HEAD` — it reads the committed version.
    Path("a.py").write_text("hello\nworld\nlocal change\n")

    ok = _run(["cat", "HEAD", "a.py"])
    assert ok.exit_code == 0
    assert ok.output == "hello\nworld\n"

    missing = CliRunner().invoke(cli, ["cat", "HEAD", "nope.py"])
    assert missing.exit_code != 0
