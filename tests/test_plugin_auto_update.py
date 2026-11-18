"""plugin_auto_update.py sets autoUpdate on the marketplace entry Claude Code already holds, and nothing else."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "plugin_auto_update.py"


def _run(settings: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), "--settings", str(settings), "--format", "json", *extra],
        capture_output=True, text=True, timeout=60,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout)}


def _settings(tmp_path: Path, content: dict) -> Path:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    return path


DECLARED = {
    "enabledPlugins": {"grimoire@grimoire": True},
    "extraKnownMarketplaces": {
        "grimoire": {"source": {"source": "github", "repo": "justinlavi/grimoire"}},
        "other": {"source": {"source": "github", "repo": "someone/else"}},
    },
    "permissions": {"allow": ["Bash(git status:*)"]},
}


def test_plan_writes_nothing_and_apply_sets_only_the_one_key(tmp_path):
    path = _settings(tmp_path, DECLARED)
    before = path.read_text(encoding="utf-8")

    plan = _run(path)
    assert plan["returncode"] == 0 and plan["report"]["status"] == "noop"
    assert plan["report"]["summary"]["auto_update"] is False
    assert path.read_text(encoding="utf-8") == before

    applied = _run(path, "--apply")
    assert applied["returncode"] == 0, applied
    assert applied["report"]["mutations"][0]["action"] == "write"
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["extraKnownMarketplaces"]["grimoire"]["autoUpdate"] is True
    expected = json.loads(before)
    expected["extraKnownMarketplaces"]["grimoire"]["autoUpdate"] = True
    assert after == expected  # every other setting, and the other marketplace, untouched
    assert not (tmp_path / "settings.json.tmp").exists()


def test_already_on_is_a_noop(tmp_path):
    content = json.loads(json.dumps(DECLARED))
    content["extraKnownMarketplaces"]["grimoire"]["autoUpdate"] = True
    path = _settings(tmp_path, content)
    before = path.read_text(encoding="utf-8")
    out = _run(path, "--apply")
    assert out["returncode"] == 0 and out["report"]["status"] == "noop"
    assert out["report"]["summary"]["auto_update"] is True
    assert out["report"]["mutations"] == []
    assert path.read_text(encoding="utf-8") == before


def test_a_marketplace_that_is_not_declared_is_refused(tmp_path):
    path = _settings(tmp_path, {"extraKnownMarketplaces": {"other": {"source": {"source": "github", "repo": "a/b"}}}})
    out = _run(path, "--apply")
    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert "not declared" in out["report"]["messages"][0]["message"]


def test_missing_or_unreadable_settings_are_refused(tmp_path):
    missing = _run(tmp_path / "absent.json", "--apply")
    assert missing["returncode"] == 1 and missing["report"]["status"] == "blocked"

    broken = tmp_path / "settings.json"
    broken.write_text("{ not json", encoding="utf-8")
    out = _run(broken, "--apply")
    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert broken.read_text(encoding="utf-8") == "{ not json"
