"""The committed plugins/ tree is the render of the skill sources, and every plugin skill is self-contained."""

import json
import re
import subprocess
import sys
from pathlib import Path

import build_plugins

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS = REPO_ROOT / "plugins"
RITE = REPO_ROOT / "rites" / "build_plugins.py"


def test_marketplace_lists_both_plugins_from_inside_the_repository():
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == "grimoire"
    entries = {p["name"]: p for p in marketplace["plugins"]}
    assert set(entries) == {"grimoire", "grimoire-dev"}
    for name, entry in entries.items():
        assert entry["source"] == f"./plugins/{name}"
        assert (REPO_ROOT / "plugins" / name / ".claude-plugin" / "plugin.json").is_file()


def test_committed_render_matches_sources():
    result = subprocess.run([sys.executable, str(RITE), "--format", "json"], capture_output=True, text=True, timeout=120)
    report = json.loads(result.stdout)
    assert result.returncode == 0, report
    assert report["status"] == "noop"
    assert report["summary"]["create"] == report["summary"]["update"] == report["summary"]["remove"] == 0


def test_each_plugin_carries_the_release_number_in_its_manifest_alone():
    release = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    for family in ("grimoire", "grimoire-dev"):
        manifest = json.loads((PLUGINS / family / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == family
        assert manifest["version"] == release
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert all("version" not in entry for entry in marketplace["plugins"])


def test_plugin_skills_are_slug_named_self_contained_and_framework_rooted():
    skills = sorted(PLUGINS.glob("*/skills/*/SKILL.md"))
    assert skills, "no plugin skills rendered"
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        slug = skill.parent.name
        assert f"\nname: {slug}\n" in text, skill
        assert "!`" not in text, f"{skill} still carries a dynamic-context directive"
        assert "{{FRAMEWORK_PATH}}" not in text and "{{SKILL_PREFIX}}" not in text and "FRAMEWORK_HOME/" not in text, skill
        assert "~/.grimoire" in text, f"{skill} does not reference the framework home"
        assert text.count("\n") < 500, f"{skill} exceeds the 500-line skill guidance"


def test_grimoire_plugin_carries_the_hook_and_the_routing_block_copy():
    hooks = json.loads((PLUGINS / "grimoire" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    commands = [h["command"] for group in hooks["hooks"]["SessionStart"] for h in group["hooks"]]
    assert any("session_context.sh" in c for c in commands)
    assert (PLUGINS / "grimoire" / "scripts" / "session_context.py").is_file()
    template = (REPO_ROOT / "rites" / "templates" / "grimoire_block.md").read_text(encoding="utf-8")
    assert (PLUGINS / "grimoire" / "scripts" / "grimoire_block.md").read_text(encoding="utf-8") == template


def test_render_names_every_shipped_skill_once():
    rendered = build_plugins.render_all()
    for family in ("grimoire", "grimoire-dev"):
        slugs = sorted(k.split("/")[2] for k in rendered if k.startswith(f"{family}/skills/"))
        assert slugs and len(slugs) == len(set(slugs)), family
    assert {"grimoire/skills/add/SKILL.md", "grimoire-dev/skills/validate/SKILL.md", "grimoire/.claude-plugin/plugin.json"} <= set(rendered)


def test_plugin_skills_spell_commands_the_way_a_plugin_install_types_them():
    text = build_plugins.plugin_command_names(
        "Run `/grm-update skills`, then /grm-dev-validate. The `/grm-*` verbs and the /grm-dev-* verbs. "
        "Folders such as ~/.claude/skills/grm-add and the `grm-` prefix keep their names."
    )
    assert "`/grimoire:update skills`" in text
    assert "/grimoire-dev:validate" in text
    assert "`/grimoire:*` verbs" in text and "/grimoire-dev:* verbs" in text
    assert "skills/grm-add" in text and "`grm-` prefix" in text

    for skill in sorted(PLUGINS.glob("*/skills/*/SKILL.md")):
        body = skill.read_text(encoding="utf-8")
        assert "/grm-" not in body.replace("skills/grm-", ""), f"{skill} names a flat command"


def _marketplace_entries():
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return {entry["name"]: entry for entry in marketplace["plugins"]}


def test_rendered_plugin_descriptions_are_the_marketplace_entries():
    rendered = build_plugins.render_all()
    for name, entry in _marketplace_entries().items():
        manifest = json.loads(rendered[f"{name}/.claude-plugin/plugin.json"])
        assert manifest["description"] == entry["description"], name


def test_each_description_names_exactly_the_verbs_its_plugin_carries():
    rendered = build_plugins.render_all()
    for name, entry in _marketplace_entries().items():
        named = re.search(r"\(([^)]*)\)", entry["description"])
        assert named, f"{name}: the description lists no verbs in parentheses"
        verbs = sorted(verb.strip() for verb in named.group(1).split(","))
        carried = sorted(k.split("/")[2] for k in rendered if k.startswith(f"{name}/skills/"))
        assert verbs == carried, name


def test_plugin_descriptions_state_the_task_not_the_audience():
    for entry in _marketplace_entries().values():
        assert "people who" not in entry["description"]


def test_render_all_loads_the_command_catalog_once(monkeypatch):
    calls = []
    real = build_plugins.sync_skills.collect_framework_skill_specs
    monkeypatch.setattr(
        build_plugins.sync_skills, "collect_framework_skill_specs", lambda *a, **k: calls.append(1) or real(*a, **k)
    )

    build_plugins.render_all()

    assert len(calls) == 1
