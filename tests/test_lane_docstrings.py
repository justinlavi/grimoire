"""The module docstring of each install and registration rite states what the rite does:
every flag it parses, its mutation profile and its exit codes."""

import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES = REPO_ROOT / "rites"

CLI_MODULES = [
    "summon.py",
    "summon_state.py",
    "sync_library.py",
    "adopt_grimoire.py",
    "install_grimoire.py",
    "inject_agent_file.py",
    "plugin_auto_update.py",
]
PROFILED_MODULES = CLI_MODULES + ["summon_core.py"]


def _docstring(name: str) -> str:
    return ast.get_docstring(ast.parse((RITES / name).read_text(encoding="utf-8"))) or ""


def _flags(name: str) -> set[str]:
    source = (RITES / name).read_text(encoding="utf-8")
    flags = set()
    for call in re.findall(r"add_argument\(([^)]*)\)", source, re.DOTALL):
        flags.update(re.findall(r'"(--[a-z][a-z-]*)"', call))
    return flags


@pytest.mark.parametrize("name", CLI_MODULES)
def test_the_docstring_names_every_flag_the_rite_parses(name):
    docstring = _docstring(name)
    missing = sorted(flag for flag in _flags(name) if flag not in docstring)
    assert not missing, f"{name} parses {missing} but its docstring does not name them"


@pytest.mark.parametrize("name", PROFILED_MODULES)
def test_the_docstring_states_the_mutation_profile(name):
    assert "Mutation profile:" in _docstring(name)


@pytest.mark.parametrize("name", CLI_MODULES)
def test_the_docstring_states_the_exit_codes(name):
    assert "Exit codes:" in _docstring(name)


def test_the_profiles_in_the_docstrings_match_the_profile_contract():
    profiles = {entry["path"]: entry["profile"] for entry in
                json.loads((RITES / "data" / "rite_profiles.json").read_text(encoding="utf-8"))["profiles"]}
    for name in ("sync_library.py", "adopt_grimoire.py", "install_grimoire.py",
                 "plugin_auto_update.py", "summon_core.py"):
        profile = profiles[f"rites/{name}"]
        assert f"Mutation profile: {profile}" in _docstring(name), name
