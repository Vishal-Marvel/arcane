"""Tests for DependencyGraph."""

import pytest
from arcane.features.dac.graph import DependencyGraph


def test_transitive_dependents():
    g = DependencyGraph()
    g.add_edge("app.py", "auth.py")
    g.add_edge("auth.py", "token.py")
    g.add_edge("utils.py", "token.py")

    # token.py changed — who is affected?
    impacted = g.transitive_dependents({"token.py"})
    assert "auth.py" in impacted
    assert "utils.py" in impacted
    assert "app.py" in impacted


def test_no_dependents():
    g = DependencyGraph()
    g.add_edge("app.py", "lib.py")
    impacted = g.transitive_dependents({"app.py"})
    assert len(impacted) == 0


def test_roundtrip_dict():
    g = DependencyGraph()
    g.add_edge("a.py", "b.py")
    g.add_edge("b.py", "c.py")

    d = g.to_dict()
    g2 = DependencyGraph.from_dict(d)
    assert g2.direct_deps("a.py") == {"b.py"}
    assert g2.direct_deps("b.py") == {"c.py"}


def test_transitive_deps():
    g = DependencyGraph()
    g.add_edge("a.py", "b.py")
    g.add_edge("b.py", "c.py")
    deps = g.transitive_deps("a.py")
    assert "b.py" in deps
    assert "c.py" in deps
