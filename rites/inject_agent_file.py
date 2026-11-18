#!/usr/bin/env python3
"""Agent routing-block injector: create, insert and refresh mechanically, judgment for the rest.

Sister to `sync_skills.py` (skill registration) and `sync_library.py` (library
reconciliation). This rite keeps the Grimoire routing block - the region between
`<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->` and `<!-- END GRIMOIRE KNOWLEDGE BASE -->` -
current in the instruction file of each installed agent (`~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md`). An agent whose home folder is absent is not installed and
is skipped; `--agent <id>` names an agent explicitly.

The BEGIN and END markers are the sole contract. The framework owns every line
between them and the user owns every line outside. The rite does only what is
unambiguous from those markers:

  * absent file                  -> create it with a heading and the block
  * no block signature at all    -> insert the block (after a leading `# <title>`
                                    heading, else at the end)
  * exactly one clean BEGIN..END -> refresh it in place (idempotent: a block that
                                    already matches the template is left alone)
  * anything else                -> report `review` and write nothing

`review` covers a block with duplicate or malformed markers, an unmarked block (a heading
with no markers), and a file that is not UTF-8 or cannot be read. These are
not mechanical decisions: the agentfile judgment edit (`/grm-update agentfile`)
reads the file, rewrites the block, and keeps every line outside the
marked region. The rite never guesses and never duplicates.

The classifier and the writer live in `summon_core`; this rite calls them.
Writes are UTF-8 without BOM and LF line endings.

Mutation profile: plan_apply. The default plans; `--apply` performs the
create, insert and refresh actions.

Usage:
    python rites/inject_agent_file.py [--agent all|TARGET] [--apply] [--framework-root PATH]
                                 [--format human|json|jsonl]

Exit codes: 0 = plan or apply completed (files left for review are reported, not
failed), 1 = a file could not be written, 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import summon_core
from agent_targets import automatic_instruction_targets, installed_instruction_targets
from diagnostics import ResultReporter, add_output_format_arg

BEGIN_SENTINEL = summon_core.BEGIN_SENTINEL
END_SENTINEL = summon_core.END_SENTINEL

# Actions that write to disk under --apply.
WRITING_ACTIONS = ("create", "insert", "refresh")


def canonical_marked_block() -> str:
    """Return the canonical BEGIN..END block with no surrounding blank lines."""
    return summon_core.canonical_routing_block()


def plan_block(content: str | None) -> tuple[str, str]:
    """Classify the action one file's content needs: `(action, reason)`."""
    action = summon_core.classify_routing_block(content)
    return action, summon_core.ROUTING_REASONS[action]


def apply_block(path: Path, title: str, *, apply: bool) -> dict[str, Any]:
    """Plan, and under `apply` perform, the block action for one target.

    Returns {"path", "action", "reason", "status"}: `status` is "planned" in
    plan mode; in apply mode it is "ok" (wrote), "noop" (already current),
    "review" (handed to the judgment edit; nothing written) or "error" (the write
    failed). `summon_core.apply_routing_block` does the work.
    """
    return summon_core.apply_routing_block(Path(path), title, apply=apply)


def resolve_targets(framework_root: Path, agent: str, home: Path | None = None) -> list[dict[str, Any]]:
    """Return the instruction targets of the installed agents, or the one agent `agent` names.

    `home` is the user's home directory (default: `Path.home()`).
    """
    if agent and agent != "all":
        return [t for t in automatic_instruction_targets(framework_root, home) if t.get("id") == agent]
    return installed_instruction_targets(framework_root, home)


def _record(reporter: ResultReporter, target: dict[str, Any], result: dict[str, Any], apply: bool) -> None:
    """Record one target's result on the structured reporter."""
    tid = target.get("id") or "?"
    path = target.get("path")
    action = result["action"]
    if result["status"] == "error":
        reporter.message("error", f"{tid}: routing block {result['reason']} ({path})", path=path)
    elif action in WRITING_ACTIONS:
        if apply:
            reporter.mutation(action, path=path, detail=f"{action} routing block in {tid}")
        else:
            reporter.message("info", f"would {action} routing block in {tid} ({path})", path=path)
    elif action == "review":
        reporter.message(
            "warning",
            f"{tid}: {result['reason']} - handed to the agentfile judgment edit ({path})",
            path=path,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent routing-block injector")
    parser.add_argument(
        "--agent",
        default="all",
        help="Agent id from rites/data/agent_targets.json (default: all installed agents)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create, insert or refresh the routing block (default: plan only)",
    )
    parser.add_argument(
        "--framework-root",
        dest="framework_root",
        default=None,
        help="Override framework root (default: detected)",
    )
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    framework_root = (
        Path(args.framework_root).expanduser().resolve()
        if args.framework_root else summon_core.REPO_ROOT
    )
    reporter = ResultReporter("inject_agent_file", mode="apply" if args.apply else "plan")
    targets = resolve_targets(framework_root, args.agent)

    if human:
        print()
        print("  Agent Routing-Block Injector")
        print("  ----------------------------")
        if not args.apply:
            print("  [INFO]  Plan mode - no files will be written")
        print()

    if not targets:
        message = f"no installed agent's instruction target matched --agent {args.agent!r}"
        if human:
            print(f"  [WARN]  {message}")
            print()
        else:
            reporter.message("warning", message)
            reporter.emit(args.format, summary={"created": 0, "inserted": 0, "refreshed": 0,
                                                "present": 0, "review": 0})
        return 0

    counts = {"create": 0, "insert": 0, "refresh": 0, "present": 0, "review": 0}
    for target in targets:
        result = apply_block(Path(target["path"]), target.get("title") or Path(target["path"]).name,
                             apply=args.apply)
        counts[result["action"]] = counts.get(result["action"], 0) + 1
        _record(reporter, target, result, args.apply)
        if human:
            verb = {
                "create": "would create" if not args.apply else "created",
                "insert": "would insert into" if not args.apply else "inserted into",
                "refresh": "would refresh" if not args.apply else "refreshed",
                "present": "present (no change)",
                "review": f"needs the agentfile judgment edit - {result['reason']}",
            }[result["action"]]
            if result["status"] == "error":
                verb = f"routing block {result['reason']}"
            tag = "OK" if result["status"] in ("ok", "noop", "planned") and result["action"] != "review" else "WARN"
            print(f"  [{tag}]    {target.get('id')}: {verb} ({target.get('path')})")

    summary = {
        "created": counts["create"],
        "inserted": counts["insert"],
        "refreshed": counts["refresh"],
        "present": counts["present"],
        "review": counts["review"],
    }

    if human:
        print()
        prefix = "Plan:" if not args.apply else "Done:"
        print(f"  {prefix} create {counts['create']}, insert {counts['insert']}, "
              f"refresh {counts['refresh']}, present {counts['present']}, review {counts['review']}.")
        if counts["review"]:
            print("  Review targets keep their content unchanged; resolve them with the "
                  "agentfile judgment edit (/grm-update agentfile).")
        print()
    else:
        reporter.emit(args.format, summary=summary)

    return reporter.exit_code()


if __name__ == "__main__":
    sys.exit(main())
