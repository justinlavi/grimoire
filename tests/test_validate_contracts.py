"""Tests for the validation orchestrator, the two contract loaders and the skill catalog."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import command_surface
import rite_profiles
import sync_docs
import validate

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES = REPO_ROOT / "rites"


def _git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(root), *args],
        check=True, capture_output=True,
    )


def _completed(stdout, returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


# --- Suite status comes from the report -------------------------------------


def test_unparseable_report_is_a_failure(monkeypatch):
    monkeypatch.setattr(validate.subprocess, "run", lambda *a, **k: _completed("not json"))

    name, ok, report = validate.run_rite("validate_links.py")

    assert not ok
    assert report["status"] == "fail"
    suite = validate.empty_suite_report(["validate_links.py"], [report], "framework", REPO_ROOT)
    assert suite["status"] == "fail"
    assert suite["summary"]["failed_validators"] == 1


def test_report_that_is_not_an_object_is_a_failure(monkeypatch):
    monkeypatch.setattr(validate.subprocess, "run", lambda *a, **k: _completed("[]"))

    _, ok, report = validate.run_rite("validate_links.py")

    assert not ok
    assert report["diagnostics"][0]["code"] == "VALIDATE_INVALID_VALIDATOR_REPORT"


def test_failing_report_with_exit_zero_is_a_failure(monkeypatch):
    stdout = json.dumps({"validator": "links", "status": "fail", "summary": {}})
    monkeypatch.setattr(validate.subprocess, "run", lambda *a, **k: _completed(stdout, 0))

    _, ok, report = validate.run_rite("validate_links.py")

    assert not ok
    suite = validate.empty_suite_report(["validate_links.py"], [report], "framework", REPO_ROOT)
    assert suite["status"] == "fail"


def test_passing_report_passes(monkeypatch):
    stdout = json.dumps({"validator": "links", "status": "pass", "summary": {}})
    monkeypatch.setattr(validate.subprocess, "run", lambda *a, **k: _completed(stdout, 0))

    _, ok, _ = validate.run_rite("validate_links.py")

    assert ok


# --- The orchestrator writes nothing ----------------------------------------


def test_parallel_mode_writes_nothing(monkeypatch):
    def stub(name, profile="framework", target_root=None):
        report = {"validator": Path(name).stem, "status": "pass", "returncode": 0,
                  "summary": {"errors": 0, "warnings": 0, "diagnostics": 0}}
        return name, True, report

    monkeypatch.setattr(validate, "run_rite", stub)
    before = sorted(entry.name for entry in validate.RITE_DIR.iterdir() if entry.name != "__pycache__")

    failed = validate.run_parallel(["validate_links.py", "validate_orphans.py"], output_format="json")

    after = sorted(entry.name for entry in validate.RITE_DIR.iterdir() if entry.name != "__pycache__")
    assert failed == 0
    assert before == after
    assert ".artifacts" not in after


def test_clean_artifacts_rite_is_gone():
    assert not (RITES / "clean_artifacts.py").exists()
    contract = rite_profiles.load_rite_profiles(REPO_ROOT)
    paths = {entry["path"] for entry in rite_profiles.profile_entries(contract)}
    assert "rites/clean_artifacts.py" not in paths
    assert "rites/validate.py" not in paths
    assert "read_only" not in rite_profiles.ALLOWED_PROFILES


def test_nonexistent_grimoire_path_exits_two(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RITES / "validate.py"), "--grimoire", str(tmp_path / "nope")],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2


def test_smart_listing_prints_no_python3():
    result = subprocess.run(
        [sys.executable, str(RITES / "validate.py"), "--smart"],
        capture_output=True, text=True, timeout=60,
    )
    assert "python3" not in result.stdout


# --- Smart selection reads git output correctly -----------------------------


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "寿司.md").write_text("one\n", encoding="utf-8")
    (root / "sub" / "a.md").write_text("one\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_git_changed_files_keeps_non_ascii_paths(repo):
    (repo / "寿司.md").write_text("two\n", encoding="utf-8")

    assert ("M", "寿司.md") in validate.git_changed_files(repo)


def test_git_changed_files_includes_untracked_files(repo):
    (repo / "new_page.md").write_text("x\n", encoding="utf-8")
    (repo / "寿司2.md").write_text("x\n", encoding="utf-8")

    changes = validate.git_changed_files(repo)

    assert ("A", "new_page.md") in changes
    assert ("A", "寿司2.md") in changes


def test_git_changed_files_paths_are_relative_to_the_target(repo):
    (repo / "sub" / "a.md").write_text("two\n", encoding="utf-8")
    (repo / "sub" / "b.md").write_text("x\n", encoding="utf-8")
    (repo / "outside.md").write_text("x\n", encoding="utf-8")

    changes = validate.git_changed_files(repo / "sub")

    assert ("M", "a.md") in changes
    assert ("A", "b.md") in changes
    assert all(path != "outside.md" and not path.startswith("sub/") for _, path in changes)


def test_git_changed_files_clean_tree_lists_tracked_files(repo):
    changes = validate.git_changed_files(repo)

    assert ("M", "寿司.md") in changes
    assert ("M", "sub/a.md") in changes


def test_git_changed_files_outside_a_repository_is_empty(tmp_path):
    assert validate.git_changed_files(tmp_path) == []


def test_smart_reads_markdown_as_utf8(tmp_path, monkeypatch):
    page = tmp_path / "docs" / "café.md"
    page.parent.mkdir()
    page.write_text("café [[docs/other]]\n", encoding="utf-8")
    monkeypatch.setattr(validate, "git_changed_files", lambda root: [("M", "docs/café.md")])

    rites = validate.determine_smart_rites("framework", tmp_path)

    assert "validate_links.py" in rites


def test_smart_treats_an_unreadable_page_as_needing_every_content_check(tmp_path, monkeypatch):
    page = tmp_path / "docs" / "latin.md"
    page.parent.mkdir()
    page.write_bytes(b"caf\xe9 [[docs/other]]\n")
    monkeypatch.setattr(validate, "git_changed_files", lambda root: [("M", "docs/latin.md")])

    rites = validate.determine_smart_rites("framework", tmp_path)

    assert {"validate_links.py", "validate_frontmatter.py", "validate_skill_refs.py"} <= set(rites)


# --- Smart selection reaches every validator --------------------------------


def _touch(root, rel, text="# Page\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _selected(monkeypatch, root, profile, changes):
    monkeypatch.setattr(validate, "git_changed_files", lambda _root: changes)
    return set(validate.determine_smart_rites(profile, root))


FRAMEWORK_PAGE = "---\ntype: reference\nauthority: grimoire\n---\n# Page\n[x](y.md) /grm-check\n"


def test_every_framework_validator_is_reachable_from_some_change(tmp_path, monkeypatch):
    _touch(tmp_path, "invocations/a.md", FRAMEWORK_PAGE)
    _touch(tmp_path, "rites/x.py", "x = 1\n")
    changes = [
        [("M", "invocations/a.md")],
        [("M", "rites/x.py")],
        [("A", "docs/new.txt")],
        [("D", "docs/gone.md")],
        [("M", "framework.json")],
    ]
    _touch(tmp_path, "framework.json", "{}")
    reached = set()
    for change in changes:
        reached |= _selected(monkeypatch, tmp_path, "framework", change)

    assert reached == set(validate.FRAMEWORK_RITES)


def test_every_grimoire_validator_is_reachable_from_some_change(tmp_path, monkeypatch):
    _touch(tmp_path, "chapters/a/page.md")
    _touch(tmp_path, "grimoire.json", "{}")
    reached = set()
    for change in ([("M", "chapters/a/page.md")], [("M", "grimoire.json")], [("A", "chapters/a/x.txt")]):
        reached |= _selected(monkeypatch, tmp_path, "grimoire", change)

    assert reached == set(validate.GRIMOIRE_RITES)


def test_a_new_file_selects_doc_trees(tmp_path, monkeypatch):
    _touch(tmp_path, "docs/new.txt", "x")

    assert "validate_doc_trees.py" in _selected(monkeypatch, tmp_path, "framework", [("A", "docs/new.txt")])
    assert "validate_doc_trees.py" in _selected(monkeypatch, tmp_path, "grimoire", [("A", "chapters/x.txt")])


def test_contract_files_are_all_mapped():
    contract_files = {p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "rites" / "data").glob("*.json")}
    contract_files |= {"framework.json", "formulae/grimoire/scaffold_contract.json"}

    assert contract_files == set(validate.CONTRACT_VALIDATORS)


@pytest.mark.parametrize("contract_file", sorted(validate.CONTRACT_VALIDATORS))
def test_a_contract_change_selects_its_validators(contract_file, tmp_path, monkeypatch):
    _touch(tmp_path, contract_file, "{}")
    expected = validate.CONTRACT_VALIDATORS[contract_file]

    selected = _selected(monkeypatch, tmp_path, "framework", [("M", contract_file)])

    if expected is None:
        assert selected == set(validate.FRAMEWORK_RITES)
    else:
        assert set(expected) <= selected
        assert expected


def test_contract_validators_are_the_ones_that_read_the_contracts():
    reads = {
        "rites/data/command_surface.json": "validate_skill_refs.py",
        "rites/data/rite_profiles.json": "validate_structure.py",
        "framework.json": "validate_naming.py",
    }
    for contract_file, validator in reads.items():
        assert validator in validate.CONTRACT_VALIDATORS[contract_file]
        assert validator in validate.FRAMEWORK_RITES


def test_validators_json_lists_existing_validators():
    for name in validate.FRAMEWORK_RITES + validate.GRIMOIRE_RITES:
        assert (RITES / name).is_file()


def test_a_deleted_framework_contract_selects_its_validators(tmp_path, monkeypatch):
    selected = _selected(monkeypatch, tmp_path, "framework", [("D", "rites/data/command_surface.json")])

    assert "validate_skill_refs.py" in selected


def test_a_command_reference_selects_skill_refs(tmp_path, monkeypatch):
    (tmp_path / "framework.json").write_text(
        json.dumps({"skill_prefix": "grm", "skill_families": {
            "grm": {"skill_prefix": "grm", "path": "skills/grm", "slug_prefix": ""}}}),
        encoding="utf-8",
    )
    _touch(tmp_path, "docs/a.md", "Run /grm-check.\n")

    assert "validate_skill_refs.py" in _selected(monkeypatch, tmp_path, "framework", [("M", "docs/a.md")])


# --- Rite-profile contract --------------------------------------------------


def _profile(path="rites/x.py", tests=("tests/test_x.py",)):
    return {
        "path": path, "profile": "apply_only", "default_mode": "apply", "plan_command": None,
        "apply_command": "x", "writes": ["y"], "idempotency": "z", "validation_profile": "v",
        "tests": list(tests),
    }


def _contract_root(tmp_path, entries):
    (tmp_path / "rites" / "data").mkdir(parents=True)
    (tmp_path / "rites" / "x.py").write_text("from pathlib import Path\nPath('a').write_text('b')\n", encoding="utf-8")
    (tmp_path / "rites" / "data" / "rite_profiles.json").write_text(
        json.dumps({"schema_version": 1, "profiles": entries}), encoding="utf-8"
    )
    return tmp_path


def test_listed_test_must_exist(tmp_path):
    root = _contract_root(tmp_path, [_profile(tests=("tests/test_missing.py",))])

    _, errors = rite_profiles.validate_rite_profiles(root)

    assert [e["code"] for e in errors] == ["RITE_PROFILE_TEST"]
    assert "tests/test_missing.py" in errors[0]["message"]


def test_listed_test_that_exists_passes(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("", encoding="utf-8")
    root = _contract_root(tmp_path, [_profile()])

    _, errors = rite_profiles.validate_rite_profiles(root)

    assert errors == []


def test_real_profiles_name_existing_tests_that_mention_the_rite():
    contract = rite_profiles.load_rite_profiles(REPO_ROOT)
    for entry in rite_profiles.profile_entries(contract):
        stem = Path(entry["path"]).stem
        assert entry["tests"], entry["path"]
        for test in entry["tests"]:
            assert (REPO_ROOT / test).is_file()
        # Each rite has at least one listed test that names it.
        assert any(
            stem in (REPO_ROOT / test).read_text(encoding="utf-8") for test in entry["tests"]
        ), entry["path"]


def test_non_object_contracts_are_reported_not_raised(tmp_path):
    (tmp_path / "rites" / "data").mkdir(parents=True)
    (tmp_path / "rites" / "data" / "rite_profiles.json").write_text("[]", encoding="utf-8")
    (tmp_path / "rites" / "data" / "command_surface.json").write_text("[]", encoding="utf-8")

    _, rite_errors = rite_profiles.validate_rite_profiles(tmp_path)
    _, command_errors = command_surface.validate_command_surface(tmp_path)

    assert rite_errors[0]["code"] == "RITE_PROFILE_SCHEMA"
    assert command_errors[0]["code"] == "COMMAND_SURFACE_SCHEMA"


def test_unreadable_contract_keeps_its_read_code(tmp_path):
    (tmp_path / "rites" / "data").mkdir(parents=True)
    (tmp_path / "rites" / "data" / "rite_profiles.json").write_bytes(b"\xff\xfe{")

    _, errors = rite_profiles.validate_rite_profiles(tmp_path)

    assert [e["code"] for e in errors] == ["RITE_PROFILE_READ"]


def test_the_two_contracts_share_one_profile_vocabulary():
    assert rite_profiles.ALLOWED_PROFILES < command_surface.ALLOWED_MUTATION_PROFILES
    assert command_surface.ALLOWED_MUTATION_PROFILES - rite_profiles.ALLOWED_PROFILES == {
        "read_only", "judgment_gated",
    }


# --- Skill catalog ----------------------------------------------------------


def test_catalog_groups_follow_the_declared_families():
    skills = sync_docs.collect_skills()
    groups = sync_docs.group_skills(skills)

    declared = [family["name"] for family in sync_docs.load_framework_skill_families()]
    assert [family["name"] for family, _ in groups] == declared
    for family, members in groups:
        assert all(skill["family"] == family["name"] for skill in members)
    patterns = [sync_docs.command_pattern(family) for family, _ in groups]
    assert patterns == ["/grm-<verb>", "/grm-dev-<verb>"]


def test_catalog_text_names_the_two_families_without_audience_labels():
    content = sync_docs.render_skills_doc(sync_docs.collect_skills(), sync_docs.load_command_metadata())

    text = " ".join(content.split())
    assert "`/grm-<verb>` commands work with grimoires" in text
    assert "`/grm-dev-<verb>` commands maintain the framework" in text
    assert "/grm-help all" in content
    assert "python3" not in content
    for label in ("most people", "maintainers", "your grimoires", "Maintainer reference"):
        assert label not in content


def test_catalog_last_verified_is_the_newest_release_date():
    content = sync_docs.render_skills_doc(sync_docs.collect_skills(), sync_docs.load_command_metadata())
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    released = next(line for line in changelog.splitlines() if line.startswith("## [") and " - " in line)

    assert f"last_verified: {released.rsplit(' - ', 1)[1]}\n" in content
    assert sync_docs.catalog_date() == released.rsplit(" - ", 1)[1]


def test_sync_docs_json_envelope_and_exit_code():
    result = subprocess.run(
        [sys.executable, str(RITES / "sync_docs.py"), "--format", "json"],
        capture_output=True, text=True, timeout=60,
    )
    report = json.loads(result.stdout)

    assert report["rite"] == "sync_docs"
    assert report["mode"] == "plan"
    assert report["summary"]["skills"] == len(sync_docs.collect_skills())
    assert result.returncode == (0 if report["status"] == "noop" else 1)


def test_sync_docs_honours_framework_home(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RITES / "sync_docs.py"), "--format", "json"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "FRAMEWORK_HOME": str(tmp_path)},
    )
    report = json.loads(result.stdout)

    assert report["root"] == str(tmp_path)
    assert report["status"] == "error"
    assert result.returncode == 1


def test_sync_docs_docstring_states_exit_codes_and_profile():
    doc = sync_docs.__doc__

    assert "Exit codes:" in doc
    assert "--format" in doc
    assert "plan_apply" in doc
    assert "python3" not in doc
