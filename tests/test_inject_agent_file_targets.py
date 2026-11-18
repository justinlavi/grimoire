"""inject_agent_file: files that are not UTF-8, installed agents only, one writer."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import inject_agent_file as I
import summon_core

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "inject_agent_file.py"


@pytest.mark.parametrize(
    "encoding",
    ["utf-16", "cp1252"],
)
def test_apply_leaves_a_file_that_is_not_utf8_untouched(tmp_path, encoding):
    target = tmp_path / "AGENTS.md"
    original = "# AGENTS\nnotes: café\n".encode(encoding)
    target.write_bytes(original)

    result = I.apply_block(target, "AGENTS", apply=True)

    assert result["action"] == "review" and result["status"] == "review"
    assert result["reason"] == "not UTF-8"
    assert target.read_bytes() == original


def test_the_rite_reports_a_file_that_is_not_utf8_for_review(tmp_path):
    target = tmp_path / "AGENTS.md"
    original = "café\n".encode("utf-16")
    target.write_bytes(original)
    result = I.apply_block(target, "AGENTS", apply=False)
    assert result["action"] == "review" and result["reason"] == "not UTF-8"
    assert target.read_bytes() == original


def test_apply_block_is_the_core_writer(tmp_path):
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    assert I.apply_block(first, "A", apply=True) == {
        **summon_core.apply_routing_block(second, "A", apply=True),
        "path": str(first),
    }
    assert first.read_bytes() == second.read_bytes()


def test_the_reasons_come_from_the_core_table():
    for content, action in ((None, "create"), ("x\n", "insert")):
        assert I.plan_block(content) == (action, summon_core.ROUTING_REASONS[action])


def test_resolve_targets_covers_installed_agents_only(tmp_path):
    (tmp_path / ".codex").mkdir()
    assert [t["id"] for t in I.resolve_targets(REPO_ROOT, "all", tmp_path)] == ["codex"]
    assert [t["path"] for t in I.resolve_targets(REPO_ROOT, "all", tmp_path)] == [tmp_path / ".codex" / "AGENTS.md"]


def test_an_agent_named_explicitly_is_resolved_whether_or_not_it_is_installed(tmp_path):
    (tmp_path / ".codex").mkdir()
    assert [t["id"] for t in I.resolve_targets(REPO_ROOT, "claude", tmp_path)] == ["claude"]


def test_with_no_agent_installed_every_target_counts(tmp_path):
    assert [t["id"] for t in I.resolve_targets(REPO_ROOT, "all", tmp_path)] == ["claude", "codex"]


def test_the_cli_exit_code_is_1_when_a_file_cannot_be_written(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "CLAUDE.md").mkdir(parents=True)  # a folder where the file belongs
    result = subprocess.run(
        [sys.executable, str(RITE), "--agent", "claude", "--apply", "--format", "json"],
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "HOME": str(home), "USERPROFILE": str(home)},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "error" and report["mutations"] == []
