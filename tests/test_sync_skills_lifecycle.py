"""Managed prefixes, library paths, the JSON envelope, safe replacement and placeholder scope for sync_skills."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import sync_skills

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "sync_skills.py"


def _grimoire(root: Path, prefix: str, skills: tuple[str, ...] = ("lookup",), name_template: str | None = None) -> Path:
    root.mkdir(parents=True)
    (root / "grimoire.json").write_text(
        json.dumps({"name": root.name, "skill_prefix": prefix, "description": "t"}) + "\n", encoding="utf-8"
    )
    for slug in skills:
        skill = root / "skills" / slug
        skill.mkdir(parents=True)
        declared = name_template or "{{SKILL_PREFIX}}-" + slug
        (skill / "SKILL.md").write_text(f"---\nname: {declared}\ndescription: d\n---\n\nbody\n", encoding="utf-8")
    return root


def _library(path: Path, entries: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"grimoires": entries}) + "\n", encoding="utf-8")
    return path


def _config(path: Path, **extra) -> dict:
    return {"label": "Test", "path": path, "pointer_only": True, **extra}


def test_stale_scan_covers_a_grimoire_that_dropped_its_last_skill(tmp_path, monkeypatch):
    # Prefix ownership comes from every library manifest, not from the skills that still exist.
    grimoire = _grimoire(tmp_path / "grimoires" / "cook", "cook", skills=())
    (grimoire / "skills").mkdir()
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", _library(tmp_path / "grimoires" / "library.json", {"cook": {"local_path": str(grimoire)}}))
    target = tmp_path / "skills"
    leftover = target / "cook-lookup"
    leftover.mkdir(parents=True)
    (leftover / "SKILL.md").write_text("registered earlier\n", encoding="utf-8")

    result = sync_skills.register_target("claude", _config(target), dry_run=False)

    assert result["cleaned"] == 1
    assert not leftover.exists()


def test_grimoire_without_a_skills_folder_still_owns_its_prefix(tmp_path, monkeypatch):
    grimoire = _grimoire(tmp_path / "grimoires" / "cook", "cook", skills=())
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", _library(tmp_path / "grimoires" / "library.json", {"cook": {"local_path": str(grimoire)}}))

    assert "cook-" in sync_skills.collect_catalog(None).prefixes


def test_scoped_run_does_not_claim_other_grimoires_prefixes(tmp_path, monkeypatch):
    first = _grimoire(tmp_path / "grimoires" / "cook", "cook")
    second = _grimoire(tmp_path / "grimoires" / "dnd", "dnd")
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", _library(
        tmp_path / "grimoires" / "library.json",
        {"cook": {"local_path": str(first)}, "dnd": {"local_path": str(second)}},
    ))

    prefixes = sync_skills.collect_catalog(str(first)).prefixes

    assert "cook-" in prefixes and "dnd-" not in prefixes


def test_dry_run_reset_reports_what_apply_resets(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", tmp_path / "missing.json")
    target = tmp_path / "skills"
    for name in ("grm-stale", "grm-old", "grm-add"):
        (target / name).mkdir(parents=True)
        (target / name / "SKILL.md").write_text("x\n", encoding="utf-8")

    planned = sync_skills.register_target("claude", _config(target), dry_run=True, reset_managed=True)
    applied = sync_skills.register_target("claude", _config(target), dry_run=False, reset_managed=True)

    assert planned["reset"] == applied["reset"] == 3
    assert planned["cleaned"] == applied["cleaned"] == 0
    assert not (target / "grm-stale").exists() and not (target / "grm-old").exists()


def test_deprecated_location_cleanup_removes_every_managed_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", tmp_path / "missing.json")
    old_root = tmp_path / "old" / "skills"
    for name in ("grm-stale", "grm-add", "personal"):
        (old_root / name).mkdir(parents=True)

    result = sync_skills.register_target(
        "codex", _config(tmp_path / "new" / "skills", deprecated_paths=[old_root]), dry_run=False
    )

    assert result["cleaned"] == 2
    assert [p.name for p in old_root.iterdir()] == ["personal"]


@pytest.mark.parametrize("local_path", ["", "relative/folder", "grimoires/cook"])
def test_library_entry_with_unusable_local_path_is_not_read_from_the_working_directory(tmp_path, monkeypatch, local_path):
    # The working directory holds a grimoire; an empty or relative entry must not resolve to it.
    cwd = _grimoire(tmp_path / "cwd", "cwd")
    (cwd / "relative" / "folder").mkdir(parents=True)
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", _library(tmp_path / "library.json", {"x": {"local_path": local_path}}))
    warnings = []

    catalog = sync_skills.collect_catalog(None, warnings.append)

    assert not [spec for spec in catalog.specs if spec.source_kind == "grimoire"]
    assert "cwd-" not in catalog.prefixes
    assert any("x: library local_path is empty or relative" in text for text in warnings)


def test_a_failed_swap_leaves_the_previous_skill_in_place(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", tmp_path / "missing.json")
    spec = next(s for s in sync_skills.collect_framework_skill_specs() if s.command_name == "grm-add")
    skills_target = tmp_path / "skills"
    target = skills_target / "grm-add"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("previous\n", encoding="utf-8")
    real_replace = os.replace

    def failing_replace(src, dst):
        if Path(src).name == "grm-add.tmp":
            raise PermissionError("locked")
        return real_replace(src, dst)

    monkeypatch.setattr(sync_skills.os, "replace", failing_replace)
    warnings = []

    assert sync_skills.write_rendered_skill(spec, target, skills_target, True, warnings.append) is False

    assert (target / "SKILL.md").read_text(encoding="utf-8") == "previous\n"
    assert sorted(p.name for p in skills_target.iterdir()) == ["grm-add"]
    assert any("Could not register /grm-add" in text for text in warnings)


def test_a_successful_swap_replaces_the_previous_skill_and_leaves_nothing_behind(tmp_path, monkeypatch):
    spec = next(s for s in sync_skills.collect_framework_skill_specs() if s.command_name == "grm-add")
    skills_target = tmp_path / "skills"
    target = skills_target / "grm-add"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("previous\n", encoding="utf-8")
    (target / "extra.md").write_text("gone\n", encoding="utf-8")

    assert sync_skills.write_rendered_skill(spec, target, skills_target, True) is True

    assert "previous" not in (target / "SKILL.md").read_text(encoding="utf-8")
    assert sorted(p.name for p in skills_target.iterdir()) == ["grm-add"]
    assert sorted(p.name for p in target.iterdir()) == ["SKILL.md"]


def test_collisions_are_detected_once_per_target(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_skills, "LOCAL_LIBRARY", tmp_path / "missing.json")
    calls = []
    real = sync_skills.detect_prefix_collisions
    monkeypatch.setattr(sync_skills, "detect_prefix_collisions", lambda specs: calls.append(1) or real(specs))

    sync_skills.register_target("claude", _config(tmp_path / "skills"), dry_run=True)

    assert len(calls) == 1


def test_framework_family_problems_are_reported(tmp_path, monkeypatch):
    (tmp_path / "framework.json").write_text(
        json.dumps({"skill_prefix": "grm", "skill_families": {"bad": {"skill_prefix": "Bad!", "path": "skills/x"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(sync_skills, "FRAMEWORK_PATH", tmp_path)
    warnings = []

    assert sync_skills.collect_framework_skill_specs(warnings.append) == []

    assert any("skill_families.bad has an invalid skill_prefix" in text for text in warnings)


def _run_json(home: Path, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    result = subprocess.run(
        [sys.executable, str(RITE), "--format", "json", *args],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
    )
    return result, json.loads(result.stdout)


def test_json_envelope_carries_counts_and_every_warning_and_only_json_on_stdout(tmp_path):
    home = tmp_path / "home"
    bad = _grimoire(home / "grimoires" / "bad", "bad", name_template="bad-wrong-name")
    _library(home / "grimoires" / "library.json", {
        "bad": {"local_path": str(bad)},
        "unset": {"local_path": ""},
    })

    result, report = _run_json(home, "--dry-run", "--agent", "claude")

    assert result.returncode == 0, result.stderr
    assert report["rite"] == "sync_skills"
    assert {"registered", "cleaned", "reset", "blocked"} <= set(report["summary"])
    warnings = [m["message"] for m in report["messages"] if m["severity"] == "warning"]
    assert any("SKILL.md name must be '{{SKILL_PREFIX}}-lookup'" in text for text in warnings)
    assert any("unset: library local_path is empty or relative" in text for text in warnings)


def test_json_envelope_reports_a_collision_as_an_error_with_exit_one(tmp_path):
    home = tmp_path / "home"
    first = _grimoire(home / "grimoires" / "one", "dup")
    second = _grimoire(home / "grimoires" / "two", "dup")
    _library(home / "grimoires" / "library.json", {"one": {"local_path": str(first)}, "two": {"local_path": str(second)}})

    result, report = _run_json(home, "--agent", "claude")

    assert result.returncode == 1
    assert report["summary"]["blocked"] >= 1
    assert any(m["severity"] == "error" and "dup" in m["message"] for m in report["messages"])


def test_unknown_agent_exits_two(tmp_path):
    home = tmp_path / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    result = subprocess.run(
        [sys.executable, str(RITE), "--agent", "no-such-agent"], capture_output=True, text=True, timeout=60, env=env
    )

    assert result.returncode == 2
    assert "unknown --agent" in result.stderr


def test_targets_are_resolved_when_asked_not_at_import(tmp_path, monkeypatch):
    (tmp_path / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert [agent for agent, _config in sync_skills.selected_targets("all")] == ["claude"]
    assert sync_skills.selected_targets("claude")[0][1]["path"] == tmp_path / ".claude" / "skills"


def test_an_explicit_agent_is_used_even_when_it_is_not_installed(tmp_path, monkeypatch):
    (tmp_path / ".claude").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    [(agent, config)] = sync_skills.selected_targets("codex")

    assert agent == "codex"
    assert not (tmp_path / ".codex").exists()
    assert config["path"] == tmp_path / ".agents" / "skills"
