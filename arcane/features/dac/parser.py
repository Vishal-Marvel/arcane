"""DAC — Language-specific dependency parsers."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Protocol


class DependencyParser(Protocol):
    def parse(self, file_path: Path, content: str, repo_root: Path) -> set[str]:
        """Return set of repo-relative dependency paths."""
        ...


class PythonParser:
    """Extracts imports from Python files using the AST."""

    def parse(self, file_path: Path, content: str, repo_root: Path) -> set[str]:
        deps: set[str] = set()
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return deps

        file_dir = file_path.parent

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = self._resolve_module(alias.name, file_dir, repo_root)
                    if resolved:
                        deps.add(resolved)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    resolved = self._resolve_module(node.module, file_dir, repo_root)
                    if resolved:
                        deps.add(resolved)
                elif node.level and node.level > 0:
                    # Relative import
                    base = file_dir
                    for _ in range(node.level - 1):
                        base = base.parent
                    if node.module:
                        module_path = base / node.module.replace(".", "/")
                    else:
                        module_path = base
                    for suffix in (".py", "/__init__.py"):
                        candidate = Path(str(module_path) + suffix)
                        if candidate.exists():
                            try:
                                deps.add(candidate.relative_to(repo_root).as_posix())
                            except ValueError:
                                pass
                            break

        return deps

    def _resolve_module(self, module_name: str, file_dir: Path, repo_root: Path) -> str | None:
        """Try to resolve a dotted module name to a repo-relative path."""
        parts = module_name.split(".")
        # Try as a relative path from repo root
        candidate = repo_root
        for part in parts:
            candidate = candidate / part
        for suffix in (".py", "/__init__.py"):
            p = Path(str(candidate) + suffix) if suffix == ".py" else candidate / "__init__.py"
            if p.exists():
                try:
                    return p.relative_to(repo_root).as_posix()
                except ValueError:
                    pass
        return None


class JavaScriptParser:
    """Extracts relative imports from JS/TS files using regex."""

    IMPORT_RE = re.compile(
        r"""(?:import|require)\s*(?:\(['"](\.\.?/[^'"]+)['"]\)|[^'"]*from\s+['"](\.\.?/[^'"]+)['"])""",
        re.MULTILINE,
    )
    JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

    def parse(self, file_path: Path, content: str, repo_root: Path) -> set[str]:
        deps: set[str] = set()
        file_dir = file_path.parent
        for match in self.IMPORT_RE.finditer(content):
            raw = match.group(1) or match.group(2)
            if not raw:
                continue
            candidate = (file_dir / raw).resolve()
            # Try with and without extension
            for ext in ("", *self.JS_EXTENSIONS):
                p = Path(str(candidate) + ext) if ext else candidate
                if p.exists() and p.is_file():
                    try:
                        deps.add(p.relative_to(repo_root).as_posix())
                    except ValueError:
                        pass
                    break
                # Try index file
                index_candidate = candidate / f"index{ext}"
                if index_candidate.exists():
                    try:
                        deps.add(index_candidate.relative_to(repo_root).as_posix())
                    except ValueError:
                        pass
                    break
        return deps


class GoParser:
    """Extracts intra-repo imports from Go files using regex."""

    IMPORT_RE = re.compile(r'"([^"]+)"')

    def parse(self, file_path: Path, content: str, repo_root: Path) -> set[str]:
        # Only match imports block
        import_block = re.search(r'import\s*\(([^)]+)\)', content, re.DOTALL)
        single_imports = re.findall(r'import\s+"([^"]+)"', content)

        candidates: list[str] = single_imports
        if import_block:
            candidates += self.IMPORT_RE.findall(import_block.group(1))

        deps: set[str] = set()
        for imp in candidates:
            # Only intra-repo: must map to a real directory inside repo
            candidate_dir = repo_root / imp.replace("/", "\\")
            if candidate_dir.is_dir():
                for go_file in candidate_dir.glob("*.go"):
                    try:
                        deps.add(go_file.relative_to(repo_root).as_posix())
                    except ValueError:
                        pass
        return deps


# Registry: file extension → parser instance
_PARSERS: dict[str, DependencyParser] = {
    ".py": PythonParser(),
    ".js": JavaScriptParser(),
    ".jsx": JavaScriptParser(),
    ".ts": JavaScriptParser(),
    ".tsx": JavaScriptParser(),
    ".mjs": JavaScriptParser(),
    ".go": GoParser(),
}


def parse_dependencies(file_path: Path, content: str, repo_root: Path) -> set[str]:
    """Parse dependencies for any supported file type. Returns repo-relative paths."""
    ext = file_path.suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        return set()
    return parser.parse(file_path, content, repo_root)
