# Arcane VCS — VS Code extension

Brings Git-style source control to the **Arcane** version control system:
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

- Arcane installed and the `arc` command runnable (see the Arcane repository root README).
- The workspace folder must contain an `.arcane/` directory (run `arc init`).

## Install

There are two ways to get the extension into VS Code. **Most users want Option A.**
(Verified on VS Code 1.102, Windows.)

### Option A — Install the packaged `.vsix` (permanent)

1. Build the package (one time):
   ```bat
   cd vscode-arcane
   npm install
   npm run package      REM produces vscode-arcane-0.1.0.vsix
   ```
   *(Or use the prebuilt `vscode-arcane-0.1.0.vsix` if it's already in this folder.)*
2. Install it, either way:
   - **From the UI:** open the Extensions view (`Ctrl+Shift+X`) → click the **`...`**
     menu at the top of the panel → **Install from VSIX…** → select the `.vsix`.
   - **From the terminal:**
     ```bat
     code --install-extension vscode-arcane-0.1.0.vsix
     ```
3. Reload: `Ctrl+Shift+P` → **Developer: Reload Window**.

To update later, rebuild the `.vsix` and install again (it overwrites). To remove it:
Extensions view → find **Arcane VCS** → gear icon → **Uninstall**.

### Option B — Run from source (for developing the extension)

```bat
cd vscode-arcane
npm install
npm run compile
```

Open the `vscode-arcane` folder in VS Code and press **F5** → an **Extension Development
Host** window launches with the extension loaded. Use `npm run watch` and reload the host
(`Ctrl+R`) to pick up code changes.

## After installing: open an Arcane repo

The extension only activates in a folder that **contains a `.arcane/` directory**
(it watches for `workspaceContains:**/.arcane`). The Arcane *source* repo uses Git, not
Arcane — so to actually see the UI, open a folder that is an Arcane repository:

1. `File → Open Folder…` and pick a repo created with `arc init`
   (e.g. the `taskflow-demo` from `TRY_ARCANE.md`).
2. You should now see:
   - the **Arcane** icon in the **Activity Bar** (left rail) → opens the **History** view;
   - the current branch in the **status bar** (bottom-left, e.g. `$(git-branch) main`);
   - an **Arcane** provider in the **Source Control** view (`Ctrl+Shift+G`).

> If you also have Git initialized in the same folder, VS Code shows **both** providers in
> the Source Control view — that's expected; they're independent.

## Configuration

Open settings with `Ctrl+,` and search **arcane**, or edit `settings.json` directly.

| Setting | Default | Description |
|---|---|---|
| `arcane.executablePath` | `arc` | Path to the `arc` executable. Supports `${workspaceFolder}`. When left as `arc`, the extension also auto-detects a virtualenv at `${workspaceFolder}/.venv` (`Scripts\arc.exe` on Windows, `bin/arc` elsewhere). |
| `arcane.autoRefresh` | `true` | Refresh the UI automatically when files change. |

### Pointing the extension at `arc`

The extension shells out to `arc`. It finds it in this order: (1) your
`arcane.executablePath` setting, (2) a `.venv` inside the open folder, (3) `arc` on your
system `PATH`. Pick whichever fits:

- **`arc` is already on your PATH** → leave the default. Verify in a VS Code terminal:
  ```bat
  arc --version
  ```
- **You installed Arcane into its repo's virtualenv** (the common case) → point the
  setting at that absolute path. In **User** settings (`settings.json`):
  ```json
  {
    "arcane.executablePath": "D:\\projects\\arcane\\.venv\\Scripts\\arc.exe"
  }
  ```
  (Use **double backslashes** in JSON.) Adjust the path to wherever your Arcane checkout is.
- **The open folder has its own `.venv`** → no setting needed; auto-detection finds
  `.venv\Scripts\arc.exe`.

> **Important:** the executable path is read **once when the extension activates**. After
> changing `arcane.executablePath`, run **Developer: Reload Window** for it to take effect.

### Workspace vs. User settings

- Put it in **User** settings if you want it everywhere.
- Put it in **Workspace** settings (`.vscode/settings.json` in the repo) if the path is
  repo-specific — this is also where `${workspaceFolder}` is most useful, e.g.
  `"arcane.executablePath": "${workspaceFolder}\\.venv\\Scripts\\arc.exe"`.

## Using it

- **Stage / unstage:** hover a file in the Source Control view and click `+` / `-`, or use
  the group-level icons to stage/unstage everything.
- **Commit:** type a message in the Source Control input box, click the **✓** (or run
  **Arcane: Commit**) → pick a **CIT intent** (feat/fix/refactor/…). The commit is made
  with `arc commit -m … -i <intent>`.
- **Diffs & gutter bars:** click a changed file to open **HEAD ↔ Working Tree**; change
  bars appear in the editor gutter automatically.
- **Open the graph:** click the **merge** icon in the Source Control title bar or the
  History view title bar, or run **Arcane: Open Commit Graph**.
- **Switch branch/tag:** click the branch name in the status bar.
- **Impact (DAC):** right-click a commit in the History view → **Show Impact**.

### Troubleshooting

- **Nothing appears / no Arcane icon:** the open folder probably has no `.arcane/`. Open an
  Arcane repo, or run `arc init` in the current folder, then **Reload Window**.
- **"command failed (using …)" error toast:** the `arc` path is wrong. Run `arc --version`
  in the terminal, set `arcane.executablePath` to a working path, and **Reload Window**.
- **Changes don't refresh:** make sure `arcane.autoRefresh` is `true`, or run
  **Arcane: Refresh** (also on the Source Control / History title bars).

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
