"""The grimoire plugin's session-start hook installs or updates the framework and prints routing context."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugins" / "grimoire" / "scripts" / "session_context.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _framework_remote(tmp_path: Path) -> Path:
    """A bare framework remote holding just what the hook reads (the routing block template)."""
    work = tmp_path / "framework-work"
    (work / "rites" / "templates").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "rites" / "templates" / "grimoire_block.md", work / "rites" / "templates" / "grimoire_block.md")
    (work / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "Tester")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "framework")
    bare = tmp_path / "framework.git"
    _git(work, "clone", "-q", "--bare", str(work), str(bare))
    return bare


def _run(tmp_path: Path, framework_home: Path, remote: Path, *, no_network: bool = False, claude_home: Path | None = None) -> str:
    env = dict(os.environ)
    env.update({
        "FRAMEWORK_HOME": str(framework_home),
        "FRAMEWORK_URL": str(remote),
        "FRAMEWORK_SESSION_HOME": str(tmp_path / "grimoires"),
        "FRAMEWORK_CLAUDE_HOME": str(claude_home or tmp_path / "claude-home"),
    })
    if no_network:
        env["FRAMEWORK_SESSION_NO_NETWORK"] = "1"
    result = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_first_session_clones_the_framework_and_prints_the_block(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"

    out = _run(tmp_path, framework, remote)

    assert (framework / ".git").is_dir()
    assert "framework: installed at" in out
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" in out
    assert "## Installed grimoires" in out
    assert "none registered yet" in out
    assert len(out) < 10000


def test_later_session_fast_forwards_a_clean_main_and_lists_grimoires(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    _run(tmp_path, framework, remote)

    # Upstream moves on; a grimoire gets registered.
    work = tmp_path / "framework-work"
    (work / "NOTE").write_text("x\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "more")
    _git(work, "push", "-q", str(remote), "main")
    home = tmp_path / "grimoires"
    shutil.copytree(GOOD, home / "good_grimoire")
    (home / "library.json").write_text(json.dumps({"grimoires": {"good_grimoire": {"local_path": str(home / "good_grimoire"), "online_path": None}}}), encoding="utf-8")

    out = _run(tmp_path, framework, remote)

    assert "framework: updated at" in out and "1 new commit" in out
    assert (framework / "NOTE").is_file()
    assert "- good_grimoire:" in out and "good fixture" in out.lower() or "- good_grimoire:" in out


def test_dirty_or_offbranch_framework_is_left_alone(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    _run(tmp_path, framework, remote)
    (framework / "VERSION").write_text("local edit\n", encoding="utf-8")

    out = _run(tmp_path, framework, remote)
    assert "with local changes; not updated" in out
    assert (framework / "VERSION").read_text(encoding="utf-8") == "local edit\n"

    _git(framework, "checkout", "-q", "--", "VERSION")
    _git(framework, "checkout", "-q", "-b", "release/next")
    out = _run(tmp_path, framework, remote)
    assert "on branch release/next; not updated" in out


def test_block_is_omitted_when_the_instruction_file_already_carries_it(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    template = (REPO_ROOT / "rites" / "templates" / "grimoire_block.md").read_text(encoding="utf-8")
    (claude_home / "CLAUDE.md").write_text("# CLAUDE\n" + template, encoding="utf-8")

    out = _run(tmp_path, framework, remote, claude_home=claude_home)
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" not in out
    assert "## Installed grimoires" in out


def test_no_network_degrades_to_a_note(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    out = _run(tmp_path, framework, remote, no_network=True)
    assert "framework: not installed" in out and "network disabled" in out
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" in out  # from the plugin's own copy
