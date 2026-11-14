"""The committed plugins/ tree is the render of the skill sources, and every plugin skill is self-contained."""

import json
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


def test_plugin_manifests_carry_the_release_version():
    version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    for family in ("grimoire", "grimoire-dev"):
        manifest = json.loads((PLUGINS / family / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == family
        assert manifest["version"] == version


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
