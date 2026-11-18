"""Pytest configuration - make `from _lib import ...` work in tests."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES_DIR = REPO_ROOT / "rites"

if str(RITES_DIR) not in sys.path:
    sys.path.insert(0, str(RITES_DIR))


@pytest.fixture
def library_home(tmp_path, monkeypatch):
    """A temporary home whose `~/grimoires/library.json` a test fills with `register`.

    The home is in force for this process (`Path.home`) and for subprocesses
    (`HOME`, `USERPROFILE`), so a rite never reads the real library. Returns
    `register(folder, access=None, key=None)`, which records `folder` in the
    library (with an `access` field when one is given) and returns the key; the
    library file is `register.library`.
    """
    home = tmp_path / "library_home"
    (home / "grimoires").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    library = home / "grimoires" / "library.json"

    def register(folder, access=None, key=None):
        key = key or Path(folder).name
        data = json.loads(library.read_text(encoding="utf-8")) if library.is_file() else {"grimoires": {}}
        entry = {"local_path": str(Path(folder).resolve()), "online_path": None}
        if access is not None:
            entry["access"] = access
        data["grimoires"][key] = entry
        library.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        return key

    register.library = library
    register.home = home
    return register
