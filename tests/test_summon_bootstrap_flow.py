"""The piped install: the five downloaded files run from a temporary folder, reach the
installed framework only after it is on disk, and still write the transcript."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_FILES = [
    "rites/summon.py",
    "rites/summon_core.py",
    "rites/agent_targets.py",
    "rites/data/agent_targets.json",
    "rites/templates/grimoire_block.md",
]


def _framework_copy(destination: Path) -> None:
    shutil.copytree(
        REPO_ROOT / "rites", destination / "rites",
        ignore=shutil.ignore_patterns("__pycache__", ".artifacts"),
    )
    shutil.copytree(REPO_ROOT / "skills", destination / "skills")
    for name in ("framework.json", "README.md", "VERSION"):
        if (REPO_ROOT / name).is_file():
            shutil.copy(REPO_ROOT / name, destination / name)
    (destination / ".git").mkdir()  # a checkout whose pull fails offline, so the run stays local


def test_the_piped_install_writes_the_block_the_skills_and_the_transcript(tmp_path):
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)  # the only installed assistant
    _framework_copy(home / ".grimoire")

    bootstrap = tmp_path / "bootstrap"
    for relative in BOOTSTRAP_FILES:
        (bootstrap / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / relative, bootstrap / relative)

    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "GIT_TERMINAL_PROMPT": "0"}
    env.pop("FRAMEWORK_URL", None)
    result = subprocess.run(
        [sys.executable, str(bootstrap / "rites" / "summon.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, env=env, timeout=300, cwd=tmp_path,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Install transcript not written" not in output, output
    assert "Traceback" not in output, output

    # Only the installed assistant is configured.
    agents = home / ".codex" / "AGENTS.md"
    assert agents.is_file() and "BEGIN GRIMOIRE KNOWLEDGE BASE" in agents.read_text(encoding="utf-8")
    assert not (home / ".claude").exists()
    assert any((home / ".agents" / "skills").glob("grm-*"))

    # The transcript exists although the bootstrap folder holds no state module.
    transcript = json.loads((home / ".cache" / "grimoire" / "summon-last.json").read_text(encoding="utf-8"))
    assert transcript["operation"] == "install"
    assert [agent["id"] for agent in transcript["final_state"]["agent_targets"]] == ["codex"]
    assert transcript["final_state"]["framework"]["root"] == str(home / ".grimoire")
