"""formulae/publish/build.sh: arguments, content directory, placeholders and the Quartz clone.

The tests never run a generator: a stand-in `node` that reports an old version stops the
script right after the clone, and the Quartz repository is a local one.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SH = REPO_ROOT / "formulae" / "publish" / "build.sh"
CONFIG = REPO_ROOT / "formulae" / "publish" / "quartz.config.yaml"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")


def _grimoire(tmp_path: Path) -> Path:
    root = tmp_path / "good_grimoire"
    shutil.copytree(GOOD, root)
    shutil.copy(BUILD_SH, root / "publish" / "build.sh")
    return root


def _build(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    full_env["FRAMEWORK_HOME"] = REPO_ROOT.as_posix()
    full_env.update(env or {})
    return subprocess.run(
        [BASH, (root / "publish" / "build.sh").as_posix(), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=full_env,
    )


def test_script_is_valid_bash():
    assert subprocess.run([BASH, "-n", BUILD_SH.as_posix()], capture_output=True).returncode == 0


def test_an_unknown_argument_is_an_error_and_stages_nothing(tmp_path):
    root = _grimoire(tmp_path)
    result = _build(root, "--chek")
    assert result.returncode == 2
    assert "usage" in result.stderr
    assert not (root / "publish" / "content").exists()


def test_check_stages_into_the_configured_content_dir(tmp_path):
    root = _grimoire(tmp_path)
    (root / "publish" / "publish.json").write_text(json.dumps({"content_dir": "publish/site"}), encoding="utf-8")

    result = _build(root, "--check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Staged into publish/site" in result.stdout
    assert (root / "publish" / "site" / "index.md").is_file()
    assert not (root / "publish" / "content").exists()


def test_a_refused_stage_stops_the_build_with_the_reason(tmp_path):
    root = _grimoire(tmp_path)
    (root / "publish" / "publish.json").write_text(json.dumps({"content_dir": "publish"}), encoding="utf-8")
    result = _build(root, "--check")
    assert result.returncode == 1
    assert "Staging was refused" in result.stderr and "below publish/" in result.stderr


def test_the_stock_config_quotes_its_placeholders_so_a_colon_in_a_title_is_valid_yaml():
    lines = CONFIG.read_text(encoding="utf-8").splitlines()
    assert '  pageTitle: "{{SITE_TITLE}}"' in lines
    assert '  baseUrl: "{{BASE_URL}}"' in lines


def test_a_build_refuses_while_a_placeholder_is_unfilled(tmp_path):
    root = _grimoire(tmp_path)
    shutil.copy(CONFIG, root / "publish" / "quartz.config.yaml")

    result = _build(root)

    assert result.returncode == 1
    assert "placeholder" in result.stderr
    assert not (root / "publish" / "quartz").exists()


def _quartz_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "quartz_repo"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Tester")
    for tag in ("v1", "v2"):
        (repo / "package.json").write_text("{}\n", encoding="utf-8")
        (repo / "VERSION").write_text(tag + "\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", tag)
        git("tag", tag)
    return repo


def _old_node(tmp_path: Path) -> str:
    """A PATH that starts with a `node` reporting Node 20 and an inert `npm`."""
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "node").write_text("#!/bin/sh\nif [ \"$1\" = \"-p\" ]; then echo 20; else echo v20.0.0; fi\n", encoding="utf-8", newline="\n")
    (shim / "npm").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    for name in ("node", "npm"):
        (shim / name).chmod(0o755)
    return shim.as_posix() + os.pathsep + os.environ["PATH"]


def test_the_quartz_clone_keeps_a_restored_cache_and_follows_a_changed_ref(tmp_path):
    root = _grimoire(tmp_path)
    config = CONFIG.read_text(encoding="utf-8").replace("{{SITE_TITLE}}", "Good").replace("{{BASE_URL}}", "example.com")
    (root / "publish" / "quartz.config.yaml").write_text(config, encoding="utf-8")
    cached = root / "publish" / "quartz" / "node_modules" / "pkg"
    cached.mkdir(parents=True)  # what a CI cache restores: no package.json beside it
    (cached / "index.js").write_text("cached\n", encoding="utf-8")
    quartz = _quartz_repo(tmp_path)
    env = {"QUARTZ_REPO": quartz.as_posix(), "QUARTZ_REF": "v1", "PATH": _old_node(tmp_path)}

    first = _build(root, env=env)

    assert first.returncode == 1 and "Node.js" in first.stderr, first.stdout + first.stderr
    clone = root / "publish" / "quartz"
    assert (clone / "VERSION").read_text(encoding="utf-8").strip() == "v1"
    assert (clone / "node_modules" / "pkg" / "index.js").read_text(encoding="utf-8") == "cached\n"

    env["QUARTZ_REF"] = "v2"
    second = _build(root, env=env)

    assert second.returncode == 1, second.stdout + second.stderr
    assert (clone / "VERSION").read_text(encoding="utf-8").strip() == "v2"
    assert (clone / "node_modules" / "pkg" / "index.js").is_file()
    assert (clone / "quartz.config.yaml").read_text(encoding="utf-8") == config
