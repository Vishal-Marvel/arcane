# Arcane

A version control system built from scratch in Python, inspired by Git's internals but extended with three unique features that Git lacks: **Commit Intent Tracking (CIT)**, **Dependency-Aware Changes (DAC)**, and **Line-Level Annotations (LLA)**.

## Why this project exists

Two goals drove this:

1. **Learn how Git works internally** — by building the same primitives (content-addressed object store, trees, commits, refs, index, 3-way merge) from scratch.
2. **Explore what a VCS could do beyond Git** — the three features above are the USP: structured intent on every commit, automatic dependency impact analysis, and persistent line-anchored notes that survive refactoring.

## Unique features (USP)

### CIT — Commit Intent Tracking

Every `arc commit` requires an **intent label**:

| Intent | Meaning |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructure, no behavior change |
| `perf` | Performance improvement |
| `debt` | Explicit technical debt |
| `docs` | Documentation only |
| `test` | Tests only |
| `chore` | Build/config/tooling |

The intent is stored inside the commit object (not just the message). `arc debt-score` computes a **0–100 debt score** from the last N commits:

```
score = (debt + fix commits) / max(1, feat + refactor commits) × 50
```

This gives teams a quantitative signal of codebase health over time.

### DAC — Dependency-Aware Changes

At every commit, `arc` automatically snapshots the dependency graph of all tracked files (currently: Python, JavaScript/TypeScript, Go). After a commit, `arc impact <ref>` answers: *"Which files in this repo transitively depend on what I just changed?"*

```
arc impact HEAD

Directly changed (1 file):
  + api.py

Transitively affected (2 files):
  > auth.py
  > main.py
```

The dependency graph is stored as a `dep_snapshot` object in the object store and referenced from the commit. This means impact analysis is O(1) to look up — the graph was already computed at commit time.

### LLA — Line-Level Annotations

Annotations are persistent notes anchored to a specific line in a specific file **at a specific commit**. Unlike code comments, they live outside the source file and survive across commits. The LLA tracker replays diffs to keep line numbers current:

```
arc annotate add auth.py 42 "This token check has a race condition"
arc annotate list auth.py      # shows current line numbers, even after edits
arc annotate history auth.py 42
```

If the annotated line is deleted in a later commit, the annotation is marked **orphaned** rather than silently lost.

## CLI reference

```
arc init                          Create a new repository
arc add <file>                    Stage a file
arc rm <file>                     Unstage a file
arc status                        Show staged/unstaged/untracked files
arc commit -m <msg> -i <intent>   Commit with intent label
arc log                           Show commit history
arc diff [ref]                    Show diffs
arc branch [name]                 List or create branches
arc checkout <branch|ref>         Switch branch or restore files
arc merge <branch>                Merge a branch (3-way)
arc tag <name> [ref]              Create a tag

arc annotate add <file> <line> <text>   Add a line annotation
arc annotate list <file>                List annotations on a file
arc annotate history <file> <line>      Annotation history for a line

arc impact [ref]                  Show transitive impact of a commit
arc debt-score [--window N]       Show technical debt score
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

Requires Python 3.11+.

## Running tests

```bash
.venv\Scripts\pytest                          # all 81 tests
.venv\Scripts\pytest tests/features/ -v      # feature tests only
.venv\Scripts\pytest tests/integration/ -v   # integration tests
```

## How it relates to Git internals

| Git concept | Arcane equivalent |
|---|---|
| `.git/` | `.arcane/` |
| Object store (SHA-1) | `ObjectStore` (SHA-256) |
| Blob / Tree / Commit | `Blob` / `Tree` / `Commit` — same model, msgpack+zlib instead of zlib |
| Index / staging area | `Index` — msgpack, lockfile-protected |
| `refs/heads/`, `HEAD` | `RefsManager` — same layout |
| 3-way merge | `MergeEngine` — difflib-based |
| — | `Annotation` object (new type) |
| — | `dep_snapshot` object (new type) |
| — | `intent` field on every Commit (new) |
