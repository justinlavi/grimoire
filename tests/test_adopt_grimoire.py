"""Temp-target tests for the grimoire adoption rite."""

import json
import subprocess
import sys
from pathlib import Path


import adopt_grimoire

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "adopt_grimoire.py"


def _adopt(home: Path, directory: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RITE), directory, "--home", str(home), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_adopt_grimoire_json_envelope(tmp_path):
    home = tmp_path / "grimoires"
    target = home / "dnd-grimoire"
    target.mkdir(parents=True)

    result = _adopt(home, "dnd-grimoire", "--skill-prefix", "dnd", "--format", "json")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["rite"] == "adopt_grimoire"
    assert report["status"] == "ok"
    assert report["mode"] == "apply"
    assert report["mutations"][0]["action"] == "write"
    assert report["mutations"][0]["path"] == "dnd-grimoire/grimoire.json"

    manifest_path = target / "grimoire.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["skill_prefix"] == "dnd"
    assert manifest["name"] == "dnd-grimoire"


def test_adopt_grimoire_json_collision_is_clean(tmp_path):
    home = tmp_path / "grimoires"

    # First grimoire claims the "dnd" skill prefix.
    first = home / "dnd-grimoire"
    first.mkdir(parents=True)
    (first / "grimoire.json").write_text(
        json.dumps({"name": "dnd-grimoire", "skill_prefix": "dnd", "description": "x"}) + "\n",
        encoding="utf-8",
    )

    # Second grimoire wants the same skill prefix -> collision (exit 1; 2 is argparse's).
    second = home / "other-grimoire"
    second.mkdir(parents=True)

    result = _adopt(home, "other-grimoire", "--skill-prefix", "dnd", "--format", "json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["rite"] == "adopt_grimoire"
    assert report["status"] == "error"
    assert report["mutations"] == []
    assert any(msg["severity"] == "error" for msg in report["messages"])

    # No manifest was written for the second grimoire.
    assert not (second / "grimoire.json").is_file()


def test_adopt_grimoire_human_mode_writes_manifest(tmp_path):
    home = tmp_path / "grimoires"
    target = home / "dnd-grimoire"
    target.mkdir(parents=True)

    result = _adopt(home, "dnd-grimoire", "--skill-prefix", "dnd")

    assert result.returncode == 0
    assert "Wrote" in result.stdout
    manifest_path = target / "grimoire.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["skill_prefix"] == "dnd"


def test_a_prefix_the_framework_owns_is_refused(tmp_path):
    home = tmp_path / "grimoires"
    target = home / "notes-grimoire"
    target.mkdir(parents=True)

    result = _adopt(home, "notes-grimoire", "--skill-prefix", "grm", "--format", "json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error" and report["mutations"] == []
    assert any("belongs to the framework" in m["message"] for m in report["messages"])
    assert not (target / "grimoire.json").exists()


def test_the_manifest_is_written_as_utf8_with_lf(tmp_path):
    home = tmp_path / "grimoires"
    target = home / "travel"
    target.mkdir(parents=True)

    result = _adopt(home, "travel", "--skill-prefix", "tr", "--description", "日本の旅", "--format", "json")

    assert result.returncode == 0, result.stderr
    raw = (target / "grimoire.json").read_bytes()
    assert "日本の旅".encode("utf-8") in raw and b"\r" not in raw
    assert json.loads(raw.decode("utf-8"))["description"] == "日本の旅"


def test_find_existing_skill_prefixes_reads_manifests_through_the_shared_loader(tmp_path):
    home = tmp_path / "grimoires"
    (home / "one").mkdir(parents=True)
    (home / "one" / "grimoire.json").write_text(json.dumps({"name": "one", "skill_prefix": "on"}), encoding="utf-8")
    (home / "broken").mkdir()
    (home / "broken" / "grimoire.json").write_bytes(b"\xff\xfe not json")
    (home / "list").mkdir()
    (home / "list" / "grimoire.json").write_text("[1]", encoding="utf-8")
    (home / "typed").mkdir()
    (home / "typed" / "grimoire.json").write_text(json.dumps({"name": "t", "skill_prefix": 5}), encoding="utf-8")

    assert adopt_grimoire.find_existing_skill_prefixes(home) == {"on": "one"}


def test_the_framework_prefixes_are_those_of_its_command_families():
    assert adopt_grimoire.framework_skill_prefixes() == {"grm"}
