"""The grimoire plugin's session-start hook installs or updates the framework and prints routing context."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugins" / "grimoire" / "scripts" / "session_context.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _framework_remote(tmp_path: Path) -> Path:
    """A bare framework remote holding just what the hook reads (the routing block template)."""
    work = tmp_path / "framework-work"
    (work / "rites" / "templates").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "rites" / "templates" / "grimoire_block.md", work / "rites" / "templates" / "grimoire_block.md")
    (work / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "Tester")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "framework")
    bare = tmp_path / "framework.git"
    _git(work, "clone", "-q", "--bare", str(work), str(bare))
    return bare


def _run(tmp_path: Path, framework_home: Path, remote: Path, *, no_network: bool = False, claude_home: Path | None = None) -> str:
    env = dict(os.environ)
    env.update({
        "FRAMEWORK_HOME": str(framework_home),
        "FRAMEWORK_URL": str(remote),
        "FRAMEWORK_SESSION_HOME": str(tmp_path / "grimoires"),
        "FRAMEWORK_CLAUDE_HOME": str(claude_home or tmp_path / "claude-home"),
    })
    if no_network:
        env["FRAMEWORK_SESSION_NO_NETWORK"] = "1"
    result = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_first_session_clones_the_framework_and_prints_the_block(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"

    out = _run(tmp_path, framework, remote)

    assert (framework / ".git").is_dir()
    assert "framework: installed at" in out
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" in out
    assert "## Installed grimoires" in out
    assert "none registered yet" in out
    assert len(out) < 10000


def test_later_session_fast_forwards_a_clean_main_and_lists_grimoires(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    _run(tmp_path, framework, remote)

    # Upstream moves on; a grimoire gets registered.
    work = tmp_path / "framework-work"
    (work / "NOTE").write_text("x\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "more")
    _git(work, "push", "-q", str(remote), "main")
    home = tmp_path / "grimoires"
    shutil.copytree(GOOD, home / "good_grimoire")
    (home / "library.json").write_text(json.dumps({"grimoires": {"good_grimoire": {"local_path": str(home / "good_grimoire"), "online_path": None}}}), encoding="utf-8")

    out = _run(tmp_path, framework, remote)

    assert "framework: updated at" in out and "1 new commit" in out
    assert (framework / "NOTE").is_file()
    assert "- good_grimoire:" in out and "good fixture" in out.lower() or "- good_grimoire:" in out


def test_dirty_or_offbranch_framework_is_left_alone(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    _run(tmp_path, framework, remote)
    (framework / "VERSION").write_text("local edit\n", encoding="utf-8")

    out = _run(tmp_path, framework, remote)
    assert "with local changes; not updated" in out
    assert (framework / "VERSION").read_text(encoding="utf-8") == "local edit\n"

    _git(framework, "checkout", "-q", "--", "VERSION")
    _git(framework, "checkout", "-q", "-b", "release/next")
    out = _run(tmp_path, framework, remote)
    assert "on branch release/next; not updated" in out


def test_block_is_omitted_when_the_instruction_file_already_carries_it(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    claude_home = tmp_path / "claude-home"
    claude_home.mkdir()
    template = (REPO_ROOT / "rites" / "templates" / "grimoire_block.md").read_text(encoding="utf-8")
    (claude_home / "CLAUDE.md").write_text("# CLAUDE\n" + template, encoding="utf-8")

    out = _run(tmp_path, framework, remote, claude_home=claude_home)
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" not in out
    assert "## Installed grimoires" in out


def test_no_network_degrades_to_a_note(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    out = _run(tmp_path, framework, remote, no_network=True)
    assert "framework: not installed" in out and "network disabled" in out
    assert "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->" in out  # from the plugin's own copy


def _load_hook(monkeypatch, framework_home: Path):
    import importlib.util

    monkeypatch.setenv("FRAMEWORK_HOME", str(framework_home))
    spec = importlib.util.spec_from_file_location("session_context_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_check(monkeypatch, module, report: dict, returncode: int) -> None:
    class _Proc:
        stdout = json.dumps(report)

    _Proc.returncode = returncode
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: _Proc())


def test_drift_line_names_the_next_action_when_the_check_has_no_warnings(tmp_path, monkeypatch):
    framework = tmp_path / ".grimoire"
    (framework / "rites").mkdir(parents=True)
    (framework / "rites" / "summon.py").write_text("", encoding="utf-8")
    module = _load_hook(monkeypatch, framework)
    _fake_check(monkeypatch, module, {
        "status": "noop",
        "messages": [{"severity": "info", "message": "agent_blocks: would create routing block for claude"}],
        "summary": {"next_actions": [{"kind": "agent_block_update", "reason": "agent routing block missing for: claude"}]},
    }, returncode=1)
    assert module.drift_line() == "setup: drift detected; offer /grimoire:update (agent routing block missing for: claude)"


def test_drift_line_reports_in_sync(tmp_path, monkeypatch):
    framework = tmp_path / ".grimoire"
    (framework / "rites").mkdir(parents=True)
    (framework / "rites" / "summon.py").write_text("", encoding="utf-8")
    module = _load_hook(monkeypatch, framework)
    _fake_check(monkeypatch, module, {"status": "noop", "messages": [], "summary": {}}, returncode=0)
    assert module.drift_line() == "setup: in sync"


def test_first_session_tells_the_agent_how_commands_are_typed(tmp_path):
    remote = _framework_remote(tmp_path)
    out = _run(tmp_path, tmp_path / ".grimoire", remote)
    assert "commands: this install runs Grimoire as a Claude Code plugin" in out
    assert "/grimoire:<verb>" in out and "/grimoire-dev:<verb>" in out


def _run_raw(tmp_path: Path, framework_home: Path, remote: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "FRAMEWORK_HOME": str(framework_home),
        "FRAMEWORK_URL": str(remote),
        "FRAMEWORK_SESSION_HOME": str(tmp_path / "grimoires"),
        "FRAMEWORK_CLAUDE_HOME": str(tmp_path / "claude-home"),
        "FRAMEWORK_SESSION_NO_NETWORK": "1",
    })
    env.update(extra_env)
    return subprocess.run([sys.executable, str(HOOK)], capture_output=True, env=env, timeout=120)


def test_non_ascii_output_survives_a_narrow_stdout_encoding(tmp_path):
    home = tmp_path / "grimoires"
    shelf = home / "nihon"
    shelf.mkdir(parents=True)
    (shelf / "grimoire.json").write_text(json.dumps({"description": "日本 café"}, ensure_ascii=False), encoding="utf-8")
    (home / "library.json").write_text(json.dumps({"grimoires": {"nihon": {"local_path": str(shelf)}}}), encoding="utf-8")

    result = _run_raw(tmp_path, tmp_path / ".grimoire", tmp_path / "none", PYTHONIOENCODING="ascii")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert "- nihon: 日本 café" in result.stdout.decode("utf-8")


@pytest.mark.parametrize("library", [
    "[]",
    "null",
    '{"grimoires": []}',
    '{"grimoires": "x"}',
    '{"grimoires": {"a": "text", "b": null, "c": {"local_path": 7}, "d": {"local_path": null}}}',
    '{"grimoires": {"a": {"local_path": "' + "x" * 5 + '"}}}',
    "﻿{broken",
])
def test_malformed_library_never_fails_the_hook(tmp_path, library):
    home = tmp_path / "grimoires"
    home.mkdir()
    (home / "library.json").write_text(library, encoding="utf-8")

    result = _run_raw(tmp_path, tmp_path / ".grimoire", tmp_path / "none")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert "## Installed grimoires" in result.stdout.decode("utf-8")


def test_undecodable_library_never_fails_the_hook(tmp_path):
    home = tmp_path / "grimoires"
    home.mkdir()
    (home / "library.json").write_bytes(b"\xff\xfe\x00{")

    result = _run_raw(tmp_path, tmp_path / ".grimoire", tmp_path / "none")

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def test_an_unexpected_exception_degrades_to_one_note(tmp_path, monkeypatch, capsys):
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")

    def boom():
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(module, "installed_grimoires", boom)
    assert module.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("framework:") and "RuntimeError" in out
    assert len(out.strip().splitlines()) == 1


def test_every_git_step_fits_inside_the_hook_timeout(tmp_path, monkeypatch):
    hooks = json.loads((REPO_ROOT / "plugins" / "grimoire" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    timeout = hooks["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")
    assert module.BUDGET + 10 <= timeout

    seen = []

    class _Proc:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: seen.append(k["timeout"]) or _Proc())
    monkeypatch.setattr(module, "START", module.time.monotonic() - (module.BUDGET - 7))
    module.git("fetch", timeout=30)
    assert 0 < seen[-1] <= 7


def test_a_clone_without_a_working_tree_is_completed(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    subprocess.run(["git", "clone", "-q", "--no-checkout", str(remote), str(framework)], check=True)
    assert not (framework / "rites").exists()

    out = _run(tmp_path, framework, remote)

    assert (framework / "rites" / "templates" / "grimoire_block.md").is_file()
    assert out.splitlines()[0].startswith("framework: restored the working tree")


def test_a_broken_git_folder_without_a_working_tree_is_recloned(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    (framework / ".git").mkdir(parents=True)

    out = _run(tmp_path, framework, remote)

    assert (framework / "rites" / "templates" / "grimoire_block.md").is_file()
    assert "framework: installed at" in out


def test_a_git_folder_with_other_files_and_no_rites_is_left_alone(tmp_path):
    remote = _framework_remote(tmp_path)
    framework = tmp_path / ".grimoire"
    (framework / ".git").mkdir(parents=True)
    (framework / "mine.txt").write_text("keep\n", encoding="utf-8")

    out = _run(tmp_path, framework, remote)

    assert (framework / "mine.txt").read_text(encoding="utf-8") == "keep\n"
    assert out.splitlines()[0].startswith("framework:") and "no rites folder" in out.splitlines()[0]


_AUTHOR = ("-c", "user.name=Tester", "-c", "user.email=t@example.com")


class _Shelf:
    """A grimoire home holding clones of bare remotes, with a work tree per remote to publish from."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.home = tmp_path / "grimoires"
        self.home.mkdir()
        self.library: dict = {}

    def add(self, key: str, **entry: object) -> Path:
        work = self.tmp_path / f"{key}-work"
        work.mkdir()
        (work / "grimoire.json").write_text(json.dumps({"description": f"{key} knowledge"}), encoding="utf-8")
        _git(work, "init", "-q", "-b", "main")
        _git(work, *_AUTHOR, "add", "-A")
        _git(work, *_AUTHOR, "commit", "-q", "-m", "first")
        bare = self.tmp_path / f"{key}.git"
        _git(work, "clone", "-q", "--bare", str(work), str(bare))
        clone = self.home / key
        subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True, capture_output=True)
        self.library[key] = {"local_path": str(clone), **entry}
        return clone

    def publish(self, key: str, name: str = "page.md") -> None:
        """Commit one more file to the remote of ``key``."""
        work = self.tmp_path / f"{key}-work"
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{name}\n", encoding="utf-8")
        _git(work, *_AUTHOR, "add", "-A")
        _git(work, *_AUTHOR, "commit", "-q", "-m", f"add {name}")
        _git(work, "push", "-q", str(self.tmp_path / f"{key}.git"), "main")

    def lines(
        self, monkeypatch, *, fetches: list | None = None, no_network: bool = False,
        fetch_results: dict[str, tuple[int, str]] | None = None,
    ) -> dict[str, str]:
        """The hook's line for each grimoire. ``fetch_results`` answers a key's fetch without running it."""
        (self.home / "library.json").write_text(json.dumps({"grimoires": self.library}), encoding="utf-8")
        module = _load_hook(monkeypatch, self.tmp_path / ".grimoire")
        monkeypatch.setattr(module, "GRIMOIRE_HOME", self.home)
        monkeypatch.setattr(module, "NO_NETWORK", no_network)
        if fetches is not None or fetch_results is not None:
            real_git = module.git

            def spy(*args, **kwargs):
                if args[:1] == ("fetch",):
                    cwd = kwargs.get("cwd")
                    if fetches is not None:
                        fetches.append(cwd)
                    if fetch_results is not None and Path(cwd).name in fetch_results:
                        return fetch_results[Path(cwd).name]
                return real_git(*args, **kwargs)

            monkeypatch.setattr(module, "git", spy)
        self.module = module
        return {line[2:].split(":", 1)[0]: line for line in module.installed_grimoires()}


@pytest.mark.parametrize("commits, word", [(1, "1 new commit)"), (3, "3 new commits)")])
def test_grimoire_behind_its_remote_is_fast_forwarded_with_a_commit_count(tmp_path, monkeypatch, commits, word):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    for index in range(commits):
        shelf.publish("alpha", f"note{index}.md")

    line = shelf.lines(monkeypatch)["alpha"]

    assert line.endswith(f" - updated ({word}")
    assert (clone / f"note{commits - 1}.md").is_file()
    assert "commands changed" not in line


def test_grimoire_with_unsaved_changes_is_left_alone_with_a_note(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    shelf.publish("alpha")
    (clone / "grimoire.json").write_text("my edit\n", encoding="utf-8")

    line = shelf.lines(monkeypatch)["alpha"]

    assert line.endswith(" - has unsaved changes; not updated")
    assert (clone / "grimoire.json").read_text(encoding="utf-8") == "my edit\n"
    assert not (clone / "page.md").exists()


def test_grimoire_with_local_and_remote_commits_is_left_alone_with_a_note(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    (clone / "mine.md").write_text("mine\n", encoding="utf-8")
    _git(clone, *_AUTHOR, "add", "-A")
    _git(clone, *_AUTHOR, "commit", "-q", "-m", "local")
    head = _git(clone, "rev-parse", "HEAD")
    shelf.publish("alpha")

    line = shelf.lines(monkeypatch)["alpha"]

    assert line.endswith(" - has local commits and remote commits; run /grimoire:update")
    assert _git(clone, "rev-parse", "HEAD") == head
    assert not (clone / "page.md").exists()


def _shelf_on_one_host(tmp_path) -> _Shelf:
    """Two grimoires whose remotes sit on the same host."""
    shelf = _Shelf(tmp_path)
    for key in ("alpha", "beta"):
        clone = shelf.add(key)
        _git(clone, "remote", "set-url", "origin", f"https://git.example.test/team/{key}.git")
    return shelf


@pytest.mark.parametrize("result", [
    (128, "fatal: unable to access 'https://git.example.test/team/alpha.git/': Could not resolve host: git.example.test"),
    (128, "fatal: unable to access 'https://git.example.test/team/alpha.git/': Failed to connect to git.example.test port 443"),
    (124, "timed out"),
])
def test_unreachable_host_is_noted_and_fetched_once(tmp_path, monkeypatch, result):
    shelf = _shelf_on_one_host(tmp_path)
    fetches: list = []

    lines = shelf.lines(monkeypatch, fetches=fetches, fetch_results={"alpha": result, "beta": result})

    note = " - could not reach its remote; using the copy on disk"
    assert lines["alpha"].endswith(note) and lines["beta"].endswith(note)
    assert len(fetches) == 1


@pytest.mark.parametrize("output", [
    "fatal: unable to access 'https://git.example.test/team/alpha.git/': The requested URL returned error: 403",
    "fatal: Authentication failed for 'https://git.example.test/team/alpha.git/'",
    "fatal: could not read Username for 'https://git.example.test': terminal prompts disabled",
    "remote: The project you were looking for could not be found or you don't have permission to view it.",
])
def test_refused_remote_is_noted_and_the_same_host_is_still_fetched(tmp_path, monkeypatch, output):
    shelf = _shelf_on_one_host(tmp_path)
    fetches: list = []

    lines = shelf.lines(monkeypatch, fetches=fetches, fetch_results={"alpha": (128, output), "beta": (0, "")})

    assert lines["alpha"].endswith(
        " - could not update from its remote (sign-in, permission, or the repository moved); "
        "using the copy on disk; run /grimoire:update"
    )
    assert " - " not in lines["beta"]
    assert len(fetches) == 2


def test_the_host_comes_from_the_checkout_and_not_from_the_library(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    unreachable = (128, "fatal: unable to access 'https://old.example.test/': Could not resolve host: old.example.test")
    shelf.add("alpha", online_path="https://old.example.test/team/alpha.git")
    shelf.add("beta", online_path="https://old.example.test/team/beta.git")
    shelf.publish("beta")

    lines = shelf.lines(monkeypatch, fetch_results={"alpha": unreachable})

    assert lines["alpha"].endswith(" - could not reach its remote; using the copy on disk")
    assert lines["beta"].endswith(" - updated (1 new commit)")


def test_missing_remote_without_a_host_does_not_block_other_grimoires(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    for key in ("alpha", "beta"):
        clone = shelf.add(key)
        _git(clone, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    fetches: list = []

    lines = shelf.lines(monkeypatch, fetches=fetches)

    assert "could not update from its remote" in lines["alpha"] and "could not update from its remote" in lines["beta"]
    assert len(fetches) == 2


def test_read_only_access_is_marked_on_the_line(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    shelf.add("alpha", access="read")
    shelf.add("beta", access="write")

    lines = shelf.lines(monkeypatch)

    assert lines["alpha"].endswith(f"({(tmp_path / 'grimoires' / 'alpha').as_posix()}) [read-only]")
    assert "[read-only]" not in lines["beta"]


def test_change_under_skills_names_the_manual_step_when_registration_is_unavailable(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    shelf.add("alpha")
    shelf.publish("alpha", "skills/tool/SKILL.md")

    line = shelf.lines(monkeypatch)["alpha"]

    assert line.endswith(" - updated (1 new commit); its commands changed: run /grimoire:update skills, then open a new session")


def test_change_under_skills_registers_the_commands_once(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    shelf.add("alpha")
    shelf.add("beta")
    shelf.add("gamma")
    shelf.publish("alpha", "skills/tool/SKILL.md")
    shelf.publish("beta", "skills/other/SKILL.md")
    shelf.publish("gamma", "page.md")
    (shelf.home / "library.json").write_text(json.dumps({"grimoires": shelf.library}), encoding="utf-8")
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")
    monkeypatch.setattr(module, "GRIMOIRE_HOME", shelf.home)
    monkeypatch.setattr(module, "NO_NETWORK", False)
    calls = []
    monkeypatch.setattr(module, "register_skills", lambda: calls.append(1) or True)

    lines = {line[2:].split(":", 1)[0]: line for line in module.installed_grimoires()}

    assert calls == [1]
    assert lines["alpha"].endswith(" - updated (1 new commit); its commands changed: open a new session to use them")
    assert lines["beta"].endswith(" - updated (1 new commit); its commands changed: open a new session to use them")
    assert lines["gamma"].endswith(" - updated (1 new commit)")


def test_register_skills_reports_failure_without_the_framework_rite(tmp_path, monkeypatch):
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")

    assert module.register_skills() is False


def test_git_runs_without_a_credential_prompt_or_window(tmp_path, monkeypatch):
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")
    seen = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args, **kwargs):
        seen.update(kwargs["env"])
        return _Proc()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.git("status")

    assert seen["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["GCM_INTERACTIVE"] == "never"


def test_no_network_flag_performs_no_fetch_and_adds_no_note(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    shelf.publish("alpha")
    fetches: list = []

    line = shelf.lines(monkeypatch, fetches=fetches, no_network=True)["alpha"]

    assert fetches == [] and " - " not in line.split(") ", 1)[-1] and line.endswith(")")
    assert not (clone / "page.md").exists()


def test_folder_without_git_gets_no_note(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    plain = shelf.home / "plain"
    plain.mkdir()
    (plain / "grimoire.json").write_text(json.dumps({"description": "plain notes"}), encoding="utf-8")
    shelf.library["plain"] = {"local_path": str(plain)}
    shelf.library["gone"] = {"local_path": str(shelf.home / "gone")}
    fetches: list = []

    lines = shelf.lines(monkeypatch, fetches=fetches)

    assert lines["plain"] == f"- plain: plain notes ({plain.as_posix()})"
    assert " - " not in lines["gone"].split(") ", 1)[-1]
    assert fetches == []


def test_detached_head_and_missing_upstream_are_not_fetched(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    detached = shelf.add("alpha")
    _git(detached, "checkout", "-q", "--detach")
    lonely = shelf.add("beta")
    _git(lonely, "checkout", "-q", "-b", "side")
    fetches: list = []

    lines = shelf.lines(monkeypatch, fetches=fetches)

    assert fetches == []
    assert lines["alpha"].endswith(")") and lines["beta"].endswith(")")


def test_grimoire_pass_stops_when_too_little_time_is_left(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    shelf.publish("alpha")
    fetches: list = []
    (shelf.home / "library.json").write_text(json.dumps({"grimoires": shelf.library}), encoding="utf-8")
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")
    monkeypatch.setattr(module, "GRIMOIRE_HOME", shelf.home)
    monkeypatch.setattr(module, "remaining", lambda: module.CHECK_TIMEOUT + module.MIN_STEP_SECONDS - 1)
    real_git = module.git
    monkeypatch.setattr(module, "git", lambda *a, **k: fetches.append(a) or real_git(*a, **k))

    lines = module.installed_grimoires()

    assert lines == [f"- alpha: alpha knowledge ({clone.as_posix()})"]
    assert fetches == []


def test_a_failure_inside_the_grimoire_pass_leaves_the_line_without_a_note(tmp_path, monkeypatch):
    shelf = _Shelf(tmp_path)
    clone = shelf.add("alpha")
    shelf.lines(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(shelf.module, "git", boom)
    assert shelf.module.installed_grimoires() == [f"- alpha: alpha knowledge ({clone.as_posix()})"]


SESSION_SH = REPO_ROOT / "plugins" / "grimoire" / "scripts" / "session_context.sh"
BASH = shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="no bash available")
def _hook_for_marketplace(tmp_path, monkeypatch, source):
    """The hook module as it runs from the plugin cache of a marketplace added with `source`."""
    monkeypatch.delenv("FRAMEWORK_URL", raising=False)
    module = _load_hook(monkeypatch, tmp_path / ".grimoire")
    claude_home = tmp_path / ".claude"
    (claude_home / "plugins").mkdir(parents=True)
    if source is not None:
        (claude_home / "plugins" / "known_marketplaces.json").write_text(
            json.dumps({"sample": {"source": source}}), encoding="utf-8",
        )
    monkeypatch.setattr(module, "CLAUDE_HOME", claude_home)
    monkeypatch.setattr(module, "PLUGIN_ROOT", claude_home / "plugins" / "cache" / "sample" / "grimoire" / "1.0.0")
    return module


def test_a_plugin_from_a_mirror_clones_the_framework_from_that_mirror(tmp_path, monkeypatch):
    mirror = "https://gitlab.example.com/tools/grimoire.git"
    module = _hook_for_marketplace(tmp_path, monkeypatch, {"source": "git", "url": mirror})

    assert module.framework_url() == mirror


def test_a_plugin_from_a_github_marketplace_clones_that_repository(tmp_path, monkeypatch):
    module = _hook_for_marketplace(tmp_path, monkeypatch, {"source": "github", "repo": "sample-owner/grimoire"})

    assert module.framework_url() == "https://github.com/sample-owner/grimoire.git"


def test_the_framework_url_variable_overrides_the_marketplace(tmp_path, monkeypatch):
    module = _hook_for_marketplace(tmp_path, monkeypatch, {"source": "git", "url": "https://gitlab.example.com/a.git"})
    monkeypatch.setenv("FRAMEWORK_URL", "https://git.example.org/b.git")

    assert module.framework_url() == "https://git.example.org/b.git"


def test_an_unknown_marketplace_falls_back_to_the_bundled_address(tmp_path, monkeypatch):
    module = _hook_for_marketplace(tmp_path, monkeypatch, None)
    bundled = json.loads((HOOK.parent / "framework_source.json").read_text(encoding="utf-8"))["url"]

    assert module.framework_url() == bundled


def test_the_shell_entry_exits_zero_when_the_hook_script_crashes(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(SESSION_SH, scripts / "session_context.sh")
    (scripts / "session_context.py").write_text("raise SystemExit(5)\n", encoding="utf-8")
    result = subprocess.run([BASH, str(scripts / "session_context.sh")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0


@pytest.mark.skipif(BASH is None, reason="no bash available")
def test_the_shell_entry_prints_one_framework_line_without_python(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = subprocess.run(
        [BASH, str(SESSION_SH)], capture_output=True, text=True, timeout=60, env={"PATH": str(empty)},
    )
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("framework:") and "3.10" in lines[0]
