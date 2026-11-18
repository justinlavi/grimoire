"""Tests for stage_publish.py and audit_publish.py: data loss, link forms, waivers."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from test_publish_rites import GOOD, RITES, _grimoire, _run

SOURCE = "chapters/recipes/sources/card.pdf"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _page(root: Path, name: str, body: str, front: str = "") -> Path:
    path = root / "chapters" / "recipes" / name
    _write(path, f"---\ntype: concept\ntitle: \"T\"\n{front}authority: hybrid\n---\n\n{body}\n")
    return path


def _staged(root: Path, rel: str) -> str:
    return (root / "publish" / "content" / rel).read_text(encoding="utf-8")


def _settings(root: Path) -> dict:
    files = {"build.sh": "echo build\n", "README.md": "readme\n", "quartz.config.yaml": "x: 1\n"}
    for name, text in files.items():
        _write(root / "publish" / name, text)
    return files


def test_content_dir_publish_is_refused_and_settings_survive(tmp_path):
    root = _grimoire(tmp_path)
    files = _settings(root)
    _write(root / "publish" / "publish.json", json.dumps({"content_dir": "publish"}))

    out = _run("stage_publish.py", root, "--apply")

    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert "below publish/" in out["report"]["messages"][0]["message"]
    for name, text in files.items():
        assert (root / "publish" / name).read_text(encoding="utf-8") == text
    assert (root / "publish" / "publish.json").is_file()


def test_content_dir_holding_publish_settings_is_refused(tmp_path):
    root = _grimoire(tmp_path)
    _write(root / "publish" / "site" / "build.sh", "echo build\n")
    _write(root / "publish" / "publish.json", json.dumps({"content_dir": "publish/site"}))

    out = _run("stage_publish.py", root, "--apply")

    assert out["returncode"] == 1 and "publishing settings" in out["report"]["messages"][0]["message"]
    assert (root / "publish" / "site" / "build.sh").is_file()


def test_summary_names_the_content_dir_relative_to_the_grimoire(tmp_path):
    root = _grimoire(tmp_path)
    assert _run("stage_publish.py", root)["report"]["summary"]["content_dir"] == "publish/content"


def test_blank_link_target_does_not_crash_stage_or_audit(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "blank.md", "An [empty]( ) link and an [empty]() one.")

    staged = _run("stage_publish.py", root, "--apply")
    audited = _run("audit_publish.py", root)

    assert staged["returncode"] == 0, staged
    assert audited["returncode"] == 0, audited


def test_every_sources_form_is_rewritten_and_audited_alike(tmp_path):
    root = _grimoire(tmp_path)
    forms = {
        "unquoted_inline.md": f"sources: [{SOURCE}]\n",
        "quoted_inline.md": f"sources: [\"{SOURCE}\", 'https://example.com/a']\n",
        "scalar.md": f"sources: {SOURCE}\n",
        "block_flush.md": f"sources:\n- {SOURCE}\n",
        "block_indented.md": f"sources:\n  - \"{SOURCE}\"  # the card\n",
        "dot_slash.md": f"sources: [./{SOURCE}]\n",
    }
    for name, front in forms.items():
        _page(root, name, "Body.", front)

    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0
    for name in forms:
        page = _staged(root, f"recipes/{name}")
        assert "recipes/sources/card.pdf" in page and "chapters/" not in page, (name, page)
    audit = _run("audit_publish.py", root)
    assert audit["returncode"] == 0, audit

    _write(root / "publish" / "content" / "recipes" / "unquoted_inline.md", "---\nsources: [recipes/sources/gone.pdf]\n---\n\nBody.\n")
    broken = _run("audit_publish.py", root)
    assert broken["returncode"] == 1
    assert any("unresolved-frontmatter-source" in d["message"] for d in broken["report"]["diagnostics"])


def test_source_described_in_words_is_not_a_blocker(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "wrapper.md", "Body.", "sources: [\"Interview with the chef, 2026\"]\n")
    _run("stage_publish.py", root, "--apply")
    assert _run("audit_publish.py", root)["returncode"] == 0


def test_rooted_and_root_hub_asset_links_are_flattened(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "rooted.md", f"The card is [here](/{SOURCE}) and [there](<../../{SOURCE}#p2> \"Card\").")
    hub = root / "good_grimoire.md"
    hub.write_text(hub.read_text(encoding="utf-8") + f"\nThe [card]({SOURCE}).\n", encoding="utf-8", newline="\n")

    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0

    assert "(/recipes/sources/card.pdf)" in _staged(root, "recipes/rooted.md")
    assert "</recipes/sources/card.pdf#p2> \"Card\"" in _staged(root, "recipes/rooted.md")
    assert "[card](/recipes/sources/card.pdf)" in _staged(root, "index.md")
    assert not [d for d in _run("audit_publish.py", root)["report"]["diagnostics"] if "unresolved-asset" in d["message"]]


def test_link_to_the_unstaged_readme_becomes_plain_text_and_code_is_untouched(tmp_path):
    root = _grimoire(tmp_path)
    hub = root / "good_grimoire.md"
    hub.write_text(
        hub.read_text(encoding="utf-8")
        + "\nSee [[README|README]] and [[README]] and `[[chapters/recipes/recipes|code]]`.\n\n```\n[[chapters/recipes/sourdough]]\n```\n",
        encoding="utf-8", newline="\n",
    )
    _write(root / "README.md", "# readme\n")

    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0

    index = _staged(root, "index.md")
    assert "[[README" not in index and "See README and README and" in index
    assert "`[[chapters/recipes/recipes|code]]`" in index
    assert "[[chapters/recipes/sourdough]]" in index
    assert "[[recipes/recipes|recipes]]" in index


def test_include_asset_folders_is_respected_by_the_audit(tmp_path):
    root = _grimoire(tmp_path)
    _write(root / "publish" / "publish.json", json.dumps({"include_asset_folders": True}))
    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0
    assert (root / "publish" / "content" / "recipes" / "templates" / "card_template.md").is_file()

    audit = _run("audit_publish.py", root)

    assert audit["returncode"] == 0, audit
    assert not [d for d in audit["report"]["diagnostics"] if "authoring root" in d["message"]]


def test_audit_names_the_asset_folder_it_matched(tmp_path):
    root = _grimoire(tmp_path)
    _run("stage_publish.py", root, "--apply")
    _write(root / "publish" / "content" / "recipes" / "templates" / "t.md", "# t\n")

    out = _run("audit_publish.py", root)

    messages = [d["message"] for d in out["report"]["diagnostics"] if "authoring root" in d["message"]]
    assert messages == ["authoring root staged: remove recipes/templates/ from the published output"]


def test_audit_allow_turns_a_matching_blocker_into_a_named_warning(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "visa.md", "Bring your passport and a photo.")
    _page(root, "other.md", "Bring your passport and a photo.")
    _run("stage_publish.py", root, "--apply")
    assert _run("audit_publish.py", root)["returncode"] == 1

    _write(root / "publish" / "publish.json", json.dumps({"audit": {"allow": [{"risk": "identity-document-scan", "path": "recipes/*"}]}}))
    out = _run("audit_publish.py", root)

    assert out["returncode"] == 0, out
    waived = [d for d in out["report"]["diagnostics"] if "waived by audit.allow" in d["message"]]
    assert len(waived) == 2 and all(d["severity"] == "warning" for d in waived)

    _write(root / "publish" / "publish.json", json.dumps({"audit": {"allow": [{"risk": "identity-document-scan", "path": "recipes/visa.md"}]}}))
    narrow = _run("audit_publish.py", root)
    assert narrow["returncode"] == 1
    assert [d["path"] for d in narrow["report"]["diagnostics"] if d["severity"] == "error"] == ["recipes/other.md"]


def test_audit_allow_never_waives_a_different_risk(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "visa.md", "password: hunter2")
    _write(root / "publish" / "publish.json", json.dumps({"audit": {"allow": [{"risk": "bank-account-data", "path": "recipes/*"}]}}))
    _run("stage_publish.py", root, "--apply")
    assert _run("audit_publish.py", root)["returncode"] == 1


def test_malformed_audit_allow_is_a_configuration_error(tmp_path):
    root = _grimoire(tmp_path)
    _write(root / "publish" / "publish.json", json.dumps({"audit": {"allow": ["recipes/*"]}}))
    _run("stage_publish.py", root, "--apply")
    out = _run("audit_publish.py", root)
    assert out["returncode"] == 2
    assert out["report"]["diagnostics"][0]["code"] == "PUBLISH_CONFIG_INVALID"


def test_non_ascii_and_spaced_page_names_are_staged_and_linked(tmp_path):
    root = _grimoire(tmp_path)
    _page(root, "日本.md", "Nihon.")
    _page(root, "my page.md", "Spaced.", "")
    _page(root, "links.md", "See [[chapters/recipes/日本|日本]] and [[chapters/recipes/my page|spaced]].")

    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0

    assert (root / "publish" / "content" / "recipes" / "日本.md").is_file()
    assert "[[recipes/日本|日本]]" in _staged(root, "recipes/links.md")
    assert "[[recipes/my page|spaced]]" in _staged(root, "recipes/links.md")


def test_a_page_that_is_not_utf8_is_staged_byte_for_byte_with_a_warning(tmp_path):
    root = _grimoire(tmp_path)
    raw = b"---\ntype: concept\n---\n\ncaf\xe9 [[chapters/recipes/recipes]]\n"
    (root / "chapters" / "recipes" / "latin.md").write_bytes(raw)

    out = _run("stage_publish.py", root, "--apply")

    assert out["returncode"] == 0
    assert (root / "publish" / "content" / "recipes" / "latin.md").read_bytes() == raw
    assert any("not valid UTF-8" in m["message"] for m in out["report"]["messages"])


def test_a_link_in_a_page_with_crlf_line_endings_is_flattened_to_lf(tmp_path):
    root = _grimoire(tmp_path)
    (root / "chapters" / "recipes" / "crlf.md").write_bytes(b"---\r\ntype: concept\r\n---\r\n\r\n[[chapters/recipes/recipes|r]]\r\n")
    assert _run("stage_publish.py", root, "--apply")["returncode"] == 0
    data = (root / "publish" / "content" / "recipes" / "crlf.md").read_bytes()
    assert b"\r" not in data and b"[[recipes/recipes|r]]" in data


def test_the_rites_run_from_the_command_line_without_a_publish_folder(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    shutil.rmtree(root / "publish")
    result = subprocess.run(
        [sys.executable, str(RITES / "stage_publish.py"), "--grimoire", str(root), "--apply", "--format", "json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


FORMULA = Path(__file__).resolve().parent.parent / "formulae" / "grimoire"


def test_scaffold_exempts_chapter_local_sources_from_line_ending_conversion():
    lines = (FORMULA / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "chapters/**/sources/** -text" in lines
    assert lines[lines.index("chapters/**/sources/** -text") - 1].startswith("# ")


def test_scaffold_chapters_marker_is_empty():
    assert (FORMULA / "chapters" / ".gitkeep").read_bytes() == b""
