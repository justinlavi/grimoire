"""install_grimoire.py clones a grimoire into the home and registers it."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import _lib
import install_grimoire

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "install_grimoire.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _bare_remote(tmp_path: Path, name: str, with_manifest: bool = True) -> Path:
    work = tmp_path / f"{name}-work"
    shutil.copytree(GOOD, work)
    if not with_manifest:
        (work / "grimoire.json").unlink()
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
    return {"returncode": result.returncode, "report": json.loads(result.stdout), "stderr": result.stderr}


def test_derive_key_from_urls():
    assert install_grimoire.derive_key("https://gitlab.example.com/group/cooking-grimoire.git") == "cooking-grimoire"
    assert install_grimoire.derive_key("git@github.com:you/cooking-grimoire.git") == "cooking-grimoire"
    assert install_grimoire.derive_key("https://github.com/you/notes") == "notes"


def test_join_clones_and_registers(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"

    out = _run(str(remote), home)
    report = out["report"]

    assert out["returncode"] == 0, out
    assert report["status"] == "ok"
    assert (home / "recipes-grimoire" / "grimoire.json").is_file()
    actions = [m["action"] for m in report["mutations"]]
    assert actions == ["clone", "register"]
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    entry = library["grimoires"]["recipes-grimoire"]
    assert entry["local_path"] == _lib.format_local_path(home / "recipes-grimoire")
    assert entry["online_path"] == str(remote)
    assert report["summary"]["manifest"] == "ok"
    assert report["summary"]["skills"] == "skipped"

    # Second run fast-forwards instead of re-cloning and stays registered.
    again = _run(str(remote), home)
    assert again["returncode"] == 0
    assert [m["action"] for m in again["report"]["mutations"]] == ["pull", "register"]


def test_join_without_manifest_is_blocked_with_adopt_hint(tmp_path):
    remote = _bare_remote(tmp_path, "notes", with_manifest=False)
    home = tmp_path / "home"

    out = _run(str(remote), home)
    report = out["report"]

    assert out["returncode"] == 1
    assert report["status"] == "blocked"
    assert report["summary"]["manifest"] == "missing"
    assert (home / "notes").is_dir()  # the clone is kept for /grm-setup <folder>
    assert not (home / "library.json").exists()
    assert any("/grm-setup" in m["message"] for m in report["messages"])


def test_bad_url_is_an_error_not_a_crash(tmp_path):
    home = tmp_path / "home"
    out = _run(str(tmp_path / "does-not-exist.git"), home, "--name", "ghost")
    assert out["returncode"] == 1
    assert out["report"]["status"] == "error"
    assert any("could not clone" in m["message"] for m in out["report"]["messages"])


def test_join_registers_the_copy_for_reading(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"

    out = _run(str(remote), home)

    assert out["report"]["summary"]["access"] == "read"
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["recipes-grimoire"]["access"] == "read"


def test_join_with_access_edit_registers_the_copy_for_editing(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"

    out = _run(str(remote), home, "--access", "edit")

    assert out["report"]["summary"]["access"] == "edit"
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["recipes-grimoire"]["access"] == "edit"


def test_join_keeps_the_access_of_an_existing_entry(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    home.mkdir()
    (home / "library.json").write_text(json.dumps({"grimoires": {
        "recipes-grimoire": {"local_path": _lib.format_local_path(home / "recipes-grimoire"),
                             "online_path": str(remote), "access": "edit"},
    }}), encoding="utf-8")

    out = _run(str(remote), home)

    assert out["report"]["summary"]["access"] == "edit"
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["recipes-grimoire"]["access"] == "edit"


def test_join_with_access_changes_the_access_of_an_existing_entry(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    assert _run(str(remote), home)["report"]["summary"]["access"] == "read"

    out = _run(str(remote), home, "--access", "edit")

    assert out["returncode"] == 0
    assert out["report"]["summary"]["access"] == "edit"
    assert {"action": "write", "detail": "recipes-grimoire.access = edit"}.items() <= {
        k: v for m in out["report"]["mutations"] if m["action"] == "write" for k, v in m.items()
    }.items()
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["recipes-grimoire"]["access"] == "edit"

    back = _run(str(remote), home, "--access", "read")

    assert back["report"]["summary"]["access"] == "read"


def _origin(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), "remote", "get-url", "origin"], check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _second_address(tmp_path: Path, remote: Path) -> Path:
    """Another address that serves the same repository."""
    other = tmp_path / "elsewhere" / remote.name
    other.parent.mkdir()
    subprocess.run(["git", "clone", "-q", "--bare", str(remote), str(other)], check=True, capture_output=True)
    return other


def test_join_from_another_address_stops_and_changes_nothing(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    _run(str(remote), home)
    other = _second_address(tmp_path, remote)
    library_before = (home / "library.json").read_text(encoding="utf-8")

    out = _run(str(other), home, "--access", "edit")

    assert out["returncode"] == 1
    assert out["report"]["status"] == "blocked"
    assert out["report"]["mutations"] == []
    assert install_grimoire.same_address(out["report"]["summary"]["origin"], str(remote))
    assert any("--switch-url" in m["message"] for m in out["report"]["messages"])
    assert install_grimoire.same_address(_origin(home / "recipes-grimoire"), str(remote))
    assert (home / "library.json").read_text(encoding="utf-8") == library_before


def test_switch_url_points_the_copy_and_the_library_at_the_new_address(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    _run(str(remote), home)
    other = _second_address(tmp_path, remote)

    out = _run(str(other), home, "--switch-url", "--access", "edit")

    assert out["returncode"] == 0
    assert [m["action"] for m in out["report"]["mutations"]] == ["remote", "pull", "write", "register"]
    assert install_grimoire.same_address(_origin(home / "recipes-grimoire"), str(other))
    entry = json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]["recipes-grimoire"]
    assert install_grimoire.same_address(entry["online_path"], str(other))
    assert entry["access"] == "edit"


def test_switch_url_brings_in_what_the_new_address_holds(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    _run(str(remote), home)
    other = _second_address(tmp_path, remote)
    work = tmp_path / "recipes-grimoire-work"
    (work / "later.md").write_text("later\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "later")
    _git(work, "push", "-q", str(other), "main")

    out = _run(str(other), home, "--switch-url")

    assert out["returncode"] == 0
    assert (home / "recipes-grimoire" / "later.md").is_file()


def test_switch_url_refuses_a_repository_with_no_shared_history(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    _run(str(remote), home)
    stranger = _bare_remote(tmp_path, "stranger", with_manifest=False)  # other content, so other commits

    out = _run(str(stranger), home, "--name", "recipes-grimoire", "--switch-url")

    assert out["returncode"] == 1
    assert out["report"]["status"] == "blocked"
    assert out["report"]["mutations"] == []
    assert any("shares no history" in m["message"] for m in out["report"]["messages"])
    assert install_grimoire.same_address(_origin(home / "recipes-grimoire"), str(remote))


def test_switch_url_to_an_address_that_cannot_be_fetched_is_an_error(tmp_path):
    remote = _bare_remote(tmp_path, "recipes-grimoire")
    home = tmp_path / "home"
    _run(str(remote), home)

    out = _run(str(tmp_path / "nowhere" / "recipes-grimoire.git"), home, "--switch-url")

    assert out["returncode"] == 1
    assert out["report"]["status"] == "error"
    assert out["report"]["mutations"] == []
    assert install_grimoire.same_address(_origin(home / "recipes-grimoire"), str(remote))


def test_the_same_address_written_another_way_is_not_another_address():
    assert install_grimoire.same_address("https://git.example.com/You/Notes.git", "https://git.example.com/you/notes/")
    assert install_grimoire.same_address("C:\\repos\\notes.git", "c:/repos/notes")
    assert not install_grimoire.same_address("https://git.example.com/you/notes", "https://read.example.com/you/notes")

