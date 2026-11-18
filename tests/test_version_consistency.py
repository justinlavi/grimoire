"""The VERSION file, pyproject.toml and the plugin manifests must declare the same version."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match, "no [project] version found in pyproject.toml"
    return match.group(1)


def test_version_file_matches_pyproject():
    version_file = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert version_file == _pyproject_version(), (
        f"VERSION ({version_file}) and pyproject.toml ({_pyproject_version()}) disagree; "
        "bump both together."
    )


def test_plugin_manifests_match_the_version_file():
    version_file = VERSION_FILE.read_text(encoding="utf-8").strip()
    manifests = sorted((REPO_ROOT / "plugins").glob("*/.claude-plugin/plugin.json"))
    assert manifests, "no plugin manifests found"
    for manifest in manifests:
        declared = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        assert declared == version_file, (
            f"{manifest.relative_to(REPO_ROOT).as_posix()} declares {declared}; VERSION is {version_file}. "
            "Run python rites/build_plugins.py --apply."
        )

