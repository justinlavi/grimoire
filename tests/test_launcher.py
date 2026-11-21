"""bin/grimoire runs a rite with whatever Python the machine has, beside the framework or from a copy elsewhere."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SH = shutil.which("sh") or shutil.which("bash")


def _sh(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full = dict(os.environ)
    if env:
        full.update(env)
    return subprocess.run([SH, str(REPO_ROOT / "bin" / "grimoire"), *args], capture_output=True, text=True, env=full, timeout=120)


@pytest.mark.skipif(SH is None, reason="no POSIX shell available")
def test_launcher_runs_a_rite_beside_the_framework():
    result = _sh("validate", "--help")
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


@pytest.mark.skipif(SH is None, reason="no POSIX shell available")
def test_launcher_lists_rites_and_refuses_unknown_ones():
    listing = _sh("--list")
    assert listing.returncode == 0
    names = listing.stdout.split()
    assert "validate" in names and "sync_skills" in names and not any(n.startswith("_") for n in names)

    missing = _sh("no_such_rite")
    assert missing.returncode == 2
    assert "no rite named" in missing.stderr


@pytest.mark.skipif(SH is None, reason="no POSIX shell available")
def test_a_copy_of_the_launcher_resolves_the_framework_through_framework_home(tmp_path):
    copy_bin = tmp_path / "elsewhere" / "bin"
    copy_bin.mkdir(parents=True)
    for name in ("grimoire", "grimoire.py"):
        shutil.copy(REPO_ROOT / "bin" / name, copy_bin / name)
    result = subprocess.run(
        [SH, str(copy_bin / "grimoire"), "recent_changes", "--help"],
        capture_output=True, text=True, env={**os.environ, "FRAMEWORK_HOME": str(REPO_ROOT)}, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "--since" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="cmd launcher is Windows-only")
def test_cmd_launcher_runs_a_rite():
    result = subprocess.run(
        ["cmd", "/c", str(REPO_ROOT / "bin" / "grimoire.cmd"), "validate", "--help"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()


@pytest.mark.skipif(sys.platform != "win32", reason="cmd launcher is Windows-only")
def test_cmd_launcher_passes_a_failing_rite_exit_code_through():
    result = subprocess.run(
        ["cmd", "/c", str(REPO_ROOT / "bin" / "grimoire.cmd"), "no_such_rite"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 2, result.stderr
    assert "no rite named" in result.stderr


def test_no_plugin_has_a_top_level_bin_folder():
    """claude.ai and Cowork refuse to install a plugin that has one."""
    plugins = [path for path in (REPO_ROOT / "plugins").iterdir() if path.is_dir()]
    assert plugins
    assert [path.name for path in plugins if (path / "bin").exists()] == []


def test_no_plugin_skill_runs_the_launcher_as_a_bare_command():
    """Nothing puts `grimoire` on the PATH, so a skill names the launcher by its path."""
    rites = "|".join(sorted(path.stem for path in (REPO_ROOT / "rites").glob("*.py") if not path.name.startswith("_")))
    bare = re.compile(rf"(?<![/\w.-])grimoire (?:--list|(?:{rites})\b)")
    skills = sorted((REPO_ROOT / "plugins").glob("*/skills/*/SKILL.md"))
    assert skills
    for skill in skills:
        for line in skill.read_text(encoding="utf-8").splitlines():
            assert not bare.search(line), f"{skill}: {line.strip()}"


def test_launcher_runs_rites_in_utf8_mode(tmp_path):
    framework = tmp_path / "framework"
    (framework / "rites").mkdir(parents=True)
    (framework / "rites" / "probe.py").write_text(
        "import sys\n"
        "name = sys.argv[1]\n"
        "open(name + '.txt', 'w').write(name)\n"
        "print(sys.flags.utf8_mode, open(name + '.txt').read() == name)\n",
        encoding="utf-8",
    )
    copy_bin = tmp_path / "elsewhere" / "bin"
    copy_bin.mkdir(parents=True)
    shutil.copy(REPO_ROOT / "bin" / "grimoire.py", copy_bin / "grimoire.py")
    env = {**os.environ, "FRAMEWORK_HOME": str(framework), "PYTHONIOENCODING": "cp1252"}
    env.pop("PYTHONUTF8", None)
    result = subprocess.run(
        [sys.executable, str(copy_bin / "grimoire.py"), "probe", "café_日本"],
        capture_output=True, cwd=tmp_path, env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert result.stdout.decode("ascii").split() == ["1", "True"]
