"""Unit tests for rites/_lib.py, the shared library, and its use by rites/diagnostics.py."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import _lib
import diagnostics

RITES = Path(__file__).resolve().parent.parent / "rites"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _set_home(monkeypatch, home: Path) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))


# ---------------------------------------------------------------------------
# Text and JSON I/O
# ---------------------------------------------------------------------------


def test_read_utf8_returns_non_ascii_text(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes("café 日本\r\nsecond\n".encode("utf-8"))
    assert _lib.read_utf8(page) == "café 日本\nsecond\n"


def test_read_utf8_raises_instead_of_substituting(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes("café".encode("cp1252"))
    with pytest.raises(UnicodeDecodeError):
        _lib.read_utf8(page)


def test_write_utf8_writes_lf_and_creates_parents(tmp_path):
    page = tmp_path / "chapters" / "new" / "日本.md"
    _lib.write_utf8(page, "one\r\ntwo\n日本\n")
    assert page.read_bytes() == "one\ntwo\n日本\n".encode("utf-8")


def test_write_utf8_failure_leaves_original_and_no_temporary(tmp_path, monkeypatch):
    page = tmp_path / "page.md"
    page.write_bytes(b"original\n")

    def refuse(src, dst):
        raise PermissionError("file is in use")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(PermissionError):
        _lib.write_utf8(page, "replacement\n")
    assert page.read_bytes() == b"original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["page.md"]


def test_write_utf8_unencodable_text_leaves_original(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes(b"original\n")
    with pytest.raises(UnicodeEncodeError):
        _lib.write_utf8(page, "lone surrogate \ud800\n")
    assert page.read_bytes() == b"original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["page.md"]


def test_write_json_keeps_non_ascii_and_ends_with_newline(tmp_path):
    target = tmp_path / "library.json"
    _lib.write_json(target, {"grimoires": {"travel": {"description": "日本の旅"}}})
    raw = target.read_bytes()
    assert raw.endswith(b"}\n") and b"\r" not in raw
    assert "日本の旅" in raw.decode("utf-8")
    assert raw.decode("utf-8").splitlines()[1] == '  "grimoires": {'
    assert json.loads(raw) == {"grimoires": {"travel": {"description": "日本の旅"}}}


def test_importing_diagnostics_lets_a_rite_print_non_ascii(tmp_path):
    script = tmp_path / "print_path.py"
    script.write_text("import diagnostics\nprint('\\u65e5\\u672c')\n", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(RITES))
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, env=env)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout.decode("utf-8").strip() == "日本"


def test_ensure_utf8_stdio_ignores_a_stream_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", object())
    _lib.ensure_utf8_stdio()


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_returns_empty_dict_when_no_frontmatter():
    assert _lib.parse_frontmatter("# heading only\n\nbody") == {}


def test_parse_frontmatter_extracts_simple_scalars():
    text = '---\ntype: hub\ntitle: "Hello"\n---\n\nbody'
    fm = _lib.parse_frontmatter(text)
    assert fm["type"] == "hub"
    assert fm["title"] == "Hello"


def test_parse_frontmatter_inline_list():
    text = "---\ntype: hub\ntags: [a, b, c]\n---\n\nbody"
    fm = _lib.parse_frontmatter(text)
    assert fm["tags"] == ["a", "b", "c"]


def test_parse_frontmatter_multiline_list():
    text = "---\ntype: hub\naliases:\n  - one\n  - two\n  - three\n---\n\nbody"
    fm = _lib.parse_frontmatter(text)
    assert fm["aliases"] == ["one", "two", "three"]


def test_parse_frontmatter_block_list_without_indentation():
    text = "---\ntype: concept\ntags:\n- a\n- b\nsources:\n- chapters/x/sources/a.pdf\ntitle: T\n---\n\nbody"
    fm = _lib.parse_frontmatter(text)
    assert fm["tags"] == ["a", "b"]
    assert fm["sources"] == ["chapters/x/sources/a.pdf"]
    assert fm["title"] == "T"


def test_parse_frontmatter_handles_empty_inline_list():
    text = "---\ntype: hub\naliases: []\n---\n\nbody"
    assert _lib.parse_frontmatter(text)["aliases"] == []


def test_parse_frontmatter_strips_quotes():
    text = "---\ntype: 'hub'\ntitle: \"quoted\"\n---\n\nbody"
    fm = _lib.parse_frontmatter(text)
    assert fm["type"] == "hub"
    assert fm["title"] == "quoted"


# ---------------------------------------------------------------------------
# frontmatter_bounds, page_type, frontmatter_sources, page constants
# ---------------------------------------------------------------------------


def test_frontmatter_bounds_are_the_offsets_of_the_body():
    text = "---\ntype: hub\ntitle: T\n---\n\n# Body\n"
    start, end = _lib.frontmatter_bounds(text)
    assert text[start:end] == "type: hub\ntitle: T"
    assert text[end + 1:].startswith("---\n")


def test_frontmatter_bounds_is_none_without_frontmatter():
    assert _lib.frontmatter_bounds("# Body\n\n---\nnot: frontmatter\n---\n") is None


def test_page_type_reads_the_frontmatter_type():
    assert _lib.page_type("---\ntype: playbook\ntitle: T\n---\nbody") == "playbook"
    assert _lib.page_type("# no frontmatter\n") == ""
    assert _lib.page_type("---\ntitle: T\n---\nbody") == ""
    assert _lib.page_type("---\ntype: [hub, concept]\n---\nbody") == ""


def test_page_types_and_authorities_are_the_schema_values():
    assert _lib.PAGE_TYPES == ("hub", "concept", "entity", "source", "playbook", "reference")
    assert _lib.PAGE_AUTHORITIES == ("external", "grimoire", "hybrid")


def _page(frontmatter: str) -> str:
    return f"---\ntype: concept\n{frontmatter}\ntitle: T\n---\n\nbody [x](y.md)\n"


@pytest.mark.parametrize(
    "frontmatter, expected",
    [
        ('sources: ["chapters/x/sources/a.pdf", \'chapters/x/sources/b.pdf\']',
         ["chapters/x/sources/a.pdf", "chapters/x/sources/b.pdf"]),
        ("sources: [chapters/x/sources/a.pdf, https://example.com/a]",
         ["chapters/x/sources/a.pdf", "https://example.com/a"]),
        ("sources: [chapters/x/sources/a.pdf]  # the receipt",
         ["chapters/x/sources/a.pdf"]),
        ("sources: [\n  chapters/x/sources/a.pdf,\n  \"chapters/x/sources/b, c.pdf\"\n]",
         ["chapters/x/sources/a.pdf", "chapters/x/sources/b, c.pdf"]),
        ("sources:\n  - chapters/x/sources/a.pdf\n  - \"chapters/x/sources/b.pdf\"",
         ["chapters/x/sources/a.pdf", "chapters/x/sources/b.pdf"]),
        ("sources:\n- chapters/x/sources/a.pdf\n- chapters/x/sources/b.pdf",
         ["chapters/x/sources/a.pdf", "chapters/x/sources/b.pdf"]),
        ("sources:\n  - chapters/x/sources/a.pdf # scanned 2026\n  # a note\n  - 'chapters/x/sources/b.pdf' # second",
         ["chapters/x/sources/a.pdf", "chapters/x/sources/b.pdf"]),
        ("sources: chapters/x/sources/a.pdf", ["chapters/x/sources/a.pdf"]),
        ("sources: chapters/x/sources/a.pdf # only one", ["chapters/x/sources/a.pdf"]),
        ('sources: "chapters/x/sources/a #1.pdf"', ["chapters/x/sources/a #1.pdf"]),
        ("sources: https://example.com/page#section", ["https://example.com/page#section"]),
        ("sources: [chapters/x/sources/bob's notes.pdf]", ["chapters/x/sources/bob's notes.pdf"]),
        ("sources: []", []),
        ("sources:", []),
        ("tags: [a]", []),
    ],
)
def test_frontmatter_sources_reads_every_form(frontmatter, expected):
    assert _lib.frontmatter_sources(_page(frontmatter)) == expected


def test_frontmatter_sources_is_empty_without_frontmatter():
    assert _lib.frontmatter_sources("sources: chapters/x/sources/a.pdf\n") == []


# ---------------------------------------------------------------------------
# Code fences: FENCE_RE, strip_code_blocks, mask_code
# ---------------------------------------------------------------------------


def test_fence_regex_matches_indented_and_tilde_fences():
    assert _lib.FENCE_RE.match("```python")
    assert _lib.FENCE_RE.match("   ```")
    assert _lib.FENCE_RE.match("~~~")
    assert not _lib.FENCE_RE.match("text ```")
    assert _lib.CODE_FENCE_RE is _lib.FENCE_RE


def test_strip_code_blocks_removes_fenced_content():
    text = "before\n```\n[fake](link.md)\n```\nafter"
    cleaned = _lib.strip_code_blocks(text)
    assert "[fake]" not in cleaned
    assert "before" in cleaned and "after" in cleaned


def test_strip_code_blocks_removes_inline_backticks():
    text = "live link [real](real.md) and `[fake](fake.md)` end"
    cleaned = _lib.strip_code_blocks(text)
    assert "[real]" in cleaned
    assert "[fake]" not in cleaned


def test_strip_code_blocks_preserves_line_count():
    text = "a\n```\nb\nc\n```\nd"
    assert len(_lib.strip_code_blocks(text).splitlines()) == len(text.splitlines())


def test_strip_code_blocks_recognises_indented_and_tilde_fences():
    text = (
        "- step\n"
        "  ```\n"
        "  [[chapters/fake/indented]]\n"
        "  ```\n"
        "~~~\n"
        "[[chapters/fake/tilde]]\n"
        "~~~\n"
        "[[chapters/real/page]]\n"
    )
    cleaned = _lib.strip_code_blocks(text)
    assert "fake" not in cleaned
    assert "[[chapters/real/page]]" in cleaned


def test_strip_code_blocks_closes_a_fence_only_with_its_own_marker():
    text = (
        "```\n"
        "~~~\n"
        "[[chapters/fake/in_backticks]]\n"
        "```\n"
        "[[chapters/real/between]]\n"
        "~~~\n"
        "```\n"
        "[[chapters/fake/in_tildes]]\n"
        "~~~\n"
        "[[chapters/real/after]]\n"
    )
    cleaned = _lib.strip_code_blocks(text)
    assert "fake" not in cleaned
    assert "[[chapters/real/between]]" in cleaned
    assert "[[chapters/real/after]]" in cleaned


def test_strip_code_blocks_keeps_a_short_fence_inside_a_longer_one_as_code():
    text = (
        "````markdown\n"
        "```\n"
        "[[chapters/fake/nested]]\n"
        "```\n"
        "[[chapters/fake/still_code]]\n"
        "````\n"
        "[[chapters/real/after]]\n"
    )
    cleaned = _lib.strip_code_blocks(text)
    assert "fake" not in cleaned
    assert "[[chapters/real/after]]" in cleaned


def test_strip_code_blocks_masks_double_backtick_spans():
    cleaned = _lib.strip_code_blocks("a ``[[chapters/fake/x]] ` tick`` and [[chapters/real/y]]")
    assert "fake" not in cleaned
    assert "[[chapters/real/y]]" in cleaned


def test_mask_code_keeps_length_and_offsets():
    text = (
        "see [[chapters/a/one]] and `[[chapters/a/code]]`\r\n"
        "  ~~~text\n"
        "  [[chapters/a/fenced]]\n"
        "  ~~~\n"
        "then [[chapters/a/two|Two]]\n"
    )
    masked = _lib.mask_code(text)
    assert len(masked) == len(text)
    assert [i for i, c in enumerate(masked) if c == "\n"] == [i for i, c in enumerate(text) if c == "\n"]
    found = [(m.start(), m.group(1)) for m in _lib.WIKILINK_RE.finditer(masked)]
    assert [target for _start, target in found] == ["chapters/a/one", "chapters/a/two|Two"]
    for start, target in found:
        assert text[start:start + len(target) + 4] == f"[[{target}]]"


def test_mask_code_edit_at_masked_offsets_leaves_code_untouched():
    text = "`[[old]]` then [[old]]\n```\n[[old]]\n```\n"
    masked = _lib.mask_code(text)
    edited = text
    for match in reversed(list(_lib.WIKILINK_RE.finditer(masked))):
        edited = edited[:match.start()] + "[[new]]" + edited[match.end():]
    assert edited == "`[[old]]` then [[new]]\n```\n[[old]]\n```\n"


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def test_wikilink_target_body_drops_label_section_and_escaped_pipe():
    assert _lib.wikilink_target_body("page|Label") == "page"
    assert _lib.wikilink_target_body("chapters/places/places#Routes|Places") == "chapters/places/places"
    assert _lib.wikilink_target_body("chapters/recipes/sourdough\\|sourdough") == "chapters/recipes/sourdough"
    assert _lib.wikilink_target_body("chapters/recipes/sourdough#Starter\\|sourdough") == "chapters/recipes/sourdough"


def test_rebuild_wikilink_keeps_section_and_label():
    assert _lib.rebuild_wikilink("sourdough#Starter", "chapters/recipes/sourdough") == "chapters/recipes/sourdough#Starter"
    assert _lib.rebuild_wikilink("old/page#Sec|Shown", "new/page") == "new/page#Sec|Shown"
    assert _lib.rebuild_wikilink("old/page", "new/page") == "new/page"


def test_rebuild_wikilink_label_argument_replaces_or_drops_the_label():
    assert _lib.rebuild_wikilink("old/page|Shown", "new/page", label="page") == "new/page|page"
    assert _lib.rebuild_wikilink("old/page#Sec", "new/page", label="page") == "new/page#Sec|page"
    assert _lib.rebuild_wikilink("old/page|Shown", "new/page", label="") == "new/page"


def test_rebuild_wikilink_keeps_a_table_escaped_pipe():
    rebuilt = _lib.rebuild_wikilink("old/page\\|Shown", "new/page")
    assert rebuilt == "new/page\\|Shown"
    assert _lib.wikilink_target_body(rebuilt) == "new/page"
    assert _lib.rebuild_wikilink("old/page#Sec\\|Shown", "new/page", label="X") == "new/page#Sec\\|X"


def test_resolve_wikilink_path_appends_md_to_multi_dot_names(tmp_path):
    root = tmp_path.resolve()
    (root / "chapters").mkdir()
    (root / "chapters" / "plugin_ICD.template.md").write_text("x\n", encoding="utf-8")
    (root / "chapters" / "notes.txt").write_text("x\n", encoding="utf-8")
    expected = root / "chapters" / "plugin_ICD.template.md"
    assert _lib.resolve_wikilink_path("chapters/plugin_ICD.template", root) == expected
    assert _lib.resolve_wikilink_path("chapters/plugin_ICD.template.md", root) == expected
    assert _lib.resolve_wikilink_path("chapters/notes.txt", root) is None
    assert _lib.resolve_wikilink_path("../outside", root) is None


def test_markdown_link_path_strips_title_brackets_anchor_and_query():
    assert _lib.markdown_link_path('good_grimoire.md "The hub"') == "good_grimoire.md"
    assert _lib.markdown_link_path("page.md 'Title'") == "page.md"
    assert _lib.markdown_link_path("<chapters/my file.md>") == "chapters/my file.md"
    assert _lib.markdown_link_path('<chapters/my file.md> "Title"') == "chapters/my file.md"
    assert _lib.markdown_link_path("docs/page.md#section") == "docs/page.md"
    assert _lib.markdown_link_path("docs/page.md?plain=1#L10") == "docs/page.md"
    assert _lib.markdown_link_path("#section") == ""


def test_markdown_link_path_decodes_percent_encoding():
    assert _lib.markdown_link_path("chapters/recipes/my%20file.md") == "chapters/recipes/my file.md"
    assert _lib.markdown_link_path("chapters/%E6%97%A5%E6%9C%AC.md#top") == "chapters/日本.md"
    assert _lib.markdown_link_path("chapters/issue%231.md") == "chapters/issue#1.md"


def test_is_external_url_distinguishes_urls_from_paths():
    assert _lib.is_external_url("https://example.com/a")
    assert _lib.is_external_url("mailto:someone@example.com")
    assert _lib.is_external_url("obsidian://open?vault=x")
    assert _lib.is_external_url("//cdn.example.com/a.png")
    assert not _lib.is_external_url("chapters/recipes/sourdough.md")
    assert not _lib.is_external_url("/chapters/recipes/sourdough.md")
    assert not _lib.is_external_url("../docs/page.md")
    assert not _lib.is_external_url("C:/notes/page.md")


def test_placeholder_markers_match_on_any_page():
    assert _lib.is_placeholder_target("chapters/{chapter}/page", in_formula=False)
    assert _lib.is_placeholder_target("chapters/<chapter>/page", in_formula=False)


def test_placeholder_prose_tokens_match_only_in_a_formula():
    for target in ("chapters/recipes/Title_page", "chapters/recipes/filename_rules", "FRAMEWORK_HOME/docs/x"):
        assert _lib.is_placeholder_target(target, in_formula=True)
        assert not _lib.is_placeholder_target(target, in_formula=False)
    assert not _lib.is_placeholder_target("chapters/recipes/sourdough", in_formula=True)


def test_placeholder_tokens_hold_the_markers_and_the_prose_tokens():
    assert _lib.PLACEHOLDER_TOKENS == _lib.PLACEHOLDER_MARKERS + _lib.PLACEHOLDER_PROSE_TOKENS
    assert _lib.PLACEHOLDER_MARKERS == ("{", "<")
    assert "Title" in _lib.PLACEHOLDER_PROSE_TOKENS and "{" not in _lib.PLACEHOLDER_PROSE_TOKENS


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


def test_load_manifest_reads_good_fixture():
    metadata, errors = _lib.load_manifest(GOOD)
    assert errors == []
    assert metadata["name"] == "good_grimoire"
    assert metadata["skill_prefix"] == "good"


def test_load_manifest_returns_none_when_missing(tmp_path):
    metadata, errors = _lib.load_manifest(tmp_path)
    assert metadata is None
    assert errors == ["missing grimoire.json"]


def test_load_manifest_flags_invalid_skill_prefix(tmp_path):
    (tmp_path / "grimoire.json").write_text(
        '{"name": "x", "skill_prefix": "BAD-NS"}'
    )
    metadata, errors = _lib.load_manifest(tmp_path)
    assert metadata is not None
    assert any("invalid skill_prefix" in e for e in errors)


def test_load_manifest_handles_permission_error(tmp_path, monkeypatch):
    # An unstattable grimoire.json must degrade to an error, not raise, so a
    # restricted directory under the grimoire home cannot crash a scan.
    restricted = tmp_path / "restricted"
    restricted.mkdir()
    real_is_file = Path.is_file

    def fake_is_file(self):
        if self.name == "grimoire.json":
            raise PermissionError("[Errno 13] Permission denied")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    metadata, errors = _lib.load_manifest(restricted)
    assert metadata is None
    assert errors and "could not access" in errors[0]


def test_load_manifest_reads_non_ascii_as_utf8(tmp_path):
    (tmp_path / "grimoire.json").write_bytes(
        '{"name": "café", "skill_prefix": "cafe", "description": "Água e 日本"}'.encode("utf-8")
    )
    metadata, errors = _lib.load_manifest(tmp_path)
    assert errors == []
    assert metadata["name"] == "café"
    assert metadata["description"] == "Água e 日本"


def test_load_manifest_reports_a_file_that_is_not_utf8(tmp_path):
    (tmp_path / "grimoire.json").write_bytes(
        '{"name": "café", "skill_prefix": "cafe"}'.encode("cp1252")
    )
    metadata, errors = _lib.load_manifest(tmp_path)
    assert metadata is None
    assert len(errors) == 1 and "UTF-8" in errors[0]


@pytest.mark.parametrize("content", ["[]", '"text"', "5", "null"])
def test_load_manifest_rejects_a_value_that_is_not_an_object(tmp_path, content):
    (tmp_path / "grimoire.json").write_text(content, encoding="utf-8")
    metadata, errors = _lib.load_manifest(tmp_path)
    assert metadata is None
    assert len(errors) == 1 and "JSON object" in errors[0]


@pytest.mark.parametrize("field", ["name", "skill_prefix", "description", "naming"])
def test_load_manifest_reports_a_field_that_is_not_a_string(tmp_path, field):
    manifest = {"name": "x", "skill_prefix": "x", "description": "d", "naming": "snake_case"}
    manifest[field] = 5
    (tmp_path / "grimoire.json").write_text(json.dumps(manifest), encoding="utf-8")
    metadata, errors = _lib.load_manifest(tmp_path)
    assert metadata == manifest
    assert len(errors) == 1 and f"'{field}'" in errors[0]


# ---------------------------------------------------------------------------
# read_library / load_library
# ---------------------------------------------------------------------------


def test_load_library_returns_empty_when_missing(tmp_path):
    assert _lib.load_library(tmp_path / "missing.json") == {"grimoires": {}}


def test_load_library_normalizes_missing_grimoires_key(tmp_path):
    p = tmp_path / "library.json"
    p.write_text("{}")
    assert _lib.load_library(p) == {"grimoires": {}}


def test_read_library_reports_an_absent_file_as_an_empty_library(tmp_path):
    assert _lib.read_library(tmp_path / "library.json") == ({"grimoires": {}}, "")


def test_read_library_returns_a_valid_library_with_non_ascii(tmp_path):
    p = tmp_path / "library.json"
    library = {"grimoires": {"travel": {"local_path": "$HOME/grimoires/travel", "description": "日本"}}, "extra": 1}
    p.write_bytes(json.dumps(library, ensure_ascii=False).encode("utf-8"))
    assert _lib.read_library(p) == (library, "")
    assert _lib.load_library(p) == library


@pytest.mark.parametrize(
    "raw",
    [
        b'{"grimoires": {"a": {}},}',
        b"[]",
        b'{"grimoires": []}',
        '{"grimoires": {"café": {}}}'.encode("cp1252"),
    ],
    ids=["trailing-comma", "list", "grimoires-not-object", "not-utf8"],
)
def test_read_library_tells_an_unusable_file_from_an_absent_one(tmp_path, raw, capsys):
    p = tmp_path / "library.json"
    p.write_bytes(raw)
    library, reason = _lib.read_library(p)
    assert library is None
    assert "library.json" in reason
    assert _lib.load_library(p) == {"grimoires": {}}
    assert "[WARN]" in capsys.readouterr().out
    assert p.read_bytes() == raw


# ---------------------------------------------------------------------------
# local_path: resolve, usable, format
# ---------------------------------------------------------------------------


def test_format_local_path_round_trips_through_resolve(tmp_path, monkeypatch):
    home = tmp_path / "a"
    _set_home(monkeypatch, home)
    folder = home / "grimoires" / "travel-grimoire"
    written = _lib.format_local_path(folder)
    assert written == "$HOME/grimoires/travel-grimoire"
    assert _lib.resolve_local_path(written) == folder
    assert _lib.format_local_path(home) == "$HOME"
    assert _lib.resolve_local_path("$HOME") == home


def test_format_local_path_does_not_match_a_home_that_is_a_string_prefix(tmp_path, monkeypatch):
    home = tmp_path / "a"
    _set_home(monkeypatch, home)
    sibling = tmp_path / "ab" / "grimoires" / "travel-grimoire"
    written = _lib.format_local_path(sibling)
    assert written == sibling.as_posix()
    assert "$HOME" not in written and "\\" not in written
    assert _lib.resolve_local_path(written) == sibling


def test_resolve_local_path_reads_the_backslash_home_form(tmp_path, monkeypatch):
    home = tmp_path / "a"
    _set_home(monkeypatch, home)
    assert _lib.resolve_local_path("$HOME\\grimoires\\travel-grimoire") == home / "grimoires" / "travel-grimoire"
    assert _lib.resolve_local_path("$HOME/grimoires/travel-grimoire", resolve=True) == (
        home / "grimoires" / "travel-grimoire"
    ).resolve()


def test_is_usable_local_path_rejects_empty_and_relative(tmp_path):
    assert not _lib.is_usable_local_path("")
    assert not _lib.is_usable_local_path("   ")
    assert not _lib.is_usable_local_path("grimoires/travel-grimoire")
    assert not _lib.is_usable_local_path("./travel-grimoire")
    assert not _lib.is_usable_local_path(None)
    assert _lib.is_usable_local_path("$HOME/grimoires/travel-grimoire")
    assert _lib.is_usable_local_path("$HOME\\grimoires\\travel-grimoire")
    assert _lib.is_usable_local_path("~/grimoires/travel-grimoire")
    assert _lib.is_usable_local_path(str(tmp_path))


# ---------------------------------------------------------------------------
# Root hub and hub predicate
# ---------------------------------------------------------------------------


def _write_manifest(root: Path, name: str) -> None:
    (root / "grimoire.json").write_text(
        json.dumps({"name": name, "skill_prefix": "x"}), encoding="utf-8"
    )


def test_root_hub_uses_the_manifest_name_in_a_checkout_named_otherwise(tmp_path):
    root = tmp_path / "cloned-checkout"
    root.mkdir()
    _write_manifest(root, "good_grimoire")
    (root / "good_grimoire.md").write_text("# hub\n", encoding="utf-8")
    assert _lib.root_hub_stem(root) == "good_grimoire"
    assert _lib.root_hub_path(root) == root / "good_grimoire.md"
    assert _lib.root_hub_stem(root, {"name": "good_grimoire"}) == "good_grimoire"


def test_root_hub_falls_back_to_the_directory_name(tmp_path):
    root = tmp_path / "cooking"
    root.mkdir()
    assert _lib.root_hub_stem(root) == "cooking"
    _write_manifest(root, "renamed")
    assert _lib.root_hub_stem(root) == "cooking"
    assert _lib.root_hub_path(root) == root / "cooking.md"
    assert _lib.root_hub_stem(root, {"name": "../outside"}) == "cooking"


def test_is_hub_compares_stem_and_parent_folder_ignoring_case():
    assert _lib.is_hub(Path("chapters/recipes/recipes.md"))
    assert _lib.is_hub(Path("chapters/Recipes/recipes.md"))
    assert not _lib.is_hub(Path("chapters/recipes/sourdough.md"))
    assert not _lib.is_hub(Path("recipes.md"))


# ---------------------------------------------------------------------------
# Skill families and commands
# ---------------------------------------------------------------------------


def _write_framework(root: Path, manifest) -> None:
    (root / "framework.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_load_skill_families_checked_reads_the_framework_manifest(tmp_path):
    _write_framework(tmp_path, {
        "skill_prefix": "grm",
        "skill_families": {
            "grm": {"path": "skills/grm", "plugin": "grimoire"},
            "dev": {"skill_prefix": "grm", "path": "skills/dev", "slug_prefix": "dev"},
        },
    })
    families, problems = _lib.load_skill_families_checked(tmp_path)
    assert problems == []
    assert families == [
        {"name": "grm", "skill_prefix": "grm", "path": tmp_path / "skills/grm", "slug_prefix": "", "plugin": "grimoire"},
        {"name": "dev", "skill_prefix": "grm", "path": tmp_path / "skills/dev", "slug_prefix": "dev", "plugin": "dev"},
    ]
    assert _lib.load_skill_families(tmp_path) == families


def test_load_skill_families_checked_names_each_invalid_family(tmp_path):
    _write_framework(tmp_path, {
        "skill_prefix": "grm",
        "skill_families": {
            "good": {"path": "skills/good"},
            "prefix": {"skill_prefix": "Bad-Prefix", "path": "skills/a"},
            "slug": {"path": "skills/b", "slug_prefix": "Not_A_Slug"},
            "nopath": {},
            "escape": {"path": "../outside"},
            "rooted": {"path": "/abs/skills"},
            "scalar": "skills/c",
        },
    })
    families, problems = _lib.load_skill_families_checked(tmp_path)
    assert [family["name"] for family in families] == ["good"]
    assert len(problems) == 6
    for name, word in [
        ("prefix", "skill_prefix"), ("slug", "slug_prefix"), ("nopath", "path"),
        ("escape", "path"), ("rooted", "path"), ("scalar", "object"),
    ]:
        assert any(f"skill_families.{name} " in p and word in p for p in problems), name
    assert [family["name"] for family in _lib.load_skill_families(tmp_path)] == ["good"]


@pytest.mark.parametrize(
    "raw, word",
    [
        (None, "could not read"),
        (b"{not json", "could not read"),
        ('{"description": "café"}'.encode("cp1252"), "could not read"),
        (b"[]", "JSON object"),
        (b'{"skill_prefix": "grm"}', "no skill_families"),
        (b'{"skill_families": {}}', "skill_families"),
        (b'{"skill_families": ["grm"]}', "skill_families"),
    ],
    ids=["missing", "invalid-json", "not-utf8", "list", "no-families", "empty-families", "families-list"],
)
def test_load_skill_families_checked_reports_an_unusable_manifest(tmp_path, raw, word):
    if raw is not None:
        (tmp_path / "framework.json").write_bytes(raw)
    families, problems = _lib.load_skill_families_checked(tmp_path)
    assert families == []
    assert len(problems) == 1 and word in problems[0]
    assert _lib.load_skill_families(tmp_path, with_fallback=True) == []


def test_load_skill_families_reads_this_framework_without_problems():
    families, problems = _lib.load_skill_families_checked(RITES.parent)
    assert problems == []
    assert families and all(family["path"].is_dir() for family in families)


def test_discover_skill_commands_carries_slug_description_and_argument_hint(tmp_path):
    _write_framework(tmp_path, {
        "skill_prefix": "grm",
        "skill_families": {"grm": {"path": "skills/grm"}},
    })
    for slug, frontmatter in {
        "add": 'name: {{SKILL_PREFIX}}-add\ndescription: Put knowledge in\nargument-hint: "[topic | file]"',
        "create": "name: {{SKILL_PREFIX}}-create\ndescription: Start a grimoire\nargument-hint: [grimoire-name]",
        "help": "name: {{SKILL_PREFIX}}-help",
        "broken": "description: no name",
    }.items():
        skill = tmp_path / "skills" / "grm" / slug / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(f"---\n{frontmatter}\n---\n\n# Body\n", encoding="utf-8")

    commands = _lib.discover_skill_commands(tmp_path)
    assert sorted(commands) == ["/grm-add", "/grm-create", "/grm-help"]
    assert commands["/grm-add"] == {
        "family": "grm",
        "skill_prefix": "grm",
        "skill_source": "skills/grm/add/SKILL.md",
        "slug": "add",
        "description": "Put knowledge in",
        "argument_hint": "[topic | file]",
    }
    assert commands["/grm-create"]["argument_hint"] == "[grimoire-name]"
    assert commands["/grm-help"]["description"] == ""
    assert commands["/grm-help"]["argument_hint"] == ""


# ---------------------------------------------------------------------------
# iter_pages, iter_link_pages, walk_files
# ---------------------------------------------------------------------------


def test_iter_pages_finds_chapter_and_root_hub():
    pages = list(_lib.iter_pages(GOOD, ["chapters"], exempt_filenames={"README.md"}))
    names = {p.name for p in pages}
    assert "good_grimoire.md" in names      # root hub yielded via include_root_md
    assert "sourdough.md" in names           # leaf in chapters/recipes/
    assert "recipes.md" in names             # chapter hub
    assert "README.md" not in names          # exempted


def test_iter_pages_respects_skip_dirs():
    # Construct a tree with a skip target and ensure it's filtered.
    pages = list(_lib.iter_pages(GOOD, ["chapters"], skip_dirs={"recipes"}))
    assert all("recipes" not in p.parts for p in pages)


def _touch(root: Path, rel: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return path


def test_iter_pages_does_not_descend_into_pruned_directories(tmp_path):
    _touch(tmp_path, "chapters/recipes/sourdough.md")
    _touch(tmp_path, "chapters/recipes/node_modules/pkg/README.md")
    _touch(tmp_path, "chapters/recipes/.obsidian/plugin/README.md")
    _touch(tmp_path, "chapters/recipes/publish/site.md")  # a chapter folder named publish is content
    pages = list(_lib.iter_pages(tmp_path, ["chapters"], include_root_md=False))
    assert pages == [
        tmp_path / "chapters" / "recipes" / "publish" / "site.md",
        tmp_path / "chapters" / "recipes" / "sourdough.md",
    ]


def test_iter_link_pages_skips_publish_sources_and_skip_dirs(tmp_path):
    kept = [
        _touch(tmp_path, "cooking.md"),
        _touch(tmp_path, "chapters/recipes/recipes.md"),
        _touch(tmp_path, "chapters/recipes/sourdough.md"),
        _touch(tmp_path, "chapters/sources/not_a_source_folder.md"),
        _touch(tmp_path, "docs/guide.md"),
        _touch(tmp_path, "sources/root_level.md"),
    ]
    _touch(tmp_path, "chapters/recipes/sources/wrapper.md")
    _touch(tmp_path, "chapters/recipes/Sources/raw/deep.md")
    _touch(tmp_path, "publish/content/recipes/sourdough.md")
    _touch(tmp_path, "publish/quartz/node_modules/pkg/README.md")
    _touch(tmp_path, "inbox/drop.md")
    _touch(tmp_path, "tests/fixtures/bad/page.md")
    _touch(tmp_path, ".git/description.md")
    _touch(tmp_path, "chapters/recipes/notes.txt")

    assert list(_lib.iter_link_pages(tmp_path)) == sorted(kept)
    assert _lib.LINK_SKIP_DIRS == {"inbox", "tests"}


def test_walk_files_returns_a_sorted_list(tmp_path):
    _touch(tmp_path, "b.md")
    _touch(tmp_path, "a.md")
    _touch(tmp_path, "publish/c.md")
    assert _lib.walk_files(tmp_path, "*.md") == [tmp_path / "a.md", tmp_path / "b.md"]


def test_history_filenames_name_the_changelog():
    assert _lib.HISTORY_FILENAMES == {"CHANGELOG.md"}


# ---------------------------------------------------------------------------
# resolve_grimoire_arg
# ---------------------------------------------------------------------------


def test_resolve_grimoire_arg_returns_an_existing_directory(tmp_path):
    assert _lib.resolve_grimoire_arg(tmp_path) == tmp_path.resolve()


def test_resolve_grimoire_arg_exits_2_for_a_path_that_is_not_a_directory(tmp_path, capsys):
    missing = tmp_path / "no_such_grimoire"
    with pytest.raises(SystemExit) as excinfo:
        _lib.resolve_grimoire_arg(missing)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1 and "no_such_grimoire" in captured.err

    a_file = _touch(tmp_path, "page.md")
    with pytest.raises(SystemExit) as excinfo:
        _lib.resolve_grimoire_arg(a_file)
    assert excinfo.value.code == 2


def test_a_validator_exits_2_for_a_grimoire_path_that_does_not_exist(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(RITES / "validate_links.py"), "--grimoire", str(tmp_path / "no_such_grimoire")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 2
    assert "no_such_grimoire" in proc.stderr


# ---------------------------------------------------------------------------
# run_git
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_run_git_reports_a_non_ascii_filename_unquoted(tmp_path):
    code, _out, err = _lib.run_git(tmp_path, "init")
    assert code == 0, err
    (tmp_path / "寿司.md").write_text("x\n", encoding="utf-8")
    code, out, err = _lib.run_git(tmp_path, "status", "--porcelain", "--untracked-files=all")
    assert code == 0, err
    assert out.splitlines() == ["?? 寿司.md"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_run_git_returns_the_failure_of_a_folder_that_is_not_a_repository(tmp_path):
    code, out, err = _lib.run_git(tmp_path / "missing", "status")
    assert code not in (0, 124, 127)
    assert out == "" and err


def test_run_git_reports_a_missing_git_binary(tmp_path, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    assert _lib.run_git(tmp_path, "status") == (127, "", "git is not installed")


def test_run_git_reports_a_timeout_and_disables_prompts(tmp_path, monkeypatch):
    seen = {}

    def slow(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", slow)
    assert _lib.run_git(tmp_path, "fetch", timeout=1) == (124, "", "timed out")
    assert seen["cmd"][:5] == ["git", "-c", "core.quotepath=false", "-C", str(tmp_path)]
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"


# ---------------------------------------------------------------------------
# diagnostics: one path normalizer for both reporters
# ---------------------------------------------------------------------------


def test_both_reporters_normalize_paths_the_same_way(tmp_path):
    inside = tmp_path / "chapters" / "recipes" / "sourdough.md"
    outside = tmp_path.parent / "elsewhere.md"
    validator = diagnostics.DiagnosticReporter("validate_links", tmp_path)
    rite = diagnostics.ResultReporter("repair_links", tmp_path)
    for path in (inside, outside, "chapters\\recipes\\sourdough.md", None):
        expected = diagnostics.normalize_path(path, tmp_path)
        assert validator.error("CODE", "message", path=path).path == expected
        rite.mutation("rewrite", path=path)
        assert rite.mutations[-1]["path"] == expected
    assert diagnostics.normalize_path(inside, tmp_path) == "chapters/recipes/sourdough.md"
    assert diagnostics.normalize_path("chapters\\recipes\\sourdough.md", None) == "chapters/recipes/sourdough.md"


# ---------------------------------------------------------------------------
# Regex sanity (constants are part of the public surface)
# ---------------------------------------------------------------------------


def test_skill_prefix_regex_accepts_valid_slugs():
    assert _lib.SKILL_PREFIX_RE.fullmatch("cook")
    assert _lib.SKILL_PREFIX_RE.fullmatch("oly2")


def test_skill_prefix_regex_rejects_invalid_slugs():
    assert not _lib.SKILL_PREFIX_RE.fullmatch("cook-bad")
    assert not _lib.SKILL_PREFIX_RE.fullmatch("Cook")
    assert not _lib.SKILL_PREFIX_RE.fullmatch("2cook")


def test_skill_slug_regex_accepts_kebab_case():
    assert _lib.SKILL_SLUG_RE.fullmatch("validate-all")
    assert _lib.SKILL_SLUG_RE.fullmatch("a")


def test_skill_slug_regex_rejects_mixed_case():
    assert not _lib.SKILL_SLUG_RE.fullmatch("Cook-Bad")
    assert not _lib.SKILL_SLUG_RE.fullmatch("framework_underscore")


def test_date_regex_basic():
    assert _lib.DATE_RE.match("2026-05-15")
    assert not _lib.DATE_RE.match("2026-5-15")
    assert not _lib.DATE_RE.match("not-a-date")


# ---------------------------------------------------------------------------
# is_skipped
# ---------------------------------------------------------------------------


def test_is_skipped_matches_single_segment_dir():
    assert _lib.is_skipped("sources/article.md", {"sources"})
    assert _lib.is_skipped(Path("inbox/note.md"), {"inbox", "tests"})


def test_is_skipped_does_not_match_sibling_prefix():
    # A skip entry matches whole path segments, so a sibling that shares a
    # name prefix is not skipped.
    assert not _lib.is_skipped("sources_extra/page.md", {"sources"})
    assert not _lib.is_skipped("inbox_archive/page.md", {"inbox"})


def test_is_skipped_matches_multi_segment_prefix():
    skip = {"invocations/validators"}
    assert _lib.is_skipped("invocations/validators/x.md", skip)
    assert not _lib.is_skipped("invocations/validators_extra/x.md", skip)


def test_is_skipped_is_anchored_at_path_start():
    assert not _lib.is_skipped("chapters/sources/x.md", {"sources"})


def test_is_skipped_normalizes_backslashes():
    assert _lib.is_skipped("sources\\article.md", {"sources"})


# ---------------------------------------------------------------------------
# source-layer helpers
# ---------------------------------------------------------------------------


def test_colocated_source_path_requires_chapter_context():
    assert _lib.is_colocated_source_path("chapters/recipes/sources/example.md")
    assert _lib.is_colocated_source_path("chapters/trips/2026/sources/map.png")
    assert not _lib.is_colocated_source_path("sources/example.md")
    assert not _lib.is_colocated_source_path("chapters/sources/example.md")


def test_inside_colocated_source_dir_matches_descendants():
    assert _lib.is_inside_colocated_source_dir("chapters/recipes/sources")
    assert _lib.is_inside_colocated_source_dir("chapters/recipes/sources/raw/file.pdf")
    assert not _lib.is_inside_colocated_source_dir("chapters/sources")


def test_resolve_local_source_path_stays_under_root(tmp_path):
    target = tmp_path / "chapters" / "recipes" / "sources" / "example.md"
    target.parent.mkdir(parents=True)
    target.write_text("source\n", encoding="utf-8")

    resolved = _lib.resolve_local_source_path(
        tmp_path, "chapters/recipes/sources/example.md"
    )

    assert resolved == target.resolve()
    assert _lib.resolve_local_source_path(tmp_path, "sources/example.md") is None
    assert _lib.resolve_local_source_path(tmp_path, "../outside.md") is None


# ---------------------------------------------------------------------------
# public_document
# ---------------------------------------------------------------------------


def test_public_document_top_level_filenames(tmp_path):
    assert _lib.public_document(tmp_path / "README.md", tmp_path)
    assert _lib.public_document(tmp_path / "CHANGELOG.md", tmp_path)


def test_public_document_docs_tree(tmp_path):
    assert _lib.public_document(tmp_path / "docs" / "installation.md", tmp_path)


def test_public_document_vault_surface_is_not_public(tmp_path):
    assert not _lib.public_document(tmp_path / "chapters" / "recipes" / "sourdough.md", tmp_path)


def test_walk_files_prunes_publish_only_at_the_root(tmp_path):
    for rel in ("publish/site/a.md", "formulae/publish/b.md", "chapters/x/.obsidian/c.md",
                "chapters/x/node_modules/d.md", "chapters/x/e.md", ".git/f.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    found = {p.relative_to(tmp_path).as_posix() for p in _lib.walk_files(tmp_path, "*.md")}
    assert found == {"formulae/publish/b.md", "chapters/x/e.md"}
