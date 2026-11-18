"""Currency classification, root-source relocation, README injection and exit codes of update_grimoires."""

import json
import sys
from pathlib import Path

import pytest

import update_grimoires as U

REPO_ROOT = Path(__file__).resolve().parent.parent

UP_TO_DATE = {
    "symbolic-ref": (0, "main", ""),
    "rev-parse --abbrev-ref": (0, "origin/main", ""),
    "status --porcelain": (0, "", ""),
    "fetch": (0, "", ""),
    "rev-list": (0, "0\t0", ""),
}


def _git(**overrides):
    table = {**UP_TO_DATE, **overrides}

    def git(*args, cwd=None):
        text = " ".join(str(a) for a in args)
        for key, response in table.items():
            if key in text:
                return response
        return (0, "", "")

    return git


def _page(root: Path, rel: str, sources: str, body: str = "# Page\n") -> Path:
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f'---\ntype: concept\ntitle: "Page"\ntags: [type/concept]\nauthority: external\n{sources}\nlast_verified: 2026-05-25\n---\n\n{body}',
        encoding="utf-8",
        newline="\n",
    )
    return page


def test_current_statuses_is_the_one_name_for_current():
    assert U.CURRENT_STATUSES == frozenset({"up_to_date", "fast_forwarded", "ahead", "local_only"})
    assert not hasattr(U, "HEAL_ELIGIBLE")


@pytest.mark.parametrize("failure", [(1, "", "fatal: bad revision '@{u}...HEAD'"), (0, "garbage", ""), (0, "", "")])
def test_a_failed_comparison_is_not_current_and_is_not_healed(tmp_path, failure):
    repo = tmp_path / "g"
    (repo / ".git").mkdir(parents=True)
    healed = []

    rec = U.process_grimoire(
        "g", {"local_path": str(repo)}, REPO_ROOT, apply=True, git=_git(**{"rev-list": failure}),
        heal_fn=lambda *a: healed.append(a) or {"status": "ok"}, revalidate_fn=lambda a, b: (True, ""),
    )

    assert rec["status"] == "compare_failed"
    assert rec["heal_eligible"] is False
    assert healed == []
    assert rec["status"] not in U.CURRENT_STATUSES


@pytest.mark.parametrize("local_path", ["", "relative/path"])
def test_an_empty_or_relative_local_path_is_a_missing_grimoire_never_the_working_directory(tmp_path, monkeypatch, local_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "relative" / "path").mkdir(parents=True)
    monkeypatch.chdir(repo)
    healed = []

    rec = U.process_grimoire(
        "g", {"local_path": local_path}, REPO_ROOT, apply=True, git=_git(),
        heal_fn=lambda *a: healed.append(a) or {"status": "ok"}, revalidate_fn=lambda a, b: (True, ""),
    )

    assert rec["status"] == "missing_local"
    assert rec["heal_eligible"] is False
    assert healed == []


def test_relocation_rewrites_only_the_exact_sources_entry(tmp_path):
    grimoire = tmp_path / "g"
    (grimoire / "sources").mkdir(parents=True)
    (grimoire / "sources" / "report.pdf").write_bytes(b"%PDF")
    # x cites the root source; y cites a chapter-local source whose path ends in the root source's path.
    x = _page(grimoire, "chapters/x/page.md", 'sources: ["sources/report.pdf"]')
    y = _page(grimoire, "chapters/y/page.md", 'sources: ["chapters/y/sources/report.pdf"]')
    both = _page(
        grimoire, "chapters/x/other.md",
        "sources:\n  - sources/report.pdf\n  - chapters/y/sources/report.pdf",
        body="See sources/report.pdf in prose.\n",
    )
    y_before = y.read_text(encoding="utf-8")

    result = U.relocate_root_sources(grimoire)

    assert result["moved"] == [{"from": "sources/report.pdf", "to": "chapters/x/sources/report.pdf"}]
    assert 'sources: ["chapters/x/sources/report.pdf"]' in x.read_text(encoding="utf-8")
    assert y.read_text(encoding="utf-8") == y_before
    rewritten = both.read_text(encoding="utf-8")
    assert "  - chapters/x/sources/report.pdf\n  - chapters/y/sources/report.pdf" in rewritten
    assert "chapters/y/chapters/x" not in rewritten
    assert "See sources/report.pdf in prose." in rewritten


def test_relocation_writes_lf_and_leaves_a_source_a_non_utf8_page_may_cite(tmp_path):
    grimoire = tmp_path / "g"
    (grimoire / "sources").mkdir(parents=True)
    (grimoire / "sources" / "a.pdf").write_bytes(b"%PDF")
    (grimoire / "sources" / "b.pdf").write_bytes(b"%PDF")
    cited = _page(grimoire, "chapters/x/page.md", 'sources: ["sources/a.pdf"]')
    unreadable = grimoire / "chapters" / "z" / "page.md"
    unreadable.parent.mkdir(parents=True)
    unreadable.write_bytes('---\nsources: ["sources/b.pdf"]\n---\ncaf\xe9\n'.encode("cp1252"))
    before = unreadable.read_bytes()

    result = U.relocate_root_sources(grimoire)

    assert [m["from"] for m in result["moved"]] == ["sources/a.pdf"]
    assert result["left_for_review"] == ["sources/b.pdf"]
    assert b"\r\n" not in cited.read_bytes()
    assert unreadable.read_bytes() == before


def test_readme_injection_writes_lf_line_endings(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_bytes(b"# G\r\n\r\nintro\r\n\r\n## Layout\r\n")

    assert U.inject_update_readme_block(readme, U.UPDATE_BEGIN + "\nbody\n" + U.UPDATE_END) is True

    assert b"\r\n" not in readme.read_bytes()


def test_a_readme_that_is_not_utf8_is_reported_not_rewritten(tmp_path):
    grimoire = tmp_path / "g"
    grimoire.mkdir()
    readme = grimoire / "README.md"
    readme.write_bytes("# Caf\xe9\n".encode("cp1252"))
    before = readme.read_bytes()

    result = U.default_heal(grimoire, REPO_ROOT)

    assert result["status"] == "error"
    assert any("README block injection failed" in m for m in result["messages"])
    assert readme.read_bytes() == before


def _result(heal_status):
    return {
        "grimoires": [{
            "key": "g", "status": "up_to_date", "local_path": "/x", "pulled": False, "behind": 0, "ahead": 0,
            "heal": {"status": heal_status, "messages": ["scaffold sync failed: boom"]}, "heal_eligible": True,
            "reason": None, "host": "", "online_path": None,
        }],
        "needs_manual_pull": [],
        "summary": {"total": 1, "already_current": 1, "brought_current": 0, "ahead": 0, "healed": 0,
                    "heal_skipped": 0, "needs_manual_pull": 0},
    }


@pytest.mark.parametrize("heal_status,expected", [("error", 1), ("ok", 0)])
def test_the_cli_exits_one_when_a_heal_errored(monkeypatch, capsys, heal_status, expected):
    monkeypatch.setattr(U, "process_all", lambda *a, **k: _result(heal_status))
    monkeypatch.setattr(sys, "argv", ["update_grimoires.py", "--format", "json", "--apply"])

    assert U.main() == expected
    report = json.loads(capsys.readouterr().out)
    errors = [m["message"] for m in report["messages"] if m["severity"] == "error"]
    assert bool(errors) == (heal_status == "error")
    assert all("scaffold sync failed: boom" in text for text in errors)


def test_content_that_fails_validation_after_a_heal_is_a_warning_with_its_writes_recorded(tmp_path, monkeypatch, capsys):
    grimoire = tmp_path / "g"
    grimoire.mkdir()
    rec = U.process_grimoire(
        "g", {"local_path": str(grimoire)}, REPO_ROOT, apply=True,
        heal_fn=lambda local_path, framework_root: {"status": "ok", "scaffold_synced": [".editorconfig"]},
        revalidate_fn=lambda framework_root, local_path: (False, "validate_orphans.py FAILED"),
    )
    assert rec["status"] == "local_only"
    assert rec["heal"]["status"] == "needs_check"
    assert rec["heal"]["validate"] == "fail"
    assert U.heal_wrote(rec)
    severity, text = U.heal_finding(rec)
    assert severity == "warning"
    assert "/grm-check" in text

    result = {"grimoires": [rec], "needs_manual_pull": [], "warnings": [],
              "summary": {"total": 1, "already_current": 0, "brought_current": 0, "ahead": 0,
                          "local_only": 1, "healed": 1, "needs_check": 1, "heal_skipped": 0,
                          "needs_manual_pull": 0}}
    reporter = U._build_reporter(tmp_path, result, apply=True)
    assert [m["severity"] for m in reporter.messages] == ["warning"]
    assert [m["action"] for m in reporter.mutations] == ["heal"]
    assert U.needs_attention(result) is True

    monkeypatch.setattr(U, "process_all", lambda *a, **k: result)
    monkeypatch.setattr(sys, "argv", ["update_grimoires.py", "--format", "json", "--apply"])
    assert U.main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_a_failed_heal_stays_an_error_when_validation_also_fails(tmp_path):
    grimoire = tmp_path / "g"
    grimoire.mkdir()
    rec = U.process_grimoire(
        "g", {"local_path": str(grimoire)}, REPO_ROOT, apply=True,
        heal_fn=lambda local_path, framework_root: {"status": "error", "messages": ["scaffold sync failed: boom"]},
        revalidate_fn=lambda framework_root, local_path: (False, "validate_orphans.py FAILED"),
    )
    assert rec["heal"]["status"] == "error"
    assert U.heal_finding(rec)[0] == "error"


def test_an_unreadable_library_is_reported_as_a_warning_not_a_crash(tmp_path):
    (tmp_path / "library.json").write_text('{"grimoires": {"a": {"local_path": "x"},}}', encoding="utf-8")

    result = U.process_all(tmp_path, REPO_ROOT, apply=False, fetch=False)

    assert result["grimoires"] == []
    assert any("could not read library" in text for text in result["warnings"])
    assert [m["severity"] for m in U._build_reporter(tmp_path, result, apply=False).messages] == ["warning"]
