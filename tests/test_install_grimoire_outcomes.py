"""install_grimoire reports what it did: a clone only when it cloned, a pull only
when the pull worked, and a failed registration as a failure."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import _lib
import install_grimoire

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "install_grimoire.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _bare_remote(tmp_path: Path, name: str) -> Path:
    work = tmp_path / f"{name}-work"
    shutil.copytree(GOOD, work)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "Tester")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "scaffold")
    bare = tmp_path / f"{name}.git"
    _git(work, "clone", "-q", "--bare", str(work), str(bare))
    return bare


def _run(url: str, home: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), url, "--home", str(home), "--no-skills", "--format", "json", *extra],
        capture_output=True, text=True, timeout=120,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout)}


def test_a_folder_that_is_not_a_checkout_is_an_error_and_records_no_clone(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    (home / "recipes-grimoire").mkdir(parents=True)
    shutil.copy(GOOD / "grimoire.json", home / "recipes-grimoire" / "grimoire.json")

    out = _run(str(remote), home)

    assert out["returncode"] == 1
    assert out["report"]["status"] == "error"
    assert out["report"]["mutations"] == []
    assert any("not a git checkout" in m["message"] for m in out["report"]["messages"])
    assert not (home / "library.json").exists()


def test_a_failed_pull_is_a_warning_and_is_not_recorded_as_a_pull(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    assert _run(str(remote), home)["returncode"] == 0
    remote.rename(tmp_path / "moved.git")  # the remote is gone: the next pull fails

    out = _run(str(remote), home)

    assert out["returncode"] == 0
    assert [m["action"] for m in out["report"]["mutations"]] == ["register"]
    assert any(m["severity"] == "warning" and "pull failed" in m["message"] for m in out["report"]["messages"])


def test_the_library_entry_follows_the_home_the_grimoire_went_into(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "kb"
    _run(str(remote), home)
    entry = json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]["recipes-grimoire"]
    assert entry["local_path"] == _lib.format_local_path(home / "recipes-grimoire")


def test_a_library_that_cannot_be_read_is_not_overwritten_and_fails_the_rite(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    home.mkdir()
    broken = '{"grimoires": {"old": {},}}'
    (home / "library.json").write_text(broken, encoding="utf-8")

    out = _run(str(remote), home)

    assert out["returncode"] == 1
    assert (home / "library.json").read_text(encoding="utf-8") == broken
    assert out["report"]["status"] == "error"
    assert "register" not in [m["action"] for m in out["report"]["mutations"]]


def _main(monkeypatch, capsys, remote, home, *extra):
    monkeypatch.setattr(sys, "argv", ["install_grimoire", str(remote), "--home", str(home), "--format", "json", *extra])
    code = install_grimoire.main()
    return code, json.loads(capsys.readouterr().out)


def test_a_skill_registration_that_fails_fails_the_rite(tmp_path, monkeypatch, capsys):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    monkeypatch.setattr(install_grimoire, "_run_sync_skills", lambda: (False, "sync_skills exited 1: collision"))

    code, report = _main(monkeypatch, capsys, remote, tmp_path / "home")

    assert code == 1
    assert report["status"] == "error"
    assert report["summary"]["skills"] == "failed"
    assert any("skill registration failed" in m["message"] for m in report["messages"])


def test_a_skill_registration_that_works_leaves_the_rite_ok(tmp_path, monkeypatch, capsys):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    monkeypatch.setattr(install_grimoire, "_run_sync_skills", lambda: (True, "registered 3 skill(s)"))

    code, report = _main(monkeypatch, capsys, remote, tmp_path / "home")

    assert code == 0 and report["status"] == "ok" and report["summary"]["skills"] == "synced"


@pytest.mark.parametrize(
    "returncode, output, ok",
    [
        (0, json.dumps({"summary": {"registered": 3, "cleaned": 0, "reset": 0, "blocked": 0}}), True),
        (1, json.dumps({"summary": {"registered": 0, "cleaned": 0, "reset": 0, "blocked": 1},
                        "messages": [{"severity": "error", "message": "collision /grm-add"}]}), False),
        (0, "not json", False),
    ],
)
def test_the_skill_sync_detail_names_what_failed(monkeypatch, returncode, output, ok):
    monkeypatch.setattr(install_grimoire.summon_core, "run_sync_skills", lambda *a, **k: (returncode, output))
    result_ok, detail = install_grimoire._run_sync_skills()
    assert result_ok is ok
    if not ok:
        assert detail
    if returncode:
        assert "collision /grm-add" in detail
