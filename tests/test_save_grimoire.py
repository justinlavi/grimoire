"""save_grimoire.py validates, commits, rebases, and pushes a grimoire."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RITE = REPO_ROOT / "rites" / "save_grimoire.py"
GOOD = Path(__file__).parent / "fixtures" / "good_grimoire"


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return proc.stdout


def _identity(root: Path) -> None:
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Tester")


def _shared_setup(tmp_path: Path):
    """A bare remote plus two clones (alice, bob) of the good fixture."""
    seed = tmp_path / "seed"
    shutil.copytree(GOOD, seed)
    _git(seed, "init", "-q", "-b", "main")
    _identity(seed)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "scaffold")
    bare = tmp_path / "remote.git"
    _git(seed, "clone", "-q", "--bare", str(seed), str(bare))
    # The root hub is <directory>.md, so each clone keeps the fixture's name.
    alice = tmp_path / "alice" / "good_grimoire"
    bob = tmp_path / "bob" / "good_grimoire"
    alice.parent.mkdir()
    bob.parent.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare), str(alice)], check=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(bob)], check=True)
    _identity(alice)
    _identity(bob)
    return bare, alice, bob


def _run(root: Path, *extra: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(RITE), "--grimoire", str(root), "--format", "json", *extra],
        capture_output=True, text=True, timeout=600,
    )
    return {"returncode": result.returncode, "report": json.loads(result.stdout), "stderr": result.stderr}


def _add_page(root: Path, slug: str, title: str) -> Path:
    page = root / "chapters" / "recipes" / f"{slug}.md"
    page.write_text(
        f"---\ntype: concept\ntitle: \"{title}\"\ntags: [chapter/recipes, type/concept]\n"
        f"authority: grimoire\nlast_verified: 2026-11-11\n---\n\n# {title}\n",
        encoding="utf-8", newline="\n",
    )
    hub = root / "chapters" / "recipes" / "recipes.md"
    hub.write_text(hub.read_text(encoding="utf-8") + f"- {title} -> [[chapters/recipes/{slug}|{slug}]]\n", encoding="utf-8", newline="\n")
    return page


def test_plan_lists_changes_and_writes_nothing(tmp_path):
    _, alice, _ = _shared_setup(tmp_path)
    _add_page(alice, "focaccia", "Focaccia")

    out = _run(alice, "--no-fetch")
    report = out["report"]

    assert out["returncode"] == 0
    assert report["mode"] == "plan"
    assert report["status"] == "noop"
    assert report["mutations"] == []
    paths = {c["path"] for c in report["summary"]["changes"]}
    assert "chapters/recipes/focaccia.md" in paths
    assert report["summary"]["upstream"] == "origin/main"
    assert _git(alice, "status", "--porcelain").strip() != ""  # still unsaved


def test_nothing_to_save_is_noop(tmp_path):
    _, alice, _ = _shared_setup(tmp_path)
    out = _run(alice, "--apply", "--message", "x")
    assert out["returncode"] == 0
    assert out["report"]["status"] == "noop"


def test_apply_commits_and_pushes(tmp_path):
    bare, alice, bob = _shared_setup(tmp_path)
    _add_page(alice, "focaccia", "Focaccia")

    out = _run(alice, "--apply", "--message", "Add focaccia page")
    report = out["report"]

    assert out["returncode"] == 0, out
    assert report["status"] == "ok"
    assert [m["action"] for m in report["mutations"]] == ["commit", "push"]
    assert report["summary"]["pushed"] is True
    assert "Add focaccia page" in _git(bare, "log", "--oneline", "-1")
    assert _git(alice, "status", "--porcelain").strip() == ""

    # Bob receives it with a plain pull: the push was a normal fast-forward.
    _git(bob, "pull", "-q", "--ff-only")
    assert (bob / "chapters" / "recipes" / "focaccia.md").is_file()


def test_apply_refuses_when_validation_fails(tmp_path):
    _, alice, _ = _shared_setup(tmp_path)
    page = _add_page(alice, "broken", "Broken")
    page.write_text(page.read_text(encoding="utf-8") + "\nSee [[chapters/nope/missing|missing]].\n", encoding="utf-8")

    out = _run(alice, "--apply", "--message", "Add broken page", "--no-fetch")
    report = out["report"]

    assert out["returncode"] == 1
    assert report["status"] == "blocked"
    assert any("validation failed" in m["message"] for m in report["messages"])
    assert _git(alice, "log", "--oneline").count("\n") == 1  # only the scaffold commit


def _conflict(tmp_path):
    """Bob shares a hub edit first; Alice edits the same spot and saves."""
    bare, alice, bob = _shared_setup(tmp_path)
    hub = "chapters/recipes/recipes.md"
    (bob / hub).write_text((bob / hub).read_text(encoding="utf-8") + "- Bob's line\n", encoding="utf-8", newline="\n")
    _git(bob, "add", "-A")
    _git(bob, "commit", "-q", "-m", "Bob edits hub")
    _git(bob, "push", "-q")
    (alice / hub).write_text((alice / hub).read_text(encoding="utf-8") + "- Alice's line\n", encoding="utf-8", newline="\n")
    return bare, alice, hub, _run(alice, "--apply", "--message", "Alice edits hub")


def test_conflict_names_the_pages_and_records_the_work_locally(tmp_path):
    bare, alice, hub, out = _conflict(tmp_path)
    report = out["report"]

    assert out["returncode"] == 1
    assert report["status"] == "blocked"
    message = next(m["message"] for m in report["messages"] if m["severity"] == "error")
    assert hub in message and "recorded on this computer" in message and "<<<<<<<" in message
    assert [m["action"] for m in report["mutations"]] == ["commit"]  # committed locally, not pushed
    assert report["summary"]["pushed"] is False
    assert "Bob edits hub" in _git(bare, "log", "--oneline", "-1")
    assert "<<<<<<<" in (alice / hub).read_text(encoding="utf-8")  # the page waits for the person


def test_second_save_with_markers_still_in_the_page_names_it_and_stops(tmp_path):
    _, alice, hub, _ = _conflict(tmp_path)

    again = _run(alice, "--apply", "--message", "again")

    assert again["returncode"] == 1 and again["report"]["status"] == "blocked"
    assert any(hub in m["message"] and "same lines" in m["message"] for m in again["report"]["messages"])


def test_save_after_the_conflict_is_resolved_continues_and_pushes(tmp_path):
    bare, alice, hub, _ = _conflict(tmp_path)
    kept = [
        line for line in (alice / hub).read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
    ]
    (alice / hub).write_text("".join(kept), encoding="utf-8", newline="\n")

    plan = _run(alice, "--no-fetch")
    assert plan["returncode"] == 0, plan

    saved = _run(alice, "--apply", "--message", "ignored")
    report = saved["report"]
    assert saved["returncode"] == 0, saved
    assert report["summary"]["pushed"] is True
    assert report["summary"]["commit"] == _git(alice, "rev-parse", "--short", "HEAD").strip()
    assert not (alice / ".git" / "rebase-merge").exists()
    pushed = _git(bare, "show", "HEAD:" + hub)
    assert "Bob's line" in pushed and "Alice's line" in pushed and "<<<<<<<" not in pushed
    assert _git(alice, "status", "--porcelain").strip() == ""


def test_commit_reported_is_the_one_on_the_branch_after_the_rebase(tmp_path):
    _, alice, bob = _shared_setup(tmp_path)
    (bob / "chapters" / "recipes" / "sources").mkdir(exist_ok=True)
    (bob / "chapters" / "recipes" / "sources" / "ciabatta.txt").write_text("notes\n", encoding="utf-8", newline="\n")
    _git(bob, "add", "-A")
    _git(bob, "commit", "-q", "-m", "Bob adds ciabatta")
    _git(bob, "push", "-q")
    _add_page(alice, "focaccia", "Focaccia")

    out = _run(alice, "--apply", "--message", "Add focaccia page")

    assert out["returncode"] == 0, out
    head = _git(alice, "rev-parse", "--short", "HEAD").strip()
    assert out["report"]["summary"]["commit"] == head
    assert out["report"]["mutations"][0]["detail"].startswith(head)


def test_unreadable_git_state_blocks_instead_of_reporting_nothing_to_save(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    (root / ".git").mkdir()  # not a repository: `git status` fails

    out = _run(root, "--no-fetch")

    assert out["returncode"] == 1 and out["report"]["status"] == "blocked"
    assert any("git cannot read" in m["message"] for m in out["report"]["messages"])


def test_non_ascii_and_spaced_page_names_are_listed_as_they_are_on_disk(tmp_path):
    _, alice, _ = _shared_setup(tmp_path)
    for name in ("日本.md", "my page.md"):
        (alice / "chapters" / "recipes" / name).write_text("# page\n", encoding="utf-8", newline="\n")

    out = _run(alice, "--no-fetch")

    paths = {c["path"] for c in out["report"]["summary"]["changes"]}
    assert {"chapters/recipes/日本.md", "chapters/recipes/my page.md"} <= paths


def test_validation_verdict_comes_from_the_json_report_not_from_prose(monkeypatch, tmp_path):
    import save_grimoire

    def fake_run(stdout, code):
        return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=stdout, stderr="")

    passing = json.dumps({"status": "pass", "reports": [{"validator": "v", "returncode": 0, "diagnostics": [
        {"severity": "warning", "message": "an earlier run FAILED here"}]}]})
    monkeypatch.setattr(save_grimoire.subprocess, "run", fake_run(passing, 0))
    assert save_grimoire.validation_passes(tmp_path)[0] is True

    failing = json.dumps({"status": "fail", "reports": [{"validator": "validate_links", "returncode": 1, "diagnostics": [
        {"severity": "error", "message": "broken link"}]}]})
    monkeypatch.setattr(save_grimoire.subprocess, "run", fake_run(failing, 1))
    passed, detail = save_grimoire.validation_passes(tmp_path)
    assert passed is False and "validate_links: broken link" in detail


def test_not_a_git_repository_is_blocked(tmp_path):
    root = tmp_path / "g"
    shutil.copytree(GOOD, root)
    out = _run(root)
    assert out["returncode"] == 1
    assert out["report"]["status"] == "blocked"
    assert any("not a git repository" in m["message"] for m in out["report"]["messages"])


def test_abandon_ends_a_paused_save_and_keeps_the_recorded_work(tmp_path):
    bare, alice, hub, out = _conflict(tmp_path)
    recorded = out["report"]["summary"]["commit"]
    assert "<<<<<<<" in (alice / hub).read_text(encoding="utf-8")

    ended = _run(alice, "--abandon")

    assert ended["returncode"] == 0, ended
    assert [m["action"] for m in ended["report"]["mutations"]] == ["abandon"]
    assert ended["report"]["summary"]["commit"] == recorded
    assert "<<<<<<<" not in (alice / hub).read_text(encoding="utf-8")  # the recorded version is back
    assert not (alice / ".git" / "rebase-merge").exists()
    assert _git(alice, "rev-parse", "--short", "HEAD").strip() == recorded
    assert "Bob edits hub" in _git(bare, "log", "--oneline", "-1")  # nothing was sent


def test_abandon_with_no_paused_save_changes_nothing(tmp_path):
    _, alice = _shared_setup(tmp_path)[:2]
    before = _git(alice, "rev-parse", "HEAD")
    out = _run(alice, "--abandon")
    assert out["returncode"] == 0 and out["report"]["status"] == "noop"
    assert out["report"]["mutations"] == []
    assert _git(alice, "rev-parse", "HEAD") == before


def test_a_grimoire_set_up_for_reading_is_never_saved(tmp_path, library_home):
    _bare, alice, _bob = _shared_setup(tmp_path)
    library_home(alice, access="read")
    _add_page(alice, "extra", "Extra")
    head = _git(alice, "rev-parse", "HEAD")
    refusal = (
        "this grimoire is set up for reading on this computer, so nothing was changed; "
        "switch it to editing with the grimoire_access rite (--set edit --apply)"
    )
    for extra in ((), ("--apply", "--message", "x"), ("--abandon",), ("--apply", "--abandon")):
        out = _run(alice, *extra)
        assert out["returncode"] == 1, extra
        assert out["report"]["status"] == "blocked"
        assert out["report"]["summary"]["access"] == "read"
        assert [(m["severity"], m["message"]) for m in out["report"]["messages"]] == [("error", refusal)]
        assert out["report"]["mutations"] == []
    assert _git(alice, "rev-parse", "HEAD") == head
    assert "extra" in _git(alice, "status", "--porcelain")


def test_a_grimoire_set_up_for_editing_saves_as_before(tmp_path, library_home):
    _bare, alice, _bob = _shared_setup(tmp_path)
    library_home(alice, access="edit")
    _add_page(alice, "extra", "Extra")
    out = _run(alice, "--apply", "--message", "add extra")
    assert out["returncode"] == 0, out
    assert out["report"]["summary"]["pushed"] is True
    assert "access" not in out["report"]["summary"]
