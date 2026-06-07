# Arcane VCS — VS Code extension

Brings Git-style source control to the [Arcane](../README.md) version control system:
a branch indicator in the status bar, a Source Control panel for staging and committing,
a commit-history sidebar, and a drawn **commit graph** — all backed by the `arc` CLI.

> VS Code has no built-in support for non-Git VCSs, and its *native* commit graph is
> hard-wired to Git. So this extension implements VS Code's public **SCM API** on top of
> Arcane, and renders the graph itself in a webview.

## What you get

| Feature | Where | Backed by |
|---|---|---|
| Current branch (and dirty/merge state) | Status bar, bottom-left | `arc status --json` |
| Staged / Changes / Untracked groups | Source Control panel | `arc status --json` |
| Stage, unstage, discard | inline icons + context menu | `arc add`, `arc rm --cached` |
| Commit with an **intent** (CIT) | ✓ button → intent picker | `arc commit -m … -i …` |
| Side-by-side diff + gutter change bars | click a file / editor gutter | `arc cat <ref> <path>` |
| Commit history (all branches) | **Arcane** view in the Activity Bar | `arc graph --json` |
| Commit **graph** (DAG, intent-colored) | webview, opened from the toolbar | `arc graph --json` |
| Branch / tag checkout | click the status-bar branch | `arc checkout` |
| Impact analysis (DAC) | right-click a commit → *Show Impact* | `arc impact` |

The JSON commands (`arc status --json`, `arc graph --json`, `arc cat`) ship with Arcane
itself — this extension never parses the human-facing CLI output.

## Requirements

- Arcane installed and the `arc` command runnable (see the [root README](../README.md)).
- The workspace folder must contain an `.arcane/` directory (run `arc init`).

## Setup (run from source)

```bat
cd vscode-arcane
npm install
npm run compile
```

Then press **F5** in VS Code (with this folder open) to launch an **Extension
Development Host**. Open a folder that contains an Arcane repository in that host window —
the **Arcane** icon appears in the Activity Bar and the branch shows in the status bar.

> Prefer `npm run watch` while developing so changes recompile automatically; reload the
> dev host with `Ctrl+R` to pick them up.

## Configuration

| Setting | Default | Description |
|---|---|---|
| `arcane.executablePath` | `arc` | Path to the `arc` executable. Supports `${workspaceFolder}`. When left as `arc`, the extension also auto-detects a virtualenv at `${workspaceFolder}/.venv` (`Scripts\arc.exe` on Windows, `bin/arc` elsewhere). |
| `arcane.autoRefresh` | `true` | Refresh the UI automatically when files change. |

If `arc` isn't on your `PATH`, point this at the venv binary, e.g.
`${workspaceFolder}\.venv\Scripts\arc.exe`.

## How it maps to the SCM API

- `vscode.scm.createSourceControl('arcane', …)` — the Source Control provider.
- Three `SourceControlResourceGroup`s — Staged / Changes / Untracked.
- `inputBox` + `acceptInputCommand` — the commit message box and ✓ button.
- `quickDiffProvider` — gutter change indicators, served from the `arcane:` content provider.
- A `TextDocumentContentProvider` for the `arcane:` scheme — returns `arc cat HEAD <path>`
  so the diff editor can show HEAD ↔ Working Tree.
- A `TreeDataProvider` — the commit-history list.
- A `WebviewPanel` — the commit graph (lane layout + SVG, computed in `src/graph.ts`).

## Notes / limitations

- Diffs compare **HEAD ↔ working tree** (Arcane has no separate "index content" read path
  yet), so staged-vs-HEAD diffs show the same content as working-vs-HEAD.
- *Discard* restores a file to its **HEAD** version (or deletes it if untracked).
- The graph draws parent edges as curves between nodes; with very wide histories the lanes
  may cross — this is cosmetic and doesn't affect correctness.
