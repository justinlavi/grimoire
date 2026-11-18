"""summon_core: the routing-block writer, the library update, install outcomes,
skill-sync reporting, discovery paging, and the constraints of the piped bootstrap."""

import ast
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import _lib
import summon_core
import sync_skills

REPO_ROOT = Path(__file__).resolve().parent.parent


class Log:
    def __init__(self):
        self.events = []

    def info(self, m):
        self.events.append(("info", m))

    def ok(self, m):
        self.events.append(("ok", m))

    def warn(self, m):
        self.events.append(("warn", m))

    def err(self, m):
        self.events.append(("err", m))

    def line(self, m):
        self.events.append(("line", m))

    def texts(self, kind):
        return [m for k, m in self.events if k == kind]


# ---------------------------------------------------------------------------
# Literals shared with files that cannot import this module
# ---------------------------------------------------------------------------


def test_session_hook_markers_equal_the_core_markers():
    text = (REPO_ROOT / "plugins" / "grimoire" / "scripts" / "session_context.py").read_text(encoding="utf-8")
    begin = re.search(r'^BEGIN = "(.*)"$', text, re.MULTILINE).group(1)
    end = re.search(r'^END = "(.*)"$', text, re.MULTILINE).group(1)
    assert begin == summon_core.BEGIN_SENTINEL
    assert end == summon_core.END_SENTINEL


def test_the_ownership_marker_equals_the_one_sync_skills_stamps():
    assert summon_core.SKILL_OWNERSHIP_MARKER == sync_skills.OWNERSHIP_MARKER


# ---------------------------------------------------------------------------
# The piped bootstrap runs these files before the framework exists on disk
# ---------------------------------------------------------------------------

BOOTSTRAP_FILES = ("summon.py", "summon_core.py", "agent_targets.py")
BOOTSTRAP_DOWNLOADS = {
    "rites/summon.py",
    "rites/summon_core.py",
    "rites/agent_targets.py",
    "rites/data/agent_targets.json",
    "rites/templates/grimoire_block.md",
}


def _module_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or "").split(".")[0])
    return names


@pytest.mark.parametrize("name", BOOTSTRAP_FILES)
def test_bootstrap_modules_import_only_the_standard_library_and_each_other(name):
    allowed = set(sys.stdlib_module_names) | {"summon_core", "agent_targets", "__future__"}
    imported = _module_level_imports(REPO_ROOT / "rites" / name)
    assert imported <= allowed, f"{name} imports {sorted(imported - allowed)} at load time"


def test_the_bootstrap_downloads_exactly_the_files_the_dispatcher_needs():
    script = (REPO_ROOT / "rites" / "summon.sh").read_text(encoding="utf-8")
    downloaded = set(re.findall(r'download_file "\$FRAMEWORK_RAW_BASE/([^"]+)"', script))
    assert downloaded == BOOTSTRAP_DOWNLOADS
    for relative in BOOTSTRAP_DOWNLOADS:
        assert (REPO_ROOT / relative).is_file()


def test_the_contract_page_names_the_downloaded_companion_files():
    page = (REPO_ROOT / "docs" / "summoning_contract.md").read_text(encoding="utf-8")
    for relative in BOOTSTRAP_DOWNLOADS:
        assert relative.removeprefix("rites/") in page


def test_use_framework_modules_changes_nothing_when_the_rites_import(monkeypatch):
    path_before = list(sys.path)
    summon_core.use_framework_modules()
    assert sys.path == path_before


def test_use_framework_modules_appends_the_installed_framework_when_the_rites_do_not_import(tmp_path, monkeypatch):
    framework = tmp_path / "framework"
    (framework / "rites").mkdir(parents=True)
    monkeypatch.setattr(summon_core, "FRAMEWORK_DIR", framework)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setitem(sys.modules, "_lib", None)  # an import of _lib now raises ImportError

    summon_core.use_framework_modules()

    assert sys.path[-1] == str(framework / "rites")


# ---------------------------------------------------------------------------
# The framework URL
# ---------------------------------------------------------------------------


def _url_args(flag=None):
    return SimpleNamespace(framework_url=flag)


def test_framework_url_comes_from_the_flag_first(monkeypatch):
    monkeypatch.setenv("FRAMEWORK_URL", "https://env.example/f.git")
    monkeypatch.setattr(summon_core, "detect_framework_url", lambda: "https://checkout.example/f.git")
    assert summon_core.resolve_framework_url(_url_args("https://flag.example/f.git")) == "https://flag.example/f.git"


def test_framework_url_comes_from_the_environment_second(monkeypatch):
    monkeypatch.setenv("FRAMEWORK_URL", "https://env.example/f.git")
    monkeypatch.setattr(summon_core, "detect_framework_url", lambda: "https://checkout.example/f.git")
    assert summon_core.resolve_framework_url(_url_args()) == "https://env.example/f.git"


def test_framework_url_comes_from_the_checkout_origin_third(monkeypatch):
    monkeypatch.delenv("FRAMEWORK_URL", raising=False)
    monkeypatch.setattr(summon_core, "detect_framework_url", lambda: "https://checkout.example/f.git")
    assert summon_core.resolve_framework_url(_url_args()) == "https://checkout.example/f.git"


def test_framework_url_falls_back_to_the_public_default(monkeypatch):
    monkeypatch.delenv("FRAMEWORK_URL", raising=False)
    monkeypatch.setattr(summon_core, "detect_framework_url", lambda: "")
    assert summon_core.resolve_framework_url(_url_args()) == summon_core.DEFAULT_FRAMEWORK_URL


def test_the_checkout_origin_is_read_only_from_a_git_checkout(tmp_path, monkeypatch):
    calls = []

    def fake_git(*args, **_kwargs):
        calls.append(args)
        return True, "https://origin.example/f.git"

    monkeypatch.setattr(summon_core, "git", fake_git)
    monkeypatch.setattr(summon_core, "REPO_ROOT", tmp_path)
    assert summon_core.detect_framework_url() == ""
    assert calls == []  # a bootstrap folder is not a checkout: git is never asked

    (tmp_path / ".git").mkdir()
    assert summon_core.detect_framework_url() == "https://origin.example/f.git"
    assert calls and calls[0][-3:] == ("remote", "get-url", "origin")


# ---------------------------------------------------------------------------
# The routing block: one classifier, one writer
# ---------------------------------------------------------------------------


def test_a_file_that_is_not_utf8_is_left_for_review_and_never_rewritten(tmp_path):
    target = tmp_path / "AGENTS.md"
    original = "# AGENTS\nnotes with an accent: café\n".encode("utf-16")
    target.write_bytes(original)

    result = summon_core.apply_routing_block(target, "AGENTS.md", apply=True)

    assert result["action"] == "review" and result["status"] == "review"
    assert result["reason"] == "not UTF-8"
    assert target.read_bytes() == original


def test_the_install_injector_leaves_a_file_that_is_not_utf8_untouched(tmp_path):
    target = tmp_path / "CLAUDE.md"
    original = "café notes\n".encode("cp1252")
    target.write_bytes(original)
    log = Log()

    summon_core.inject_agent_file(log, target, "CLAUDE.md")

    assert target.read_bytes() == original
    assert any("not UTF-8" in message for message in log.texts("warn"))


def test_plan_mode_classifies_and_writes_nothing(tmp_path):
    target = tmp_path / "AGENTS.md"
    result = summon_core.apply_routing_block(target, "AGENTS.md", apply=False)
    assert (result["action"], result["status"]) == ("create", "planned")
    assert not target.exists()


def test_the_writer_writes_lf_and_keeps_text_outside_the_block(tmp_path):
    target = tmp_path / "AGENTS.md"
    target.write_bytes(b"# AGENTS\r\nmine\r\n")
    result = summon_core.apply_routing_block(target, "AGENTS.md", apply=True)
    assert (result["action"], result["status"]) == ("insert", "ok")
    raw = target.read_bytes()
    assert b"\r" not in raw
    assert raw.startswith(b"# AGENTS\n") and b"mine" in raw


def test_a_plugin_served_target_gets_no_block_written_into_a_blockless_file(tmp_path):
    absent = tmp_path / "absent.md"
    blockless = tmp_path / "blockless.md"
    blockless.write_text("# mine\n", encoding="utf-8")
    for target in (absent, blockless):
        result = summon_core.apply_routing_block(target, "t", apply=True, plugin_served=True)
        assert (result["action"], result["status"]) == ("served", "noop")
    assert not absent.exists()
    assert blockless.read_text(encoding="utf-8") == "# mine\n"


def test_a_plugin_served_target_still_refreshes_a_stale_block(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text(f"{summon_core.BEGIN_SENTINEL}\nold\n{summon_core.END_SENTINEL}\n", encoding="utf-8")
    result = summon_core.apply_routing_block(target, "CLAUDE.md", apply=True, plugin_served=True)
    assert (result["action"], result["status"]) == ("refresh", "ok")
    assert summon_core.canonical_routing_block() in target.read_text(encoding="utf-8")


def test_a_write_that_fails_is_reported_not_raised(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(summon_core, "write_text", boom)
    result = summon_core.apply_routing_block(tmp_path / "AGENTS.md", "AGENTS.md", apply=True)
    assert result["status"] == "error" and "denied" in result["reason"]


def test_the_installer_writes_the_block_only_for_installed_agents(tmp_path, monkeypatch):
    (tmp_path / ".codex").mkdir()
    import agent_targets

    monkeypatch.setattr(
        summon_core,
        "installed_instruction_targets",
        lambda root: agent_targets.installed_instruction_targets(root, tmp_path),
    )
    summon_core.inject_agent_configs(Log())
    assert (tmp_path / ".codex" / "AGENTS.md").is_file()
    assert not (tmp_path / ".claude").exists()


# ---------------------------------------------------------------------------
# The library update
# ---------------------------------------------------------------------------


def _home_with(tmp_path, text=None):
    home = tmp_path / "kb"
    home.mkdir()
    if text is not None:
        (home / "library.json").write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return home


def test_a_library_that_does_not_parse_is_never_overwritten(tmp_path):
    broken = '{"grimoires": {"old": {"local_path": "x"},}}'
    home = _home_with(tmp_path, broken)
    log = Log()

    assert summon_core.update_local_library(["new"], {"grimoires": {}}, log, home=home) is False

    assert (home / "library.json").read_text(encoding="utf-8") == broken
    assert any("not valid JSON" in message for message in log.texts("err"))


@pytest.mark.parametrize("text", ['["not", "an", "object"]', '{"grimoires": []}', b"\xff\xfe"])
def test_an_unusable_library_is_left_as_it_is(tmp_path, text):
    home = _home_with(tmp_path, text)
    before = (home / "library.json").read_bytes()
    assert summon_core.update_local_library(["new"], {"grimoires": {}}, Log(), home=home) is False
    assert (home / "library.json").read_bytes() == before


def test_a_library_object_without_grimoires_gains_the_entry(tmp_path):
    home = _home_with(tmp_path, '{"note": "keep"}')
    (home / "new").mkdir()
    assert summon_core.update_local_library(
        ["new"], {"grimoires": {"new": {"online_path": "https://example.test/new.git"}}}, Log(), home=home,
    ) is True
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["note"] == "keep"
    assert library["grimoires"]["new"]["online_path"] == "https://example.test/new.git"


def test_the_update_keeps_other_entries_and_unknown_fields(tmp_path):
    home = _home_with(tmp_path, json.dumps({"grimoires": {
        "old": {"local_path": "$HOME/old", "online_path": "u", "pinned": True},
        "new": {"local_path": "stale", "online_path": "kept", "note": "n"},
    }}))
    summon_core.update_local_library(["new"], {"grimoires": {"new": {"online_path": ""}}}, Log(), home=home)
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["old"] == {"local_path": "$HOME/old", "online_path": "u", "pinned": True}
    assert library["grimoires"]["new"]["note"] == "n"
    assert library["grimoires"]["new"]["online_path"] == "kept"  # an empty discovered URL keeps the recorded one
    assert list(library["grimoires"]) == ["new", "old"]


def test_local_path_follows_the_home_it_was_installed_under(tmp_path):
    home = _home_with(tmp_path)
    summon_core.update_local_library(["recipes"], {"grimoires": {}}, Log(), home=home)
    entry = json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]["recipes"]
    assert entry["local_path"] == _lib.format_local_path(home / "recipes")
    assert "\\" not in entry["local_path"]
    assert not entry["local_path"].startswith("$HOME/grimoires/")


def test_the_library_is_written_as_utf8_with_lf(tmp_path):
    home = _home_with(tmp_path)
    summon_core.update_local_library(
        ["n"], {"grimoires": {"n": {"online_path": "https://example.test/café.git"}}}, Log(), home=home,
    )
    raw = (home / "library.json").read_bytes()
    assert b"\r" not in raw and "café".encode("utf-8") in raw


def test_finalize_reports_a_library_that_could_not_be_updated(monkeypatch):
    monkeypatch.setattr(summon_core, "update_local_library", lambda *a, **k: False)
    monkeypatch.setattr(summon_core, "inject_agent_configs", lambda log: None)
    monkeypatch.setattr(summon_core, "sync_skills", lambda log: True)
    assert summon_core.finalize_install(["k"], {"grimoires": {}}, Log()) is False


# ---------------------------------------------------------------------------
# What install_grimoire did
# ---------------------------------------------------------------------------


def _fake_git(populate=None, ok=True):
    calls = []

    def git(*args, log=None, **_kwargs):
        calls.append(args)
        if populate and args[0] == "clone":
            target = Path(args[-1])
            (target / ".git").mkdir(parents=True)
            (target / "README.md").write_text("x", encoding="utf-8")
        return ok, ""

    git.calls = calls
    return git


def test_install_grimoire_reports_a_clone(tmp_path):
    outcome = summon_core.install_grimoire(
        "g", {"name": "g", "online_path": "u"}, Log(), git_fn=_fake_git(populate=True), home=tmp_path,
    )
    assert outcome == summon_core.CLONED


def test_install_grimoire_reports_a_failed_clone_as_none(tmp_path):
    assert summon_core.install_grimoire("g", {"online_path": "u"}, Log(), git_fn=_fake_git(ok=False), home=tmp_path) is None


def test_install_grimoire_reports_a_pull(tmp_path):
    (tmp_path / "g" / ".git").mkdir(parents=True)
    (tmp_path / "g" / "README.md").write_text("x", encoding="utf-8")
    assert summon_core.install_grimoire("g", {}, Log(), git_fn=_fake_git(), home=tmp_path) == summon_core.PULLED


def test_install_grimoire_reports_a_pull_that_failed(tmp_path):
    (tmp_path / "g" / ".git").mkdir(parents=True)
    (tmp_path / "g" / "README.md").write_text("x", encoding="utf-8")
    log = Log()
    assert summon_core.install_grimoire("g", {}, log, git_fn=_fake_git(ok=False), home=tmp_path) == summon_core.KEPT
    assert any("pull failed" in message for message in log.texts("warn"))


def test_install_grimoire_reports_a_folder_that_is_not_a_checkout(tmp_path):
    (tmp_path / "g").mkdir()
    git = _fake_git()
    assert summon_core.install_grimoire("g", {}, Log(), git_fn=git, home=tmp_path) == summon_core.SKIPPED
    assert git.calls == []


# ---------------------------------------------------------------------------
# Skill registration reports
# ---------------------------------------------------------------------------

REPORT = {
    "rite": "sync_skills",
    "status": "ok",
    "summary": {"registered": 4, "cleaned": 2, "reset": 1, "blocked": 0},
    "messages": [
        {"severity": "warning", "message": "cook: skipped /cook-x (wrong name)", "path": None},
        {"severity": "error", "message": "collision /grm-add", "path": "x"},
        {"severity": "info", "message": "would register /grm-y"},
        {"message": "no severity"},
        "not an object",
    ],
}


def test_the_skill_sync_report_is_read_into_counts_and_messages():
    report = summon_core.read_skill_sync_report(json.dumps(REPORT))
    assert report["counts"] == {"registered": 4, "cleaned": 2, "reset": 1, "blocked": 0}
    assert report["problems"] == []
    assert [m["severity"] for m in report["messages"]] == ["warning", "error", "info", "info"]


@pytest.mark.parametrize(
    "output, problem",
    [
        ("", "no JSON report"),
        ("Traceback (most recent call last): boom", "no JSON report"),
        ("[1, 2]", "not an object"),
        (json.dumps({"summary": {"registered": 1, "cleaned": 0, "reset": 0}}), "'blocked' count"),
        (json.dumps({"summary": {"registered": "x", "cleaned": 0, "reset": 0, "blocked": 0}}), "'registered' count"),
        (json.dumps({}), "'registered' count"),
        (None, "no JSON report"),
    ],
)
def test_a_missing_key_or_unparseable_report_is_reported_not_raised(output, problem):
    report = summon_core.read_skill_sync_report(output)
    assert any(problem in item for item in report["problems"])


def test_run_sync_skills_says_why_a_script_cannot_run(tmp_path):
    returncode, output = summon_core.run_sync_skills(tmp_path / "absent.py", "--agent", "all")
    assert returncode != 0
    assert summon_core.read_skill_sync_report(output)["problems"]


def test_the_installer_relays_what_sync_skills_reported(monkeypatch, tmp_path):
    script = tmp_path / "sync_skills.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(summon_core, "skill_sync_script", lambda: script)
    seen = {}

    def fake_run(path, *args, **_kwargs):
        seen["args"] = args
        return 0, json.dumps(REPORT)

    monkeypatch.setattr(summon_core, "run_sync_skills", fake_run)
    monkeypatch.setattr(summon_core, "installed_skill_targets", lambda root: {})
    log = Log()

    assert summon_core.sync_skills(log) is True

    assert seen["args"] == ("--agent", "all")
    assert "cook: skipped /cook-x (wrong name)" in log.texts("warn")
    assert "collision /grm-add" in log.texts("err")
    assert any("4 registered, 2 cleaned, 1 reset, 0 blocked" in message for message in log.texts("info"))


def test_the_installer_names_the_launcher_when_skill_sync_fails(monkeypatch, tmp_path):
    script = tmp_path / "sync_skills.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(summon_core, "skill_sync_script", lambda: script)
    monkeypatch.setattr(summon_core, "run_sync_skills", lambda *a, **k: (1, "garbage"))
    log = Log()

    assert summon_core.sync_skills(log) is False

    errors = " ".join(log.texts("err"))
    assert "bin/grimoire sync_skills" in errors
    assert "python3" not in errors


def test_printed_commands_use_the_framework_launcher(tmp_path):
    command = summon_core.grimoire_command("summon", "--reconcile", "--apply", root=tmp_path)
    assert command == f"{tmp_path.as_posix()}/bin/grimoire summon --reconcile --apply"


# ---------------------------------------------------------------------------
# Discovery reads every page
# ---------------------------------------------------------------------------


def _repos(start, count):
    return [{"name": f"repo-{n}-grimoire", "clone_url": f"u{n}"} for n in range(start, start + count)]


def test_a_listing_is_read_until_a_short_page(monkeypatch):
    pages = {1: _repos(0, 100), 2: _repos(100, 100), 3: _repos(200, 7)}
    urls = []

    def fake_get(url, **_k):
        urls.append(url)
        return pages[int(url.rsplit("&page=", 1)[1]) if "&page=" in url else 1], None

    monkeypatch.setattr(summon_core, "_api_get", fake_get)
    entries, err = summon_core._api_get_all("https://api.example/x?per_page=100")
    assert err is None and len(entries) == 207
    assert urls == [
        "https://api.example/x?per_page=100",
        "https://api.example/x?per_page=100&page=2",
        "https://api.example/x?per_page=100&page=3",
    ]


def test_paging_stops_at_the_upper_bound(monkeypatch):
    calls = []

    def endless(url, **_k):
        calls.append(url)
        return _repos(0, summon_core.LIST_PAGE_SIZE), None

    monkeypatch.setattr(summon_core, "_api_get", endless)
    entries, _err = summon_core._api_get_all("https://api.example/x?per_page=100")
    assert len(calls) == summon_core.LIST_MAX_PAGES
    assert len(entries) == summon_core.LIST_MAX_PAGES * summon_core.LIST_PAGE_SIZE


def test_a_failure_on_a_later_page_keeps_the_pages_already_read(monkeypatch):
    def fake_get(url, **_k):
        return (_repos(0, 100), None) if "&page=" not in url else (None, "HTTP 502")

    monkeypatch.setattr(summon_core, "_api_get", fake_get)
    entries, err = summon_core._api_get_all("https://api.example/x?per_page=100")
    assert err is None and len(entries) == 100


def test_a_failure_on_the_first_page_is_the_result(monkeypatch):
    monkeypatch.setattr(summon_core, "_api_get", lambda url, **_k: (None, "HTTP 403"))
    assert summon_core._api_get_all("https://api.example/x?per_page=100") == (None, "HTTP 403")


def test_github_discovery_finds_a_grimoire_past_the_first_hundred_repositories(monkeypatch):
    first = [{"name": f"project-{n}", "description": ""} for n in range(100)]
    second = [{"name": "late-grimoire", "clone_url": "u-late"}]
    base = "https://api.github.com/orgs/acme/repos?per_page=100"
    responses = {base: (first, None), base + "&page=2": (second, None)}
    monkeypatch.setattr(summon_core, "_api_get", lambda url, **_k: responses[url])

    entries = summon_core.try_github_discovery("github.com", "acme", "", Log())

    assert set(entries) == {"late-grimoire"}


# ---------------------------------------------------------------------------
# Access recorded with a registration
# ---------------------------------------------------------------------------


def test_a_new_key_is_registered_for_reading_by_default(tmp_path):
    home = _home_with(tmp_path)
    assert summon_core.update_local_library(["new"], {"grimoires": {}}, Log(), home=home) is True
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["new"]["access"] == "read"


def test_a_new_key_takes_the_access_it_is_given(tmp_path):
    home = _home_with(tmp_path)
    summon_core.update_local_library(["new"], {"grimoires": {}}, Log(), home=home, access="edit")
    library = json.loads((home / "library.json").read_text(encoding="utf-8"))
    assert library["grimoires"]["new"]["access"] == "edit"


def test_an_existing_entry_keeps_its_own_access_or_lack_of_one(tmp_path):
    home = _home_with(tmp_path, json.dumps({"grimoires": {
        "edited": {"local_path": "x", "online_path": "u", "access": "edit"},
        "plain": {"local_path": "y", "online_path": "u"},
        "reader": {"local_path": "z", "online_path": "u", "access": "read"},
    }}))
    summon_core.update_local_library(["edited", "plain", "reader"], {"grimoires": {}}, Log(), home=home, access="read")
    entries = json.loads((home / "library.json").read_text(encoding="utf-8"))["grimoires"]
    assert entries["edited"]["access"] == "edit"
    assert "access" not in entries["plain"]
    assert entries["reader"]["access"] == "read"


# ---------------------------------------------------------------------------
# A grimoire checkout is complete when it holds any file
# ---------------------------------------------------------------------------


def _has_commit(answer):
    return lambda *args, **kwargs: (answer, "")


def test_a_grimoire_checkout_with_any_file_is_populated(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "grimoire.json").write_text("{}", encoding="utf-8")

    assert summon_core.grimoire_tree_populated(tmp_path, _has_commit(True)) is True
    assert summon_core.working_tree_populated(tmp_path) is False  # the framework check wants its own files


def test_a_grimoire_checkout_with_commits_and_no_files_is_not_populated(tmp_path):
    (tmp_path / ".git").mkdir()

    assert summon_core.grimoire_tree_populated(tmp_path, _has_commit(True)) is False


def test_a_repository_with_no_commit_counts_as_populated(tmp_path):
    (tmp_path / ".git").mkdir()

    assert summon_core.grimoire_tree_populated(tmp_path, _has_commit(False)) is True


def test_a_grimoire_without_a_readme_is_cloned(tmp_path):
    import subprocess

    def run(*args, cwd):
        subprocess.run(["git", "-c", "user.name=Sample", "-c", "user.email=sample@example.com", *args],
                       cwd=cwd, check=True, capture_output=True)

    source = tmp_path / "source"
    source.mkdir()
    (source / "grimoire.json").write_text('{"name": "notes", "skill_prefix": "nt"}', encoding="utf-8")
    (source / "bread.md").write_text("# Bread\n", encoding="utf-8")
    run("init", "-q", "-b", "main", cwd=source)
    run("add", "-A", cwd=source)
    run("commit", "-q", "-m", "first", cwd=source)
    home = tmp_path / "grimoires"
    home.mkdir()
    log = Log()

    outcome = summon_core.install_grimoire("notes", {"name": "notes", "online_path": str(source)}, log, home=home)

    assert outcome == summon_core.CLONED
    assert (home / "notes" / "bread.md").is_file()
    assert log.texts("err") == [] and log.texts("warn") == []

