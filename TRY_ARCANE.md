# Trying Arcane — A Hands-On Walkthrough

This guide builds a small demo project from scratch and walks you through **every Arcane command**, with special focus on the three signature features:

- **CIT** — Commit Intent Tracking (`arc commit -i`, `arc debt-score`)
- **DAC** — Dependency-Aware Changes (`arc impact`)
- **LLA** — Line-Level Annotations (`arc annotate`)

The demo is a tiny Python app called **taskflow** with a deliberate dependency chain
(`utils → models → service → main`) so that impact analysis has something real to trace.

> Commands are shown for **Windows PowerShell** (the primary environment). Equivalent
> bash commands are noted where they differ. Everything Arcane does is from scratch —
> there is no Git involved.

---

## 0. Install Arcane

From the Arcane repo (`D:\projects\arcane`):

```powershell
# Create a virtualenv if you don't have one
python -m venv .venv

# Install Arcane in editable mode with dev extras
.venv\Scripts\pip install -e ".[dev]"
```

This puts the `arc` binary on the venv's path. Verify:

```powershell
.venv\Scripts\arc --version
.venv\Scripts\arc --help
```

> **Tip:** To type `arc` instead of `.venv\Scripts\arc`, activate the venv first:
> ```powershell
> .venv\Scripts\Activate.ps1
> ```
> The rest of this guide assumes the venv is **activated**, so commands read `arc ...`.
> If you didn't activate it, prefix every `arc` with the full path.

---

## 1. Create the demo project

We create the sandbox **outside** the Arcane source repo so the two never get confused.

```powershell
# From anywhere
New-Item -ItemType Directory -Force D:\projects\taskflow-demo
Set-Location D:\projects\taskflow-demo
```

> bash: `mkdir -p ~/taskflow-demo && cd ~/taskflow-demo`

Now create four Python files that import each other in a chain.

**`utils.py`** — the leaf module everything depends on:

```python
"""Low-level helpers. Nothing depends on, lots depends on this."""


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-")


def clamp(n: int, low: int, high: int) -> int:
    return max(low, min(n, high))
```

**`models.py`** — imports `utils`:

```python
"""Domain models."""

from utils import slugify


class Task:
    def __init__(self, title: str, priority: int = 1) -> None:
        self.title = title
        self.slug = slugify(title)
        self.priority = priority
        self.done = False
```

**`service.py`** — imports `models`:

```python
"""Business logic."""

from models import Task


class TaskService:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    def add(self, title: str, priority: int = 1) -> Task:
        task = Task(title, priority)
        self.tasks.append(task)
        return task

    def pending(self) -> list[Task]:
        return [t for t in self.tasks if not t.done]
```

**`main.py`** — imports `service` (top of the chain):

```python
"""Entry point."""

from service import TaskService


def run() -> None:
    svc = TaskService()
    svc.add("Write the report", priority=3)
    svc.add("Buy milk", priority=1)
    for t in svc.pending():
        print(f"[{t.priority}] {t.title} ({t.slug})")


if __name__ == "__main__":
    run()
```

The dependency chain is:

```
utils.py  ←  models.py  ←  service.py  ←  main.py
(changing utils ripples all the way up to main)
```

(Optional) confirm the app runs:

```powershell
python main.py
```

---

## 2. Initialize an Arcane repository

```powershell
arc init
```

You should see `Initialized empty arc repository in ...\.arcane`. Inspect the layout:

```powershell
Get-ChildItem -Force .arcane
```

> bash: `ls -la .arcane`

You'll see `HEAD`, `objects/`, `refs/`, etc. — the same primitives Git uses, built from scratch.

(Optional) Set an author so commits are attributed:

```powershell
Set-Content .arcane\config "author=Your Name <you@example.com>"
```

---

## 3. Stage and check status

```powershell
arc add utils.py models.py service.py main.py
arc status
```

`arc add` stages each file (and prints `staged: <file>`). Because of **DAC**, `arc add`
also warns if you stage a file whose dependency is *not* staged — try it:

```powershell
# Stage ONLY the top of the chain; its dependencies are unstaged
arc rm --cached models.py service.py utils.py   # unstage everything but main.py
arc add main.py
```

DAC's checker notices `main.py` imports `service` (unstaged) and prints an advisory
warning. Re-stage everything before committing:

```powershell
arc add utils.py models.py service.py main.py
arc status
```

---

## 4. The first commit — CIT in action

Every Arcane commit **must** carry an intent label. This is the heart of **CIT**.

```powershell
arc commit -m "Initial taskflow skeleton" -i feat
```

Valid intents: `feat`, `fix`, `refactor`, `perf`, `debt`, `docs`, `test`, `chore`.

If you omit `-i`, Arcane **prompts** you to choose one — it will not let an
intent-less commit through:

```powershell
arc commit -m "another change"
# → Intent (feat, fix, refactor, perf, debt, docs, test, chore) [chore]:
```

You can attach a scope and mark breaking changes:

```powershell
# (after making a change and staging it)
arc commit -m "rename slug field" -i refactor --scope models --breaking
```

View history with intent badges:

```powershell
arc log
arc log --oneline
arc log --intent feat        # filter by intent
arc log --timeline           # ASCII sparkline of activity by week
```

---

## 5. Build up history (so debt-score has data)

Make a series of commits with different intents. This simulates a real codebase
accumulating both healthy work and technical debt.

```powershell
# 1. A bug fix
Add-Content service.py "`n    # FIXME: pending() ignores priority order"
arc add service.py
arc commit -m "note missing priority sort" -i fix

# 2. A feature
Add-Content models.py "`n    def mark_done(self): self.done = True"
arc add models.py
arc commit -m "add Task.mark_done" -i feat

# 3. Technical debt
Add-Content utils.py "`n# TODO: clamp() has no type validation"
arc add utils.py
arc commit -m "acknowledge clamp validation gap" -i debt

# 4. Another fix
Add-Content main.py "`n# fixed off-by-one in display"
arc add main.py
arc commit -m "fix display formatting" -i fix

# 5. A refactor
Add-Content service.py "`n    # refactored add() for clarity"
arc add service.py
arc commit -m "tidy add() method" -i refactor
```

> bash: replace `Add-Content <file> "...content"` with `echo "..." >> <file>`.

---

## 6. CIT — the debt-score

This is the **0–100 technical-debt health score** computed from commit intents:

```
score = (debt_count + fix_count) / max(1, feat_count + refactor_count) × 50
```

Run it:

```powershell
arc debt-score
arc debt-score --window 10    # only the last 10 commits
```

You'll get a colored bar, a label (`Healthy` / `Moderate debt` / `High debt`), and an
intent breakdown. To **watch the score climb**, add more `fix`/`debt` commits and rerun;
to bring it **down**, add `feat`/`refactor` commits. This gives you a quantitative signal
of codebase health over time — something Git can't tell you.

---

## 7. DAC — impact analysis

This is the killer feature: at **every commit**, Arcane snapshots the full dependency
graph of all tracked files. `arc impact` then answers *"if this commit changed file X,
what else is transitively affected?"* — as an **O(1) lookup**, because the graph was
computed at commit time.

Change the **leaf** module `utils.py` (everything depends on it) and commit:

```powershell
Add-Content utils.py "`n# touch the leaf module"
arc add utils.py
arc commit -m "tweak slugify helper" -i refactor
```

Now ask what that commit impacts:

```powershell
arc impact            # defaults to HEAD
arc impact HEAD
```

Expected: `utils.py` is **directly changed**, and `models.py`, `service.py`, `main.py`
show up as **transitively affected** — the change ripples all the way up the chain.

Contrast with changing the **top** of the chain, which nothing imports:

```powershell
Add-Content main.py "`n# touch the entry point"
arc add main.py
arc commit -m "tweak main entry" -i chore
arc impact
```

Expected: `main.py` is directly changed, and **no other files** are affected — nothing
depends on the entry point.

You can run impact on any historical commit too:

```powershell
arc log --oneline           # grab a commit hash
arc impact <commit-hash>
```

---

## 8. LLA — line-level annotations

Annotations are persistent notes anchored to a **specific line at a specific commit**.
They live outside the source file (in `.arcane/annotations/`) and **follow the line** as
the file changes across commits. If the line is deleted, the annotation is marked
**orphaned** rather than silently lost.

Add a few annotations (types: `note`, `warning`, `todo`, `link`):

```powershell
arc annotate add utils.py 5 "slugify doesn't handle unicode" --type warning
arc annotate add models.py 7 "consider a UUID instead of a slug" --type todo
arc annotate add service.py 11 "see RFC for sort stability" --type link
```

List annotations on a file (shows current tracked line numbers + the line's content):

```powershell
arc annotate list utils.py
```

### Watch annotations track line movement

Insert lines **above** an annotated line, commit, then list again — the annotation's
reported line number should shift to stay on the same logical line:

```powershell
# Prepend two new lines at the top of utils.py
$content = Get-Content utils.py
Set-Content utils.py (@("# new header line 1", "# new header line 2") + $content)

arc add utils.py
arc commit -m "add header comments" -i docs

arc annotate list utils.py     # the line number should have moved down by 2
```

> bash equivalent for prepending:
> ```bash
> printf '# new header line 1\n# new header line 2\n' | cat - utils.py > tmp && mv tmp utils.py
> ```

### See the orphaning behavior

Delete the annotated line entirely, commit, and list — the annotation becomes
`(orphaned)` instead of vanishing:

```powershell
# Delete the line slugify was annotated on, then commit
# (edit utils.py to remove the slugify body line, then:)
arc add utils.py
arc commit -m "remove old slugify body" -i refactor
arc annotate list utils.py     # the warning is now marked (orphaned)
```

See the full history of annotations that ever touched a line:

```powershell
arc annotate history utils.py 5
```

---

## 9. Branching, checkout, and merge

Arcane implements branches, refs, and a real **3-way merge** (with merge-base /
lowest-common-ancestor detection) from scratch.

```powershell
arc branch                       # list branches (shows current with *)
arc checkout -b feature/sorting  # create + switch to a new branch
```

Make a change on the branch and commit:

```powershell
Add-Content service.py "`n    def sorted_tasks(self): return sorted(self.tasks, key=lambda t: t.priority)"
arc add service.py
arc commit -m "add sorted_tasks" -i feat
```

Switch back and merge:

```powershell
arc checkout main          # or 'master' — whatever your default branch is named
arc merge feature/sorting
```

If `main` had no new commits, you'll see a **fast-forward**. If both branches diverged,
Arcane performs a 3-way merge; on conflicting lines it writes conflict markers, sets
`MERGE_HEAD`, and asks you to resolve and `arc commit`.

To force a **real 3-way merge** (and possibly a conflict), commit to *both* branches on
the *same lines* before merging, then resolve:

```powershell
# After a conflict:
arc status                 # shows "You are in the middle of a merge"
# (edit the conflicted files to resolve)
arc add <conflicted-file>
arc commit -m "merge feature/sorting" -i chore
```

Clean up:

```powershell
arc branch -d feature/sorting
```

---

## 10. Tags

```powershell
arc tag v0.1.0                   # tag current HEAD
arc tag v0.0.1 <older-hash>      # tag a specific commit
arc tag -l                       # list tags
arc checkout v0.1.0              # checkout a tag (detached HEAD)
arc tag -d v0.0.1                # delete a tag
```

---

## 11. Diffing

```powershell
# Make an unstaged edit
Add-Content main.py "`n# scratch change"

arc diff                 # workdir vs index (unstaged)
arc add main.py
arc diff --staged        # index vs HEAD (staged)
arc diff --stat          # names + change summary only
arc diff HEAD~ HEAD      # NOTE: Arcane resolves refs/hashes, not ~ syntax — use two hashes:
arc log --oneline        #   grab two hashes, then:
arc diff <hashA> <hashB> # diff between two commits
```

---

## 12. Full feature checklist

By the end you should have exercised:

| Area | Commands |
|---|---|
| Repo setup | `arc init`, `arc status` |
| Staging | `arc add`, `arc rm`, `arc rm --cached` |
| **CIT** | `arc commit -i <intent>`, `arc log --intent`, `arc log --timeline`, `arc debt-score` |
| **DAC** | dependency warning on `arc add`, `arc impact [ref]` |
| **LLA** | `arc annotate add/list/history`, line tracking, orphaning |
| History | `arc log`, `arc log --oneline`, `arc diff`, `arc diff --staged` |
| Branching | `arc branch`, `arc checkout -b`, `arc checkout`, `arc merge` |
| Tags | `arc tag`, `arc tag -l`, `arc tag -d` |

---

## 13. Run the project's own test suite (optional)

Back in the Arcane source repo, all of the above is covered by automated tests:

```powershell
Set-Location D:\projects\arcane
.venv\Scripts\pytest                       # full suite
.venv\Scripts\pytest tests/features/ -v    # CIT / DAC / LLA feature tests
.venv\Scripts\pytest tests/integration/ -v # end-to-end flows
```

---

## 14. Tear down

```powershell
Remove-Item -Recurse -Force D:\projects\taskflow-demo
```

That removes the entire sandbox (Arcane keeps everything inside `.arcane/`, so deleting
the folder is a clean reset).
