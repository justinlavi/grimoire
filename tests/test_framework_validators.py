"""Tests for the structure, format, naming, security, semantics and
skill-reference validators and the scaffold contract."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import scaffold_contract
import validate_structure

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES = REPO_ROOT / "rites"
GOOD = REPO_ROOT / "tests" / "fixtures" / "good_grimoire"

FRAMEWORK_JSON = {
    "name": "sample",
    "skill_prefix": "smp",
    "skill_families": {"main": {"path": "skills/main", "skill_prefix": "smp"}},
}


def _run(script, *args, framework_home=None):
    env = dict(os.environ)
    if framework_home is not None:
        env["FRAMEWORK_HOME"] = str(framework_home)
    return subprocess.run(
        [sys.executable, str(RITES / script), *args, "--format", "json"],
        capture_output=True, text=True, timeout=60, env=env,
    )


def _report(result):
    return json.loads(result.stdout)


def _codes(result, severity=None):
    return [
        d["code"] for d in _report(result)["diagnostics"]
        if severity is None or d["severity"] == severity
    ]


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _framework(tmp_path, manifest=FRAMEWORK_JSON):
    """A minimal framework tree with one skill family and one skill."""
    root = tmp_path / "fw"
    _write(root, "framework.json", json.dumps(manifest))
    _write(root, "skills/main/do-it/SKILL.md", "---\nname: {{SKILL_PREFIX}}-do-it\n---\n# Do it\n")
    return root


# --- validate_format ---------------------------------------------------------

PLAYBOOK_SECTIONS = ["Trigger", "Inputs", "Never", "Steps", "Evidence and checks", "Outputs"]


def _playbook(sections, page_type="playbook"):
    body = "".join(f"## {name}\n\nText.\n\n" for name in sections)
    return f'---\ntype: {page_type}\ntitle: "P"\n---\n\n# P\n\n{body}'


def _missing_sections(root):
    result = _run("validate_format.py", "--grimoire", str(root))
    return [
        d["message"] for d in _report(result)["diagnostics"]
        if d["code"] == "FORMAT_MISSING_INVOCATION_SECTION"
    ]


def test_playbook_with_all_six_sections_passes(tmp_path):
    _write(tmp_path, "invocations/do_it.md", _playbook(PLAYBOOK_SECTIONS))
    assert _missing_sections(tmp_path) == []


@pytest.mark.parametrize("missing", PLAYBOOK_SECTIONS)
def test_playbook_missing_one_section_is_reported(tmp_path, missing):
    _write(tmp_path, "invocations/do_it.md", _playbook([n for n in PLAYBOOK_SECTIONS if n != missing]))
    assert _missing_sections(tmp_path) == [f"missing section: ## {missing} section"]


def test_quoted_playbook_type_still_requires_the_sections(tmp_path):
    _write(tmp_path, "invocations/do_it.md", _playbook(["Trigger"], page_type='"playbook"'))
    assert len(_missing_sections(tmp_path)) == 5


def test_reference_page_needs_only_a_title(tmp_path):
    _write(tmp_path, "invocations/ref.md", _playbook([], page_type="reference"))
    assert _missing_sections(tmp_path) == []


def test_playbook_type_in_the_body_does_not_make_a_playbook(tmp_path):
    _write(tmp_path, "invocations/ref.md", '---\ntype: reference\ntitle: "R"\n---\n\n# R\n\ntype: playbook\n')
    assert _missing_sections(tmp_path) == []


def test_playbook_outside_invocations_is_not_checked(tmp_path):
    _write(tmp_path, "chapters/x/x.md", _playbook([]))
    assert _missing_sections(tmp_path) == []


@pytest.mark.parametrize("lines, flagged", [(200, False), (201, True)])
def test_hub_length_limit_is_inclusive_and_the_message_says_so(tmp_path, lines, flagged):
    _write(tmp_path, "invocations/big/big.md", "# Big\n" + "line\n" * (lines - 1))
    result = _run("validate_format.py", "--grimoire", str(tmp_path))
    messages = [d["message"] for d in _report(result)["diagnostics"] if d["code"] == "FORMAT_HUB_TOO_LONG"]
    assert bool(messages) is flagged
    if flagged:
        assert messages == ["hub too long (201 lines, at most 200)"]


def test_format_reports_an_undecodable_file_and_skips_it(tmp_path):
    (tmp_path / "bad.md").write_bytes(b"# caf\xe9\n```\n")
    _write(tmp_path, "good.md", "# Good\n")
    result = _run("validate_format.py", "--grimoire", str(tmp_path))
    diagnostics = _report(result)["diagnostics"]
    assert [(d["code"], d["severity"]) for d in diagnostics] == [("FORMAT_READ_ERROR", "warning")]
    assert result.returncode == 0


def test_format_reads_utf8_not_the_locale_encoding(tmp_path):
    _write(tmp_path, "chapters/a.md", "# 寿司\n\n| a | b |\n|--|--|\n")
    result = _run("validate_format.py", "--grimoire", str(tmp_path))
    diagnostics = _report(result)["diagnostics"]
    assert [(d["code"], d["line"]) for d in diagnostics] == [("FORMAT_SHORT_TABLE_DELIMITER", 4)]


def test_format_scans_the_framework_publish_folder_but_not_a_grimoire_publish_layer(tmp_path):
    _write(tmp_path, "formulae/publish/page.md", "no title here\n")
    _write(tmp_path, "publish/generated.md", "```\nunclosed\n")
    result = _run("validate_format.py", "--grimoire", str(tmp_path))
    assert _codes(result) == ["FORMAT_FORMULA_MISSING_TITLE"]


def test_format_rejects_a_missing_grimoire_path(tmp_path):
    result = _run("validate_format.py", "--grimoire", str(tmp_path / "absent"))
    assert result.returncode == 2


# --- validate_security -------------------------------------------------------


@pytest.mark.parametrize("source, code", [
    ("import ast\nvalue = ast.literal_eval(text)\n", None),
    ("rows = cursor.execute(query)\n", None),
    ("value = eval(text)\n", "SECURITY_EVAL"),
    ("value = builtins.eval(text)\n", "SECURITY_EVAL"),
    ("exec(text)\n", "SECURITY_EXEC"),
])
def test_security_matches_calls_not_longer_names(tmp_path, source, code):
    _write(tmp_path, "framework.json", "{}")
    _write(tmp_path, "rites/tool.py", source)
    result = _run("validate_security.py", framework_home=tmp_path)
    assert _codes(result) == ([code] if code else [])


def test_security_reports_an_undecodable_file_and_skips_it(tmp_path):
    _write(tmp_path, "framework.json", "{}")
    (tmp_path / "docs").mkdir()
    # Not UTF-8, and it holds a credential-shaped assignment that must not be reported.
    (tmp_path / "docs" / "bad.md").write_bytes(b"pass" + b'word = "caf\xe9"\n')
    (tmp_path / "rites").mkdir()
    (tmp_path / "rites" / "bad.py").write_bytes(b"x = 'caf\xe9'\n")
    result = _run("validate_security.py", framework_home=tmp_path)
    assert sorted(_codes(result)) == ["SECURITY_READ_ERROR", "SECURITY_READ_ERROR"]
    assert result.returncode == 0


# --- validate_semantics ------------------------------------------------------


def test_semantics_flags_a_hyphenated_chapters_path_but_not_a_bare_file_name(tmp_path):
    _write(tmp_path, "framework.json", "{}")
    _write(tmp_path, "docs/bare.md", "Name the file file-name.md in the folder.\n")
    _write(tmp_path, "docs/deep.md", "See chapters/recipes/file-name.md for details.\n")
    result = _run("validate_semantics.py", framework_home=tmp_path)
    flagged = [d["path"] for d in _report(result)["diagnostics"]]
    assert flagged == ["docs/deep.md"]


# --- validate_naming ---------------------------------------------------------


@pytest.mark.parametrize("name", ["My-File.md", "Title_Case.md", "FOO.md", "my file.md", "Mixed_case.py"])
def test_naming_warns_about_names_that_are_not_snake_case(tmp_path, name):
    root = _framework(tmp_path)
    _write(root, f"docs/{name}", "# x\n")
    result = _run("validate_naming.py", framework_home=root)
    assert _codes(result) == ["NAMING_NOT_SNAKE_CASE"]
    assert _report(result)["diagnostics"][0]["severity"] == "warning"
    assert result.returncode == 0


@pytest.mark.parametrize("name, code", [
    ("quick-start.md", "NAMING_HYPHENATED"),
    ("quickStart.md", "NAMING_CAMELCASE"),
])
def test_naming_errors_keep_their_codes(tmp_path, name, code):
    root = _framework(tmp_path)
    _write(root, f"docs/{name}", "# x\n")
    result = _run("validate_naming.py", framework_home=root)
    assert _codes(result) == [code]
    assert result.returncode == 1


@pytest.mark.parametrize("name", [
    "README.md", "UPDATE.md", "CHANGELOG.md", "CONTRIBUTING.md", "root_hub.formula.md",
    "quick_start.md", "page2.md", "_private.py", "__init__.py",
])
def test_naming_accepts_deliberate_and_snake_case_names(tmp_path, name):
    root = _framework(tmp_path)
    _write(root, f"docs/{name}", "# x\n")
    result = _run("validate_naming.py", framework_home=root)
    assert _codes(result) == []


def test_naming_leaves_kebab_case_skill_folders_alone(tmp_path):
    root = _framework(tmp_path)
    assert _codes(_run("validate_naming.py", framework_home=root)) == []


@pytest.mark.parametrize("path", ["skills", "elsewhere/main", "skills/main/deeper"])
def test_naming_rejects_a_family_path_that_is_not_one_folder_under_skills(tmp_path, path):
    root = _framework(tmp_path, {**FRAMEWORK_JSON, "skill_families": {"main": {"path": path}}})
    result = _run("validate_naming.py", framework_home=root)
    assert "SKILL_SCHEMA_FAMILY_INVALID" in _codes(result)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_naming_reads_framework_json_as_utf8(tmp_path):
    root = _framework(tmp_path, {**FRAMEWORK_JSON, "description": "Água"})
    assert _codes(_run("validate_naming.py", framework_home=root)) == []


def test_naming_reports_an_unreadable_manifest(tmp_path):
    root = _framework(tmp_path)
    (root / "framework.json").write_bytes(b'{"name": "caf\xe9"}')
    assert "SKILL_SCHEMA_MANIFEST_READ" in _codes(_run("validate_naming.py", framework_home=root))


def test_the_framework_itself_has_no_naming_diagnostics():
    result = _run("validate_naming.py")
    assert result.returncode == 0
    assert _codes(result) == []


# --- validate_skill_refs -----------------------------------------------------


def test_skill_refs_reports_an_unreadable_manifest(tmp_path):
    root = _framework(tmp_path)
    (root / "framework.json").write_bytes(b'{"name": "caf\xe9"}')
    assert "SKILL_REFS_MANIFEST_READ" in _codes(_run("validate_skill_refs.py", framework_home=root))


def test_skill_refs_resolves_a_command_and_flags_a_dangling_one(tmp_path):
    root = _framework(tmp_path)
    _write(root, "docs/use.md", "Run /smp-do-it, then /smp-ghost.\n")
    result = _run("validate_skill_refs.py", framework_home=root)
    dangling = [d["message"] for d in _report(result)["diagnostics"] if d["code"] == "SKILL_REFS_DANGLING"]
    assert dangling == ["references /smp-ghost with no source SKILL.md"]
    assert _report(result)["checked"]["valid_commands"] == 1


def test_skill_refs_exits_1_for_a_command_surface_error_alone(tmp_path):
    root = _framework(tmp_path)
    result = _run("validate_skill_refs.py", framework_home=root)
    codes = _codes(result)
    assert "SKILL_REFS_DANGLING" not in codes
    assert any(code.startswith("COMMAND_SURFACE_") for code in codes)
    assert result.returncode == 1


# --- validate_structure ------------------------------------------------------


def _doc_tree(tmp_path, hub_links, readme_links):
    _write(tmp_path, "grimoire.md", "# Hub\n" + "".join(f"[[docs/{stem}|x]]\n" for stem in hub_links))
    _write(tmp_path, "README.md", "# Readme\n" + "".join(f"[x](docs/{name}.md)\n" for name in readme_links))
    for name in ("agent", "agent_targets"):
        _write(tmp_path, f"docs/{name}.md", "# Doc\n")


def test_doc_index_requires_the_whole_page_name(tmp_path):
    _doc_tree(tmp_path, hub_links=["agent_targets"], readme_links=["agent_targets"])
    violations = validate_structure.doc_index_violations(tmp_path)
    assert sorted((code, path) for code, path, _ in violations) == [
        ("STRUCTURE_DOC_NOT_IN_HUB", "docs/agent.md"),
        ("STRUCTURE_DOC_NOT_IN_README", "docs/agent.md"),
    ]


def test_doc_index_accepts_anchored_and_labelled_links(tmp_path):
    _write(tmp_path, "grimoire.md", "[[docs/agent#top|a]] [[docs/agent_targets]]\n")
    _write(tmp_path, "README.md", "[a](docs/agent.md#top) [b](docs/agent_targets.md)\n")
    for name in ("agent", "agent_targets"):
        _write(tmp_path, f"docs/{name}.md", "# Doc\n")
    assert validate_structure.doc_index_violations(tmp_path) == []


def test_required_directories_come_from_the_skill_families(tmp_path):
    root = _framework(tmp_path, {
        **FRAMEWORK_JSON,
        "skill_families": {
            "main": {"path": "skills/main"},
            "extra": {"path": "skills/extra", "slug_prefix": "x"},
        },
    })
    required = validate_structure.required_dirs(root)
    assert "skills/main" in required and "skills/extra" in required
    assert set(validate_structure.HUB_DIRS) <= set(required)
    assert len(required) == len(set(required))


def test_the_frameworks_required_directories_name_its_families():
    required = validate_structure.required_dirs(REPO_ROOT)
    assert {"skills/grm", "skills/dev"} <= set(required)


# --- validate_grimoire_structure ---------------------------------------------


def _grimoire(tmp_path, name="g"):
    root = tmp_path / name
    shutil.copytree(GOOD, root)
    return root


def _structure(root):
    return _run("validate_grimoire_structure.py", "--grimoire", str(root))


def test_root_hub_is_found_by_manifest_name_in_a_differently_named_checkout(tmp_path):
    root = _grimoire(tmp_path, "cloned-checkout")
    result = _structure(root)
    assert result.returncode == 0, result.stdout
    assert "GRIMOIRE_STRUCTURE_MISSING_ROOT_HUB" not in _codes(result)


def test_root_hub_named_after_the_folder_is_accepted_when_the_manifest_name_has_none(tmp_path):
    root = _grimoire(tmp_path, "renamed")
    (root / "good_grimoire.md").rename(root / "renamed.md")
    result = _structure(root)
    assert "GRIMOIRE_STRUCTURE_MISSING_ROOT_HUB" not in _codes(result)


def test_missing_root_hub_names_the_manifest_name(tmp_path):
    root = _grimoire(tmp_path, "cloned-checkout")
    (root / "good_grimoire.md").unlink()
    result = _structure(root)
    messages = [d["message"] for d in _report(result)["diagnostics"] if d["code"] == "GRIMOIRE_STRUCTURE_MISSING_ROOT_HUB"]
    assert messages == ["missing root hub: good_grimoire.md"]


def test_customised_obsidian_graph_passes(tmp_path):
    root = _grimoire(tmp_path)
    _write(root, ".obsidian/graph.json", '{"showTags": true}\n')
    result = _structure(root)
    assert result.returncode == 0
    assert [d for d in _report(result)["diagnostics"] if d["path"] == ".obsidian/graph.json"] == []


def test_missing_obsidian_graph_warns_like_a_missing_gitignore(tmp_path):
    root = _grimoire(tmp_path)
    (root / ".obsidian" / "graph.json").unlink()
    result = _structure(root)
    flagged = {
        d["path"]: (d["code"], d["severity"]) for d in _report(result)["diagnostics"]
        if d["code"] == "GRIMOIRE_STRUCTURE_MISSING_SEEDED"
    }
    assert flagged[".obsidian/graph.json"] == ("GRIMOIRE_STRUCTURE_MISSING_SEEDED", "warning")
    assert flagged[".gitignore"] == ("GRIMOIRE_STRUCTURE_MISSING_SEEDED", "warning")
    assert result.returncode == 0


def test_obsidian_app_settings_stay_managed(tmp_path):
    root = _grimoire(tmp_path)
    _write(root, ".obsidian/app.json", "{}\n")
    assert "GRIMOIRE_STRUCTURE_STALE_MANAGED" in _codes(_structure(root))


@pytest.mark.parametrize("content", [b'{"newLinkFormat": "caf\xe9"}', b"[]"])
def test_unreadable_obsidian_settings_are_reported_not_a_crash(tmp_path, content):
    root = _grimoire(tmp_path)
    (root / ".obsidian" / "app.json").write_bytes(content)
    result = _structure(root)
    assert "GRIMOIRE_STRUCTURE_JSON_UNREADABLE" in _codes(result)
    assert "Traceback" not in result.stderr


def test_a_chapter_folder_named_publish_is_checked_for_its_hub(tmp_path):
    root = _grimoire(tmp_path)
    _write(root, "chapters/publish/note.md", "# note\n")
    assert "GRIMOIRE_STRUCTURE_MISSING_CHAPTER_HUB" in _codes(_structure(root))


def test_a_folder_without_markdown_needs_no_hub(tmp_path):
    root = _grimoire(tmp_path)
    (root / "chapters" / "recipes" / "empty").mkdir()
    _write(root, "chapters/recipes/media_only/photo.txt", "x\n")
    assert _structure(root).returncode == 0


def test_a_missing_grimoire_path_exits_2(tmp_path):
    assert _structure(tmp_path / "absent").returncode == 2


# --- scaffold contract -------------------------------------------------------

FILE_ENTRY_KEYS = {"source", "target", "create", "required", "managed", "role", "seed_if_absent"}


def test_contract_entries_use_only_keys_the_code_or_the_create_playbook_reads():
    contract = scaffold_contract.load_scaffold_contract(REPO_ROOT)
    assert set(contract) <= {"version", "description", "root_hub", "directories", "files", "json_requirements"}
    for entry in scaffold_contract.file_entries(contract, include_root_hub=True):
        assert set(entry) <= FILE_ENTRY_KEYS, entry
    for entry in scaffold_contract.directory_entries(contract):
        assert set(entry) <= {"path", "source", "create", "required"}, entry


def test_create_playbook_reads_the_create_flag():
    text = (REPO_ROOT / "invocations" / "grm" / "create_grimoire.md").read_text(encoding="utf-8")
    assert "`create: true`" in text


def test_contract_that_is_not_utf8_is_reported_as_a_contract_error(tmp_path):
    path = tmp_path / scaffold_contract.CONTRACT_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"description": "caf\xe9"}')
    with pytest.raises(scaffold_contract.ScaffoldContractError):
        scaffold_contract.load_scaffold_contract(tmp_path)
