import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

export interface StatusEntry {
  status: 'A' | 'M' | 'D' | string;
  path: string;
}

export interface StatusResult {
  branch: string | null;
  detached: boolean;
  head: string | null;
  headShort: string | null;
  merging: boolean;
  staged: StatusEntry[];
  unstaged: StatusEntry[];
  untracked: string[];
}

export interface GraphCommit {
  hash: string;
  short: string;
  parents: string[];
  intent: string;
  scope: string | null;
  breaking: boolean;
  message: string;
  subject: string;
  author: string;
  timestamp: number;
}

export interface GraphRef {
  name: string;
  hash: string | null;
}

export interface GraphResult {
  head: string | null;
  headShort: string | null;
  currentBranch: string | null;
  detached: boolean;
  branches: GraphRef[];
  tags: GraphRef[];
  commits: GraphCommit[];
}

export class ArcError extends Error {
  constructor(message: string, public readonly stderr: string, public readonly code: number | null) {
    super(message);
  }
}

/** Thin wrapper around the `arc` CLI, scoped to one repository root. */
export class Arc {
  constructor(private readonly exe: string, private readonly cwd: string) {}

  /** Resolve the executable to use, honoring config and auto-detecting a local venv. */
  static resolveExecutable(folder: vscode.WorkspaceFolder): string {
    const cfg = vscode.workspace.getConfiguration('arcane');
    let exe = (cfg.get<string>('executablePath') || 'arc').trim();
    exe = exe.replace(/\$\{workspaceFolder\}/g, folder.uri.fsPath);

    if (exe === 'arc') {
      const root = folder.uri.fsPath;
      const candidates =
        process.platform === 'win32'
          ? [path.join(root, '.venv', 'Scripts', 'arc.exe'), path.join(root, '.venv', 'Scripts', 'arc')]
          : [path.join(root, '.venv', 'bin', 'arc')];
      for (const c of candidates) {
        if (fs.existsSync(c)) {
          return c;
        }
      }
    }
    return exe;
  }

  private exec(args: string[], opts: { encoding?: 'utf8' | 'buffer' } = {}): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      cp.execFile(
        this.exe,
        args,
        { cwd: this.cwd, windowsHide: true, maxBuffer: 64 * 1024 * 1024, encoding: 'buffer' },
        (err, stdout, stderr) => {
          if (err) {
            const code = (err as cp.ExecException).code;
            const numericCode = typeof code === 'number' ? code : null;
            reject(new ArcError(err.message, stderr.toString('utf8'), numericCode));
            return;
          }
          resolve(stdout as Buffer);
        }
      );
    });
  }

  private async json<T>(args: string[]): Promise<T> {
    const out = await this.exec(args);
    return JSON.parse(out.toString('utf8')) as T;
  }

  status(): Promise<StatusResult> {
    return this.json<StatusResult>(['status', '--json']);
  }

  graph(): Promise<GraphResult> {
    return this.json<GraphResult>(['graph', '--json']);
  }

  /** Return file content at a ref, or null if the file did not exist there. */
  async cat(ref: string, relPath: string): Promise<string | null> {
    try {
      const out = await this.exec(['cat', ref, relPath]);
      return out.toString('utf8');
    } catch {
      return null;
    }
  }

  async add(relPaths: string[]): Promise<void> {
    if (relPaths.length === 0) {
      return;
    }
    await this.exec(['add', ...relPaths]);
  }

  async rmCached(relPaths: string[]): Promise<void> {
    if (relPaths.length === 0) {
      return;
    }
    await this.exec(['rm', '--cached', ...relPaths]);
  }

  async commit(message: string, intent: string, scope?: string, breaking?: boolean): Promise<void> {
    const args = ['commit', '-m', message, '-i', intent];
    if (scope) {
      args.push('--scope', scope);
    }
    if (breaking) {
      args.push('--breaking');
    }
    await this.exec(args);
  }

  async checkout(target: string, createBranch = false): Promise<void> {
    const args = createBranch ? ['checkout', '-b', target] : ['checkout', target];
    await this.exec(args);
  }

  get executable(): string {
    return this.exe;
  }
}
