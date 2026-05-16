"""DAC — Dependency graph data structure and traversal."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DependencyGraph:
    """Directed graph: edges[A] = {B, C} means A directly imports B and C."""

    edges: dict[str, set[str]] = field(default_factory=dict)

    def add_edge(self, source: str, target: str) -> None:
        self.edges.setdefault(source, set()).add(target)

    def direct_deps(self, file_path: str) -> set[str]:
        return self.edges.get(file_path, set())

    def transitive_deps(self, file_path: str) -> set[str]:
        """Return all files that file_path transitively depends on."""
        visited: set[str] = set()
        queue = [file_path]
        while queue:
            current = queue.pop()
            for dep in self.edges.get(current, set()):
                if dep not in visited:
                    visited.add(dep)
                    queue.append(dep)
        return visited

    def reverse_edges(self) -> dict[str, set[str]]:
        """Return the reverse graph: {B: {A, C}} means A and C import B."""
        rev: dict[str, set[str]] = {}
        for source, targets in self.edges.items():
            for target in targets:
                rev.setdefault(target, set()).add(source)
        return rev

    def transitive_dependents(self, changed_files: set[str]) -> set[str]:
        """Return all files that transitively depend on any file in changed_files.

        This is the 'impact radius': which files could break if changed_files changed.
        """
        rev = self.reverse_edges()
        visited: set[str] = set()
        queue = list(changed_files)
        while queue:
            current = queue.pop()
            for dependent in rev.get(current, set()):
                if dependent not in visited and dependent not in changed_files:
                    visited.add(dependent)
                    queue.append(dependent)
        return visited

    def to_dict(self) -> dict[str, list[str]]:
        return {k: sorted(v) for k, v in self.edges.items()}

    @classmethod
    def from_dict(cls, d: dict[str, list[str]]) -> "DependencyGraph":
        g = cls()
        for source, targets in d.items():
            g.edges[source] = set(targets)
        return g
