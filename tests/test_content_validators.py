"""Tests for the content validators: links, orphans, provenance,
frontmatter, encoding, portability and doc trees.

Each test builds a small grimoire from the good fixture, adds the page that
shows one defect, and runs the validator as a subprocess in `--format json`.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES = REPO_ROOT / "rites"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"

PAGE = (
    "---\ntype: concept\ntitle: \"{title}\"\ntags: [chapter/recipes, type/concept]\n"
    "authority: grimoire\nlast_verified: 2026-11-10\n---\n\n# {title}\n\n{body}\n"
)


def run_validator(script: str, root: Path, env_extra: dict | None = None) -> dict:
    import os

    env = dict(os.environ)
    env.update(env_extra or {})
    result = subprocess.run(
        [sys.executable, str(RITES / script), "--grimoire", str(root), "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
    )
    return {
        "returncode": result.returncode,
        "report": json.loads(result.stdout),
        "stderr": result.stderr,
    }


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def page(root: Path, rel: str, body: str, title: str = "Probe", frontmatter: str | None = None) -> Path:
    text = frontmatter if frontmatter is not None else PAGE.format(title=title, body=body)
    return write(root, rel, text)


def link_to(root: Path, *names: str) -> None:
    """Append wikilinks to the chapter hub so the new pages are reachable."""
    hub = root / "chapters" / "recipes" / "recipes.md"
    lines = "".join(f"- [[chapters/recipes/{n}|{n}]]\n" for n in names)
    hub.write_text(hub.read_text(encoding="utf-8") + lines, encoding="utf-8", newline="\n")


def hits(out: dict, code: str) -> list:
    return [d for d in out["report"]["diagnostics"] if d["code"] == code]


def codes(out: dict) -> list:
    return [d["code"] for d in out["report"]["diagnostics"]]


@pytest.fixture
def grimoire(tmp_path):
    root = tmp_path / "good_grimoire"
    shutil.copytree(GOOD, root)
    return root


# ---------------------------------------------------------------------------
# validate_links
# ---------------------------------------------------------------------------


def test_links_page_that_is_not_utf8_is_reported_and_skipped(grimoire):
    (grimoire / "chapters" / "recipes" / "latin1.md").write_bytes(
        b"---\ntype: concept\n---\n\ncaf\xe9 [[chapters/recipes/nowhere|nowhere]]\n"
    )
    out = run_validator("validate_links.py", grimoire)

    assert out["returncode"] == 1
    assert [d["path"] for d in hits(out, "LINK_READ_ERROR")] == ["chapters/recipes/latin1.md"]
    assert hits(out, "LINK_WIKILINK_BROKEN") == []


def test_links_non_ascii_wikilink_resolves(grimoire):
    page(grimoire, "chapters/recipes/caf\u00e9.md", "Text.", title="Caf\u00e9")
    page(grimoire, "chapters/recipes/probe.md", "See [[chapters/recipes/caf\u00e9|caf\u00e9]].")
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_WIKILINK_BROKEN") == []
    assert hits(out, "LINK_READ_ERROR") == []


def test_links_target_with_a_template_word_is_checked_outside_formulae(grimoire):
    page(
        grimoire,
        "chapters/recipes/probe.md",
        "See [[chapters/recipes/Title_page|Title page]] and "
        "[[chapters/recipes/filename_rules|filename rules]].",
    )
    out = run_validator("validate_links.py", grimoire)

    assert [d["line"] for d in hits(out, "LINK_WIKILINK_BROKEN")] == [11, 11]


def test_links_placeholder_markers_are_skipped_everywhere(grimoire):
    page(grimoire, "chapters/recipes/probe.md", "See [[chapters/<chapter>/page|page]] and [x](docs/{name}.md).")
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_WIKILINK_BROKEN") == []
    assert hits(out, "LINK_MARKDOWN_BROKEN") == []


def test_links_template_words_stay_placeholders_under_formulae(grimoire):
    write(grimoire, "formulae/probe.formula.md", "See [[chapters/recipes/Title_page|Title]].\n")
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_WIKILINK_BROKEN") == []


def test_links_markdown_link_with_title_and_percent_encoding_resolves(grimoire):
    write(grimoire, "chapters/recipes/my file.txt", "x\n")
    readme = grimoire / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + '\nSee [hub](good_grimoire.md "The hub") and [x](chapters/recipes/my%20file.txt).\n',
        encoding="utf-8", newline="\n",
    )
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_MARKDOWN_BROKEN") == []
    assert out["returncode"] == 0


def test_links_broken_link_diagnostics_carry_the_line(grimoire):
    page(
        grimoire,
        "chapters/recipes/probe.md",
        "First line.\n\nSee [[chapters/recipes/nowhere|nowhere]] and "
        "[[chapters/recipes/sourdough|not the name]].\n\n[x](missing.txt)\n",
    )
    out = run_validator("validate_links.py", grimoire)

    assert [d["line"] for d in hits(out, "LINK_WIKILINK_BROKEN")] == [13]
    assert [d["line"] for d in hits(out, "LINK_LABEL_VERBOSE")] == [13]
    assert [d["line"] for d in hits(out, "LINK_MARKDOWN_BROKEN")] == [15]


def test_links_wikilink_in_indented_and_tilde_fences_is_not_reported(grimoire):
    page(
        grimoire,
        "chapters/recipes/probe.md",
        "1. Step one:\n\n   ```markdown\n   [[chapters/recipes/in_indented|x]]\n   ```\n\n"
        "~~~\n[[chapters/recipes/in_tilde|x]]\n~~~\n",
    )
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_WIKILINK_BROKEN") == []


def test_links_escaped_pipe_in_a_table_resolves(grimoire):
    page(
        grimoire,
        "chapters/recipes/probe.md",
        "| Page |\n|---|\n| [[chapters/recipes/sourdough\\|sourdough]] |",
    )
    out = run_validator("validate_links.py", grimoire)

    assert hits(out, "LINK_WIKILINK_BROKEN") == []
    assert hits(out, "LINK_LABEL_VERBOSE") == []


# ---------------------------------------------------------------------------
# validate_orphans
# ---------------------------------------------------------------------------


def test_orphans_page_that_links_only_to_itself_is_an_orphan(grimoire):
    page(grimoire, "chapters/recipes/lonely.md", "See [[chapters/recipes/lonely|lonely]].")
    out = run_validator("validate_orphans.py", grimoire)

    assert [d["path"] for d in hits(out, "ORPHAN_PAGE")] == ["chapters/recipes/lonely.md"]


def test_orphans_page_linked_by_another_page_is_reachable(grimoire):
    page(grimoire, "chapters/recipes/lonely.md", "Text.")
    link_to(grimoire, "lonely")
    out = run_validator("validate_orphans.py", grimoire)

    assert out["returncode"] == 0


def test_orphans_root_hub_follows_the_manifest_name_not_the_folder(tmp_path):
    clone = tmp_path / "cloned-checkout"
    shutil.copytree(GOOD, clone)
    out = run_validator("validate_orphans.py", clone)

    assert out["returncode"] == 0, out["report"]["diagnostics"]


@pytest.mark.parametrize("folder", [".grimoire", "grimoire", "checkout"])
def test_orphans_framework_hub_structure_passes_under_any_folder_name(tmp_path, folder):
    import re

    real_hub = (REPO_ROOT / "grimoire.md").read_text(encoding="utf-8")
    root = tmp_path / folder
    write(root, "framework.json", json.dumps({"name": "grimoire", "kind": "framework"}))
    write(root, "grimoire.md", real_hub)
    targets = {re.split(r"[|#]", m)[0] for m in re.findall(r"\[\[([^\]\n]+)\]\]", real_hub)}
    for target in targets:
        stub = root / (target if target.endswith(".md") else target + ".md")
        if not stub.exists():
            write(root, stub.relative_to(root).as_posix(), "---\ntype: reference\n---\n\nStub.\n")
    assert targets, "the framework hub links to no page"

    out = run_validator("validate_orphans.py", root)

    assert out["returncode"] == 0, out["report"]["diagnostics"]
    assert out["report"]["checked"]["pages"] == len(targets) + 1


def test_orphans_markdown_link_with_title_counts_in_a_public_document(grimoire):
    page(grimoire, "chapters/recipes/lonely.md", "Text.")
    readme = grimoire / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + '\n[lonely](chapters/recipes/lonely.md "Lonely")\n',
        encoding="utf-8", newline="\n",
    )
    out = run_validator("validate_orphans.py", grimoire)

    assert hits(out, "ORPHAN_PAGE") == []


def test_orphans_link_inside_indented_fence_does_not_count(grimoire):
    page(grimoire, "chapters/recipes/lonely.md", "Text.")
    page(grimoire, "chapters/recipes/probe.md", "1. Example:\n\n   ```\n   [[chapters/recipes/lonely|lonely]]\n   ```")
    link_to(grimoire, "probe")
    out = run_validator("validate_orphans.py", grimoire)

    assert [d["path"] for d in hits(out, "ORPHAN_PAGE")] == ["chapters/recipes/lonely.md"]


# ---------------------------------------------------------------------------
# validate_provenance
# ---------------------------------------------------------------------------


def external_page(root: Path, rel: str, sources_block: str, authority: str = "external") -> Path:
    return write(
        root,
        rel,
        "---\ntype: concept\ntitle: \"Ext\"\ntags: [chapter/recipes, type/concept]\n"
        f"authority: {authority}\nlast_verified: 2026-11-10\n{sources_block}---\n\n# Ext\n\nText.\n",
    )


def test_provenance_publish_citation_is_a_warning(grimoire):
    external_page(grimoire, "chapters/recipes/ext.md", 'sources: ["publish/site/index.html"]\n')
    out = run_validator("validate_provenance.py", grimoire)

    assert [d["severity"] for d in hits(out, "PROVENANCE_PUBLISH_SOURCE")] == ["warning"]
    assert out["returncode"] == 0


def test_provenance_entry_that_names_nothing_is_a_warning(grimoire):
    external_page(
        grimoire,
        "chapters/recipes/ext.md",
        'sources: ["chapters/recipes/source/typo.pdf", "notes/nowhere.txt"]\n',
    )
    out = run_validator("validate_provenance.py", grimoire)

    unresolved = hits(out, "PROVENANCE_SOURCE_UNRESOLVED")
    assert [d["severity"] for d in unresolved] == ["warning", "warning"]
    assert out["returncode"] == 0


def test_provenance_url_existing_path_and_local_source_are_clean(grimoire):
    write(grimoire, "chapters/recipes/sources/method.txt", "raw\n")
    external_page(
        grimoire,
        "chapters/recipes/ext.md",
        'sources: ["https://example.com/a", "chapters/recipes/sourdough.md", '
        '"chapters/recipes/sources/method.txt"]  # cited\n',
    )
    out = run_validator("validate_provenance.py", grimoire)

    assert out["report"]["diagnostics"] == []


def test_provenance_missing_local_source_is_still_an_error(grimoire):
    external_page(grimoire, "chapters/recipes/ext.md", 'sources: ["chapters/recipes/sources/gone.pdf"]\n')
    out = run_validator("validate_provenance.py", grimoire)

    assert out["returncode"] == 1
    assert len(hits(out, "PROVENANCE_SOURCE_MISSING")) == 1


def test_provenance_unindented_block_list_is_read(grimoire):
    external_page(
        grimoire,
        "chapters/recipes/ext.md",
        "sources:\n- https://example.com/a\n- chapters/recipes/sources/gone.pdf\n",
    )
    out = run_validator("validate_provenance.py", grimoire)

    assert hits(out, "PROVENANCE_MISSING_SOURCES") == []
    assert len(hits(out, "PROVENANCE_SOURCE_MISSING")) == 1


def test_provenance_scalar_sources_still_needs_a_list(grimoire):
    external_page(grimoire, "chapters/recipes/ext.md", "sources: https://example.com/a\n")
    out = run_validator("validate_provenance.py", grimoire)

    assert len(hits(out, "PROVENANCE_SOURCES_LIST_REQUIRED")) == 1


def test_provenance_wrapper_may_name_its_origin_in_words(grimoire):
    write(
        grimoire,
        "chapters/recipes/sources/chat.md",
        "---\ntype: source\ntitle: \"Chat\"\ntags: [type/source]\n"
        "sources: [\"Telegram chat export, 2026-11-01\"]\nauthority: external\n"
        "last_verified: 2026-11-10\n---\n\n# Chat\n",
    )
    out = run_validator("validate_provenance.py", grimoire)

    assert out["report"]["diagnostics"] == []
    assert out["report"]["checked"]["source_wrappers"] == 1


def test_provenance_page_that_is_not_utf8_is_reported(grimoire):
    (grimoire / "chapters" / "recipes" / "latin1.md").write_bytes(
        b"---\ntype: concept\nauthority: external\n---\n\ncaf\xe9\n"
    )
    out = run_validator("validate_provenance.py", grimoire)

    assert out["returncode"] == 1
    assert [d["path"] for d in hits(out, "PROVENANCE_READ_ERROR")] == ["chapters/recipes/latin1.md"]
    assert hits(out, "PROVENANCE_MISSING_SOURCES") == []


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


def test_frontmatter_list_valued_type_and_authority_are_reported_not_a_crash(grimoire):
    write(
        grimoire,
        "chapters/recipes/list_type.md",
        "---\ntype: [concept, entity]\ntitle: \"A\"\ntags: [x]\n---\n\n# A\n",
    )
    write(
        grimoire,
        "chapters/recipes/list_authority.md",
        "---\ntype: concept\ntitle: \"B\"\ntags: [x]\nauthority: [grimoire, external]\n"
        "last_verified: 2026-11-10\n---\n\n# B\n",
    )
    out = run_validator("validate_frontmatter.py", grimoire)

    assert out["returncode"] == 1
    assert [d["path"] for d in hits(out, "FRONTMATTER_INVALID_TYPE")] == ["chapters/recipes/list_type.md"]
    assert [d["path"] for d in hits(out, "FRONTMATTER_INVALID_AUTHORITY")] == [
        "chapters/recipes/list_authority.md"
    ]
    assert "Traceback" not in out["stderr"]


def test_frontmatter_unindented_block_lists_are_read(grimoire):
    write(
        grimoire,
        "chapters/recipes/block.md",
        "---\ntype: concept\ntitle: \"Block\"\ntags:\n- chapter/recipes\n- type/concept\n"
        "authority: external\nsources:\n- https://example.com/a\nlast_verified: 2026-11-10\n---\n\n# Block\n",
    )
    out = run_validator("validate_frontmatter.py", grimoire)

    assert hits(out, "FRONTMATTER_MISSING_REQUIRED") == []
    assert hits(out, "FRONTMATTER_MISSING_SOURCES") == []


def test_frontmatter_missing_source_file_is_reported_by_provenance_only(grimoire):
    external_page(grimoire, "chapters/recipes/ext.md", 'sources: ["chapters/recipes/sources/gone.pdf"]\n')

    assert "FRONTMATTER_SOURCE_MISSING" not in codes(run_validator("validate_frontmatter.py", grimoire))
    provenance = run_validator("validate_provenance.py", grimoire)
    assert provenance["returncode"] == 1
    assert len(hits(provenance, "PROVENANCE_SOURCE_MISSING")) == 1


def test_frontmatter_external_page_with_commented_empty_sources_is_flagged(grimoire):
    external_page(grimoire, "chapters/recipes/ext.md", "sources:  # none yet\n")
    out = run_validator("validate_frontmatter.py", grimoire)

    assert len(hits(out, "FRONTMATTER_MISSING_SOURCES")) == 1


def test_frontmatter_page_that_is_not_utf8_is_reported(grimoire):
    (grimoire / "chapters" / "recipes" / "latin1.md").write_bytes(
        b"---\ntype: concept\ntitle: \"caf\xe9\"\n---\n"
    )
    out = run_validator("validate_frontmatter.py", grimoire)

    assert [d["path"] for d in hits(out, "FRONTMATTER_READ_ERROR")] == ["chapters/recipes/latin1.md"]


# ---------------------------------------------------------------------------
# validate_encoding
# ---------------------------------------------------------------------------


def test_encoding_valid_french_text_is_not_mojibake(grimoire):
    page(
        grimoire,
        "chapters/recipes/french.md",
        "Du p\u00e2t\u00e9 et un ch\u00e2teau. \u00c2 la carte, \u00c3 bient\u00f4t. "
        "S\u00c3O PAULO et A\u00c7\u00c3O.",
    )
    out = run_validator("validate_encoding.py", grimoire)

    assert out["report"]["diagnostics"] == []


def test_encoding_url_query_is_not_a_repair_artifact(grimoire):
    page(
        grimoire,
        "chapters/recipes/urls.md",
        "See https://example.com/item/12?3 and example.com/list/4?5 and "
        "[x](https://example.com/p?id=7&n=8).",
    )
    out = run_validator("validate_encoding.py", grimoire)

    assert out["report"]["diagnostics"] == []


def test_encoding_numeric_range_artifact_is_still_caught(grimoire):
    page(grimoire, "chapters/recipes/range.md", "Bake 10" + "?20 minutes.")
    out = run_validator("validate_encoding.py", grimoire)

    assert [d["code"] for d in out["report"]["diagnostics"]] == ["ENCODING_REPAIR_ARTIFACT"]


@pytest.mark.parametrize(
    "text",
    [
        "caf\u00c3\u00a9",
        "dash \u00e2\u20ac\u201d dash",
        "dash \u00e2\u0080\u0094 dash",
        "copyright \u00c2\u00a9",
        "lost \ufffd byte",
    ],
)
def test_encoding_real_mojibake_is_still_caught(grimoire, text):
    page(grimoire, "chapters/recipes/moji.md", text)
    out = run_validator("validate_encoding.py", grimoire)

    assert [d["code"] for d in out["report"]["diagnostics"]] == ["ENCODING_MOJIBAKE"]


def test_encoding_checks_a_publish_folder_below_the_root(grimoire):
    (grimoire / "formulae" / "publish").mkdir(parents=True)
    (grimoire / "formulae" / "publish" / "note.md").write_bytes(b"line\r\n")
    (grimoire / "publish" / "site.md").write_bytes(b"line\r\n")
    out = run_validator("validate_encoding.py", grimoire)

    assert [d["path"] for d in hits(out, "ENCODING_CRLF")] == ["formulae/publish/note.md"]


# ---------------------------------------------------------------------------
# validate_portability
# ---------------------------------------------------------------------------


def codes_of(findings):
    return [code for code, _issue, _path in findings]


def test_portability_directory_case_collision_is_one_error():
    import validate_portability

    findings = validate_portability.check_paths(
        [("Notes", "a.md"), ("Notes", "b.md"), ("notes", "c.md"), ("other", "d.md")]
    )

    assert codes_of(findings) == ["PORTABILITY_CASE_COLLISION"]
    assert findings[0][2] == "."
    assert "Notes, notes" in findings[0][1]


def test_portability_file_case_collision_in_a_subfolder_is_reported_once():
    import validate_portability

    findings = validate_portability.check_paths(
        [("chapters", "Sourdough.md"), ("chapters", "sourdough.md"), ("chapters", "x.md")]
    )

    assert [(c, p) for c, _i, p in findings] == [("PORTABILITY_CASE_COLLISION", "chapters")]


def test_portability_reserved_folder_name_is_reported_once_not_per_file():
    import validate_portability

    findings = validate_portability.check_paths(
        [("aux", "a.md"), ("aux", "b.md"), ("aux", "sub", "c.md")]
    )

    assert [(c, p) for c, _i, p in findings] == [("PORTABILITY_RESERVED_BASENAME", "aux")]


def test_portability_reserved_file_and_trailing_dot_keep_the_file_path():
    import validate_portability

    findings = validate_portability.check_paths([("docs", "nul.md"), ("docs", "name.")])

    assert sorted((c, p) for c, _i, p in findings) == [
        ("PORTABILITY_RESERVED_BASENAME", "docs/nul.md"),
        ("PORTABILITY_TRAILING_DOT_SPACE", "docs/name."),
    ]


def test_portability_case_colliding_folders_on_disk(tmp_path):
    root = tmp_path / "g"
    (root / "Notes").mkdir(parents=True)
    (root / "notes").mkdir(exist_ok=True)
    if len({p.name for p in root.iterdir()}) < 2:
        pytest.skip("this filesystem ignores case, so the two folders cannot coexist")
    write(root, "Notes/a.md", "x\n")
    write(root, "notes/b.md", "x\n")
    out = run_validator("validate_portability.py", root)

    assert out["returncode"] == 1
    assert [d["code"] for d in out["report"]["diagnostics"]] == ["PORTABILITY_CASE_COLLISION"]


# ---------------------------------------------------------------------------
# validate_doc_trees
# ---------------------------------------------------------------------------

TREE_TOP = "├──"
TREE_LAST = "└──"
TREE_BAR = "│"


def diagram(root: Path, rel: str, text: str, fence: str = "```") -> Path:
    return write(root, rel, f"# Layout\n\n{fence}\n{text}\n{fence}\n")


def test_doc_trees_slashless_directories_from_tree_output(grimoire):
    diagram(
        grimoire,
        "chapters/recipes/layout.md",
        "chapters\n"
        f"{TREE_LAST} recipes\n"
        f"    {TREE_TOP} recipes.md\n"
        f"    {TREE_LAST} sourdough.md",
    )
    out = run_validator("validate_doc_trees.py", grimoire)

    assert out["report"]["checked"]["validated"] == 1
    assert out["report"]["diagnostics"] == []


def test_doc_trees_slashless_directory_children_attach_to_their_parent(grimoire):
    diagram(
        grimoire,
        "chapters/recipes/layout.md",
        "chapters\n"
        f"{TREE_LAST} recipes\n"
        f"    {TREE_TOP} recipes.md\n"
        f"    {TREE_LAST} nowhere.md",
    )
    out = run_validator("validate_doc_trees.py", grimoire)

    missing = hits(out, "DOC_TREE_MISSING_ENTRY")
    assert [d["message"].split("`")[1] for d in missing] == ["recipes/nowhere.md"]


@pytest.mark.parametrize("folder", [".grimoire", "grimoire", "checkout"])
def test_doc_trees_anchor_does_not_depend_on_the_root_folder_name(tmp_path, folder):
    root = tmp_path / folder
    write(root, "framework.json", json.dumps({"name": "grimoire", "kind": "framework"}))
    write(root, "grimoire.md", "# Hub\n")
    write(root, "docs/a.md", "# A\n")
    write(root, "rites/b.py", "x = 1\n")
    write(root, "plugins/grimoire/readme.txt", "x\n")
    diagram(
        root,
        "docs/layout.md",
        f"grimoire/\n{TREE_TOP} docs/\n{TREE_TOP} rites/\n{TREE_LAST} ...",
    )
    out = run_validator("validate_doc_trees.py", root)

    assert out["report"]["checked"]["validated"] == 1
    assert out["report"]["diagnostics"] == []


def test_doc_trees_single_name_anchor_ignores_pruned_folders(grimoire):
    write(grimoire, "publish/site/assets/logo.txt", "x\n")
    diagram(
        grimoire,
        "chapters/recipes/layout.md",
        f"assets/\n{TREE_LAST} missing.png",
    )
    out = run_validator("validate_doc_trees.py", grimoire)

    assert out["report"]["checked"]["validated"] == 0
    assert out["report"]["diagnostics"] == []


def test_doc_trees_dot_prefixed_anchor_keeps_its_dot(grimoire):
    write(grimoire, ".github/workflows/ci.yml", "x\n")
    diagram(
        grimoire,
        "chapters/recipes/layout.md",
        f".github/workflows/\n{TREE_TOP} ci.yml\n{TREE_LAST} release.yml",
    )
    out = run_validator("validate_doc_trees.py", grimoire)

    assert out["report"]["checked"]["validated"] == 1
    assert [d["message"].split("`")[1] for d in hits(out, "DOC_TREE_MISSING_ENTRY")] == ["release.yml"]


@pytest.mark.parametrize("fence", ["~~~", "   ```"])
def test_doc_trees_reads_tilde_and_indented_fences(grimoire, fence):
    diagram(
        grimoire,
        "chapters/recipes/layout.md",
        f"chapters/\n{TREE_LAST} nowhere/",
        fence=fence,
    )
    out = run_validator("validate_doc_trees.py", grimoire)

    assert len(hits(out, "DOC_TREE_MISSING_ENTRY")) == 1


def test_doc_trees_document_that_is_not_utf8_is_reported(grimoire):
    (grimoire / "chapters" / "recipes" / "latin1.md").write_bytes(b"caf\xe9\n")
    out = run_validator("validate_doc_trees.py", grimoire)

    assert out["returncode"] == 1
    assert [d["path"] for d in hits(out, "DOC_TREE_PARSE_FAILED")] == ["chapters/recipes/latin1.md"]


def test_doc_trees_missing_root_exits_2(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RITES / "validate_doc_trees.py"), "--grimoire", str(tmp_path / "nope")],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 2
    assert "nope" in result.stderr


# ---------------------------------------------------------------------------
# All seven validators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script",
    [
        "validate_links.py",
        "validate_orphans.py",
        "validate_provenance.py",
        "validate_frontmatter.py",
        "validate_encoding.py",
        "validate_portability.py",
        "validate_doc_trees.py",
    ],
)
def test_missing_grimoire_path_exits_2_and_names_the_path(tmp_path, script):
    result = subprocess.run(
        [sys.executable, str(RITES / script), "--grimoire", str(tmp_path / "nope"), "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )

    assert result.returncode == 2
    assert "nope" in result.stderr
    assert result.stdout == ""
