"""Tests for DAC dependency parsers."""

import pytest
from pathlib import Path

from arcane.features.dac.parser import PythonParser, JavaScriptParser


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


def test_python_parser_import(repo_root: Path):
    dep_file = repo_root / "utils" / "token.py"
    dep_file.parent.mkdir(parents=True)
    dep_file.write_text("# token module\n")

    source_file = repo_root / "auth" / "login.py"
    source_file.parent.mkdir(parents=True)
    content = "from utils.token import get_token\n"

    parser = PythonParser()
    deps = parser.parse(source_file, content, repo_root)
    assert "utils/token.py" in deps


def test_python_parser_no_deps(repo_root: Path):
    source_file = repo_root / "main.py"
    content = "import os\nimport sys\nprint('hello')\n"
    parser = PythonParser()
    deps = parser.parse(source_file, content, repo_root)
    # os and sys are stdlib, not in repo
    assert len(deps) == 0


def test_python_parser_syntax_error(repo_root: Path):
    source_file = repo_root / "broken.py"
    parser = PythonParser()
    deps = parser.parse(source_file, "def (broken syntax:", repo_root)
    assert deps == set()


def test_js_parser_relative_import(repo_root: Path):
    dep_file = repo_root / "utils" / "api.js"
    dep_file.parent.mkdir(parents=True)
    dep_file.write_text("// api\n")

    source_file = repo_root / "components" / "App.js"
    source_file.parent.mkdir(parents=True)
    content = "import { fetch } from '../utils/api';\n"

    parser = JavaScriptParser()
    deps = parser.parse(source_file, content, repo_root)
    assert "utils/api.js" in deps
