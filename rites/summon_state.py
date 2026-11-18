#!/usr/bin/env python3
"""Agent-legible state surface of the Summoning Rite.

Sister module to `summon_core.py` (the install core). Where `summon_core`
talks to a person through tagged stdout, this module gives an orchestrator a
machine-readable view of an installation: a read-only `--check` that reports
drift, a `--reconcile` that repairs the offline, deterministic subset of the
update, a network-aware `--update` that pulls and heals every library grimoire
(delegated to `update_grimoires.py`), and a durable transcript
(`~/.cache/grimoire/summon-last.json`) so the outcome of any summon-family
operation can be compared with its intent without parsing prose.

`summon.py` routes the flags here:

    python rites/summon.py --check (alias --plan) | --reconcile [--apply] [--prune] | --update [--apply] [--prune]
                      [--home PATH] [--framework-root PATH] [--transcript-path PATH]
                      [--format human|json|jsonl]

Mutation profile: plan_apply. `--check`, and `--reconcile` or `--update` without
`--apply`, write only the transcript. With `--apply`, the commands write the
library, the skill folders, the routing block of each installed agent and (for
`--update`) the grimoires they confirm current. A command refuses to apply on a
framework that fails `validate.py` and deletes no library entry unless `--prune`
is given. A file whose routing block is not one clean region (a stray or
duplicate marker, an unmarked heading-only block, a file that is not UTF-8) is
left untouched and reported for `/grm-update agentfile`.

Exit codes: 0 = in sync, or the applied run converged; 1 = drift found (without
`--apply`), or the applied run ended `blocked` or `error`, left something it
does not fix, or met a grimoire that needs a manual pull; 2 = argparse invalid
arguments.

`--check` and `--reconcile` stay offline. Pulling the framework itself is a
step a person approves.

Every entry point takes `home` and `framework_root` explicitly and never reads
`summon_core`'s import-time constants for logic; those serve only as the
production defaults in `run_state_command`. `user_home` is the user's home
directory, from which the agent paths resolve (default: `Path.home()`).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import summon_core
import sync_library
import update_grimoires
from _lib import read_library, write_json
from agent_targets import installed_instruction_targets, installed_skill_targets
from diagnostics import ResultReporter, add_output_format_arg

SCHEMA_VERSION = 1

NETWORK_PULL_NOTE = "skipped (pulling the framework is a step a person approves)"

# The classifier's action for a file, as the state of its routing block.
BLOCK_STATES = {
    "create": "none",
    "insert": "none",
    "present": "present",
    "refresh": "stale",
    "review": "review",
}


# ---------------------------------------------------------------------------
# Time / identity seams (injectable so transcripts are deterministic in tests)
# ---------------------------------------------------------------------------


def _real_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_transcript_path() -> Path:
    """Owned cache location for the last summon-family transcript."""
    return Path.home() / ".cache" / "grimoire" / "summon-last.json"


# ---------------------------------------------------------------------------
# Inspection (read-only)
# ---------------------------------------------------------------------------


def _instruction_targets(framework_root: Path, override: Any, user_home: Path | None) -> list[dict[str, Any]]:
    if override is not None:
        return list(override)
    return installed_instruction_targets(framework_root, user_home)


def _skill_targets(framework_root: Path, override: Any, user_home: Path | None = None) -> list[dict[str, Any]]:
    if override is not None:
        return list(override)
    targets = []
    for tid, config in installed_skill_targets(framework_root, user_home).items():
        targets.append({
            "id": tid,
            "label": config["label"],
            "path": config["path"],
            "plugin_families": config.get("plugin_families") or set(),
        })
    return targets


def inspect_install(
    home: Path,
    framework_root: Path,
    *,
    instruction_targets: list | None = None,
    skill_targets: list | None = None,
    git_fn: Callable | None = None,
    user_home: Path | None = None,
) -> dict[str, Any]:
    """Return a read-only snapshot of an installation's state.

    `instruction_targets` / `skill_targets` default to the targets of the agents
    installed under `user_home`; tests pass explicit lists of
    ``{"id","label","path"}`` so the snapshot never reaches the real home directory.
    """
    home = Path(home)
    framework_root = Path(framework_root)
    git_fn = git_fn or summon_core.git

    # The framework itself
    is_git_repo = (framework_root / ".git").is_dir()
    populated = summon_core.working_tree_populated(framework_root) if framework_root.is_dir() else False
    toplevel = None
    if is_git_repo:
        ok, out = git_fn("-C", str(framework_root), "rev-parse", "--show-toplevel")
        toplevel = out if ok and out else None
    framework_state = {
        "root": str(framework_root),
        "present": framework_root.is_dir(),
        "git_repo": is_git_repo,
        "working_tree_populated": populated,
        "git_toplevel": toplevel,
    }

    # Local library vs disk (reuses sync_library's drift classification)
    library_path = home / "library.json"
    scan = sync_library.scan_grimoire_home(home)
    library, unreadable = read_library(library_path)
    diff = sync_library.diff_library(scan, library or {"grimoires": {}}, home)
    library_state = {
        "path": str(library_path),
        "in_sync": not (diff["missing"] or diff["stale"] or diff["mismatched"] or unreadable),
        "unreadable": unreadable,
        "missing": list(diff["missing"]),
        "stale": [{"key": s["key"], "raw_path": s["raw_path"]} for s in diff["stale"]],
        "mismatched": [
            {"key": m["key"], "raw_path": m["raw_path"], "expected_path": m["expected_path"]}
            for m in diff["mismatched"]
        ],
        "ok": list(diff["ok"]),
        "unmanaged": [p.name for p in scan["unmanaged"]],
        "on_disk": sorted(g["key"] for g in scan["grimoires"]),
        "warnings": list(scan["warnings"]),
    }

    # Agent routing blocks
    agent_state = []
    for target in _instruction_targets(framework_root, instruction_targets, user_home):
        path = Path(target["path"])
        action, reason = summon_core.routing_block_action(path)
        marker = BLOCK_STATES[action]
        agent_state.append({
            "id": target.get("id"),
            "label": target.get("label"),
            "path": str(path),
            "title": target.get("title") or path.name,
            "instruction_file_exists": path.is_file(),
            "block_present": marker == "present",
            "block_marker": marker,
            "block_reason": reason,
            "plugin_served": bool(target.get("plugin_serves_routing")),
        })

    # Registered skills per target
    skill_state = []
    for target in _skill_targets(framework_root, skill_targets, user_home):
        path = Path(target["path"])
        skill_state.append({
            "id": target.get("id"),
            "label": target.get("label"),
            "path": str(path),
            "exists": path.is_dir(),
            "framework_managed_count": summon_core._registered_skill_count(path),
            "plugin_families": sorted(target.get("plugin_families") or ()),
        })

    return {
        "framework": framework_state,
        "library": library_state,
        "agent_targets": agent_state,
        "skills": skill_state,
        "network_pull": NETWORK_PULL_NOTE,
    }


# ---------------------------------------------------------------------------
# Drift / remediation derivation
# ---------------------------------------------------------------------------


def _library_has_fixable_drift(library: dict[str, Any]) -> bool:
    return bool(library["missing"] or library["mismatched"])


def _skills_absent(state: dict[str, Any]) -> bool:
    """True when the framework is installed but no managed skills are registered anywhere.

    A target served by the Claude Code plugins counts as registered.
    """
    if not state["framework"]["working_tree_populated"]:
        return False
    if any(s.get("plugin_families") for s in state["skills"]):
        return False
    return sum(s["framework_managed_count"] for s in state["skills"]) == 0


def _missing_block_ids(state: dict[str, Any]) -> list[str]:
    """Ids whose routing block is not current: absent, stale, or needing review.

    A target served by the grimoire plugin needs no block in its file, so an
    absent block is not drift there; a stale or malformed one still is.
    """
    return [
        a["id"] for a in state["agent_targets"]
        if a["block_marker"] != "present"
        and not (a.get("plugin_served") and a["block_marker"] == "none")
    ]


def drift_detected(state: dict[str, Any]) -> bool:
    """Single drift predicate backing the --check exit code."""
    return (
        not state["framework"]["working_tree_populated"]
        or not state["library"]["in_sync"]
        or bool(_missing_block_ids(state))
        or _skills_absent(state)
    )


def _grimoire_drift(grimoire_result: dict[str, Any] | None) -> bool:
    """True when any library grimoire is not current (see `CURRENT_STATUSES`)."""
    if not grimoire_result:
        return False
    return any(
        r["status"] not in update_grimoires.CURRENT_STATUSES
        for r in grimoire_result["grimoires"]
    )


def next_actions(state: dict[str, Any], framework_root: Path) -> list[dict[str, Any]]:
    """Structured, tier-tagged remediation - never free-text the orchestrator must parse."""
    actions: list[dict[str, Any]] = []
    lib = state["library"]
    command = lambda *args: summon_core.grimoire_command(*args, root=framework_root)  # noqa: E731

    if lib.get("unreadable"):
        actions.append({
            "kind": "library_repair",
            "tier": "red",
            "command": f"edit or delete {lib['path']}",
            "reason": f"{lib['unreadable']}; no command writes over it",
        })
    if _library_has_fixable_drift(lib):
        keys = sorted(lib["missing"] + [m["key"] for m in lib["mismatched"]])
        actions.append({
            "kind": "library_reconcile",
            "tier": "amber",
            "command": command("summon", "--reconcile", "--apply"),
            "reason": f"library entries to add/correct: {', '.join(keys)}",
        })
    if lib["stale"]:
        keys = sorted(s["key"] for s in lib["stale"])
        actions.append({
            "kind": "library_prune",
            "tier": "red",
            "command": command("summon", "--reconcile", "--apply", "--prune"),
            "reason": f"stale library entries (removal deletes them): {', '.join(keys)}",
        })
    missing_blocks = _missing_block_ids(state)
    if missing_blocks:
        actions.append({
            "kind": "agent_block_update",
            "tier": "amber",
            "command": "/grm-update agentfile",
            "reason": f"agent routing block missing, stale or not one clean region for: {', '.join(missing_blocks)}",
        })
    if _skills_absent(state):
        actions.append({
            "kind": "skill_sync",
            "tier": "amber",
            "command": command("sync_skills"),
            "reason": "no framework-managed skills registered in any agent skill directory",
        })
    if not state["framework"]["working_tree_populated"]:
        # Brings the framework to the current version. The working-tree recovery
        # in summon_core (git checkout HEAD -- .) repairs an interrupted clone
        # in place instead.
        actions.append({
            "kind": "framework_update",
            "tier": "red",
            "command": f"git -C {framework_root} pull --ff-only",
            "reason": "Framework working tree is missing or partial; pull to bring it current (network/human step)",
        })
    return actions


def residual(state: dict[str, Any], *, prune: bool) -> list[dict[str, Any]]:
    """What reconcile --apply does NOT fix - the human/RED boundary, machine-typed."""
    items: list[dict[str, Any]] = []
    if state["library"].get("unreadable"):
        items.append({
            "kind": "library_unreadable",
            "tier": "red",
            "reason": f"{state['library']['unreadable']}; reconcile leaves it as it is",
        })
    if state["library"]["stale"] and not prune:
        items.append({
            "kind": "library_stale",
            "tier": "red",
            "reason": "stale library entries preserved; re-run with --prune to remove",
        })
    missing_blocks = _missing_block_ids(state)
    if missing_blocks:
        items.append({
            "kind": "agent_block",
            "tier": "amber",
            "reason": f"agent routing block must be refreshed via /grm-update agentfile for: {', '.join(missing_blocks)}",
        })
    if not state["framework"]["working_tree_populated"]:
        items.append({
            "kind": "framework_base",
            "tier": "red",
            "reason": "Framework working tree not populated; reconcile cannot repair the base",
        })
    return items


# ---------------------------------------------------------------------------
# Default subprocess seams (injectable in tests)
# ---------------------------------------------------------------------------


def _default_skill_runner(register_script: Path) -> tuple[int, str]:
    """Register skills with `--reset-managed`, which replaces the owned framework and
    grimoire skill namespaces and writes fresh skills from the current sources, so a
    renamed or removed source leaves no stale registration. Returns `(returncode,
    json report)`."""
    return summon_core.run_sync_skills(register_script, "--reset-managed", "--agent", "all")


def _default_validate_runner(framework_root: Path) -> tuple[bool, str]:
    script = Path(framework_root) / "rites" / "validate.py"
    if not script.is_file():
        return False, f"validate.py not found at {script}"
    result = subprocess.run(
        [sys.executable, str(script), "--summary"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0, (result.stdout or "")[-500:]


# ---------------------------------------------------------------------------
# Reconcile (the repair behind --check / --reconcile)
# ---------------------------------------------------------------------------


def _reconcile_library(
    home: Path,
    diff_library: dict[str, Any],
    *,
    apply: bool,
    prune: bool,
    reporter: ResultReporter,
) -> dict[str, Any]:
    """Apply the additive library reconciliation; preserve stale unless pruning."""
    step = {"id": "library", "label": "Reconcile local library", "status": "noop",
            "mutations": [], "messages": []}

    def report(severity: str, text: str) -> None:
        reporter.message(severity, text)
        step["messages"].append({"severity": severity, "message": text})

    if diff_library.get("unreadable"):
        report("error", f"library: {diff_library['unreadable']}; left as it is")
        step["status"] = "error"
        return step

    missing = diff_library["missing"]
    mismatched = diff_library["mismatched"]
    stale = diff_library["stale"]

    if not (missing or mismatched or stale):
        return step

    for key in missing:
        report("info", f"library: + {key} (missing entry will be added)")
    for m in mismatched:
        report("info", f"library: ~ {m['key']} (local_path corrected)")
    for s in stale:
        if prune:
            report("warning", f"library: - {s['key']} (stale entry removed)")
        else:
            report("warning", f"library: ! {s['key']} (stale; preserved, use --prune to remove)")

    changed = bool(missing or mismatched or (prune and stale))

    if not apply:
        step["status"] = "drift" if changed or stale else "noop"
        return step

    if not changed:
        return step

    library_path = home / "library.json"
    scan = sync_library.scan_grimoire_home(home)

    def build(original: dict[str, Any]) -> dict[str, Any]:
        synced = sync_library.build_synced_library(scan, original, home)
        if not prune:
            # build_synced_library drops entries that no longer resolve. Re-add every
            # dropped key from the original so reconcile never deletes a library entry
            # without --prune - a structural guarantee that does not depend on the
            # stale set matching this fresh scan. setdefault keeps disk-rebuilt
            # corrections (e.g. mismatched paths) intact.
            for key, entry in original["grimoires"].items():
                synced["grimoires"].setdefault(key, entry)
            synced["grimoires"] = dict(sorted(synced["grimoires"].items()))
        return synced

    try:
        sync_library.update_library(library_path, build)
    except (sync_library.LibraryUnreadable, sync_library.LibraryWriteConflict) as exc:
        report("error", f"library: {exc}; left as it is")
        step["status"] = "error"
        return step

    for key in missing:
        reporter.mutation("add", path=library_path, detail=f"library entry {key}")
    for m in mismatched:
        reporter.mutation("update", path=library_path, detail=f"library local_path {m['key']}")
    if prune:
        for s in stale:
            reporter.mutation("remove", path=library_path, detail=f"stale library entry {s['key']}")
    step["mutations"] = [
        {"action": "write", "path": "library.json", "detail": "reconciled library"}
    ]
    step["status"] = "ok"
    return step


def _reconcile_skills(
    framework_root: Path,
    state: dict[str, Any],
    *,
    apply: bool,
    reporter: ResultReporter,
    skill_runner: Callable,
) -> dict[str, Any]:
    """Register skills, and carry what `sync_skills` reported into the step.

    The step's `summary` holds the `registered`, `cleaned`, `reset` and `blocked`
    counts of the sync_skills report; its warnings and errors become messages.
    """
    step = {"id": "skills", "label": "Sync agent skills", "status": "noop",
            "mutations": [], "messages": []}
    register_script = Path(framework_root) / "rites" / "sync_skills.py"
    sync_command = summon_core.grimoire_command("sync_skills", root=framework_root)

    def report(severity: str, text: str) -> None:
        reporter.message(severity, text)
        step["messages"].append({"severity": severity, "message": text})

    if not state["framework"]["working_tree_populated"]:
        report("error", "skills: skipped - framework working tree not populated (run summon install / git pull first)")
        step["status"] = "blocked"
        return step

    if not apply:
        if _skills_absent(state):
            report("warning", f"skills: no framework-managed skills registered (run {sync_command})")
            step["status"] = "drift"
        return step

    if not register_script.is_file():
        report("error", f"skills: sync_skills.py not found at {register_script}")
        step["status"] = "blocked"
        return step

    rc, output = skill_runner(register_script)
    sync = summon_core.read_skill_sync_report(output)
    step["summary"] = dict(sync["counts"])
    for message in sync["messages"]:
        severity = message["severity"] if message["severity"] in ("info", "warning", "error") else "info"
        report(severity, f"skills: {message['message']}")
    for problem in sync["problems"]:
        report("warning", f"skills: {problem}")

    if rc == 0:
        counts = ", ".join(f"{sync['counts'][key]} {key}" for key in summon_core.SKILL_SYNC_COUNTS
                           if key in sync["counts"])
        detail = f"synced the framework and grimoire skills ({counts})" if counts else "synced the framework and grimoire skills"
        reporter.mutation("register", detail=detail)
        step["mutations"] = [{"action": "register", "path": None, "detail": detail}]
        step["status"] = "ok"
    else:
        report("error", f"skills: sync_skills.py exited {rc}")
        step["status"] = "error"
    return step


def _grimoire_step(grimoire_result: dict[str, Any], *, reporter: ResultReporter) -> dict[str, Any]:
    """Build the steps[] entry for the pull-and-heal pass and surface manual pulls."""
    step = {"id": "grimoires", "label": "Pull and heal library grimoires", "status": "noop",
            "mutations": [], "messages": []}
    s = grimoire_result["summary"]
    for nm in grimoire_result["needs_manual_pull"]:
        text = (f"grimoire {nm['key']}: {nm['status']} - could not bring current; "
                f"pull manually with your tokens ({nm.get('suggested_command') or 'git pull --ff-only'})")
        reporter.message("warning", text)
        step["messages"].append({"severity": "warning", "message": text})
    for r in grimoire_result["grimoires"]:
        if r["pulled"]:
            reporter.mutation("pull", path=r["local_path"], detail=f"{r['key']} fast-forwarded")
        if update_grimoires.heal_wrote(r):
            reporter.mutation("heal", path=r["local_path"], detail=f"{r['key']} scaffold/README healed")
        finding = update_grimoires.heal_finding(r)
        if finding:
            reporter.message(finding[0], finding[1])
            step["messages"].append({"severity": finding[0], "message": finding[1]})
    if s["brought_current"] or s["healed"]:
        step["status"] = "ok"
    elif s["needs_manual_pull"] or s["heal_skipped"]:  # heal_skipped counts editable grimoires only
        step["status"] = "drift"
    return step


def _reconcile_agent_blocks(
    state: dict[str, Any],
    *,
    apply: bool,
    reporter: ResultReporter,
    injector: Callable | None = None,
) -> dict[str, Any]:
    """Create, insert, or refresh the marked Grimoire routing block in each agent file.

    Deterministic for the common cases: an absent file is created with the
    canonical block, a block-less file gets one inserted, and a single clean
    marked region is refreshed in place. A file with duplicate or malformed
    markers, or that is not UTF-8, is left untouched and reported for
    `/grm-update agentfile`, since its boundaries are ambiguous. A target the
    grimoire plugin serves needs no block in its file, so an absent block is
    left absent. Plan mode writes nothing and reports what `--apply` would do.
    """
    injector = injector or summon_core.apply_routing_block
    step = {"id": "agent_blocks", "label": "Agent routing blocks", "status": "noop",
            "mutations": [], "messages": []}

    wrote = False
    drift = False
    errored = False
    for target in state["agent_targets"]:
        if target.get("plugin_served") and target["block_marker"] == "none":
            continue
        path = target["path"]
        title = target.get("title") or Path(path).name
        result = injector(Path(path), title, apply=apply)
        action = result["action"]
        tid = target["id"]
        if result.get("status") == "error":
            text = f"agent_blocks: {tid} - routing block {result.get('reason')}"
            reporter.message("error", text)
            step["messages"].append({"severity": "error", "message": text})
            errored = True
        elif action in ("create", "insert", "refresh"):
            if apply:
                reporter.mutation("write", path=path, detail=f"{action} routing block {tid}")
                step["mutations"].append({"action": "write", "path": path,
                                          "detail": f"{action} {tid}"})
                wrote = True
            else:
                text = f"agent_blocks: would {action} routing block for {tid}"
                reporter.message("info", text)
                step["messages"].append({"severity": "info", "message": text})
                drift = True
        elif action == "review":
            text = (
                f"agent_blocks: {tid} - {result.get('reason', 'needs review')}; resolve with "
                "/grm-update agentfile. Not auto-written: there is no "
                "clean routing block to create or refresh mechanically."
            )
            reporter.message("warning", text)
            step["messages"].append({"severity": "warning", "message": text})
            drift = True

    if errored:
        step["status"] = "error"
    elif wrote:
        step["status"] = "ok"
    elif drift:
        step["status"] = "drift"
    return step


def reconcile(
    home: Path,
    framework_root: Path,
    *,
    apply: bool = False,
    prune: bool = False,
    pull_grimoires: bool = False,
    grimoire_fetch: bool = True,
    instruction_targets: list | None = None,
    skill_targets: list | None = None,
    git_fn: Callable | None = None,
    skill_runner: Callable | None = None,
    validate_runner: Callable | None = None,
    grimoire_processor: Callable | None = None,
    agent_injector: Callable | None = None,
    user_home: Path | None = None,
) -> dict[str, Any]:
    """Run the reconciliation and return reporter + steps + before/after state.

    With `pull_grimoires` (the `--update` path), a network-aware pull-and-heal
    pass over every library grimoire runs between the library and skill steps -
    so the skill reset picks up freshly pulled grimoire skills, and grimoires are
    brought current before any heal. `grimoire_fetch=False` keeps it offline (the
    `--check` currency snapshot: classify only, never pull or heal).
    """
    home = Path(home)
    framework_root = Path(framework_root)
    skill_runner = skill_runner or _default_skill_runner
    validate_runner = validate_runner or _default_validate_runner

    reporter = ResultReporter("summon", root=home, mode="apply" if apply else "plan")
    inspect_kwargs = dict(
        instruction_targets=instruction_targets, skill_targets=skill_targets,
        git_fn=git_fn, user_home=user_home,
    )
    state_before = inspect_install(home, framework_root, **inspect_kwargs)
    steps: list[dict[str, Any]] = []

    # Green-base gate: never repair on a tree that fails validation.
    if apply:
        ok, detail = validate_runner(framework_root)
        if not ok:
            text = "validate: the framework fails validate.py - refusing to reconcile on a broken base"
            reporter.message("error", text)
            reporter.set_status("blocked")
            steps.append({"id": "validate", "label": "Validate framework base", "status": "blocked",
                          "mutations": [], "messages": [{"severity": "error", "message": text,
                                                          "detail": detail}]})
            state_after = state_before
            return _reconcile_result(reporter, steps, state_before, state_after, prune,
                                     framework_root, grimoire_result=None)
        steps.append({"id": "validate", "label": "Validate framework base", "status": "ok",
                      "mutations": [], "messages": []})

    steps.append(_reconcile_library(home, _diff_from_state(state_before), apply=apply,
                                    prune=prune, reporter=reporter))

    # Bring every library grimoire current before re-syncing skills (so the reset
    # picks up pulled grimoire skills) and before any heal (so a heal never
    # re-derives upstream work on a stale tree).
    grimoire_result = None
    if pull_grimoires:
        processor = grimoire_processor or update_grimoires.process_all
        grimoire_result = processor(home, framework_root, apply=apply, fetch=grimoire_fetch)
        steps.append(_grimoire_step(grimoire_result, reporter=reporter))

    steps.append(_reconcile_skills(framework_root, state_before, apply=apply,
                                   reporter=reporter, skill_runner=skill_runner))
    steps.append(_reconcile_agent_blocks(state_before, apply=apply, reporter=reporter,
                                         injector=agent_injector))

    # Verify against post-write reality so the transcript reflects convergence.
    state_after = inspect_install(home, framework_root, **inspect_kwargs) if apply else state_before

    return _reconcile_result(reporter, steps, state_before, state_after, prune, framework_root,
                             grimoire_result=grimoire_result)


def _diff_from_state(state: dict[str, Any]) -> dict[str, Any]:
    """Re-shape the inspected library block into sync_library's diff vocabulary."""
    return {
        "missing": state["library"]["missing"],
        "mismatched": state["library"]["mismatched"],
        "stale": state["library"]["stale"],
        "unreadable": state["library"]["unreadable"],
    }


def _reconcile_result(reporter, steps, state_before, state_after, prune, framework_root,
                      *, grimoire_result=None):
    skill_step = next((s for s in steps if s["id"] == "skills" and "summary" in s), None)
    return {
        "reporter": reporter,
        "steps": steps,
        "state_before": state_before,
        "state_after": state_after,
        "residual": residual(state_after, prune=prune),
        "next_actions": next_actions(state_after, framework_root),
        "grimoires": grimoire_result,
        "skill_sync": skill_step["summary"] if skill_step else None,
    }


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


def build_summary(state, *, operation, drift, res, actions, extra=None):
    summary = {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "drift": drift,
        "library": {
            "in_sync": state["library"]["in_sync"],
            "missing": len(state["library"]["missing"]),
            "stale": len(state["library"]["stale"]),
            "mismatched": len(state["library"]["mismatched"]),
            "ok": len(state["library"]["ok"]),
        },
        "agent_blocks_missing": _missing_block_ids(state),
        "skills_registered": sum(s["framework_managed_count"] for s in state["skills"]),
        "next_actions": actions,
        "residual": res,
    }
    if extra:
        summary.update(extra)
    return summary


def build_transcript(reporter, *, operation, state, steps, summary, run_id, started_at, ended_at):
    """Transcript is the stdout envelope as a superset - one status/mode/summary, no nesting."""
    envelope = reporter.report(summary=summary)
    return {
        **envelope,
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "steps": steps,
        "final_state": state,
    }


def write_transcript(path: Path, transcript: dict[str, Any]) -> None:
    write_json(Path(path), transcript)


def record_install_transcript(
    home: Path,
    framework_root: Path,
    installed_keys: list,
    skills_ok: bool,
    *,
    actions: dict[str, str] | None = None,
    transcript_path: Path | None = None,
    git_fn: Callable | None = None,
    now: Callable | None = None,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    """Best-effort: drop an `operation: install` transcript after an install.

    `actions` maps an installed key to what happened (`clone` or `pull`); a key
    with no entry records no mutation, and without `actions` every key counts as
    a clone. Callers wrap the call in try/except so a transcript failure never
    breaks an otherwise-successful install.
    """
    now = now or _real_now
    started_at = now()
    state = inspect_install(home, framework_root, git_fn=git_fn)
    installed_keys = list(installed_keys or [])
    if actions is None:
        actions = {key: "clone" for key in installed_keys}
    recorded = [(key, actions[key]) for key in installed_keys if actions.get(key)]
    framework_ok = state["framework"]["working_tree_populated"]
    status = "ok" if (framework_ok and skills_ok) else "error"

    reporter = ResultReporter("summon", root=Path(home), mode="apply")
    reporter.set_status(status)
    for key, action in recorded:
        reporter.mutation(action, detail=f"grimoire {key}")
    if not framework_ok:
        reporter.message("error", "Framework working tree not populated after install")
    if not skills_ok:
        reporter.message("error", "library update or skill registration reported a problem")

    steps = [
        {"id": "framework", "label": "Install or update the framework",
         "status": "ok" if framework_ok else "error", "mutations": [], "messages": []},
        {"id": "grimoires", "label": "Clone selected grimoires",
         "status": "ok" if installed_keys else "noop",
         "mutations": [{"action": action, "path": key, "detail": None} for key, action in recorded],
         "messages": []},
        {"id": "skills", "label": "Sync skills",
         "status": "ok" if skills_ok else "error", "mutations": [], "messages": []},
    ]
    summary = build_summary(
        state, operation="install", drift=drift_detected(state),
        res=residual(state, prune=False), actions=next_actions(state, framework_root),
        extra={"installed": installed_keys, "skills_ok": bool(skills_ok)},
    )
    transcript = build_transcript(
        reporter, operation="install", state=state, steps=steps, summary=summary,
        run_id=run_id or uuid.uuid4().hex, started_at=started_at, ended_at=now(),
    )
    write_transcript(transcript_path or default_transcript_path(), transcript)
    return transcript


# ---------------------------------------------------------------------------
# Human rendering
# ---------------------------------------------------------------------------


def _print_human(operation: str, state: dict[str, Any], result_steps, drift, transcript_path,
                 grimoires=None):
    log = summon_core.Logger()
    print()
    print("============================================")
    print(f"  Grimoire Summon - {operation}")
    print("============================================")
    framework = state["framework"]
    (log.ok if framework["working_tree_populated"] else log.err)(
        f"Framework: {'populated' if framework['working_tree_populated'] else 'NOT populated'} at {framework['root']}"
    )
    lib = state["library"]
    if lib.get("unreadable"):
        log.err(f"Library unreadable: {lib['unreadable']}")
    elif lib["in_sync"]:
        log.ok("Library: in sync with disk")
    else:
        log.warn(
            f"Library drift: +{len(lib['missing'])} missing, "
            f"~{len(lib['mismatched'])} mismatched, !{len(lib['stale'])} stale"
        )
    for a in state["agent_targets"]:
        if a["block_marker"] == "present":
            log.ok(f"Routing block present: {a['id']}")
        elif a.get("plugin_served") and a["block_marker"] == "none":
            log.ok(f"Routing block supplied by the grimoire plugin: {a['id']}")
        else:
            log.warn(f"Routing block {a['block_marker']}: {a['id']} ({a['path']})")
    total_skills = sum(s["framework_managed_count"] for s in state["skills"])
    (log.ok if total_skills else log.warn)(f"Synced skills: {total_skills}")
    if grimoires is not None:
        for r in grimoires["grimoires"]:
            current = r["status"] in update_grimoires.CURRENT_STATUSES
            detail = r["status"]
            if r.get("access") == "read":
                detail += " (read-only)"
            if r["behind"] or r["ahead"]:
                detail += f" (behind {r['behind']}, ahead {r['ahead']})"
            if not current and r.get("reason"):
                detail += f" - {r['reason']}"
            (log.ok if current else log.warn)(f"Grimoire {r['key']}: {detail}")
            finding = update_grimoires.heal_finding(r)
            if finding:
                (log.err if finding[0] == "error" else log.warn)(f"  -> {finding[1]}")
        for nm in grimoires["needs_manual_pull"]:
            log.warn(f"  -> {nm['key']}: pull manually with your tokens ({nm.get('suggested_command') or 'git pull --ff-only'})")
    if result_steps:
        print()
        print("  Steps:")
        for step in result_steps:
            print(f"    [{step['status']:<7}] {step['id']}")
    print()
    if drift:
        log.warn("Drift detected - see the warnings above and next_actions in the transcript")
    elif update_grimoires.needs_attention(grimoires):
        log.warn("In sync - a grimoire needs attention, see above")
    else:
        log.ok("In sync - no action needed")
    print(f"  Transcript: {transcript_path}")
    print()


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def add_state_args(parser: argparse.ArgumentParser) -> None:
    """Register the agent-legibility flags on the summon dispatcher's parser."""
    parser.add_argument("--check", "--plan", dest="check", action="store_true",
                        help="Report installation/registry drift (read-only) and write a transcript")
    parser.add_argument("--reconcile", dest="reconcile", action="store_true",
                        help="Repair the local library and sync skills to match disk (offline)")
    parser.add_argument("--update", dest="update", action="store_true",
                        help="Pull every library grimoire (branch-aware), reconcile, sync skills, and heal current grimoires")
    parser.add_argument("--apply", dest="apply", action="store_true",
                        help="With --reconcile/--update, perform changes (default: propose only)")
    parser.add_argument("--prune", dest="prune", action="store_true",
                        help="With --reconcile/--update --apply, remove stale library entries (deletes them)")
    parser.add_argument("--home", dest="home", default=None,
                        help="Override grimoires home (default: ~/grimoires)")
    parser.add_argument("--framework-root", dest="framework_root", default=None,
                        help="Override framework root (default: detected)")
    parser.add_argument("--transcript-path", dest="transcript_path", default=None,
                        help="Override the transcript path (default: ~/.cache/grimoire/summon-last.json)")
    add_output_format_arg(parser)


def is_state_invocation(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "check", False) or getattr(args, "reconcile", False)
                or getattr(args, "update", False))


def run_state_command(
    args: argparse.Namespace,
    *,
    transcript_path: Path | None = None,
    instruction_targets: list | None = None,
    skill_targets: list | None = None,
    git_fn: Callable | None = None,
    skill_runner: Callable | None = None,
    validate_runner: Callable | None = None,
    agent_injector: Callable | None = None,
    now: Callable | None = None,
    run_id: str | None = None,
    user_home: Path | None = None,
) -> int:
    """Drive --check / --reconcile / --update: emit the envelope, write the transcript, set the exit code."""
    now = now or _real_now
    started_at = now()
    home = Path(args.home).expanduser().resolve() if getattr(args, "home", None) else summon_core.GRIMOIRES_HOME
    framework_root = (
        Path(args.framework_root).expanduser().resolve()
        if getattr(args, "framework_root", None) else summon_core.REPO_ROOT
    )
    fmt = getattr(args, "format", "human")
    do_update = bool(getattr(args, "update", False))
    do_reconcile = bool(getattr(args, "reconcile", False))
    apply = bool((do_reconcile or do_update) and getattr(args, "apply", False))
    prune = bool(getattr(args, "prune", False))
    operation = "update" if do_update else ("reconcile" if do_reconcile else "check")

    # Only --update touches grimoires: it fetches every library grimoire (branch-
    # aware) and, with --apply, fast-forwards and heals the ones confirmed current.
    # --check and --reconcile stay offline.
    pull_grimoires = do_update
    grimoire_fetch = do_update

    outcome = reconcile(
        home, framework_root, apply=apply, prune=prune,
        pull_grimoires=pull_grimoires, grimoire_fetch=grimoire_fetch,
        instruction_targets=instruction_targets, skill_targets=skill_targets,
        git_fn=git_fn, skill_runner=skill_runner, validate_runner=validate_runner,
        agent_injector=agent_injector, user_home=user_home,
    )
    reporter = outcome["reporter"]
    state = outcome["state_after"]
    grimoires = outcome.get("grimoires")
    drift = drift_detected(state) or _grimoire_drift(grimoires)
    extra = {"applied": apply, "pruned": prune}
    if outcome["skill_sync"] is not None:
        extra["skill_sync"] = outcome["skill_sync"]
    if grimoires is not None:
        extra["grimoires"] = grimoires["grimoires"]
        extra["grimoire_summary"] = grimoires["summary"]
        extra["needs_manual_pull"] = grimoires["needs_manual_pull"]
    summary = build_summary(
        state, operation=operation, drift=drift,
        res=outcome["residual"], actions=outcome["next_actions"],
        extra=extra,
    )
    transcript = build_transcript(
        reporter, operation=operation, state=state, steps=outcome["steps"], summary=summary,
        run_id=run_id or uuid.uuid4().hex, started_at=started_at, ended_at=now(),
    )

    path = transcript_path
    if path is None and getattr(args, "transcript_path", None):
        path = Path(args.transcript_path).expanduser()
    if path is None:
        path = default_transcript_path()
    try:
        write_transcript(path, transcript)
    except OSError:
        path = "<unwritten>"

    if fmt == "human":
        _print_human(operation, state, outcome["steps"], drift, path, grimoires=grimoires)
    else:
        reporter.emit(fmt, summary=summary)

    if not apply:
        # Plan/propose - --check, --reconcile, or --update without --apply - signal
        # actionable drift through the exit code, matching the documented table.
        return 1 if drift else 0
    status = reporter.status()
    if status in ("blocked", "error"):
        return 1
    left = outcome["residual"] or _grimoire_drift(grimoires) or update_grimoires.needs_attention(grimoires)
    return 1 if left else 0
