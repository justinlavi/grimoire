"""The access helpers in _lib and the grimoire_access rite."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import _lib

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "grimoire_access.py"
REFUSAL = (
    "this grimoire is set up for reading on this computer, so nothing was changed; "
    "switch it to editing with the grimoire_access rite (--set edit --apply)"
)


def _folder(tmp_path: Path, name: str = "recipes") -> Path:
    folder = tmp_path / "elsewhere" / name
    folder.mkdir(parents=True)
    return folder


def _run(folder: Path, library: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), "--grimoire", str(folder), "--library", str(library), "--format", "json", *extra],
        capture_output=True, text=True, timeout=60,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout)}


def _library(tmp_path: Path, folder: Path, **entry) -> Path:
    path = tmp_path / "lib" / "library.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"grimoires": {
        "recipes": {"local_path": str(folder), "online_path": None, **entry},
        "other": {"local_path": "$HOME/grimoires/other", "online_path": "u", "note": "keep"},
    }}, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def test_default_library_path_follows_the_home_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert _lib.default_library_path() == tmp_path / "grimoires" / "library.json"


def test_library_entry_matches_the_folder_the_local_path_names(library_home, tmp_path):
    folder = _folder(tmp_path)
    key = library_home(folder, access="read", key="recipes")
    found_key, entry = _lib.library_entry_for(folder)
    assert found_key == key and entry["access"] == "read"


def test_library_entry_expands_the_home_token(library_home):
    folder = library_home.home / "grimoires" / "cooking"
    folder.mkdir()
    library_home.library.write_text(
        json.dumps({"grimoires": {"cooking": {"local_path": "$HOME/grimoires/cooking", "access": "read"}}}),
        encoding="utf-8",
    )
    assert _lib.library_entry_for(folder)[0] == "cooking"
    assert _lib.grimoire_access(folder) == "read"


def test_library_entry_skips_unusable_paths_and_non_dict_entries(library_home, tmp_path):
    folder = _folder(tmp_path)
    library_home.library.write_text(json.dumps({"grimoires": {
        "relative": {"local_path": "recipes", "access": "read"},
        "empty": {"local_path": "", "access": "read"},
        "text": "not an entry",
    }}), encoding="utf-8")
    assert _lib.library_entry_for(folder) == (None, None)
    assert _lib.grimoire_access(folder) == "edit"


def test_a_missing_or_unreadable_library_has_no_entry(library_home, tmp_path):
    folder = _folder(tmp_path)
    assert _lib.library_entry_for(folder) == (None, None)
    library_home.library.write_text("{not json", encoding="utf-8")
    assert _lib.library_entry_for(folder) == (None, None)
    library_home.library.write_bytes(b"\xff\xfe")
    assert _lib.library_entry_for(folder) == (None, None)
    assert _lib.read_only_refusal(folder) is None


@pytest.mark.parametrize("value,expected", [("read", "read"), ("edit", "edit"), ("write", "edit"), (None, "edit"), (1, "edit")])
def test_only_read_means_read(library_home, tmp_path, value, expected):
    folder = _folder(tmp_path)
    library_home(folder, access="read")
    data = json.loads(library_home.library.read_text(encoding="utf-8"))
    data["grimoires"]["recipes"]["access"] = value
    library_home.library.write_text(json.dumps(data), encoding="utf-8")
    assert _lib.grimoire_access(folder) == expected


def test_the_refusal_text_is_exact_and_only_for_read(library_home, tmp_path):
    folder = _folder(tmp_path)
    library_home(folder)
    assert _lib.read_only_refusal(folder) is None
    library_home(folder, access="read")
    assert _lib.read_only_refusal(folder) == REFUSAL


def test_an_explicit_library_path_is_read_instead_of_the_default(library_home, tmp_path):
    folder = _folder(tmp_path)
    other = _library(tmp_path, folder, access="read")
    assert _lib.grimoire_access(folder) == "edit"
    assert _lib.grimoire_access(folder, other) == "read"


# ---------------------------------------------------------------------------
# the rite
# ---------------------------------------------------------------------------


def test_report_without_set_names_the_access_and_writes_nothing(tmp_path):
    folder = _folder(tmp_path)
    library = _library(tmp_path, folder, access="read")
    before = library.read_bytes()
    out = _run(folder, library)
    assert out["returncode"] == 0
    assert out["report"]["status"] == "noop"
    assert out["report"]["summary"] == {"key": "recipes", "access": "read", "registered": True, "library": str(library)}
    assert library.read_bytes() == before


def test_an_unregistered_grimoire_reports_edit_and_registered_false(tmp_path):
    folder = _folder(tmp_path, "stranger")
    library = _library(tmp_path, _folder(tmp_path, "recipes"))
    out = _run(folder, library)
    assert out["returncode"] == 0
    assert out["report"]["summary"]["registered"] is False
    assert out["report"]["summary"]["access"] == "edit"
    assert out["report"]["summary"]["key"] is None


def test_plan_says_what_would_change_and_writes_nothing(tmp_path):
    folder = _folder(tmp_path)
    library = _library(tmp_path, folder)
    before = library.read_bytes()
    out = _run(folder, library, "--set", "read")
    assert out["returncode"] == 0 and out["report"]["status"] == "noop"
    assert [m["message"] for m in out["report"]["messages"]] == ["would set access to read for recipes"]
    assert out["report"]["mutations"] == []
    assert library.read_bytes() == before


def test_plan_of_the_current_value_says_it_is_already_set(tmp_path):
    folder = _folder(tmp_path)
    library = _library(tmp_path, folder, access="read")
    out = _run(folder, library, "--set", "read")
    assert out["returncode"] == 0 and out["report"]["status"] == "noop"
    assert [m["message"] for m in out["report"]["messages"]] == ["access is already read"]


def test_apply_writes_the_field_and_keeps_every_other_entry_and_field(tmp_path):
    folder = _folder(tmp_path)
    library = _library(tmp_path, folder)
    out = _run(folder, library, "--set", "read", "--apply")
    assert out["returncode"] == 0 and out["report"]["status"] == "ok"
    assert out["report"]["mutations"] == [{"action": "write", "path": library.as_posix(), "detail": "recipes.access = read"}]
    assert out["report"]["summary"]["access"] == "read"
    data = json.loads(library.read_text(encoding="utf-8"))
    assert data["grimoires"]["recipes"] == {"local_path": str(folder), "online_path": None, "access": "read"}
    assert data["grimoires"]["other"] == {"local_path": "$HOME/grimoires/other", "online_path": "u", "note": "keep"}

    back = _run(folder, library, "--set", "edit", "--apply")
    assert back["report"]["status"] == "ok"
    assert json.loads(library.read_text(encoding="utf-8"))["grimoires"]["recipes"]["access"] == "edit"


def test_apply_of_the_current_value_is_a_noop_that_leaves_the_file_alone(tmp_path):
    folder = _folder(tmp_path)
    library = _library(tmp_path, folder, access="read")
    before = library.read_bytes()
    out = _run(folder, library, "--set", "read", "--apply")
    assert out["returncode"] == 0 and out["report"]["status"] == "noop"
    assert out["report"]["mutations"] == []
    assert library.read_bytes() == before


def test_set_on_an_unregistered_grimoire_is_an_error_that_names_the_registration(tmp_path):
    folder = _folder(tmp_path, "stranger")
    library = _library(tmp_path, _folder(tmp_path, "recipes"))
    before = library.read_bytes()
    out = _run(folder, library, "--set", "read", "--apply")
    assert out["returncode"] == 1 and out["report"]["status"] == "error"
    text = out["report"]["messages"][0]["message"]
    assert "not in the library" in text and "/grm-update library" in text
    assert library.read_bytes() == before


def test_a_library_that_cannot_be_read_is_left_as_it_is(tmp_path):
    folder = _folder(tmp_path)
    library = tmp_path / "library.json"
    library.write_text("{broken", encoding="utf-8")
    out = _run(folder, library, "--set", "read", "--apply")
    assert out["returncode"] == 1 and out["report"]["status"] == "error"
    assert library.read_text(encoding="utf-8") == "{broken"


def test_a_library_that_keeps_changing_is_an_error(tmp_path, monkeypatch, capsys):
    import grimoire_access
    import sync_library

    folder = _folder(tmp_path)
    library = _library(tmp_path, folder)

    def conflict(*args, **kwargs):
        raise sync_library.LibraryWriteConflict("kept changing")

    monkeypatch.setattr(sync_library, "update_library", conflict)
    monkeypatch.setattr(sys, "argv", ["grimoire_access.py", "--grimoire", str(folder), "--library", str(library),
                                      "--set", "read", "--apply", "--format", "json"])
    assert grimoire_access.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "error" and "kept changing" in report["messages"][0]["message"]


def test_the_default_library_is_the_one_under_the_home(library_home, tmp_path):
    folder = _folder(tmp_path)
    library_home(folder, access="read")
    result = subprocess.run(
        [sys.executable, str(RITE), "--grimoire", str(folder), "--format", "json"],
        capture_output=True, text=True, timeout=60,
    )
    report = json.loads(result.stdout)
    assert report["summary"]["access"] == "read"
    assert report["summary"]["library"] == str(library_home.library)
