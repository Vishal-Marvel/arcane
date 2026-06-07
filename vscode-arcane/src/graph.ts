import * as vscode from 'vscode';
import { Arc, GraphResult } from './arc';

/** A singleton webview panel that draws the commit DAG. */
export class GraphView {
  private static current: GraphView | undefined;
  private readonly panel: vscode.WebviewPanel;
  private disposed = false;

  static show(arc: Arc, onSelect: (hash: string) => void): void {
    if (GraphView.current) {
      GraphView.current.panel.reveal(vscode.ViewColumn.Active);
      void GraphView.current.refresh();
      return;
    }
    GraphView.current = new GraphView(arc, onSelect);
  }

  static refreshIfOpen(): void {
    void GraphView.current?.refresh();
  }

  private constructor(private readonly arc: Arc, private readonly onSelect: (hash: string) => void) {
    this.panel = vscode.window.createWebviewPanel('arcaneGraph', 'Arcane: Commit Graph', vscode.ViewColumn.Active, {
      enableScripts: true,
      retainContextWhenHidden: true,
    });
    this.panel.webview.html = this.html();
    this.panel.webview.onDidReceiveMessage((msg) => {
      if (msg?.type === 'ready') {
        void this.refresh();
      } else if (msg?.type === 'select' && typeof msg.hash === 'string') {
        this.onSelect(msg.hash);
      }
    });
    this.panel.onDidDispose(() => {
      this.disposed = true;
      GraphView.current = undefined;
    });
  }

  async refresh(): Promise<void> {
    if (this.disposed) {
      return;
    }
    let data: GraphResult;
    try {
      data = await this.arc.graph();
    } catch {
      return;
    }
    void this.panel.webview.postMessage({ type: 'graph', data });
  }

  private html(): string {
    const nonce = makeNonce();
    const csp = `default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';`;
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>
  :root { --row-h: 30px; }
  body { margin: 0; padding: 0; font-family: var(--vscode-font-family); font-size: var(--vscode-font-size);
         color: var(--vscode-foreground); background: var(--vscode-editor-background); }
  #empty { padding: 24px; color: var(--vscode-descriptionForeground); }
  #wrap { position: relative; }
  #graph { position: absolute; left: 0; top: 0; }
  #rows { position: relative; }
  .row { display: flex; align-items: center; height: var(--row-h); white-space: nowrap;
         padding-right: 12px; cursor: pointer; box-sizing: border-box; }
  .row:hover { background: var(--vscode-list-hoverBackground); }
  .badge { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 8px; margin-right: 8px;
           color: #fff; flex: 0 0 auto; }
  .ref { font-size: 11px; padding: 1px 6px; border-radius: 4px; margin-right: 6px; flex: 0 0 auto;
         border: 1px solid var(--vscode-contrastBorder, transparent); }
  .ref.branch { background: rgba(88,166,255,0.18); color: #58a6ff; }
  .ref.head   { background: rgba(63,185,80,0.20); color: #3fb950; font-weight: 600; }
  .ref.tag    { background: rgba(210,153,34,0.20); color: #d29922; }
  .subject { overflow: hidden; text-overflow: ellipsis; }
  .hash { color: var(--vscode-descriptionForeground); margin-right: 10px; font-family: var(--vscode-editor-font-family); flex: 0 0 auto; }
  .meta { color: var(--vscode-descriptionForeground); margin-left: auto; padding-left: 16px; flex: 0 0 auto; font-size: 11px; }
</style>
</head>
<body>
  <div id="empty">Loading commit graph…</div>
  <div id="wrap" style="display:none">
    <svg id="graph"></svg>
    <div id="rows"></div>
  </div>
<script nonce="${nonce}">
const vscode = acquireVsCodeApi();
const ROW_H = 30, LANE_W = 18, R = 5, PAD = 12;
const INTENT_COLORS = {
  feat: '#3fb950', fix: '#f85149', refactor: '#58a6ff', perf: '#bc8cff',
  debt: '#d29922', docs: '#db61a2', test: '#8b949e', chore: '#6e7681'
};
const LANE_COLORS = ['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#39c5cf','#db61a2','#8b949e'];

window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'graph') { render(e.data.data); }
});

function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function render(data) {
  const commits = data.commits || [];
  const empty = document.getElementById('empty');
  const wrap = document.getElementById('wrap');
  if (commits.length === 0) {
    empty.textContent = 'No commits yet.';
    empty.style.display = 'block';
    wrap.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  wrap.style.display = 'block';

  // ── Lane assignment: classic git-graph column allocation ──
  const lanes = [];                 // lanes[i] = hash the lane is currently waiting to reach
  const pos = {};                   // hash -> { row, col }
  commits.forEach((c, row) => {
    let col = lanes.indexOf(c.hash);
    if (col < 0) {
      col = lanes.indexOf(null);
      if (col < 0) { col = lanes.length; lanes.push(null); }
    }
    // Any other lane also waiting for this commit (a merge point) collapses here.
    for (let i = 0; i < lanes.length; i++) {
      if (i !== col && lanes[i] === c.hash) { lanes[i] = null; }
    }
    pos[c.hash] = { row, col };
    lanes[col] = c.parents[0] || null;       // continue first parent in this lane
    for (let p = 1; p < c.parents.length; p++) {
      let free = lanes.indexOf(null);
      if (free < 0) { free = lanes.length; lanes.push(null); }
      lanes[free] = c.parents[p];            // extra parents branch into new lanes
    }
  });

  let maxCol = 0;
  for (const c of commits) { maxCol = Math.max(maxCol, pos[c.hash].col); }
  const graphW = PAD + (maxCol + 1) * LANE_W;
  const height = commits.length * ROW_H;

  const cx = (col) => PAD + col * LANE_W;
  const cy = (row) => row * ROW_H + ROW_H / 2;

  // ── Edges (child -> each existing parent) ──
  let svgParts = '';
  for (const c of commits) {
    const a = pos[c.hash];
    for (const ph of c.parents) {
      const b = pos[ph];
      if (!b) { continue; }
      const x1 = cx(a.col), y1 = cy(a.row), x2 = cx(b.col), y2 = cy(b.row);
      const color = LANE_COLORS[Math.min(a.col, b.col) % LANE_COLORS.length];
      if (x1 === x2) {
        svgParts += '<path d="M' + x1 + ' ' + y1 + ' L' + x2 + ' ' + y2 + '" stroke="' + color + '" fill="none" stroke-width="1.6"/>';
      } else {
        const my = (y1 + y2) / 2;
        svgParts += '<path d="M' + x1 + ' ' + y1 + ' C' + x1 + ' ' + my + ' ' + x2 + ' ' + my + ' ' + x2 + ' ' + y2 + '" stroke="' + color + '" fill="none" stroke-width="1.6"/>';
      }
    }
  }
  // ── Nodes ──
  for (const c of commits) {
    const a = pos[c.hash];
    const fill = INTENT_COLORS[c.intent] || '#8b949e';
    svgParts += '<circle cx="' + cx(a.col) + '" cy="' + cy(a.row) + '" r="' + R + '" fill="' + fill + '" stroke="var(--vscode-editor-background)" stroke-width="1.5"/>';
  }

  const svg = document.getElementById('graph');
  svg.setAttribute('width', graphW);
  svg.setAttribute('height', height);
  svg.innerHTML = svgParts;

  // ── Ref tips ──
  const tips = {};
  const push = (h, html) => { if (!h) return; (tips[h] = tips[h] || []).push(html); };
  for (const b of (data.branches || [])) {
    const cls = b.name === data.currentBranch ? 'ref head' : 'ref branch';
    push(b.hash, '<span class="' + cls + '">' + esc(b.name) + '</span>');
  }
  for (const t of (data.tags || [])) {
    push(t.hash, '<span class="ref tag">' + esc(t.name) + '</span>');
  }

  // ── Rows ──
  const rows = document.getElementById('rows');
  rows.style.marginLeft = graphW + 'px';
  rows.style.height = height + 'px';
  let rowsHtml = '';
  for (const c of commits) {
    const fill = INTENT_COLORS[c.intent] || '#8b949e';
    const date = new Date(c.timestamp * 1000).toLocaleDateString();
    const refHtml = (tips[c.hash] || []).join('');
    rowsHtml +=
      '<div class="row" data-hash="' + c.hash + '" title="' + esc(c.message) + '">' +
        '<span class="badge" style="background:' + fill + '">' + esc(c.intent) + '</span>' +
        refHtml +
        '<span class="subject">' + esc(c.subject) + '</span>' +
        '<span class="meta">' + esc(c.short) + ' · ' + esc(c.author.split(' <')[0]) + ' · ' + date + '</span>' +
      '</div>';
  }
  rows.innerHTML = rowsHtml;
  for (const el of rows.querySelectorAll('.row')) {
    el.addEventListener('click', () => vscode.postMessage({ type: 'select', hash: el.getAttribute('data-hash') }));
  }
}

vscode.postMessage({ type: 'ready' });
</script>
</body>
</html>`;
  }
}

function makeNonce(): string {
  let s = '';
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    s += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return s;
}
