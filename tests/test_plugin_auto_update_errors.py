"""plugin_auto_update says what actually failed when it cannot read or write the settings file."""

import json
import subprocess
import sys
from pathlib import Path

import plugin_auto_update

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "plugin_auto_update.py"

DECLARED = {"extraKnownMarketplaces": {"grimoire": {"source": {"source": "github", "repo": "a/b"}}}}


def _run(settings: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), "--settings", str(settings), "--format", "json", *extra],
        capture_output=True, text=True, timeout=60,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout)}


def test_a_missing_file_is_called_a_missing_file(tmp_path):
    state, settings, reason = plugin_auto_update.inspect(tmp_path / "absent.json", "grimoire")
    assert state == "blocked" and settings is None
    assert reason == f"no settings file at {tmp_path / 'absent.json'}"


def test_a_settings_path_that_cannot_be_read_is_not_called_a_missing_file(tmp_path):
    folder = tmp_path / "settings.json"
    folder.mkdir()  # reading a folder as a file fails with a permission or is-a-directory error
    out = _run(folder, "--apply")
    message = out["report"]["messages"][0]["message"]
    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert message.startswith(f"could not read {folder}")
    assert "no settings file" not in message


def test_a_read_that_fails_for_a_reason_other_than_absence_names_the_reason(tmp_path, monkeypatch):
    def denied(_path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(plugin_auto_update, "read_utf8", denied)
    _state, _settings, reason = plugin_auto_update.inspect(tmp_path / "settings.json", "grimoire")
    assert "could not read" in reason and "Permission denied" in reason
    assert "no settings file" not in reason


def test_a_settings_file_that_is_not_utf8_is_refused_and_left_alone(tmp_path):
    path = tmp_path / "settings.json"
    original = json.dumps(DECLARED).encode("utf-16")
    path.write_bytes(original)
    out = _run(path, "--apply")
    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert "not UTF-8" in out["report"]["messages"][0]["message"]
    assert path.read_bytes() == original


def test_a_write_that_fails_is_reported_and_leaves_the_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(DECLARED), encoding="utf-8")
    before = path.read_bytes()

    def denied(_path, _data):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(plugin_auto_update, "write_json", denied)
    monkeypatch.setattr(sys, "argv", ["plugin_auto_update", "--settings", str(path), "--apply", "--format", "json"])

    assert plugin_auto_update.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked" and report["mutations"] == []
    assert "could not write" in report["messages"][0]["message"]
    assert path.read_bytes() == before


def test_the_settings_are_written_as_utf8_with_lf_and_no_temporary_file_stays(tmp_path):
    path = tmp_path / "settings.json"
    content = {**DECLARED, "note": "日本語"}
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    assert _run(path, "--apply")["returncode"] == 0
    raw = path.read_bytes()
    assert "日本語".encode("utf-8") in raw and b"\r" not in raw
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
