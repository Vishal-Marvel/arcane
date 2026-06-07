import * as vscode from 'vscode';
import { StatusResult } from './arc';

/** Shows the current Arcane branch in the status bar, like Git's branch indicator. */
export class ArcaneStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.item.command = 'arcane.checkout';
    this.item.tooltip = 'Arcane: switch branch or tag';
  }

  update(status: StatusResult): void {
    const name = status.detached
      ? `${status.headShort ?? 'detached'} (detached)`
      : status.branch ?? 'no branch';
    const dirty = status.staged.length + status.unstaged.length > 0 ? '*' : '';
    const merging = status.merging ? ' $(git-merge)' : '';
    this.item.text = `$(git-branch) ${name}${dirty}${merging}`;
    this.item.show();
  }

  hide(): void {
    this.item.hide();
  }

  dispose(): void {
    this.item.dispose();
  }
}
