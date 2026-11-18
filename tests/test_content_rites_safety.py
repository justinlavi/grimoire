"""Safety and correctness tests for the rites that create, move, delete and relink pages."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from _lib import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
RITES = REPO_ROOT / "rites"
GOOD = REPO_ROOT / "tests" / "fixtures" / "good_grimoire"


def run_rite(rite: str, grimoire: Path, *args: str, env: dict | None = None):
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(RITES / f"{rite}.py"), "--grimoire", str(grimoire), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=60, env=full_env,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def fm_page(title: str, body: str = "", sources: str = "") -> str:
    return (f'---\ntype: concept\ntitle: "{title}"\naliases: []\ntags: []\n{sources}'
            f"authority: grimoire\nlast_verified: 2026-05-15\n---\n\n# {title}\n\n{body}")


def grimoire(tmp_path: Path) -> Path:
    root = tmp_path / "g"
    write(root / "chapters/guide/guide.md", "[[chapters/guide/intro|Intro]]\n")
    write(root / "chapters/guide/intro.md", "intro\n")
    write(root / "chapters/guide/manual.md", "manual\n")
    write(root / "chapters/other/other.md", "see [[chapters/guide/intro|Intro]]\n")
    write(root / "README.md", "readme\n")
    return root


def victim(tmp_path: Path) -> Path:
    path = tmp_path / "victim"
    write(path / "precious.md", "keep me\n")
    return path


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_remove_with_dotdot_never_reaches_a_sibling_directory(tmp_path):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)

    result = run_rite("restructure_grimoire", root, "--remove", "chapters/../../victim", "--apply")

    assert result.returncode == 1
    assert (keep / "precious.md").read_text(encoding="utf-8") == "keep me\n"


@pytest.mark.parametrize("argument", [
    "chapters/../../victim/precious.md",
    "../victim/precious.md",
    "VICTIM_ABSOLUTE",
    "C:/victim/precious.md",
    "C:\\victim\\precious.md",
    "chapters/../README.md",
    "CHAPTERS/../README.md",
    "CHAPTERS",
    "chapters",
])
def test_remove_refuses_every_path_outside_chapters(tmp_path, argument):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)
    target = str(keep / "precious.md") if argument == "VICTIM_ABSOLUTE" else argument

    result = run_rite("restructure_grimoire", root, "--remove", target, "--apply")

    assert result.returncode == 1
    assert (keep / "precious.md").is_file()
    assert (root / "README.md").is_file()
    assert (root / "chapters/guide/intro.md").is_file()


@pytest.mark.parametrize("src, dst", [
    ("chapters/guide/intro.md", "chapters/../../victim/intro.md"),
    ("chapters/guide/intro.md", "../victim/intro.md"),
    ("chapters/guide/intro.md", "C:/victim/intro.md"),
    ("chapters/../README.md", "chapters/readme.md"),
    ("chapters/guide/intro.md", "chapters/../outside.md"),
])
def test_move_refuses_a_source_or_destination_outside_chapters(tmp_path, src, dst):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)

    result = run_rite("restructure_grimoire", root, "--move", src, dst, "--apply")

    assert result.returncode == 1
    assert sorted(p.name for p in keep.iterdir()) == ["precious.md"]
    assert (root / "README.md").is_file()
    assert (root / "chapters/guide/intro.md").is_file()
    assert not (tmp_path / "outside.md").exists()


def test_move_refuses_an_absolute_destination(tmp_path):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)

    result = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                      str(keep / "intro.md"), "--apply")

    assert result.returncode == 1
    assert not (keep / "intro.md").exists()


def _symlink_out(root: Path, keep: Path) -> None:
    """Make chapters/escape lead to `keep`: a symbolic link, or a junction on Windows."""
    link = root / "chapters/escape"
    try:
        os.symlink(keep, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform == "win32":
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(keep)],
                              capture_output=True, text=True)
        if made.returncode == 0:
            return
    pytest.skip("this platform or account cannot create symbolic links")


def test_symlink_leading_out_is_refused_for_remove_and_move(tmp_path):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)
    _symlink_out(root, keep)

    for args in (
        ("--remove", "chapters/escape"),
        ("--remove", "chapters/escape/precious.md"),
        ("--move", "chapters/escape", "chapters/moved"),
        ("--move", "chapters/escape/precious.md", "chapters/precious.md"),
        ("--move", "chapters/guide/intro.md", "chapters/escape/intro.md"),
    ):
        result = run_rite("restructure_grimoire", root, *args, "--apply")
        assert result.returncode == 1, args
    assert (keep / "precious.md").read_text(encoding="utf-8") == "keep me\n"
    assert sorted(p.name for p in keep.iterdir()) == ["precious.md"]
    assert (root / "chapters/guide/intro.md").is_file()


def test_new_page_refuses_paths_outside_chapters(tmp_path):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)
    for path in ("chapters/../../victim/new.md", "../victim/new.md", str(keep / "new.md"),
                 "C:/victim/new.md", "chapters/../new.md", "chapters/new.md/../../new.md"):
        result = run_rite("new_page", root, "--path", path, "--type", "concept",
                          "--title", "T", "--apply")
        assert result.returncode == 1, path
    assert sorted(p.name for p in keep.iterdir()) == ["precious.md"]
    assert not (tmp_path / "new.md").exists() and not (root / "new.md").exists()


def test_new_page_refuses_a_symlink_leading_out(tmp_path):
    root = grimoire(tmp_path)
    keep = victim(tmp_path)
    _symlink_out(root, keep)

    result = run_rite("new_page", root, "--path", "chapters/escape/new.md", "--type", "concept",
                      "--title", "T", "--apply")

    assert result.returncode == 1
    assert sorted(p.name for p in keep.iterdir()) == ["precious.md"]


# ---------------------------------------------------------------------------
# Move validation
# ---------------------------------------------------------------------------


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_hub_rename_that_lands_on_an_existing_page_is_refused_in_plan_and_apply(tmp_path):
    root = grimoire(tmp_path)
    before = snapshot(root)

    plan = run_rite("restructure_grimoire", root, "--move", "chapters/guide", "chapters/manual")
    apply = run_rite("restructure_grimoire", root, "--move", "chapters/guide", "chapters/manual",
                     "--apply")

    assert plan.returncode == 1 and apply.returncode == 1
    assert "both land at" in plan.stdout
    assert snapshot(root) == before


@pytest.mark.parametrize("src, dst", [
    ("chapters/guide/intro.md", "chapters/newplace"),
    ("chapters/guide/intro.md", "chapters/guide/intro.md/x.md"),
    ("chapters/guide", "chapters/guide/sub"),
    ("chapters/guide/intro.md", "chapters/guide/manual.md"),
    ("chapters/guide/guide.md", "chapters/guide/renamed.md"),
])
def test_plan_and_apply_agree_on_refusals(tmp_path, src, dst):
    root = grimoire(tmp_path)
    before = snapshot(root)

    plan = run_rite("restructure_grimoire", root, "--move", src, dst)
    apply = run_rite("restructure_grimoire", root, "--move", src, dst, "--apply")

    assert plan.returncode == 1 and apply.returncode == 1
    assert snapshot(root) == before


def test_page_destination_must_end_in_md(tmp_path):
    root = grimoire(tmp_path)

    result = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                      "chapters/newplace", "--apply")

    assert result.returncode == 1
    assert "must end in .md" in result.stdout
    assert not (root / "chapters/newplace").exists()


def test_case_only_rename_of_a_page_and_a_chapter(tmp_path):
    root = grimoire(tmp_path)

    page = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                    "chapters/guide/Intro.md", "--apply")
    assert page.returncode == 0, page.stdout
    assert "Intro.md" in sorted(p.name for p in (root / "chapters/guide").iterdir())
    assert "[[chapters/guide/Intro|Intro]]" in (root / "chapters/other/other.md").read_text("utf-8")

    chapter = run_rite("restructure_grimoire", root, "--move", "chapters/guide", "chapters/Guide",
                       "--apply")
    assert chapter.returncode == 0, chapter.stdout
    assert sorted(p.name for p in (root / "chapters").iterdir()) == ["Guide", "other"]
    assert (root / "chapters/Guide/Guide.md").is_file()
    assert "[[chapters/Guide/Intro|Intro]]" in (root / "chapters/other/other.md").read_text("utf-8")


def test_refusal_under_json_prints_an_envelope(tmp_path):
    root = grimoire(tmp_path)

    result = run_rite("restructure_grimoire", root, "--remove", "chapters/missing", "--format", "json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["rite"] == "restructure_grimoire"
    assert report["status"] == "blocked"
    assert report["messages"][0]["severity"] == "error"
    assert "does not exist" in report["messages"][0]["message"]


# ---------------------------------------------------------------------------
# Pages that do not decode are skipped and reported
# ---------------------------------------------------------------------------


def test_move_skips_a_page_that_is_not_utf8_and_reports_it(tmp_path):
    root = grimoire(tmp_path)
    legacy = root / "chapters/other/legacy.md"
    raw = b"caf\xe9 [[chapters/guide/intro|Intro]]\n"
    legacy.write_bytes(raw)

    result = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                      "chapters/guide/overview.md", "--apply", "--format", "json")

    assert result.returncode == 0, result.stdout
    assert legacy.read_bytes() == raw
    report = json.loads(result.stdout)
    assert report["status"] == "partial"
    assert report["summary"]["skipped"] == ["chapters/other/legacy.md"]
    assert any("legacy.md" in m["message"] for m in report["messages"])
    # The other pages were still relinked.
    assert "[[chapters/guide/overview|Intro]]" in (root / "chapters/other/other.md").read_text("utf-8")


def test_move_writes_utf8_with_lf(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/other/jp.md", "日本 [[chapters/guide/intro|Intro]]\n")

    run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
             "chapters/guide/overview.md", "--apply")

    data = (root / "chapters/other/jp.md").read_bytes()
    assert data == "日本 [[chapters/guide/overview|Intro]]\n".encode("utf-8")


# ---------------------------------------------------------------------------
# publish/ and chapter-local sources are outside the rewrite scope
# ---------------------------------------------------------------------------


def test_move_leaves_publish_and_source_wrappers_alone(tmp_path):
    root = grimoire(tmp_path)
    link = "[[chapters/guide/intro|Intro]]\n"
    write(root / "publish/quartz/node_modules/pkg/README.md", link)
    write(root / "publish/content/x.md", link)
    write(root / "chapters/other/sources/wrap.md", link)

    result = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                      "chapters/guide/overview.md", "--apply")

    assert result.returncode == 0
    for rel in ("publish/quartz/node_modules/pkg/README.md", "publish/content/x.md",
                "chapters/other/sources/wrap.md"):
        assert (root / rel).read_text(encoding="utf-8") == link


# ---------------------------------------------------------------------------
# Frontmatter sources follow a moved folder
# ---------------------------------------------------------------------------


def test_move_retargets_frontmatter_sources_into_the_moved_folder(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/guide/sources/a.pdf", "pdf")
    write(root / "chapters/guide/sources/a.md", "---\ntype: source\n---\n")
    write(root / "chapters/other/cites.md", fm_page(
        "Cites", sources=("sources:\n  - chapters/guide/sources/a.pdf\n"
                          "  - chapters/guide/sources/a.pdf.bak\n"
                          "  - chapters/guideline/sources/a.pdf\n"
                          "  - https://example.com/chapters/guide/sources/a.pdf\n")))
    write(root / "chapters/other/inline.md", fm_page(
        "Inline", sources='sources: ["chapters/guide/sources/a.md", chapters/guide/intro.md]\n'))

    result = run_rite("restructure_grimoire", root, "--move", "chapters/guide", "chapters/handbook",
                      "--apply", "--format", "json")

    assert result.returncode == 0, result.stdout
    cites = (root / "chapters/other/cites.md").read_text("utf-8")
    assert "  - chapters/handbook/sources/a.pdf\n" in cites
    assert "  - chapters/handbook/sources/a.pdf.bak\n" in cites
    assert "  - chapters/guideline/sources/a.pdf\n" in cites
    assert "https://example.com/chapters/guide/sources/a.pdf" in cites
    inline = (root / "chapters/other/inline.md").read_text("utf-8")
    assert 'sources: ["chapters/handbook/sources/a.md", chapters/handbook/intro.md]' in inline
    assert json.loads(result.stdout)["summary"]["source_rewrites"] == 4


def test_moved_hub_source_entry_follows_the_hub_rename(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/other/cites.md", fm_page(
        "Cites", sources="sources: [chapters/guide/guide.md]\n"))

    run_rite("restructure_grimoire", root, "--move", "chapters/guide", "chapters/handbook", "--apply")

    assert "sources: [chapters/handbook/handbook.md]" in (
        root / "chapters/other/cites.md").read_text("utf-8")


def test_plan_counts_match_apply(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/other/cites.md", fm_page(
        "Cites", sources="sources: [chapters/guide/intro.md]\n"))
    args = ("--move", "chapters/guide", "chapters/manual2", "--format", "json")

    plan = json.loads(run_rite("restructure_grimoire", root, *args).stdout)
    apply = json.loads(run_rite("restructure_grimoire", root, *args, "--apply").stdout)

    for key in ("moved", "link_rewrites", "source_rewrites", "files_relinked"):
        assert plan["summary"][key] == apply["summary"][key]
    assert plan["summary"]["applied"] is False and apply["summary"]["applied"] is True


# ---------------------------------------------------------------------------
# Remove: everything that will be deleted is listed
# ---------------------------------------------------------------------------


def test_remove_plan_lists_pages_and_other_files(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/guide/sources/a.pdf", "pdf")
    write(root / "chapters/guide/img/pic.png", "png")

    human = run_rite("restructure_grimoire", root, "--remove", "chapters/guide")
    report = json.loads(run_rite("restructure_grimoire", root, "--remove", "chapters/guide",
                                 "--format", "json").stdout)

    assert human.returncode == 0
    assert "chapters/guide/sources/a.pdf" in human.stdout
    assert "chapters/guide/img/pic.png" in human.stdout
    assert "chapters/guide/manual.md" in human.stdout
    summary = report["summary"]
    assert summary["removed_pages"] == 3
    assert summary["removed_other_files"] == 2
    assert summary["pages"] == ["chapters/guide/guide.md", "chapters/guide/intro.md",
                                "chapters/guide/manual.md"]
    assert summary["other_files"] == ["chapters/guide/img/pic.png", "chapters/guide/sources/a.pdf"]
    assert (root / "chapters/guide/sources/a.pdf").is_file()


def test_remove_skips_an_undecodable_page_and_reports_it(tmp_path):
    root = grimoire(tmp_path)
    (root / "chapters/other/legacy.md").write_bytes(b"caf\xe9\n")

    result = run_rite("restructure_grimoire", root, "--remove", "chapters/guide/intro.md",
                      "--apply", "--format", "json")

    report = json.loads(result.stdout)
    assert result.returncode == 0
    assert report["status"] == "partial"
    assert report["summary"]["skipped"] == ["chapters/other/legacy.md"]


# ---------------------------------------------------------------------------
# repair_links
# ---------------------------------------------------------------------------


def links_grimoire(tmp_path: Path) -> Path:
    root = tmp_path / "g"
    write(root / "chapters/recipes/recipes.md", "# Recipes\n")
    write(root / "chapters/recipes/sourdough.md", "# Sourdough\n")
    write(root / "chapters/recipes/overview.md", "# Overview\n")
    return root


def test_repair_keeps_non_ascii_pages_intact_and_lf(tmp_path):
    root = links_grimoire(tmp_path)
    page = root / "chapters/recipes/jp.md"
    write(page, "日本のパン [[sourdough]]\n")

    result = run_rite("repair_links", root, "--apply")

    assert result.returncode == 0
    assert page.read_bytes() == "日本のパン [[chapters/recipes/sourdough|sourdough]]\n".encode("utf-8")


def test_repair_writes_lf_over_crlf(tmp_path):
    root = links_grimoire(tmp_path)
    page = root / "chapters/recipes/crlf.md"
    page.write_bytes(b"a [[sourdough]]\r\nb\r\n")

    run_rite("repair_links", root, "--apply")

    assert page.read_bytes() == b"a [[chapters/recipes/sourdough|sourdough]]\nb\n"


def test_repair_skips_a_page_that_is_not_utf8_and_continues(tmp_path):
    root = links_grimoire(tmp_path)
    legacy = root / "chapters/recipes/a_legacy.md"
    raw = b"caf\xe9 [[sourdough]]\n"
    legacy.write_bytes(raw)
    good = root / "chapters/recipes/b_good.md"
    write(good, "[[sourdough]]\n")

    result = run_rite("repair_links", root, "--apply", "--format", "json")

    assert result.returncode == 0
    assert legacy.read_bytes() == raw
    assert good.read_text("utf-8") == "[[chapters/recipes/sourdough|sourdough]]\n"
    report = json.loads(result.stdout)
    assert report["status"] == "partial"
    assert report["summary"]["unreadable_pages"] == ["chapters/recipes/a_legacy.md"]
    assert report["summary"]["unreadable"] == 1
    assert report["summary"]["repairs"] == 1


def test_repair_keeps_the_section_and_the_label(tmp_path):
    root = links_grimoire(tmp_path)
    page = root / "chapters/recipes/p.md"
    write(page, "[[sourdough#Starter]] [[sourdough#Starter|the starter]] [[Chapters/Recipes/Sourdough#Starter]]\n")

    run_rite("repair_links", root, "--apply")

    assert page.read_text("utf-8") == (
        "[[chapters/recipes/sourdough#Starter|sourdough]] "
        "[[chapters/recipes/sourdough#Starter|the starter]] "
        "[[chapters/recipes/sourdough#Starter]]\n")


def test_repair_adds_no_label_inside_a_table_row(tmp_path):
    root = links_grimoire(tmp_path)
    page = root / "chapters/recipes/p.md"
    write(page, "| a | b |\n|---|---|\n| [[sourdough]] | x |\n")

    run_rite("repair_links", root, "--apply")

    assert "| [[chapters/recipes/sourdough]] | x |" in page.read_text("utf-8")


def test_repair_never_guesses_from_the_display_label(tmp_path):
    root = links_grimoire(tmp_path)
    page = root / "chapters/recipes/p.md"
    write(page, "[[gone_page|overview]]\n")

    plan = run_rite("repair_links", root, "--format", "json")
    apply = run_rite("repair_links", root, "--apply")

    assert page.read_text("utf-8") == "[[gone_page|overview]]\n"
    report = json.loads(plan.stdout)
    assert report["summary"]["ambiguous"] == 1
    assert report["summary"]["repairs"] == 0
    assert "chapters/recipes/overview.md" in plan.stdout
    assert apply.returncode == 0


def test_repair_leaves_publish_and_source_wrappers_alone(tmp_path):
    root = links_grimoire(tmp_path)
    text = "[[sourdough]]\n"
    for rel in ("publish/content/recipes/x.md", "chapters/recipes/sources/wrap.md",
                "publish/quartz/node_modules/pkg/README.md"):
        write(root / rel, text)

    result = run_rite("repair_links", root, "--apply", "--format", "json")

    assert json.loads(result.stdout)["summary"]["repairs"] == 0
    for rel in ("publish/content/recipes/x.md", "chapters/recipes/sources/wrap.md",
                "publish/quartz/node_modules/pkg/README.md"):
        assert (root / rel).read_text("utf-8") == text


def test_repair_treats_prose_tokens_as_placeholders_only_in_formulae(tmp_path):
    root = links_grimoire(tmp_path)
    write(root / "formulae/page.md", "[[Title]]\n")
    write(root / "chapters/recipes/p.md", "[[Title]]\n")

    report = json.loads(run_rite("repair_links", root, "--format", "json").stdout)

    assert report["summary"]["skipped"] == 1
    assert report["summary"]["unresolvable"] == 1


# ---------------------------------------------------------------------------
# new_page: YAML
# ---------------------------------------------------------------------------


TITLES = ['He said "hi"', "C:\\temp\\new", 'Quote " and back\\slash', "Colon: here", "tab\there",
          "日本のパン", "# hash", "line\nbreak", "ends with backslash\\"]


@pytest.mark.parametrize("title", TITLES)
def test_new_page_writes_valid_yaml_for_any_title(tmp_path, title):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    rel = "chapters/recipes/new_topic.md"

    result = run_rite("new_page", root, "--path", rel, "--type", "concept", "--title", title,
                      "--tags", 'a "quoted" tag,plain', "--apply")

    assert result.returncode == 0, result.stderr
    text = (root / rel).read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    assert fields["type"] == "concept"
    assert fields["last_verified"]
    line = next(l for l in text.splitlines() if l.startswith("title: "))
    assert line == "title: " + json.dumps(title, ensure_ascii=False)
    assert json.loads(line[len("title: "):]) == title
    assert "\r" not in text
    tags_line = next(l for l in text.splitlines() if l.startswith("tags: "))
    assert '"a \\"quoted\\" tag"' in tags_line and "plain" in tags_line


def test_new_page_escapes_sources(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    rel = "chapters/recipes/ext.md"

    result = run_rite("new_page", root, "--path", rel, "--type", "concept", "--title", "Ext",
                      "--authority", "external", "--sources", 'https://example.com/a"b', "--apply")

    assert result.returncode == 0, result.stderr
    assert 'sources: ["https://example.com/a\\"b"]' in (root / rel).read_text("utf-8")


def test_new_page_accepts_the_four_knowledge_types_only(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    for kind in ("concept", "entity", "playbook", "reference"):
        result = run_rite("new_page", root, "--path", f"chapters/recipes/{kind}.md", "--type", kind,
                          "--title", kind)
        assert result.returncode == 0, kind
    for kind in ("hub", "source", "nonsense"):
        result = run_rite("new_page", root, "--path", "chapters/recipes/x.md", "--type", kind,
                          "--title", "x")
        assert result.returncode == 1, kind


# ---------------------------------------------------------------------------
# A non-ASCII path under a single-byte console code page
# ---------------------------------------------------------------------------

LEGACY = {"PYTHONIOENCODING": "cp1252"}


def test_new_page_handles_a_non_ascii_path_under_cp1252(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    rel = "chapters/recipes/日本.md"

    plan = run_rite("new_page", root, "--path", rel, "--type", "concept", "--title", "日本",
                    env=LEGACY)
    apply = run_rite("new_page", root, "--path", rel, "--type", "concept", "--title", "日本",
                     "--apply", env=LEGACY)

    assert plan.returncode == 0, plan.stderr
    assert apply.returncode == 0, apply.stderr
    assert (root / rel).is_file()


def test_restructure_handles_non_ascii_paths_under_cp1252(tmp_path):
    root = grimoire(tmp_path)
    write(root / "chapters/other/日本.md", "[[chapters/guide/intro|Intro]]\n")

    moved = run_rite("restructure_grimoire", root, "--move", "chapters/other/日本.md",
                     "chapters/other/中文.md", "--apply", env=LEGACY)
    removed = run_rite("restructure_grimoire", root, "--remove", "chapters/other/中文.md",
                       "--apply", env=LEGACY)

    assert moved.returncode == 0, moved.stderr
    assert removed.returncode == 0, removed.stderr
    assert not (root / "chapters/other/中文.md").exists()


def test_repair_links_handles_non_ascii_paths_under_cp1252(tmp_path):
    root = links_grimoire(tmp_path)
    write(root / "chapters/recipes/日本.md", "[[sourdough]]\n")

    result = run_rite("repair_links", root, "--apply", env=LEGACY)

    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# The documented flow, end to end
# ---------------------------------------------------------------------------


def test_documented_flow_on_the_fixture_grimoire(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    hub = root / "chapters/recipes/recipes.md"

    added = run_rite("new_page", root, "--path", "chapters/recipes/focaccia.md", "--type", "concept",
                     "--title", "Focaccia", "--apply")
    assert added.returncode == 0, added.stderr
    write(hub, hub.read_text("utf-8") + "- [[focaccia]] - flatbread\n")

    repaired = run_rite("repair_links", root, "--apply")
    assert repaired.returncode == 0, repaired.stdout
    assert "[[chapters/recipes/focaccia|focaccia]]" in hub.read_text("utf-8")

    moved = run_rite("restructure_grimoire", root, "--move", "chapters/recipes", "chapters/baking",
                     "--apply")
    assert moved.returncode == 0, moved.stdout
    assert (root / "chapters/baking/baking.md").is_file()
    assert "[[chapters/baking/baking|recipes]]" in (root / "good_grimoire.md").read_text("utf-8")

    removed = run_rite("restructure_grimoire", root, "--remove", "chapters/baking/focaccia.md",
                       "--apply")
    assert removed.returncode == 0, removed.stdout
    baking = root / "chapters/baking/baking.md"
    write(baking, baking.read_text("utf-8").replace(
        "- [[chapters/baking/focaccia|focaccia]] - flatbread\n", ""))

    validated = subprocess.run(
        [sys.executable, str(RITES / "validate.py"), "--grimoire", str(root), "--summary"],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert validated.returncode == 0, validated.stdout + validated.stderr


# ---------------------------------------------------------------------------
# A grimoire set up for reading on this computer is not changed
# ---------------------------------------------------------------------------

READ_ONLY_TEXT = (
    "this grimoire is set up for reading on this computer, so nothing was changed; "
    "switch it to editing with the grimoire_access rite (--set edit --apply)"
)


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.mark.parametrize("rite,args", [
    ("restructure_grimoire", ("--move", "chapters/guide/intro.md", "chapters/guide/start.md")),
    ("restructure_grimoire", ("--move", "chapters/guide/intro.md", "chapters/guide/start.md", "--apply")),
    ("restructure_grimoire", ("--remove", "chapters/guide/manual.md")),
    ("restructure_grimoire", ("--remove", "chapters/guide/manual.md", "--apply")),
    ("new_page", ("--path", "chapters/guide/fresh.md", "--type", "concept", "--title", "Fresh")),
    ("new_page", ("--path", "chapters/guide/fresh.md", "--type", "concept", "--title", "Fresh", "--apply")),
    ("repair_links", ("--apply",)),
])
def test_a_read_only_grimoire_is_refused_and_left_untouched(tmp_path, library_home, rite, args):
    root = grimoire(tmp_path)
    write(root / "chapters/guide/guide.md", "[[intro]] [[chapters/guide/intro|Intro]]\n")
    library_home(root, access="read")
    before = _tree(root)

    result = run_rite(rite, root, *args, "--format", "json")

    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "blocked"
    assert report["summary"]["access"] == "read"
    assert [(m["severity"], m["message"]) for m in report["messages"]] == [("error", READ_ONLY_TEXT)]
    assert report["mutations"] == []
    assert _tree(root) == before


def test_a_dry_run_of_repair_links_is_allowed_in_a_read_only_grimoire(tmp_path, library_home):
    root = grimoire(tmp_path)
    write(root / "chapters/guide/guide.md", "[[intro]]\n")
    library_home(root, access="read")
    before = _tree(root)

    result = run_rite("repair_links", root, "--format", "json")

    report = json.loads(result.stdout)
    assert report["status"] != "blocked"
    assert report["summary"]["repairs"] == 1
    assert _tree(root) == before


@pytest.mark.parametrize("access", [None, "edit"])
def test_an_editable_registered_grimoire_is_changed_as_before(tmp_path, library_home, access):
    root = grimoire(tmp_path)
    library_home(root, access=access)

    moved = run_rite("restructure_grimoire", root, "--move", "chapters/guide/intro.md",
                     "chapters/guide/start.md", "--apply", "--format", "json")
    created = run_rite("new_page", root, "--path", "chapters/guide/fresh.md", "--type", "concept",
                       "--title", "Fresh", "--apply", "--format", "json")

    assert moved.returncode == 0 and json.loads(moved.stdout)["status"] == "ok"
    assert created.returncode == 0 and json.loads(created.stdout)["status"] == "ok"
    assert (root / "chapters/guide/start.md").is_file() and (root / "chapters/guide/fresh.md").is_file()
