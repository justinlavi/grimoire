"""Tests for the branch-aware, pull-before-heal grimoire update rite.

The git seam, heal, and re-validate subprocesses are injected so the suite stays
offline and deterministic. The load-bearing property under test is the
heal-eligibility gate: a grimoire that could not be brought current is never
validated-and-modified.
"""

from pathlib import Path

import pytest

import summon_core
import summon_state as S
import update_grimoires as U

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fake git seam: map a git subcommand (by a distinguishing arg substring) to
# its (returncode, stdout, stderr). Anything unspecified returns success/empty.
# ---------------------------------------------------------------------------


def make_git(responses):
    def git(*args, cwd=None):
        argstr = " ".join(str(a) for a in args)
        for key, resp in responses.items():
            if key in argstr:
                return resp
        return (0, "", "")
    return git


_UP_TO_DATE = {
    "symbolic-ref": (0, "main", ""),
    "rev-parse --abbrev-ref": (0, "origin/main", ""),
    "status --porcelain": (0, "", ""),
    "fetch": (0, "", ""),
    "rev-list": (0, "0\t0", ""),
}


def _git(**overrides):
    table = dict(_UP_TO_DATE)
    table.update(overrides)
    return make_git(table)


def _repo(tmp_path, name="g"):
    d = tmp_path / name
    (d / ".git").mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# git_capture seam + error classification
# ---------------------------------------------------------------------------


def test_git_capture_returns_three_tuple():
    rc, out, err = summon_core.git_capture("--version")
    assert rc == 0
    assert "git version" in out
    assert isinstance(err, str)


@pytest.mark.parametrize("stderr,expected", [
    ("remote: HTTP 403 ... The requested URL returned error: 403", "auth_failed"),
    ("remote: insufficient_scope", "auth_failed"),
    ("fatal: Authentication failed for 'https://host/x.git'", "auth_failed"),
    ("fatal: unable to access 'https://h/': Could not resolve host: h", "offline"),
    ("ssh: connect to host h port 22: Connection timed out", "offline"),
    ("fatal: something unexpected went wrong", "fetch_error"),
])
def test_classify_fetch_error(stderr, expected):
    assert U.classify_fetch_error(stderr) == expected


# ---------------------------------------------------------------------------
# Classification ladder
# ---------------------------------------------------------------------------


def test_missing_local_and_not_a_repo(tmp_path):
    missing = U.classify_grimoire(tmp_path / "nope", fetch=True, git=_git())
    assert missing["status"] == "missing_local"
    plain = tmp_path / "plain"
    plain.mkdir()
    shared = U.classify_grimoire(plain, fetch=True, git=_git(), host="git.example.com")
    assert shared["status"] == "not_a_repo"


def test_detached_and_no_upstream(tmp_path):
    d = _repo(tmp_path)
    assert U.classify_grimoire(d, fetch=True, git=_git(**{"symbolic-ref": (1, "", "")}))["status"] == "detached"
    no_up = U.classify_grimoire(d, fetch=True, git=_git(**{
        "rev-parse --abbrev-ref": (1, "", "no upstream"),
        "remote": (0, "origin", ""),
    }))
    assert no_up["status"] == "no_upstream"


def test_a_plain_folder_with_no_shared_copy_is_local_only(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    rec = U.classify_grimoire(plain, fetch=True, git=_git())
    assert rec["status"] == "local_only"
    assert rec["reason"] == U.LOCAL_ONLY_REASON


def test_a_repository_with_no_remote_is_local_only_even_when_dirty(tmp_path):
    d = _repo(tmp_path)
    rec = U.classify_grimoire(d, fetch=True, git=_git(**{
        "rev-parse --abbrev-ref": (1, "", "no upstream"),
        "status --porcelain": (0, " M page.md", ""),
    }))
    assert rec["status"] == "local_only"


def test_a_local_only_grimoire_is_healed_and_is_not_drift(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    healed = []

    def heal(local_path, framework_root):
        healed.append(local_path)
        return {"status": "ok"}

    rec = U.process_grimoire(
        "plain", {"local_path": str(plain)}, REPO_ROOT, apply=True, git=_git(),
        heal_fn=heal, revalidate_fn=lambda framework_root, local_path: (True, ""),
    )
    assert rec["status"] == "local_only"
    assert rec["heal_eligible"] is True
    assert healed == [plain.resolve()]
    assert rec["heal"]["status"] == "ok"
    assert S._grimoire_drift({"grimoires": [rec]}) is False


def test_dirty_tree_skips_before_fetch(tmp_path):
    d = _repo(tmp_path)
    rec = U.classify_grimoire(d, fetch=True, git=_git(**{"status --porcelain": (0, " M README.md", "")}))
    assert rec["status"] == "dirty"


@pytest.mark.parametrize("revlist,status,behind,ahead", [
    ("0\t0", "up_to_date", 0, 0),
    ("3\t0", "behind", 3, 0),
    ("0\t2", "ahead", 0, 2),
    ("2\t3", "diverged", 2, 3),
])
def test_ahead_behind_classification(tmp_path, revlist, status, behind, ahead):
    d = _repo(tmp_path)
    rec = U.classify_grimoire(d, fetch=True, git=_git(**{"rev-list": (0, revlist, "")}))
    assert rec["status"] == status
    assert rec["behind"] == behind and rec["ahead"] == ahead


def test_auth_failed_sets_creds_present(tmp_path):
    d = _repo(tmp_path)
    git = _git(**{"fetch": (1, "", "remote: HTTP 403 insufficient_scope")})
    rec = U.classify_grimoire(d, fetch=True, git=git, credential_probe=lambda host: "", host="gitlab.example")
    assert rec["status"] == "auth_failed"
    assert rec["creds_present"] is False


def test_fetch_false_is_offline(tmp_path):
    d = _repo(tmp_path)
    calls = []

    def git(*args, cwd=None):
        calls.append(args)  # token tuple, not a joined string (the tmp path contains "fetch")
        argstr = " ".join(str(a) for a in args)
        return _UP_TO_DATE.get(next((k for k in _UP_TO_DATE if k in argstr), ""), (0, "0\t0", ""))

    U.classify_grimoire(d, fetch=False, git=git)
    assert not any("fetch" in args for args in calls)  # no network when fetch=False


# ---------------------------------------------------------------------------
# Fast-forward
# ---------------------------------------------------------------------------


def test_bring_current_fast_forwards(tmp_path):
    d = _repo(tmp_path)
    rec = {"status": "behind", "behind": 3}
    U.bring_current(d, rec, git=_git(**{"pull --ff-only": (0, "", "")}))
    assert rec["status"] == "fast_forwarded" and rec["behind"] == 0


def test_bring_current_blocked(tmp_path):
    d = _repo(tmp_path)
    rec = {"status": "behind", "behind": 3}
    U.bring_current(d, rec, git=_git(**{"pull --ff-only": (1, "", "fatal: Not possible to fast-forward")}))
    assert rec["status"] == "behind_blocked"


# ---------------------------------------------------------------------------
# The heal-eligibility gate (the load-bearing invariant)
# ---------------------------------------------------------------------------


class HealSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, local_path, framework_root):
        self.calls.append(str(local_path))
        return {"status": "ok", "scaffold_synced": [], "readme_block": "unchanged", "messages": []}


def _process(tmp_path, git, *, apply, heal):
    d = _repo(tmp_path)
    entry = {"local_path": str(d), "online_path": "https://h/g.git"}
    return U.process_grimoire("g", entry, REPO_ROOT, apply=apply, git=git,
                              heal_fn=heal, revalidate_fn=lambda a, l: (True, "ok"))


def test_heal_runs_only_for_current_grimoire(tmp_path):
    heal = HealSpy()
    rec = _process(tmp_path, _git(), apply=True, heal=heal)  # up_to_date
    assert rec["heal_eligible"] is True
    assert heal.calls == [rec["local_path"]]


@pytest.mark.parametrize("override,status", [
    ({"status --porcelain": (0, " M x", "")}, "dirty"),
    ({"rev-list": (0, "2\t3", "")}, "diverged"),
    ({"symbolic-ref": (1, "", "")}, "detached"),
    ({"fetch": (1, "", "Could not resolve host: h")}, "offline"),
])
def test_heal_never_runs_for_non_current(tmp_path, override, status):
    heal = HealSpy()
    rec = _process(tmp_path, _git(**override), apply=True, heal=heal)
    assert rec["status"] == status
    assert rec["heal_eligible"] is False
    assert heal.calls == []  # a tree that is not current is never modified


def test_plan_mode_never_heals(tmp_path):
    heal = HealSpy()
    rec = _process(tmp_path, _git(), apply=False, heal=heal)  # up_to_date but plan
    assert rec["heal_eligible"] is True
    assert heal.calls == []
    assert rec["heal"]["status"] == "planned"


def test_behind_is_pulled_then_healed(tmp_path):
    heal = HealSpy()
    git = _git(**{"rev-list": (0, "3\t0", ""), "pull --ff-only": (0, "", "")})
    rec = _process(tmp_path, git, apply=True, heal=heal)
    assert rec["status"] == "fast_forwarded" and rec["pulled"] is True
    assert heal.calls == [rec["local_path"]]


def test_relocate_root_sources_moves_single_package_citations(tmp_path):
    grimoire = tmp_path / "g"
    page = grimoire / "chapters/recipes/sourdough.md"
    source = grimoire / "sources/article.pdf"
    page.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "type: concept\n"
        'title: "Sourdough"\n'
        "tags: [type/concept]\n"
        "authority: external\n"
        'sources: ["sources/article.pdf"]\n'
        "last_verified: 2026-05-25\n"
        "---\n\n"
        "# Sourdough\n",
        encoding="utf-8",
    )
    source.write_bytes(b"%PDF-1.4\n")
    (grimoire / "sources/.gitkeep").write_text("", encoding="utf-8")

    result = U.relocate_root_sources(grimoire)

    new_source = grimoire / "chapters/recipes/sources/article.pdf"
    assert result["status"] == "removed"
    assert result["moved"] == [
        {"from": "sources/article.pdf", "to": "chapters/recipes/sources/article.pdf"}
    ]
    assert new_source.is_file()
    assert not (grimoire / "sources").exists()
    assert 'sources: ["chapters/recipes/sources/article.pdf"]' in page.read_text(encoding="utf-8")


def test_relocate_root_sources_leaves_ambiguous_citations(tmp_path):
    grimoire = tmp_path / "g"
    source = grimoire / "sources/article.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4\n")
    for rel in ("chapters/recipes/sourdough.md", "chapters/techniques/lamination.md"):
        page = grimoire / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "---\n"
            "type: concept\n"
            'title: "Page"\n'
            "tags: [type/concept]\n"
            "authority: external\n"
            'sources: ["sources/article.pdf"]\n'
            "last_verified: 2026-05-25\n"
            "---\n\n"
            "# Page\n",
            encoding="utf-8",
        )

    result = U.relocate_root_sources(grimoire)

    assert result["status"] == "left_for_review"
    assert result["moved"] == []
    assert result["left_for_review"] == ["sources/article.pdf"]
    assert source.is_file()


# ---------------------------------------------------------------------------
# Library-wide processing + manual-pull fallback
# ---------------------------------------------------------------------------


def test_process_all_summary_and_needs_manual_pull(tmp_path):
    a = _repo(tmp_path, "a-grimoire")
    b = _repo(tmp_path, "b-grimoire")
    library = {"grimoires": {
        "a-grimoire": {"local_path": str(a), "online_path": "https://pub/a.git"},
        "b-grimoire": {"local_path": str(b), "online_path": "https://private/b.git"},
    }}

    def git(*args, cwd=None):
        argstr = " ".join(str(x) for x in args)
        if str(b) in argstr and "fetch" in argstr:
            return (1, "", "remote: HTTP 403 insufficient_scope")
        for key, resp in _UP_TO_DATE.items():
            if key in argstr:
                return resp
        return (0, "", "")

    result = U.process_all(tmp_path, REPO_ROOT, apply=True, library=library, git=git,
                           heal_fn=HealSpy(), revalidate_fn=lambda a, l: (True, "ok"))
    s = result["summary"]
    assert s["total"] == 2
    assert s["already_current"] == 1          # a is up_to_date
    assert s["needs_manual_pull"] == 1        # b auth_failed
    assert [n["key"] for n in result["needs_manual_pull"]] == ["b-grimoire"]
    assert result["needs_manual_pull"][0]["status"] == "auth_failed"
    assert result["needs_manual_pull"][0]["suggested_command"].startswith("git -C")


# ---------------------------------------------------------------------------
# README update-block injector
# ---------------------------------------------------------------------------


BLOCK = "<!-- BEGIN GRIMOIRE UPDATE -->\n## Out of date? Update.\nbody\n<!-- END GRIMOIRE UPDATE -->"


def _write(tmp_path, text):
    p = tmp_path / "README.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_injector_inserts_before_first_heading(tmp_path):
    p = _write(tmp_path, "# G\n\nintro\n\n## Installation\n\nsteps\n")
    assert U.inject_update_readme_block(p, BLOCK) is True
    out = p.read_text(encoding="utf-8")
    assert out.count(U.UPDATE_BEGIN) == 1
    assert out.index(U.UPDATE_BEGIN) < out.index("## Installation")


def test_injector_is_idempotent(tmp_path):
    p = _write(tmp_path, "# G\n\nintro\n\n## Installation\n")
    U.inject_update_readme_block(p, BLOCK)
    once = p.read_text(encoding="utf-8")
    assert U.inject_update_readme_block(p, BLOCK) is False
    assert p.read_text(encoding="utf-8") == once


def test_injector_replaces_block_in_place(tmp_path):
    p = _write(tmp_path, f"# G\n\nintro\n\n{U.UPDATE_BEGIN}\nstale body\n{U.UPDATE_END}\n\n## Installation\n")
    assert U.inject_update_readme_block(p, BLOCK) is True
    out = p.read_text(encoding="utf-8")
    assert out.count(U.UPDATE_BEGIN) == 1
    assert "stale body" not in out


def test_relocate_root_sources_removes_only_scaffold_files(tmp_path):
    root_sources = tmp_path / "sources"
    root_sources.mkdir()
    (root_sources / "README.md").write_text("# Sources\n", encoding="utf-8")
    (root_sources / ".gitkeep").write_text("", encoding="utf-8")

    result = U.relocate_root_sources(tmp_path)
    assert result["status"] == "removed"
    assert result["moved"] == []
    assert not root_sources.exists()


def test_relocate_root_sources_leaves_uncited_artifacts_for_review(tmp_path):
    root_sources = tmp_path / "sources"
    root_sources.mkdir()
    (root_sources / "artifact.pdf").write_bytes(b"%PDF-1.4\n")

    result = U.relocate_root_sources(tmp_path)
    assert result["status"] == "left_for_review"
    assert result["left_for_review"] == ["sources/artifact.pdf"]
    assert (root_sources / "artifact.pdf").is_file()


# ---------------------------------------------------------------------------
# Orchestration: reconcile(pull_grimoires=True) runs grimoires before skills
# ---------------------------------------------------------------------------


def test_reconcile_runs_grimoire_step_before_skills(tmp_path):
    home = tmp_path / "grimoires"
    home.mkdir()
    order = []

    def fake_processor(h, a, *, apply, fetch):
        order.append("grimoires")
        return {"grimoires": [], "needs_manual_pull": [],
                "summary": {"total": 0, "already_current": 0, "brought_current": 0,
                            "ahead": 0, "healed": 0, "heal_skipped": 0, "needs_manual_pull": 0}}

    def fake_skill_runner(script):
        order.append("skills")
        return (0, "ok")

    result = S.reconcile(
        home, REPO_ROOT, apply=True, pull_grimoires=True,
        instruction_targets=[], skill_targets=[],
        git_fn=lambda *a, **k: (False, ""),
        skill_runner=fake_skill_runner,
        validate_runner=lambda r: (True, "ok"),
        grimoire_processor=fake_processor,
    )
    assert order == ["grimoires", "skills"]            # pull before re-register
    assert result["grimoires"] is not None
    assert any(step["id"] == "grimoires" for step in result["steps"])


# ---------------------------------------------------------------------------
# A copy set up for reading is brought current and never rewritten
# ---------------------------------------------------------------------------


def _reader(tmp_path, git, *, apply, heal, access="read"):
    d = _repo(tmp_path)
    entry = {"local_path": str(d), "online_path": "https://h/g.git"}
    if access is not None:
        entry["access"] = access
    revalidate_calls = []

    def revalidate(framework_root, local_path):
        revalidate_calls.append(str(local_path))
        return True, "ok"

    rec = U.process_grimoire("g", entry, REPO_ROOT, apply=apply, git=git, heal_fn=heal, revalidate_fn=revalidate)
    return rec, revalidate_calls


@pytest.mark.parametrize("access,expected", [("read", "read"), ("edit", "edit"), (None, "edit"), ("other", "edit")])
def test_every_record_names_its_access(tmp_path, access, expected):
    rec, _ = _reader(tmp_path, _git(), apply=False, heal=HealSpy(), access=access)
    assert rec["access"] == expected


def test_a_read_only_copy_is_never_healed_or_revalidated(tmp_path):
    heal = HealSpy()
    rec, revalidated = _reader(tmp_path, _git(), apply=True, heal=heal)  # up to date
    assert rec["status"] == "up_to_date"
    assert rec["heal_eligible"] is False
    assert rec["heal"] == {"status": "not_applicable",
                           "reason": "read-only copy; its managed files come from the shared copy"}
    assert heal.calls == [] and revalidated == []


def test_a_behind_read_only_copy_is_fast_forwarded_and_still_not_healed(tmp_path):
    heal = HealSpy()
    git = _git(**{"rev-list": (0, "3\t0", ""), "pull --ff-only": (0, "", "")})
    rec, revalidated = _reader(tmp_path, git, apply=True, heal=heal)
    assert rec["status"] == "fast_forwarded" and rec["pulled"] is True
    assert rec["heal"]["status"] == "not_applicable"
    assert heal.calls == [] and revalidated == []


def test_a_read_only_copy_is_classified_the_same_in_a_plan(tmp_path):
    rec, _ = _reader(tmp_path, _git(**{"rev-list": (0, "3\t0", "")}), apply=False, heal=HealSpy())
    assert rec["status"] == "behind" and rec["pulled"] is False
    assert rec["heal"]["status"] == "not_applicable"


def test_a_dirty_read_only_copy_says_how_to_proceed(tmp_path):
    rec, _ = _reader(tmp_path, _git(**{"status --porcelain": (0, " M x", "")}), apply=True, heal=HealSpy())
    assert rec["status"] == "dirty"
    assert rec["reason"] == ("local changes in a read-only copy; switch it to editing and save them, "
                             "or discard them, then update")
    assert rec["heal"]["status"] == "not_applicable"


def test_a_dirty_editable_copy_keeps_the_general_reason(tmp_path):
    rec, _ = _reader(tmp_path, _git(**{"status --porcelain": (0, " M x", "")}), apply=True, heal=HealSpy(), access="edit")
    assert "read-only" not in rec["reason"]


def test_not_applicable_is_nothing_to_report():
    record = {"key": "g", "heal": {"status": "not_applicable", "reason": "read-only copy"}}
    assert U.heal_wrote(record) is False
    assert U.heal_finding(record) is None
    assert U.needs_attention({"grimoires": [record]}) is False


def test_the_summary_counts_read_only_copies_apart_from_skipped_heals(tmp_path):
    a = _repo(tmp_path, "a-grimoire")
    b = _repo(tmp_path, "b-grimoire")
    c = _repo(tmp_path, "c-grimoire")
    library = {"grimoires": {
        "a-grimoire": {"local_path": str(a), "online_path": "https://h/a.git", "access": "read"},
        "b-grimoire": {"local_path": str(b), "online_path": "https://h/b.git"},
        "c-grimoire": {"local_path": str(c), "online_path": "https://h/c.git"},
    }}

    def git(*args, cwd=None):
        argstr = " ".join(str(x) for x in args)
        if str(c) in argstr and "status --porcelain" in argstr:
            return (0, " M x", "")
        for key, resp in _UP_TO_DATE.items():
            if key in argstr:
                return resp
        return (0, "", "")

    heal = HealSpy()
    result = U.process_all(tmp_path, REPO_ROOT, apply=True, library=library, git=git,
                           heal_fn=heal, revalidate_fn=lambda a, l: (True, "ok"))

    assert result["summary"]["read_only"] == 1
    assert result["summary"]["heal_skipped"] == 1   # c is dirty and editable; a is read-only
    assert result["summary"]["healed"] == 1          # b
    assert heal.calls == [result["grimoires"][1]["local_path"]]


def test_human_output_marks_a_read_only_copy(tmp_path, capsys):
    rec, _ = _reader(tmp_path, _git(), apply=False, heal=HealSpy())
    result = {"grimoires": [rec], "needs_manual_pull": [], "warnings": [],
              "summary": {"total": 1, "already_current": 1, "brought_current": 0, "ahead": 0, "local_only": 0,
                          "healed": 0, "needs_check": 0, "heal_skipped": 0, "read_only": 1, "needs_manual_pull": 0}}
    U._print_human(result, apply=False)
    assert "g: up_to_date (read-only)" in capsys.readouterr().out


def test_the_grimoire_step_is_not_drift_when_only_read_only_copies_were_not_healed(tmp_path):
    rec, _ = _reader(tmp_path, _git(), apply=True, heal=HealSpy())
    summary = {"total": 1, "already_current": 1, "brought_current": 0, "ahead": 0, "local_only": 0,
               "healed": 0, "needs_check": 0, "heal_skipped": 0, "read_only": 1, "needs_manual_pull": 0}
    reporter = U.ResultReporter("update_grimoires")
    step = S._grimoire_step({"grimoires": [rec], "needs_manual_pull": [], "summary": summary}, reporter=reporter)
    assert step["status"] == "noop"
    assert reporter.messages == []


def test_the_state_report_marks_a_read_only_copy(tmp_path, capsys):
    rec, _ = _reader(tmp_path, _git(), apply=False, heal=HealSpy())
    grimoires = {"grimoires": [rec], "needs_manual_pull": [], "warnings": [], "summary": {}}
    state = {"framework": {"working_tree_populated": True, "root": "/f"},
             "library": {"in_sync": True}, "agent_targets": [], "skills": []}
    S._print_human("update", state, [], False, None, grimoires=grimoires)
    assert "up_to_date (read-only)" in capsys.readouterr().out
