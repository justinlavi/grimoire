"""Contract tests for the framework agent target registry."""

import json
import shutil
from pathlib import Path

import pytest

import agent_targets
import sync_skills as sync_skills

REPO_ROOT = Path(__file__).resolve().parent.parent


def _registry_ids() -> list[str]:
    return [entry["id"] for entry in agent_targets.target_entries(agent_targets.load_agent_targets(REPO_ROOT))]


def _record_plugins(home: Path, plugins: dict) -> None:
    record = home / ".claude" / "plugins" / "installed_plugins.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")


def test_agent_target_registry_is_valid():
    contract, errors = agent_targets.validate_agent_targets(REPO_ROOT)

    assert not errors
    assert contract is not None
    assert _registry_ids() == [
        "claude",
        "codex",
        "chatgpt-hosted",
        "github-copilot",
        "cursor",
    ]


def test_agent_target_registry_drives_registration_targets():
    expected = agent_targets.skill_registration_targets(REPO_ROOT)

    # An id names its target whether or not that agent is installed.
    for agent in ("claude", "codex"):
        assert sync_skills.selected_targets(agent) == [(agent, expected[agent])]
    assert expected["claude"]["pointer_only"] is False
    assert expected["codex"]["pointer_only"] is True


def test_agent_target_docs_cover_registry_entries():
    contract = json.loads((REPO_ROOT / agent_targets.CONTRACT_PATH).read_text(encoding="utf-8"))
    docs = (REPO_ROOT / "docs" / "agent_targets.md").read_text(encoding="utf-8")

    for entry in agent_targets.target_entries(contract):
        assert entry["label"] in docs
        assert str(entry["instruction_target"]) in docs
        if entry["skill_target"] is not None:
            assert entry["skill_target"] in docs


def test_summon_source_bootstrap_downloads_agent_target_contract():
    bootstrap = (REPO_ROOT / "rites" / "summon.sh").read_text(encoding="utf-8")

    assert "rites/agent_targets.py" in bootstrap
    assert "rites/data/agent_targets.json" in bootstrap
    assert '"$SCRIPT_DIR/data/agent_targets.json"' in bootstrap


def test_installed_plugins_map_to_command_families(tmp_path):
    assert agent_targets.family_plugins(REPO_ROOT) == {"grimoire": "grm", "grimoire-dev": "dev"}
    _record_plugins(tmp_path, {"grimoire@grimoire": [{}], "other@elsewhere": [{}]})
    assert agent_targets.installed_framework_plugins(REPO_ROOT, "grimoire", tmp_path / ".claude") == {"grm"}


def test_a_plugin_of_another_marketplace_does_not_count(tmp_path):
    _record_plugins(tmp_path, {"grimoire@someone-elses": [{}], "grimoire-dev@someone-elses": [{}], "grimoire": [{}]})
    claude_home = tmp_path / ".claude"
    assert agent_targets.installed_plugin_names("grimoire", claude_home) == set()
    assert agent_targets.installed_framework_plugins(REPO_ROOT, "grimoire", claude_home) == set()
    targets = agent_targets.skill_registration_targets(REPO_ROOT, tmp_path)
    assert targets["claude"]["plugin_families"] == set()


def test_registry_marketplace_decides_which_plugins_serve_the_claude_target(tmp_path):
    _record_plugins(tmp_path, {"grimoire@grimoire": [{}], "grimoire-dev@grimoire": [{}]})
    targets = agent_targets.skill_registration_targets(REPO_ROOT, tmp_path)
    assert targets["claude"]["plugin_families"] == {"grm", "dev"}
    assert targets["codex"]["plugin_families"] == set()
    assert targets["claude"]["path"] == tmp_path / ".claude" / "skills"


def test_the_marketplace_name_is_validated(tmp_path):
    root = tmp_path / "root"
    (root / "rites" / "data").mkdir(parents=True)
    contract = json.loads((REPO_ROOT / agent_targets.CONTRACT_PATH).read_text(encoding="utf-8"))
    contract["targets"][0]["plugin_marketplace"] = ""
    (root / "rites" / "data" / "agent_targets.json").write_text(json.dumps(contract), encoding="utf-8")
    _contract, errors = agent_targets.validate_agent_targets(root)
    assert any("plugin_marketplace" in error["message"] for error in errors)


# ---------------------------------------------------------------------------
# An agent that is not installed is not configured
# ---------------------------------------------------------------------------


def test_agent_home_is_the_parent_of_the_instruction_target(tmp_path):
    entries = {entry["id"]: entry for entry in agent_targets.target_entries(agent_targets.load_agent_targets(REPO_ROOT))}
    assert agent_targets.agent_home(entries["claude"], tmp_path) == tmp_path / ".claude"
    assert agent_targets.agent_home(entries["codex"], tmp_path) == tmp_path / ".codex"
    assert agent_targets.agent_home(entries["cursor"], tmp_path) is None


@pytest.mark.parametrize(
    "folders, expected",
    [
        ([], ["claude", "codex"]),
        ([".claude"], ["claude"]),
        ([".codex"], ["codex"]),
        ([".claude", ".codex"], ["claude", "codex"]),
        ([".agents"], ["claude", "codex"]),
    ],
)
def test_only_agents_with_a_home_folder_are_configured(tmp_path, folders, expected):
    for folder in folders:
        (tmp_path / folder).mkdir()
    assert agent_targets.installed_agent_ids(REPO_ROOT, tmp_path) == expected
    assert [t["id"] for t in agent_targets.installed_instruction_targets(REPO_ROOT, tmp_path)] == expected
    assert list(agent_targets.installed_skill_targets(REPO_ROOT, tmp_path)) == expected


def test_the_unfiltered_targets_keep_every_agent(tmp_path):
    (tmp_path / ".claude").mkdir()
    assert [t["id"] for t in agent_targets.automatic_instruction_targets(REPO_ROOT, tmp_path)] == ["claude", "codex"]
    assert list(agent_targets.skill_registration_targets(REPO_ROOT, tmp_path)) == ["claude", "codex"]


def test_instruction_paths_resolve_against_the_given_home(tmp_path):
    (tmp_path / ".codex").mkdir()
    (target,) = agent_targets.installed_instruction_targets(REPO_ROOT, tmp_path)
    assert target["path"] == tmp_path / ".codex" / "AGENTS.md"
    assert target["title"] == "AGENTS.md"


def test_the_grimoire_plugin_serves_the_routing_block(tmp_path):
    (tmp_path / ".claude").mkdir()
    _record_plugins(tmp_path, {"grimoire@grimoire": [{}]})
    (target,) = agent_targets.installed_instruction_targets(REPO_ROOT, tmp_path)
    assert target["plugin_serves_routing"] is True

    _record_plugins(tmp_path, {"grimoire-dev@grimoire": [{}], "grimoire@elsewhere": [{}]})
    (target,) = agent_targets.installed_instruction_targets(REPO_ROOT, tmp_path)
    assert target["plugin_serves_routing"] is False


def test_the_bootstrap_modules_do_not_depend_on_the_registry_copy_in_the_checkout(tmp_path):
    root = tmp_path / "bootstrap"
    (root / "rites" / "data").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "rites" / "data" / "agent_targets.json", root / "rites" / "data" / "agent_targets.json")
    assert agent_targets.installed_agent_ids(root, tmp_path) == ["claude", "codex"]
