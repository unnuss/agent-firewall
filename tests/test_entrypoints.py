"""Both ways of starting the CLI must be the same CLI.

The project ships two entry points. `pyproject.toml` declares an `agentfw` console script, and
`agentfw/__main__.py` lets the package be run as a module. The second exists because the
generated `.exe` launcher is unsigned and an Application Control policy blocks it on at least
one machine, while `python.exe` is signed and runs.

Two entry points is two chances for them to drift. These tests close that: the module entry
must *delegate* rather than re-implement, and the observable behaviour of both paths must be
byte-identical. Comparing real subprocess output rather than inspecting objects, because what a
user experiences is the process, not the import graph.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import agentfw

ROOT = Path(agentfw.__file__).resolve().parent.parent
MAIN = Path(agentfw.__file__).resolve().parent / "__main__.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Decode as UTF-8 explicitly. `text=True` alone uses the locale codec, which on Windows
    # is cp1252, and the CLI reconfigures its stdout to UTF-8 before printing arrows and em
    # dashes -- so the default would hand back mojibake and a correct assertion would fail.
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )


# ---------------------------------------------------------------------------
# the module entry must delegate, not duplicate
# ---------------------------------------------------------------------------


def test_the_module_entry_point_exists():
    assert MAIN.exists(), "agentfw/__main__.py is missing; `python -m agentfw` will not work"


def test_the_module_entry_point_defines_no_cli_of_its_own():
    """`__main__.py` may resolve `cli.main` and nothing else.

    A second `ArgumentParser` here would drift from the real one silently, and the two entry
    points would begin disagreeing about what a flag means. This is the "do not duplicate CLI
    logic" requirement expressed as a check rather than as a comment.
    """
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    forbidden = {"ArgumentParser", "add_argument", "add_parser", "set_defaults"}
    used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    duplicated = sorted(used & forbidden)
    assert not duplicated, f"__main__.py builds its own parser: {duplicated}"
    # It must import the shared entry function.
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "main" in imported, "__main__.py must import agentfw.cli.main"


def test_the_module_entry_calls_the_same_function_the_console_script_declares():
    """`pyproject.toml`'s script target and `__main__.py`'s import must be one function."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    target = pyproject["project"]["scripts"]["agentfw"]
    assert target == "agentfw.cli:main", f"console script points at {target!r}"

    from agentfw.__main__ import main as module_main
    from agentfw.cli import main as cli_main

    assert module_main is cli_main, "the two entry points resolve to different functions"


# ---------------------------------------------------------------------------
# the two paths must behave identically as processes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("args", [["--help"], ["demo", "--help"], ["learn", "--help"]])
def test_module_and_cli_paths_produce_identical_help(args: list[str]):
    """`python -m agentfw X` and `python -m agentfw.cli X` must agree, byte for byte.

    `--help` is the sharpest comparison available: argparse renders every subcommand, flag,
    default and help string, so a divergence anywhere in the parser shows up here.
    """
    via_package = _run(["-m", "agentfw", *args])
    via_module = _run(["-m", "agentfw.cli", *args])
    assert via_package.returncode == via_module.returncode
    # argparse prints the program name from sys.argv[0]; both are invoked as modules, and the
    # parser sets prog="agentfw" explicitly, so the text should match without normalisation.
    assert via_package.stdout == via_module.stdout


def test_the_module_path_reports_the_program_as_agentfw():
    """A user reading the help must see the command they are meant to type."""
    out = _run(["-m", "agentfw", "--help"])
    assert out.returncode == 0, out.stderr
    assert "usage: agentfw" in out.stdout


def test_an_unknown_subcommand_fails_the_same_way_on_both_paths():
    via_package = _run(["-m", "agentfw", "no-such-command"])
    via_module = _run(["-m", "agentfw.cli", "no-such-command"])
    assert via_package.returncode == via_module.returncode != 0


def test_the_module_path_actually_runs_a_real_command():
    """Help text agreeing is necessary but not sufficient; run something that does work.

    `demo --brief --no-color` replays four committed episodes through the reference monitor and
    needs no key and no network, so it is safe to run inside the suite.
    """
    out = _run(["-m", "agentfw", "demo", "--brief", "--no-color"])
    assert out.returncode == 0, out.stderr[-600:]
    assert out.stdout.count("SCENE") == 4
    assert "ASK -> DENIED" in out.stdout or "ASK → DENIED" in out.stdout


def test_the_readme_documents_the_module_fallback():
    """The fallback is useless if a blocked user cannot find it."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python -m agentfw" in readme, "README does not mention the `python -m` fallback"
