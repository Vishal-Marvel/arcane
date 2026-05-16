# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies
.venv\Scripts\pip install -e ".[dev]"

# Run all tests
.venv\Scripts\pytest

# Run a single test file
.venv\Scripts\pytest tests/core/test_store.py -v

# Run with coverage
.venv\Scripts\pytest --cov=arcane --cov-report=term

# Lint
.venv\Scripts\ruff check arcane/

# Format
.venv\Scripts\ruff format arcane/

# Type check (strict)
.venv\Scripts\mypy arcane/
```

Entry point after install: `arc` CLI (maps to `arcane.cli.main:cli`).

## Architecture

Arcane is a Python VCS with three domain features layered on top of a Git-like object model.

### Core (`arcane/core/`)

- **`repository.py`** — Central context object; all CLI commands discover a `Repository` and thread it through to plumbing functions. Resolves `.arcane/` root, author identity (`ARC_AUTHOR_NAME`/`ARC_AUTHOR_EMAIL` env vars), and is the entry point for everything else.
- **`store.py`** — `ObjectStore`: SHA-256 content-addressed storage in fan-out layout (`AB/CDEF...`). Reads/writes all object types uniformly via type-prefixed msgpack+zlib serialization.
- **`refs.py`** — `RefsManager`: HEAD, branch pointers (`refs/heads/`), and tags (`refs/tags/`). HEAD resolution is the entry point for history traversal.
- **`index.py`** — Staging area. Uses a lockfile-protected msgpack file; diffs run between index↔workdir or index↔HEAD.
- **`objects/`** — `Blob`, `Tree`, `Commit`, `Annotation` types. `Commit` carries CIT intent metadata and DAC snapshot refs in addition to standard tree/parent pointers.

### Three Feature Pillars (`arcane/features/`)

- **CIT** (`cit/`): Commit Intent Tracking. Structured intent labels (`feat`, `fix`, `refactor`, `perf`, `debt`, `docs`, `test`, `chore`) stored in commit metadata. `scorer.py` computes a debt score from intent histograms.
- **DAC** (`dac/`): Dependency-Aware Changes. `parser.py` builds a dependency graph from Python AST imports; `snapshot.py` captures it at commit time; `impact.py` computes which files are transitively affected by a change.
- **LLA** (`lla/`): Line-Level Annotations. Annotations are anchored to specific commit+file+line; `tracker.py` adjusts line positions across diffs; `store.py` persists them under `.arcane/annotations/`.

### CLI (`arcane/cli/`)

Each command is its own module (`cmd_*.py`). `main.py` aggregates them into the root `cli` Click group. Commands discover a `Repository`, then delegate to core or feature subsystems — no direct subsystem access from CLI.

### `.arcane/` Repository Layout

```
.arcane/
├── HEAD, MERGE_HEAD
├── config
├── objects/         # fan-out content store
├── refs/heads/, refs/tags/
├── index, index.lock
└── annotations/
```

## Key Conventions

- Python 3.11+, strict mypy, ruff line-length 100.
- All object serialization goes through `utils/serialization.py` (msgpack+zlib) and `utils/hashing.py` (SHA-256).
- Atomic writes use lockfiles (`index.lock`) and `utils/fs.py` helpers.
- `tests/conftest.py` provides `tmp_repo` and `repo_with_commit` fixtures for all test modules.
