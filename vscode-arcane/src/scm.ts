import * as path from 'path';
import * as vscode from 'vscode';
import { StatusEntry, StatusResult } from './arc';

const STATUS_LABEL: Record<string, string> = {
  A: 'Added',
  M: 'Modified',
  D: 'Deleted',
};

const STATUS_ICON: Record<string, string> = {
  A: 'diff-added',
  M: 'diff-modified',
  D: 'diff-removed',
};

/** Owns the VS Code SourceControl object: the three resource groups and the commit input. */
export class ArcaneScm implements vscode.Disposable {
  readonly sourceControl: vscode.SourceControl;
  private readonly staged: vscode.SourceControlResourceGroup;
  private readonly changes: vscode.SourceControlResourceGroup;
  private readonly untracked: vscode.SourceControlResourceGroup;
  private readonly disposables: vscode.Disposable[] = [];

  constructor(private readonly root: vscode.Uri) {
    this.sourceControl = vscode.scm.createSourceControl('arcane', 'Arcane', root);
    this.sourceControl.inputBox.placeholder = 'Message (press the ✓ to commit and pick an intent)';
    this.sourceControl.acceptInputCommand = { command: 'arcane.commit', title: 'Commit' };
    this.sourceControl.quickDiffProvider = {
      provideOriginalResource: (uri) =>
        uri.scheme === 'file' ? uri.with({ scheme: 'arcane', query: 'HEAD' }) : undefined,
    };

    this.staged = this.sourceControl.createResourceGroup('staged', 'Staged Changes');
    this.changes = this.sourceControl.createResourceGroup('changes', 'Changes');
    this.untracked = this.sourceControl.createResourceGroup('untracked', 'Untracked');
    for (const g of [this.staged, this.changes, this.untracked]) {
      g.hideWhenEmpty = true;
    }

    this.disposables.push(this.sourceControl);
  }

  get inputValue(): string {
    return this.sourceControl.inputBox.value;
  }

  set inputValue(v: string) {
    this.sourceControl.inputBox.value = v;
  }

  update(status: StatusResult): void {
    this.staged.resourceStates = status.staged.map((e) => this.resource(e, true));
    this.changes.resourceStates = status.unstaged.map((e) => this.resource(e, false));
    this.untracked.resourceStates = status.untracked.map((p) =>
      this.resource({ status: 'A', path: p }, false, true)
    );
    this.sourceControl.count =
      status.staged.length + status.unstaged.length + status.untracked.length;

    const branch = status.detached
      ? `(detached ${status.headShort ?? ''})`
      : status.branch ?? 'no branch';
    this.sourceControl.inputBox.placeholder = `Message — committing to ${branch}`;
  }

  clear(): void {
    this.staged.resourceStates = [];
    this.changes.resourceStates = [];
    this.untracked.resourceStates = [];
    this.sourceControl.count = 0;
  }

  private fileUri(rel: string): vscode.Uri {
    return vscode.Uri.joinPath(this.root, ...rel.split('/'));
  }

  private resource(entry: StatusEntry, staged: boolean, untracked = false): vscode.SourceControlResourceState {
    const uri = this.fileUri(entry.path);
    const icon = untracked ? 'diff-added' : STATUS_ICON[entry.status] ?? 'diff-modified';
    const label = untracked ? 'Untracked' : STATUS_LABEL[entry.status] ?? entry.status;
    return {
      resourceUri: uri,
      decorations: {
        tooltip: label,
        strikeThrough: entry.status === 'D',
        faded: untracked,
        iconPath: new vscode.ThemeIcon(icon),
      },
      command: {
        command: 'arcane.openChange',
        title: 'Open Change',
        arguments: [uri, entry.status, staged, untracked],
      },
    };
  }

  /** Repo-relative, forward-slash path for a workspace file URI. */
  relPath(uri: vscode.Uri): string {
    return path.relative(this.root.fsPath, uri.fsPath).split(path.sep).join('/');
  }

  dispose(): void {
    this.disposables.forEach((d) => d.dispose());
  }
}
