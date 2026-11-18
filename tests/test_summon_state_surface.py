"""summon_state: stale and plugin-served routing blocks, agents that are not installed,
an unreadable library, the skill-sync report in the envelope, and printed commands."""

import json
import types
from pathlib import Path

import pytest

import summon_core
import summon_state as S

REPO_ROOT = Path(__file__).resolve().parent.parent
NO_GIT = lambda *a, **k: (False, "")
OK_VALIDATE = lambda root: (True, "ok")
CANONICAL = summon_core.canonical_routing_block()
BLOCK = f"# Title\n{CANONICAL}\n"
STALE = f"# Title\n{summon_core.BEGIN_SENTINEL}\nold\n{summon_core.END_SENTINEL}\n"

SYNC_REPORT = {
    "summary": {"registered": 5, "cleaned": 2, "reset": 3, "blocked": 0},
    "messages": [
        {"severity": "warning", "message": "cook: skipped /cook-x (wrong name)", "path": None},
        {"severity": "error", "message": "collision /grm-add", "path": None},
    ],
}


def _home(tmp_path, grimoire=False):
    home = tmp_path / "grimoires"
    home.mkdir()
    if grimoire:
        (home / "g").mkdir()
        (home / "g" / "grimoire.json").write_text(json.dumps({"name": "g", "skill_prefix": "gg"}), encoding="utf-8")
    return home


def _agent(tmp_path, content=None, *, served=False, name="CLAUDE.md"):
    path = tmp_path / name
    if content is not None:
        path.write_text(content, encoding="utf-8")
    return [{"id": "claude", "label": "Claude", "path": str(path), "title": name,
             "plugin_serves_routing": served}]


def _skills(tmp_path, registered=1):
    folder = tmp_path / "skills"
    folder.mkdir(exist_ok=True)
    for i in range(registered):
        (folder / f"grm-{i}").mkdir(exist_ok=True)
        (folder / f"grm-{i}" / "SKILL.md").write_text(summon_core.SKILL_OWNERSHIP_MARKER, encoding="utf-8")
    return [{"id": "claude", "label": "Claude", "path": str(folder)}]


def _inspect(tmp_path, content=None, *, served=False, grimoire=False, **kw):
    return S.inspect_install(
        _home(tmp_path, grimoire) if "home" not in kw else kw.pop("home"), REPO_ROOT,
        instruction_targets=_agent(tmp_path, content, served=served),
        skill_targets=_skills(tmp_path), git_fn=NO_GIT, **kw,
    )


def _args(**kw):
    base = dict(check=False, reconcile=False, update=False, apply=False, prune=False,
                home=None, framework_root=str(REPO_ROOT), format="json")
    base.update(kw)
    return types.SimpleNamespace(**base)


def _check(tmp_path, capsys, content, **kw):
    home = kw.pop("home", None) or _home(tmp_path)
    code = S.run_state_command(
        _args(check=True, home=str(home)), transcript_path=tmp_path / "t.json",
        instruction_targets=_agent(tmp_path, content, **kw), skill_targets=_skills(tmp_path),
        git_fn=NO_GIT, now=lambda: "t", run_id="r",
    )
    return code, json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------------------
# A stale block is drift, and --check says so consistently
# ---------------------------------------------------------------------------


def test_a_stale_routing_block_is_drift_in_the_check_exit_code(tmp_path, capsys):
    code, envelope = _check(tmp_path, capsys, STALE)
    assert code == 1
    assert envelope["summary"]["drift"] is True
    assert envelope["summary"]["agent_blocks_missing"] == ["claude"]


def test_check_exit_code_and_planned_steps_agree_on_a_stale_block(tmp_path):
    out = S.reconcile(
        _home(tmp_path), REPO_ROOT, apply=False,
        instruction_targets=_agent(tmp_path, STALE), skill_targets=_skills(tmp_path), git_fn=NO_GIT,
    )
    step = next(s for s in out["steps"] if s["id"] == "agent_blocks")
    assert step["status"] == "drift"
    assert any("would refresh" in m["message"] for m in step["messages"])
    assert S.drift_detected(out["state_after"]) is True


def test_a_current_block_is_in_sync(tmp_path, capsys):
    code, _envelope = _check(tmp_path, capsys, BLOCK)
    assert code == 0


def test_apply_refreshes_the_stale_block_and_converges(tmp_path, capsys):
    target = _agent(tmp_path, STALE)
    code = S.run_state_command(
        _args(reconcile=True, apply=True, home=str(_home(tmp_path))), transcript_path=tmp_path / "t.json",
        instruction_targets=target, skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=lambda script: (0, json.dumps({**SYNC_REPORT, "messages": []})),
        validate_runner=OK_VALIDATE, now=lambda: "t", run_id="r",
    )
    capsys.readouterr()
    assert code == 0
    assert CANONICAL in Path(target[0]["path"]).read_text(encoding="utf-8")


def test_a_file_that_is_not_utf8_is_reported_for_review_and_not_rewritten(tmp_path, capsys):
    target = _agent(tmp_path)
    path = Path(target[0]["path"])
    original = "# Title\ncafé\n".encode("utf-16")
    path.write_bytes(original)
    out = S.reconcile(
        _home(tmp_path), REPO_ROOT, apply=True, instruction_targets=target,
        skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=lambda script: (0, json.dumps(SYNC_REPORT)), validate_runner=OK_VALIDATE,
    )
    assert path.read_bytes() == original
    messages = [m["message"] for m in out["reporter"].messages]
    assert any("not UTF-8" in m and "agentfile" in m for m in messages)
    assert out["state_after"]["agent_targets"][0]["block_marker"] == "review"


# ---------------------------------------------------------------------------
# A target the grimoire plugin serves needs no block in its file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("content", [None, "# mine\n"])
def test_an_absent_block_is_not_drift_for_a_plugin_served_target(tmp_path, capsys, content):
    code, envelope = _check(tmp_path, capsys, content, served=True)
    assert code == 0
    assert envelope["summary"]["agent_blocks_missing"] == []


def test_a_stale_block_is_still_drift_for_a_plugin_served_target(tmp_path, capsys):
    code, envelope = _check(tmp_path, capsys, STALE, served=True)
    assert code == 1 and envelope["summary"]["agent_blocks_missing"] == ["claude"]


def test_a_block_that_is_not_one_clean_region_is_still_drift_for_a_plugin_served_target(tmp_path, capsys):
    code, _envelope = _check(tmp_path, capsys, "# Title\n## Grimoire Knowledge Base\nlegacy\n", served=True)
    assert code == 1


def test_reconcile_writes_no_block_for_a_plugin_served_target(tmp_path):
    target = _agent(tmp_path, served=True)
    out = S.reconcile(
        _home(tmp_path), REPO_ROOT, apply=True, instruction_targets=target,
        skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=lambda script: (0, json.dumps(SYNC_REPORT)), validate_runner=OK_VALIDATE,
    )
    assert not Path(target[0]["path"]).exists()
    assert next(s for s in out["steps"] if s["id"] == "agent_blocks")["status"] == "noop"
    assert out["residual"] == []


# ---------------------------------------------------------------------------
# An agent that is not installed is not configured
# ---------------------------------------------------------------------------


def test_inspect_covers_only_agents_with_a_home_folder(tmp_path):
    user = tmp_path / "user"
    (user / ".codex").mkdir(parents=True)
    state = S.inspect_install(_home(tmp_path), REPO_ROOT, git_fn=NO_GIT, user_home=user)
    assert [a["id"] for a in state["agent_targets"]] == ["codex"]
    assert [s["id"] for s in state["skills"]] == ["codex"]
    assert state["agent_targets"][0]["path"] == str(user / ".codex" / "AGENTS.md")
    assert not (user / ".claude").exists()


def test_a_machine_with_no_assistant_counts_every_agent(tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    state = S.inspect_install(_home(tmp_path), REPO_ROOT, git_fn=NO_GIT, user_home=user)
    assert [a["id"] for a in state["agent_targets"]] == ["claude", "codex"]


def test_a_missing_codex_folder_is_not_drift(tmp_path):
    user = tmp_path / "user"
    (user / ".claude").mkdir(parents=True)
    (user / ".claude" / "CLAUDE.md").write_text(BLOCK, encoding="utf-8")
    skill = user / ".claude" / "skills" / "grm-add"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(summon_core.SKILL_OWNERSHIP_MARKER, encoding="utf-8")
    state = S.inspect_install(_home(tmp_path), REPO_ROOT, git_fn=NO_GIT, user_home=user)
    assert S.drift_detected(state) is False


def test_reconcile_never_writes_for_an_agent_that_is_not_installed(tmp_path):
    user = tmp_path / "user"
    (user / ".claude").mkdir(parents=True)
    S.reconcile(
        _home(tmp_path), REPO_ROOT, apply=True, git_fn=NO_GIT, user_home=user,
        skill_runner=lambda script: (0, json.dumps(SYNC_REPORT)), validate_runner=OK_VALIDATE,
    )
    assert (user / ".claude" / "CLAUDE.md").is_file()
    assert not (user / ".codex").exists()


# ---------------------------------------------------------------------------
# The framework tree
# ---------------------------------------------------------------------------


def test_check_exits_1_when_the_framework_tree_is_not_populated(tmp_path, capsys):
    empty = tmp_path / "framework"
    empty.mkdir()
    code = S.run_state_command(
        _args(check=True, home=str(_home(tmp_path)), framework_root=str(empty)),
        transcript_path=tmp_path / "t.json", instruction_targets=_agent(tmp_path, BLOCK),
        skill_targets=_skills(tmp_path), git_fn=NO_GIT, now=lambda: "t", run_id="r",
    )
    envelope = json.loads(capsys.readouterr().out)
    assert code == 1
    assert envelope["summary"]["drift"] is True
    assert any(a["kind"] == "framework_update" for a in envelope["summary"]["next_actions"])


# ---------------------------------------------------------------------------
# An unreadable library is never overwritten
# ---------------------------------------------------------------------------


def test_reconcile_leaves_a_library_that_does_not_parse_as_it_is(tmp_path):
    home = _home(tmp_path, grimoire=True)
    broken = '{"grimoires": {"old": {"local_path": "x"},}}'
    (home / "library.json").write_text(broken, encoding="utf-8")
    out = S.reconcile(
        home, REPO_ROOT, apply=True, instruction_targets=_agent(tmp_path, BLOCK),
        skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=lambda script: (0, json.dumps(SYNC_REPORT)), validate_runner=OK_VALIDATE,
    )
    assert (home / "library.json").read_text(encoding="utf-8") == broken
    step = next(s for s in out["steps"] if s["id"] == "library")
    assert step["status"] == "error" and "not valid JSON" in step["messages"][0]["message"]
    assert out["state_after"]["library"]["unreadable"]
    assert out["state_after"]["library"]["in_sync"] is False
    assert any(a["kind"] == "library_repair" for a in out["next_actions"])
    assert out["reporter"].status() == "error"


def test_check_reports_an_unreadable_library_as_drift(tmp_path, capsys):
    home = _home(tmp_path)
    (home / "library.json").write_text("[1]", encoding="utf-8")
    code, envelope = _check(tmp_path, capsys, BLOCK, home=home)
    assert code == 1 and envelope["summary"]["library"]["in_sync"] is False


def test_the_library_step_writes_through_compare_and_swap(tmp_path, monkeypatch):
    import sync_library

    home = _home(tmp_path, grimoire=True)
    seen = []
    real = sync_library.update_library

    def spy(path, build, retries=5):
        seen.append(Path(path))
        return real(path, build, retries)

    monkeypatch.setattr(sync_library, "update_library", spy)
    S.reconcile(
        home, REPO_ROOT, apply=True, instruction_targets=_agent(tmp_path, BLOCK),
        skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=lambda script: (0, json.dumps(SYNC_REPORT)), validate_runner=OK_VALIDATE,
    )
    assert seen == [home / "library.json"]


# ---------------------------------------------------------------------------
# What the skill registration did reaches the envelope and the transcript
# ---------------------------------------------------------------------------


def _update(tmp_path, capsys, runner, **kw):
    code = S.run_state_command(
        _args(reconcile=True, apply=True, home=str(_home(tmp_path))), transcript_path=tmp_path / "t.json",
        instruction_targets=_agent(tmp_path, BLOCK), skill_targets=_skills(tmp_path), git_fn=NO_GIT,
        skill_runner=runner, validate_runner=OK_VALIDATE, now=lambda: "t", run_id="r",
    )
    return code, json.loads(capsys.readouterr().out), json.loads((tmp_path / "t.json").read_text(encoding="utf-8"))


def test_the_envelope_carries_the_skill_sync_counts_and_messages(tmp_path, capsys):
    code, envelope, transcript = _update(tmp_path, capsys, lambda script: (0, json.dumps(SYNC_REPORT)))
    assert envelope["summary"]["skill_sync"] == {"registered": 5, "cleaned": 2, "reset": 3, "blocked": 0}
    messages = {(m["severity"], m["message"]) for m in envelope["messages"]}
    assert ("warning", "skills: cook: skipped /cook-x (wrong name)") in messages
    assert ("error", "skills: collision /grm-add") in messages
    register = next(m for m in envelope["mutations"] if m["action"] == "register")
    assert "5 registered" in register["detail"]
    assert transcript["summary"]["skill_sync"] == envelope["summary"]["skill_sync"]
    step = next(s for s in transcript["steps"] if s["id"] == "skills")
    assert step["summary"]["registered"] == 5
    assert any("collision" in m["message"] for m in step["messages"])


def test_the_default_skill_runner_asks_sync_skills_for_a_json_report(monkeypatch, tmp_path):
    seen = {}

    def fake(script, *args, **_kwargs):
        seen["args"] = args
        return 0, "{}"

    monkeypatch.setattr(summon_core, "run_sync_skills", fake)
    S._default_skill_runner(tmp_path / "sync_skills.py")
    assert seen["args"] == ("--reset-managed", "--agent", "all")


@pytest.mark.parametrize(
    "output, expected",
    [
        ("not json at all", "no JSON report"),
        (json.dumps({"summary": {"registered": 1}}), "'cleaned' count"),
        ("", "no JSON report"),
    ],
)
def test_a_skill_sync_report_that_is_unparseable_or_incomplete_is_reported_not_fatal(tmp_path, capsys, output, expected):
    code, envelope, _transcript = _update(tmp_path, capsys, lambda script: (0, output))
    assert code == 0
    assert any(expected in m["message"] and m["severity"] == "warning" for m in envelope["messages"])
    assert next(m for m in envelope["mutations"] if m["action"] == "register")


def test_a_failed_skill_sync_carries_its_messages_into_an_error(tmp_path, capsys):
    blocked = {"summary": {"registered": 0, "cleaned": 0, "reset": 0, "blocked": 2},
               "messages": [{"severity": "error", "message": "collision /grm-add (Claude Code): two sources"}]}
    code, envelope, _transcript = _update(tmp_path, capsys, lambda script: (1, json.dumps(blocked)))
    assert code == 1 and envelope["status"] == "error"
    assert envelope["summary"]["skill_sync"]["blocked"] == 2
    texts = [m["message"] for m in envelope["messages"]]
    assert "skills: collision /grm-add (Claude Code): two sources" in texts
    assert "skills: sync_skills.py exited 1" in texts


def test_a_plan_has_no_skill_sync_summary(tmp_path, capsys):
    code, envelope = _check(tmp_path, capsys, BLOCK)
    assert "skill_sync" not in envelope["summary"]


# ---------------------------------------------------------------------------
# Printed commands run through the launcher and name no step number
# ---------------------------------------------------------------------------


def test_next_actions_commands_use_the_launcher(tmp_path):
    state = _inspect(tmp_path, "just a file\n", grimoire=True)
    state["library"]["stale"] = [{"key": "ghost", "raw_path": "x"}]
    state["skills"][0]["framework_managed_count"] = 0
    commands = {a["kind"]: a["command"] for a in S.next_actions(state, REPO_ROOT)}
    launcher = f"{REPO_ROOT.as_posix()}/bin/grimoire"
    assert commands["library_reconcile"] == f"{launcher} summon --reconcile --apply"
    assert commands["library_prune"] == f"{launcher} summon --reconcile --apply --prune"
    assert commands["skill_sync"] == f"{launcher} sync_skills"
    assert not any("python" in command for command in commands.values())


def test_the_state_surface_cites_no_update_step_number():
    for name in ("summon_state.py", "summon_core.py"):
        text = (REPO_ROOT / "rites" / name).read_text(encoding="utf-8")
        assert "UPDATE.md step" not in text


# ---------------------------------------------------------------------------
# The transcripts
# ---------------------------------------------------------------------------


def test_the_install_transcript_records_what_each_grimoire_did(tmp_path):
    transcript = S.record_install_transcript(
        _home(tmp_path), REPO_ROOT, ["cloned", "pulled", "kept"], True,
        actions={"cloned": "clone", "pulled": "pull"},
        transcript_path=tmp_path / "t.json", git_fn=NO_GIT, now=lambda: "t", run_id="r",
    )
    assert [(m["action"], m["detail"]) for m in transcript["mutations"]] == [
        ("clone", "grimoire cloned"), ("pull", "grimoire pulled"),
    ]
    assert transcript["summary"]["installed"] == ["cloned", "pulled", "kept"]


def test_a_transcript_is_written_as_utf8_with_lf(tmp_path):
    path = tmp_path / "cache" / "t.json"
    S.write_transcript(path, {"rite": "summon", "note": "日本語"})
    raw = path.read_bytes()
    assert "日本語".encode("utf-8") in raw and b"\r" not in raw
