"""sync_library: one spelling of local_path, entries that name no folder, and the
single compare-and-swap writer of library.json."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import _lib
import sync_library

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "sync_library.py"


def _make_grimoire(home: Path, key: str, skill_prefix: str = "gg") -> Path:
    g = home / key
    g.mkdir(parents=True)
    (g / "grimoire.json").write_text(
        json.dumps({"name": key, "skill_prefix": skill_prefix, "description": "test"}),
        encoding="utf-8",
    )
    return g


def _run(home: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RITE), "--home", str(home), *args],
        capture_output=True, text=True, timeout=30,
    )


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    return user


# ---------------------------------------------------------------------------
# One spelling of local_path
# ---------------------------------------------------------------------------


def test_expected_local_path_is_the_shared_formatter(fake_home):
    home = fake_home / "grimoires"
    assert sync_library.expected_local_path(home, "g") == "$HOME/grimoires/g"
    assert sync_library.expected_local_path(home, "g") == _lib.format_local_path(home / "g")


def test_a_home_outside_the_user_home_is_recorded_as_an_absolute_path(fake_home, tmp_path):
    elsewhere = tmp_path / "kb"
    assert sync_library.expected_local_path(elsewhere, "g") == (elsewhere / "g").as_posix()


def test_a_sibling_folder_sharing_the_home_prefix_is_not_taken_for_the_home(fake_home, tmp_path):
    sibling = tmp_path / "user2" / "grimoires"
    expected = sync_library.expected_local_path(sibling, "g")
    assert not expected.startswith("$HOME")
    assert expected == (sibling / "g").as_posix()


def test_the_windows_spelling_of_a_home_path_is_a_mismatch_that_sync_corrects(fake_home):
    home = fake_home / "grimoires"
    _make_grimoire(home, "g")
    library = {"grimoires": {"g": {"local_path": "$HOME\\grimoires\\g", "online_path": None}}}
    scan = sync_library.scan_grimoire_home(home)
    diff = sync_library.diff_library(scan, library, home)
    assert [m["key"] for m in diff["mismatched"]] == ["g"]
    assert sync_library.build_synced_library(scan, library, home)["grimoires"]["g"]["local_path"] == "$HOME/grimoires/g"


def test_a_fresh_library_row_is_in_sync_with_what_the_installer_writes(fake_home):
    home = fake_home / "grimoires"
    _make_grimoire(home, "g")
    row = {"local_path": _lib.format_local_path(home / "g"), "online_path": None}
    diff = sync_library.diff_library(sync_library.scan_grimoire_home(home), {"grimoires": {"g": row}}, home)
    assert diff["ok"] == ["g"] and diff["mismatched"] == []


# ---------------------------------------------------------------------------
# An empty or relative local_path is a missing grimoire, never the working directory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", ".", "cwd_grimoire", "./cwd_grimoire", None, 7])
def test_an_unusable_local_path_is_stale_and_dropped(tmp_path, monkeypatch, raw):
    work = tmp_path / "work"
    (work / "cwd_grimoire").mkdir(parents=True)
    for folder in (work, work / "cwd_grimoire"):
        (folder / "grimoire.json").write_text(json.dumps({"name": "w", "skill_prefix": "ww"}), encoding="utf-8")
    monkeypatch.chdir(work)
    home = tmp_path / "grimoires"
    home.mkdir()
    library = {"grimoires": {"w": {"local_path": raw, "online_path": None}}}
    scan = sync_library.scan_grimoire_home(home)

    diff = sync_library.diff_library(scan, library, home)

    assert [s["key"] for s in diff["stale"]] == ["w"] and diff["ok"] == []
    assert sync_library.build_synced_library(scan, library, home)["grimoires"] == {}


def test_a_library_entry_that_is_not_an_object_is_stale(tmp_path):
    home = tmp_path / "grimoires"
    home.mkdir()
    library = {"grimoires": {"odd": "just a string"}}
    scan = sync_library.scan_grimoire_home(home)
    assert [s["key"] for s in sync_library.diff_library(scan, library, home)["stale"]] == ["odd"]
    assert sync_library.build_synced_library(scan, library, home)["grimoires"] == {}


def test_an_entry_outside_the_home_that_resolves_is_kept(tmp_path):
    home = tmp_path / "grimoires"
    home.mkdir()
    ext = _make_grimoire(tmp_path / "elsewhere", "ext")
    library = {"grimoires": {"ext": {"local_path": ext.as_posix(), "online_path": None, "x": 1}}}
    scan = sync_library.scan_grimoire_home(home)
    assert sync_library.diff_library(scan, library, home)["ok"] == ["ext"]
    assert sync_library.build_synced_library(scan, library, home)["grimoires"]["ext"]["x"] == 1


def test_build_synced_library_keeps_other_top_level_fields(tmp_path):
    home = tmp_path / "grimoires"
    _make_grimoire(home, "g")
    scan = sync_library.scan_grimoire_home(home)
    built = sync_library.build_synced_library(scan, {"version": 3, "grimoires": {}}, home)
    assert built["version"] == 3 and "g" in built["grimoires"]


# ---------------------------------------------------------------------------
# Reading and writing library.json
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [b"[]", b"[1, 2]", b'"text"', b"null", b"3", b'{"grimoires": []}', b'{"grimoires": null}',
     b'{"grimoires": {},}', b"\xff\xfe not utf-8", b"{"],
)
def test_library_from_bytes_never_raises_and_refuses_what_it_cannot_use(raw):
    library, reason = sync_library.library_from_bytes(raw)
    assert library is None and reason


@pytest.mark.parametrize(
    "raw, grimoires",
    [(b"", {}), (b"  \n", {}), (b"{}", {}), (b'{"grimoires": {"a": {}}}', {"a": {}})],
)
def test_library_from_bytes_reads_what_it_can_use(raw, grimoires):
    assert sync_library.library_from_bytes(raw) == ({"grimoires": grimoires}, "")


def test_library_from_bytes_keeps_unknown_top_level_fields():
    library, _ = sync_library.library_from_bytes(b'{"version": 2, "grimoires": {}}')
    assert library["version"] == 2


def test_update_library_leaves_an_unreadable_file_as_it_is(tmp_path):
    path = tmp_path / "library.json"
    path.write_bytes(b'{"grimoires": {"a": {},}}')
    with pytest.raises(sync_library.LibraryUnreadable):
        sync_library.update_library(path, lambda library: {"grimoires": {"b": {}}})
    assert path.read_bytes() == b'{"grimoires": {"a": {},}}'


def test_update_library_creates_the_file_and_writes_nothing_when_nothing_changes(tmp_path):
    path = tmp_path / "home" / "library.json"
    assert sync_library.update_library(path, lambda library: {"grimoires": {"a": {"local_path": "x"}}}) is True
    assert json.loads(path.read_text(encoding="utf-8"))["grimoires"]["a"]["local_path"] == "x"
    before = path.read_bytes()
    assert sync_library.update_library(path, lambda library: dict(library)) is False
    assert sync_library.update_library(path, lambda library: None) is False
    assert path.read_bytes() == before


def test_update_library_retries_when_the_file_changes_under_it(tmp_path, monkeypatch):
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"grimoires": {}}), encoding="utf-8")
    real = sync_library.compare_and_swap_write
    attempts = []

    def racing(library_path, expected, library):
        attempts.append(1)
        if len(attempts) == 1:
            sync_library.write_library({"grimoires": {"other": {}}}, library_path)
        return real(library_path, expected, library)

    monkeypatch.setattr(sync_library, "compare_and_swap_write", racing)

    def add(library):
        library["grimoires"]["mine"] = {}
        return library

    assert sync_library.update_library(path, add) is True
    assert len(attempts) == 2
    assert set(json.loads(path.read_text(encoding="utf-8"))["grimoires"]) == {"other", "mine"}


def test_write_library_writes_what_render_library_bytes_renders(tmp_path):
    path = tmp_path / "library.json"
    library = {"grimoires": {"日本": {"local_path": "$HOME/x", "online_path": None}}}
    sync_library.write_library(library, path)
    assert path.read_bytes() == sync_library.render_library_bytes(library)
    assert "日本".encode("utf-8") in path.read_bytes() and b"\r" not in path.read_bytes()


def test_the_temporary_file_does_not_survive_a_write(tmp_path):
    sync_library.write_library({"grimoires": {}}, tmp_path / "library.json")
    assert [p.name for p in tmp_path.iterdir()] == ["library.json"]


def test_apply_synced_library_refuses_a_library_it_cannot_read(tmp_path):
    home = tmp_path / "grimoires"
    _make_grimoire(home, "g")
    path = home / "library.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(sync_library.LibraryUnreadable):
        sync_library.apply_synced_library(sync_library.scan_grimoire_home(home), path, home)
    assert path.read_text(encoding="utf-8") == "[]"


@pytest.mark.parametrize("content", ['{"grimoires": {},}', "[]"])
def test_the_rite_exits_1_and_keeps_a_library_it_cannot_read(tmp_path, content):
    home = tmp_path / "grimoires"
    _make_grimoire(home, "g")
    (home / "library.json").write_text(content, encoding="utf-8")

    result = _run(home, "--apply", "--format", "json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "error" and report["mutations"] == []
    assert any("library.json" in m["message"] for m in report["messages"])
    assert (home / "library.json").read_text(encoding="utf-8") == content


def test_a_prefix_collision_warning_says_registration_blocks_the_prefix(tmp_path):
    home = tmp_path / "grimoires"
    _make_grimoire(home, "a", "same")
    _make_grimoire(home, "b", "same")
    warnings = sync_library.scan_grimoire_home(home)["warnings"]
    (collision,) = [w for w in warnings if "collision" in w]
    assert "blocks" in collision and "overwrite" not in collision


def test_a_folder_that_holds_a_framework_checkout_is_never_a_grimoire(tmp_path):
    home = tmp_path / "grimoires"
    _make_grimoire(home, "g")
    (home / "framework").mkdir()
    (home / "framework" / "framework.json").write_text("{}", encoding="utf-8")
    (home / "framework" / "grimoire.json").write_text(
        json.dumps({"name": "framework", "skill_prefix": "fw"}), encoding="utf-8",
    )

    scan = sync_library.scan_grimoire_home(home)

    assert [g["key"] for g in scan["grimoires"]] == ["g"]
    assert scan["unmanaged"] == []
