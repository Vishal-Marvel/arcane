import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { Arc, ArcError, GraphCommit } from './arc';
import { GraphView } from './graph';
import { ArcaneHistoryProvider, CommitItem } from './history';
import { ArcaneScm } from './scm';
import { ArcaneStatusBar } from './statusBar';

const INTENTS: { label: string; detail: string }[] = [
  { label: 'feat', detail: 'A new feature' },
  { label: 'fix', detail: 'A bug fix' },
  { label: 'refactor', detail: 'Code change that neither fixes a bug nor adds a feature' },
  { label: 'perf', detail: 'A performance improvement' },
  { label: 'debt', detail: 'Acknowledged technical debt' },
  { label: 'docs', detail: 'Documentation only' },
  { label: 'test', detail: 'Adding or fixing tests' },
  { label: 'chore', detail: 'Tooling, config, or housekeeping' },
];

export function activate(context: vscode.ExtensionContext): void {
  const folder = findArcaneFolder();
  if (!folder) {
    return;
  }

  const exe = Arc.resolveExecutable(folder);
  const arc = new Arc(exe, folder.uri.fsPath);
  const root = folder.uri;

  const scm = new ArcaneScm(root);
  const statusBar = new ArcaneStatusBar();
  const history = new ArcaneHistoryProvider(arc);

  context.subscriptions.push(scm, statusBar);
  context.subscriptions.push(vscode.window.registerTreeDataProvider('arcaneHistory', history));

  // Content provider: serves a file's content at a commit (scheme "arcane"),
  // enabling real side-by-side diffs and the quick-diff gutter indicators.
  const contentProvider: vscode.TextDocumentContentProvider = {
    provideTextDocumentContent: async (uri) => {
      const ref = uri.query || 'HEAD';
      const rel = path.relative(root.fsPath, uri.fsPath).split(path.sep).join('/');
      return (await arc.cat(ref, rel)) ?? '';
    },
  };
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider('arcane', contentProvider)
  );

  let errorShown = false;
  async function refreshAll(): Promise<void> {
    try {
      const status = await arc.status();
      errorShown = false;
      scm.update(status);
      statusBar.update(status);
    } catch (e) {
      scm.clear();
      statusBar.hide();
      if (!errorShown) {
        errorShown = true;
        showArcError(e, exe);
      }
    }
    await history.refresh();
    GraphView.refreshIfOpen();
  }

  async function showCommitByHash(hash: string): Promise<void> {
    let commit: GraphCommit | undefined;
    try {
      const g = await arc.graph();
      commit = g.commits.find((c) => c.hash === hash || c.short === hash);
    } catch {
      /* ignore */
    }
    if (!commit) {
      return;
    }
    await showCommitDetails(arc, exe, root, commit);
  }

  // ── Commands ──────────────────────────────────────────────────────────────
  const reg = (id: string, fn: (...args: any[]) => any) =>
    context.subscriptions.push(vscode.commands.registerCommand(id, fn));

  reg('arcane.refresh', () => refreshAll());

  reg('arcane.commit', async () => {
    const message = scm.inputValue.trim();
    if (!message) {
      vscode.window.showWarningMessage('Arcane: enter a commit message first.');
      return;
    }
    const pick = await vscode.window.showQuickPick(
      INTENTS.map((i) => ({ label: i.label, detail: i.detail })),
      { title: 'Commit intent (CIT)', placeHolder: 'Choose the intent for this commit' }
    );
    if (!pick) {
      return;
    }
    try {
      await arc.commit(message, pick.label);
      scm.inputValue = '';
      await refreshAll();
      vscode.window.setStatusBarMessage(`Arcane: committed [${pick.label}] ${message}`, 4000);
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.stage', async (...args: any[]) => {
    const rels = collectUris(args).map((u) => scm.relPath(u));
    try {
      await arc.add(rels);
      await refreshAll();
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.unstage', async (...args: any[]) => {
    const rels = collectUris(args).map((u) => scm.relPath(u));
    try {
      await arc.rmCached(rels);
      await refreshAll();
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.stageAll', async (...args: any[]) => {
    try {
      const status = await arc.status();
      const rels = [...status.unstaged.map((e) => e.path), ...status.untracked];
      await arc.add(rels.length ? rels : collectUris(args).map((u) => scm.relPath(u)));
      await refreshAll();
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.unstageAll', async () => {
    try {
      const status = await arc.status();
      await arc.rmCached(status.staged.map((e) => e.path));
      await refreshAll();
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.discard', async (...args: any[]) => {
    const uris = collectUris(args);
    if (uris.length === 0) {
      return;
    }
    const ok = await vscode.window.showWarningMessage(
      `Discard changes in ${uris.length} file(s)? This restores the HEAD version and cannot be undone.`,
      { modal: true },
      'Discard'
    );
    if (ok !== 'Discard') {
      return;
    }
    for (const uri of uris) {
      const rel = scm.relPath(uri);
      const head = await arc.cat('HEAD', rel);
      try {
        if (head === null) {
          await vscode.workspace.fs.delete(uri);
        } else {
          await vscode.workspace.fs.writeFile(uri, Buffer.from(head, 'utf8'));
        }
      } catch {
        /* file may not exist; ignore */
      }
    }
    await refreshAll();
  });

  reg('arcane.openChange', async (uri: vscode.Uri, status: string, _staged: boolean, untracked: boolean) => {
    const name = path.basename(uri.fsPath);
    if (untracked || status === 'A') {
      await vscode.commands.executeCommand('vscode.open', uri);
      return;
    }
    const left = uri.with({ scheme: 'arcane', query: 'HEAD' });
    await vscode.commands.executeCommand('vscode.diff', left, uri, `${name} (HEAD ↔ Working Tree)`);
  });

  reg('arcane.checkout', async () => {
    try {
      const g = await arc.graph();
      const items: (vscode.QuickPickItem & { value?: string; create?: boolean })[] = [];
      items.push({ label: 'Branches', kind: vscode.QuickPickItemKind.Separator });
      for (const b of g.branches) {
        items.push({
          label: `$(git-branch) ${b.name}`,
          description: b.name === g.currentBranch ? 'current' : b.hash?.slice(0, 8),
          value: b.name,
        });
      }
      if (g.tags.length) {
        items.push({ label: 'Tags', kind: vscode.QuickPickItemKind.Separator });
        for (const t of g.tags) {
          items.push({ label: `$(tag) ${t.name}`, description: t.hash?.slice(0, 8), value: t.name });
        }
      }
      items.push({ label: '', kind: vscode.QuickPickItemKind.Separator });
      items.push({ label: '$(add) Create new branch…', create: true });

      const pick = await vscode.window.showQuickPick(items, { title: 'Checkout', placeHolder: 'Switch to a branch or tag' });
      if (!pick) {
        return;
      }
      if (pick.create) {
        await vscode.commands.executeCommand('arcane.createBranch');
        return;
      }
      if (pick.value) {
        await arc.checkout(pick.value);
        await refreshAll();
      }
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.createBranch', async () => {
    const name = await vscode.window.showInputBox({
      title: 'Create branch',
      prompt: 'New branch name (created at HEAD and checked out)',
      validateInput: (v) => (v.trim() ? null : 'Enter a branch name'),
    });
    if (!name) {
      return;
    }
    try {
      await arc.checkout(name.trim(), true);
      await refreshAll();
    } catch (e) {
      showArcError(e, exe);
    }
  });

  reg('arcane.openGraph', () => GraphView.show(arc, (hash) => void showCommitByHash(hash)));

  reg('arcane.copyCommitHash', async (item: CommitItem) => {
    if (item?.commit) {
      await vscode.env.clipboard.writeText(item.commit.hash);
      vscode.window.setStatusBarMessage(`Arcane: copied ${item.commit.short}`, 3000);
    }
  });

  reg('arcane.showCommit', (item: CommitItem) => {
    if (item?.commit) {
      void showCommitDetails(arc, exe, root, item.commit);
    }
  });

  reg('arcane.impactCommit', (item: CommitItem) => {
    if (item?.commit) {
      runImpact(exe, root, item.commit.hash);
    }
  });

  // ── Auto-refresh on file/repo changes ───────────────────────────────────────
  let timer: NodeJS.Timeout | undefined;
  const debouncedRefresh = () => {
    const cfg = vscode.workspace.getConfiguration('arcane');
    if (!cfg.get<boolean>('autoRefresh', true)) {
      return;
    }
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => void refreshAll(), 300);
  };

  const watcher = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(folder, '**/*'));
  watcher.onDidChange(debouncedRefresh);
  watcher.onDidCreate(debouncedRefresh);
  watcher.onDidDelete(debouncedRefresh);
  context.subscriptions.push(watcher);
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(debouncedRefresh));

  void refreshAll();
}

export function deactivate(): void {
  /* nothing to clean up beyond context.subscriptions */
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function findArcaneFolder(): vscode.WorkspaceFolder | undefined {
  const folders = vscode.workspace.workspaceFolders ?? [];
  return folders.find((f) => fs.existsSync(path.join(f.uri.fsPath, '.arcane')));
}

/** Flatten command arguments (resource states, groups, uris, arrays) into a uri list. */
function collectUris(args: any[]): vscode.Uri[] {
  const out: vscode.Uri[] = [];
  const seen = new Set<string>();
  const visit = (a: any): void => {
    if (!a) {
      return;
    }
    if (Array.isArray(a)) {
      a.forEach(visit);
    } else if (a.resourceStates) {
      a.resourceStates.forEach(visit);
    } else if (a.resourceUri instanceof vscode.Uri) {
      add(a.resourceUri);
    } else if (a instanceof vscode.Uri) {
      add(a);
    }
  };
  const add = (u: vscode.Uri) => {
    if (!seen.has(u.toString())) {
      seen.add(u.toString());
      out.push(u);
    }
  };
  args.forEach(visit);
  return out;
}

async function showCommitDetails(
  arc: Arc,
  exe: string,
  root: vscode.Uri,
  commit: GraphCommit
): Promise<void> {
  const date = new Date(commit.timestamp * 1000).toLocaleString();
  const lines = [
    commit.message,
    '',
    `intent: ${commit.intent}${commit.scope ? `  scope: ${commit.scope}` : ''}${commit.breaking ? '  BREAKING' : ''}`,
    `author: ${commit.author}`,
    `date:   ${date}`,
    `commit: ${commit.hash}`,
  ];
  const choice = await vscode.window.showInformationMessage(
    lines.join('\n'),
    { modal: true },
    'Copy Hash',
    'Show Impact'
  );
  if (choice === 'Copy Hash') {
    await vscode.env.clipboard.writeText(commit.hash);
  } else if (choice === 'Show Impact') {
    runImpact(exe, root, commit.hash);
  }
}

function runImpact(exe: string, root: vscode.Uri, hash: string): void {
  const term = vscode.window.createTerminal({ name: 'Arcane Impact', cwd: root.fsPath });
  term.show();
  const quoted = /\s/.test(exe) ? `"${exe}"` : exe;
  term.sendText(`${quoted} impact ${hash}`);
}

function showArcError(e: unknown, exe: string): void {
  if (e instanceof ArcError) {
    const detail = (e.stderr || e.message).trim().split('\n').slice(-3).join(' ');
    vscode.window.showErrorMessage(`Arcane: ${detail || 'command failed'} (using "${exe}")`);
  } else {
    vscode.window.showErrorMessage(`Arcane: ${String(e)}`);
  }
}
