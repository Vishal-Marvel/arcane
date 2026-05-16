# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Arcane is a **custom version control system built from scratch in Python**, inspired by Git's internals. It was created for two explicit reasons:

1. **To understand how Git works internally** — by reimplementing the same primitives: content-addressed object store, tree objects, commits, refs, staging index, 3-way merge, branch/tag management.
2. **To explore what a VCS could do beyond Git** — via three unique features that are the project's USP.

This is not a wrapper around Git. There is no Git dependency. Everything (hashing, serialization, diff, merge, refs) is implemented from scratch.

## The three unique features (USP)

### CIT — Commit Intent Tracking (`arcane/features/cit/`)

Every commit carries a structured **intent label** stored inside the commit object itself (not just the message). Intent is enforced at `arc commit` time — users must choose one of: `feat`, `fix`, `refactor`, `perf`, `debt`, `docs`, `test`, `chore`.

`arc debt-score` computes a **0–100 debt health score** from the last N commits:
```
score = (debt_count + fix_count) / max(1, feat_count + refactor_count) × 50
```
This gives a quantitative codebase health signal over time.

Key files:
- `arcane/features/cit/intent.py` — `IntentType` enum, `DEBT_INTENTS`, `HEALTHY_INTENTS` sets
- `arcane/features/cit/scorer.py` — `compute_debt_score(repo, window=50)`
- `arcane/cli/cmd_debt_score.py` — `arc debt-score` command

### DAC — Dependency-Aware Changes (`arcane/features/dac/`)

At every `arc commit`, the full dependency graph of all tracked files is automatically snapshotted and stored as a `dep_snapshot` object. `arc impact <ref>` then answers: *"which files transitively depend on what this commit changed?"*

The graph snapshot is content-addressed and linked from the commit via `commit.dep_snapshot_hash`. Impact analysis is O(1) lookup — the graph was computed at commit time, not query time.

Supported languages: Python (AST-based), JavaScript/TypeScript (regex), Go (regex).

Key files:
- `arcane/features/dac/graph.py` — `DependencyGraph`: edges dict, `transitive_dependents()`, `transitive_deps()`
- `arcane/features/dac/parser.py` — `PythonParser`, `JavaScriptParser`, `GoParser`, `parse_dependencies()`
- `arcane/features/dac/snapshot.py` — `build_snapshot(repo)`, `load_snapshot(repo, hash)`
- `arcane/features/dac/impact.py` — `compute_impact(repo, commit_hash)` → `{changed_files, impacted_files, graph_available}`
- `arcane/features/dac/checker.py` — `check_staged(repo)`: warns if staged file imports an unstaged dependency
- `arcane/cli/cmd_impact.py` — `arc impact [ref]` command

### LLA — Line-Level Annotations (`arcane/features/lla/`)

Annotations are persistent notes anchored to a specific line in a file **at a specific commit**. They live outside the source file in `.arcane/annotations/`. As the file evolves across commits, the LLA tracker **replays diffs** to keep line numbers current. If an annotated line is deleted, the annotation is marked **orphaned** rather than silently lost.

Key files:
- `arcane/core/objects/annotation.py` — `Annotation` object: `file_path`, `line_start`, `line_end`, `commit_hash`, `annotation_type`, `text`, `author`
- `arcane/features/lla/store.py` — `AnnotationStore`: index at `.arcane/annotations/index.msgpack`, maps `file_path → [annotation_hashes]`
- `arcane/features/lla/tracker.py` — `track_annotation(repo, ann, hash, target_commit)` → `TrackedAnnotation` with `current_line_start`, `is_orphaned`; `_map_lines()` using `difflib.SequenceMatcher`
- `arcane/cli/cmd_annotate.py` — `arc annotate add/list/history` commands

## Core architecture

### Object model (`arcane/core/objects/`)

All storage is **content-addressed**: SHA-256 of the serialized bytes is the object's identity. On-disk format: **1-byte type prefix + zlib-compressed msgpack**.

| Object | Type byte | Description |
|---|---|---|
| `Blob` | `\x01` | Raw file content |
| `Tree` | `\x02` | Directory snapshot: list of `TreeEntry(name, hash, mode, type)` |
| `Commit` | `\x03` | Tree pointer + parents + metadata + **intent** + **dep_snapshot_hash** + **annotation_refs** |
| `Annotation` | `\x04` | Line-level note (LLA) |
| `dep_snapshot` | `\x05` | DAC dependency graph snapshot |

The `Commit` object is the central integration point — it carries CIT intent, the DAC snapshot reference, and LLA annotation refs all in one place.

### Core subsystems (`arcane/core/`)

- **`repository.py`** — `Repository`: central context object. All CLI commands call `Repository.discover(Path.cwd())` and pass it down. Holds `store`, `refs`, `index`. Never import subsystems directly from CLI.
- **`store.py`** — `ObjectStore`: fan-out layout (`AB/CDEF...`), `write(obj)`, `read(hash)`, `read_blob/tree/commit/annotation(hash)`, `write_raw()` for dep_snapshot
- **`refs.py`** — `RefsManager`: `HEAD`, `refs/heads/`, `refs/tags/`. `resolve_head()`, `advance_head()`, `update_branch()`, `resolve(ref_or_hash)`
- **`index.py`** — `Index`: lockfile-protected msgpack staging area. `add(path, hash, file_path)`, `remove(path)`, `diff_vs_workdir(root)`, `untracked_files()`
- **`diff.py`** — `diff_trees()`, `diff_index_vs_head()`, `_flatten_tree()` (used by merge and impact)
- **`merge.py`** — `three_way_merge()`, `find_merge_base()` (BFS LCA), `merge_trees()`

### CLI (`arcane/cli/`)

Each command is its own module. `main.py` registers all groups/commands onto the root `cli` Click group. Pattern: discover repo → call plumbing → print with Rich.

### `.arcane/` repository layout

```
.arcane/
├── HEAD                   "ref: refs/heads/main\n" or detached hash
├── MERGE_HEAD             present only during active merge
├── config                 "author=Name <email>" (optional)
├── objects/AB/CDEF...     fan-out content store
├── refs/heads/<branch>    branch pointers
├── refs/tags/<tag>        tag pointers
├── index                  staging area (msgpack+zlib)
├── index.lock             lockfile for atomic writes
└── annotations/
    └── index.msgpack      LLA annotation index
```

## Commands

```bash
# Install
.venv\Scripts\pip install -e ".[dev]"

# Tests
.venv\Scripts\pytest                      # all 81 tests
.venv\Scripts\pytest tests/features/ -v
.venv\Scripts\pytest tests/integration/ -v
.venv\Scripts\pytest tests/core/test_store.py -v   # single file

# Lint / type check / format
.venv\Scripts\ruff check arcane/
.venv\Scripts\mypy arcane/
.venv\Scripts\ruff format arcane/
```

## Key conventions

- Python 3.11+, strict mypy, ruff line-length 100
- Serialization always goes through `utils/serialization.py` (msgpack+zlib) and `utils/hashing.py` (SHA-256)
- Atomic writes use lockfiles + `utils/fs.py` helpers
- `tests/conftest.py` provides `tmp_repo` and `repo_with_commit` fixtures
- DAC and LLA features are **non-blocking** — failures are swallowed so they never prevent a commit
- The entry-point binary is `arc` (defined in `pyproject.toml` → `arcane.cli.main:cli`)
