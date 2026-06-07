import * as vscode from 'vscode';
import { Arc, GraphCommit, GraphResult } from './arc';

const INTENT_COLOR: Record<string, string> = {
  feat: 'charts.green',
  fix: 'charts.red',
  refactor: 'charts.blue',
  perf: 'charts.purple',
  debt: 'charts.yellow',
  docs: 'charts.purple',
  test: 'charts.foreground',
  chore: 'descriptionForeground',
};

export class CommitItem extends vscode.TreeItem {
  constructor(public readonly commit: GraphCommit, refLabels: string[]) {
    super(commit.subject || '(no message)', vscode.TreeItemCollapsibleState.None);
    this.contextValue = 'commit';
    this.id = commit.hash;

    const tips = refLabels.length ? `${refLabels.join(' ')} ` : '';
    this.description = `${tips}${commit.short} · ${commit.intent}`;

    const color = new vscode.ThemeColor(INTENT_COLOR[commit.intent] ?? 'charts.foreground');
    this.iconPath = new vscode.ThemeIcon('git-commit', color);

    const date = new Date(commit.timestamp * 1000).toLocaleString();
    const md = new vscode.MarkdownString();
    md.appendMarkdown(`**${commit.subject}**\n\n`);
    if (commit.message && commit.message !== commit.subject) {
      md.appendMarkdown(`${commit.message}\n\n`);
    }
    md.appendMarkdown(`\`${commit.intent}\``);
    if (commit.scope) {
      md.appendMarkdown(` · scope: \`${commit.scope}\``);
    }
    if (commit.breaking) {
      md.appendMarkdown(` · **BREAKING**`);
    }
    md.appendMarkdown(`\n\n${commit.author}  \n${date}  \n\`${commit.hash}\``);
    this.tooltip = md;
  }
}

/** Sidebar tree listing every commit across all refs (newest first). */
export class ArcaneHistoryProvider implements vscode.TreeDataProvider<CommitItem> {
  private readonly _onDidChange = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this._onDidChange.event;
  private commits: CommitItem[] = [];

  constructor(private readonly arc: Arc) {}

  getTreeItem(element: CommitItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: CommitItem): CommitItem[] {
    return element ? [] : this.commits;
  }

  async refresh(): Promise<void> {
    let graph: GraphResult;
    try {
      graph = await this.arc.graph();
    } catch {
      this.commits = [];
      this._onDidChange.fire();
      return;
    }

    const tipsByHash = new Map<string, string[]>();
    const addTip = (hash: string | null, label: string) => {
      if (!hash) {
        return;
      }
      const list = tipsByHash.get(hash) ?? [];
      list.push(label);
      tipsByHash.set(hash, list);
    };
    for (const b of graph.branches) {
      addTip(b.hash, b.name === graph.currentBranch ? `● ${b.name}` : b.name);
    }
    for (const t of graph.tags) {
      addTip(t.hash, `⌂ ${t.name}`);
    }

    this.commits = graph.commits.map((c) => new CommitItem(c, tipsByHash.get(c.hash) ?? []));
    this._onDidChange.fire();
  }
}
