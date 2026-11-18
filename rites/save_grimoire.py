#!/usr/bin/env python3
"""Save a grimoire's changes: validate, commit, pull, push.

The deterministic half of `/grm-save`, the verb that lets someone who does not
use git by hand share what they changed. The rite stages everything git would
track, commits with the message the invocation composed, brings the branch up
to date with the remote by rebasing, and pushes. It refuses to commit a
grimoire that fails validation and never force-pushes.

When everyone else's changes touch the same lines as the commit, the rebase
stops with the commit recorded locally, nothing sent, and conflict markers in
the pages named in the message. Once the person has resolved those pages, the
next save continues the rebase and pushes; while a page still holds a marker,
the save names it and stops. `--abandon` ends a paused save instead: the pages
return to the state of the recorded commit, which stays on this computer, and
nothing is sent.

A grimoire registered for reading on this computer (`"access": "read"` in the
library) is never saved: every mode reports blocked and changes nothing.

Mutation profile: plan_apply. The default run is a plan: it reports what would
be committed and whether the branch is ahead of or behind its upstream, and
writes nothing. `--apply` performs the save.

Usage:
    python rites/save_grimoire.py --grimoire <path> [--message "<text>"] [--apply]
        [--no-push] [--no-fetch] [--abandon] [--format human|json|jsonl]

Exit codes: 0 = plan rendered, saved, or nothing to save; 1 = blocked (not a git
repository, git cannot read the repository, validation failed, no git identity,
conflict, push failed); 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from _lib import add_grimoire_arg, info, ok, read_only_refusal, resolve_grimoire_arg, run_git, warn
from diagnostics import ResultReporter, add_output_format_arg
from recent_changes import STATUS_WORDS

FRAMEWORK_PATH = Path(__file__).resolve().parent.parent
GIT_TIMEOUT = 300
UNMERGED_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}|>{7}) ", re.MULTILINE)


def working_changes(root: Path) -> tuple[list[dict], str]:
    """Return the working tree's `{status, path}` records and a git error ("" when none)."""
    code, out, err = run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames")
    if code != 0:
        return [], err.strip() or "git status failed"
    changes = []
    for entry in out.split("\0"):
        if len(entry) < 4:
            continue
        pair, path = entry[:2], entry[3:]
        if pair in UNMERGED_CODES:
            flag = "U"
        elif pair == "??":
            flag = "?"
        else:
            flag = pair[0] if pair[0] != " " else pair[1]
        changes.append({"status": STATUS_WORDS.get(flag, flag), "path": path})
    return changes, ""


def git_identity(root: Path) -> tuple[str, str]:
    name = run_git(root, "config", "user.name")[1].strip()
    email = run_git(root, "config", "user.email")[1].strip()
    return name, email


def upstream_state(root: Path, fetch: bool) -> dict:
    """Describe the branch, its upstream, and ahead/behind counts."""
    branch = run_git(root, "rev-parse", "--abbrev-ref", "HEAD")[1].strip()
    has_remote = run_git(root, "remote", "get-url", "origin")[0] == 0
    code, up, _ = run_git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream = up.strip() if code == 0 else ""
    state = {"branch": branch, "remote": has_remote, "upstream": upstream, "ahead": 0, "behind": 0, "fetched": False}
    if upstream and fetch:
        fcode, _, ferr = run_git(root, "fetch", "--quiet", timeout=120)
        state["fetched"] = fcode == 0
        state["fetch_error"] = "" if fcode == 0 else ferr.strip()[-200:]
    if upstream:
        code, counts, _ = run_git(root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        if code == 0:
            behind, ahead = (counts.split() + ["0", "0"])[:2]
            state["behind"], state["ahead"] = int(behind), int(ahead)
    return state


def validation_passes(root: Path) -> tuple[bool, str]:
    """Run the grimoire validators; return (passed, a short account of what failed)."""
    cmd = [sys.executable, str(FRAMEWORK_PATH / "rites" / "validate.py"), "--grimoire", str(root), "--format", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        return False, "the validators produced no report: " + (proc.stderr or proc.stdout).strip()[-300:]
    failing = []
    for entry in report.get("reports", []):
        if entry.get("returncode", 1) == 0:
            continue
        errors = [d.get("message", "") for d in entry.get("diagnostics", []) if d.get("severity") == "error"]
        failing.append(f"{entry.get('validator', '?')}: {errors[0]}" if errors else str(entry.get("validator", "?")))
    passed = proc.returncode == 0 and report.get("status") == "pass"
    return passed, "; ".join(failing) or proc.stderr.strip()[-300:]


def rebase_in_progress(root: Path) -> bool:
    for name in ("rebase-merge", "rebase-apply"):
        code, out, _ = run_git(root, "rev-parse", "--git-path", name)
        if code == 0 and (root / out.strip()).exists():
            return True
    return False


def conflicted_files(root: Path) -> list[str]:
    code, out, _ = run_git(root, "diff", "--name-only", "-z", "--diff-filter=U")
    return [path for path in out.split("\0") if path] if code == 0 else []


def holds_conflict_marker(root: Path, rel: str) -> bool:
    try:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(CONFLICT_MARKER_RE.search(text))


def conflict_text(pages: list[str], commit: str) -> str:
    recorded = f"Your work is recorded on this computer as {commit}" if commit else "Your work is recorded on this computer"
    return (
        f"changes that were already saved touch the same lines as yours in {', '.join(pages)}, so the save stopped before sending anything. "
        f"{recorded}. Open each page, keep the lines you want, delete the lines that start with <<<<<<<, ======= and >>>>>>>, "
        "then save again. To stop instead, run the save with --abandon: the pages go back to your recorded version and nothing is sent."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a grimoire's changes: validate, commit, pull, push")
    add_grimoire_arg(parser)
    parser.add_argument("--message", default="", help="Commit message (required with --apply when there are changes)")
    parser.add_argument("--apply", action="store_true", help="Commit, pull --rebase, and push (default: plan only)")
    parser.add_argument("--no-push", action="store_true", help="Commit and rebase but do not push")
    parser.add_argument("--abandon", action="store_true",
                        help="End a save that stopped on a conflict: restore the recorded commit, send nothing")
    parser.add_argument("--no-fetch", action="store_true", help="Do not contact the remote while planning")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    root = resolve_grimoire_arg(args.grimoire)
    mode = "apply" if args.apply else "plan"
    reporter = ResultReporter("save_grimoire", root=root, mode=mode)
    summary: dict = {"changes": [], "change_count": 0, "branch": "", "upstream": "", "ahead": 0, "behind": 0, "commit": "", "pushed": False}
    commit_recorded = False

    def record_commit() -> None:
        nonlocal commit_recorded
        if summary["commit"] and not commit_recorded:
            commit_recorded = True
            reporter.mutation("commit", path=root, detail=f"{summary['commit']} {args.message.strip()[:72]}")

    def finish(code: int) -> int:
        if human:
            return code
        reporter.emit(args.format, summary=summary)
        return code

    def block(text: str, path=None) -> int:
        record_commit()
        reporter.message("error", text, path=path)
        reporter.set_status("blocked")
        if human:
            warn(text)
        return finish(1)

    def share(state: dict) -> int:
        """Push the branch (or stop short of it) and report."""
        if args.no_push:
            reporter.message("info", "push skipped (--no-push)")
            if human:
                info("Push skipped.")
            return finish(0)
        if state["upstream"]:
            code, _, err = run_git(root, "push", "--quiet", timeout=GIT_TIMEOUT)
        elif state["remote"]:
            code, _, err = run_git(root, "push", "--quiet", "--set-upstream", "origin", state["branch"], timeout=GIT_TIMEOUT)
        else:
            record_commit()
            reporter.message("info", "no remote configured; committed locally only")
            if human:
                info("No remote configured; your changes are committed locally.")
            return finish(0)
        if code != 0:
            return block(f"push failed: {err.strip()[-300:]}; your work is kept locally")
        summary["pushed"] = True
        record_commit()
        reporter.mutation("push", path=root, detail=f"{state['branch']} -> origin")
        if human:
            ok(f"Pushed {state['branch']} to origin. Everyone else receives it on their next /grm-update.")
        return finish(0)

    if human:
        print()
        print(f"Save grimoire - {root.name} ({mode})")
        print()

    refusal = read_only_refusal(root)
    if refusal:
        summary["access"] = "read"
        return block(refusal, path=root)

    if not (root / ".git").exists():
        return block("this grimoire is not a git repository, so there is nothing to save to; initialise it with git first", path=root)

    changes, status_error = working_changes(root)
    if status_error:
        return block(f"git cannot read this grimoire's state: {status_error}", path=root)
    summary["changes"] = changes
    summary["change_count"] = len(changes)

    if args.abandon:
        if not rebase_in_progress(root):
            reporter.set_status("noop")
            if human:
                ok("No save is paused on a conflict; nothing to abandon.")
            return finish(0)
        code, _, err = run_git(root, "rebase", "--abort")
        if code != 0:
            return block(f"could not end the paused save: {err.strip()[-300:]}")
        summary["commit"] = run_git(root, "rev-parse", "--short", "HEAD")[1].strip()
        reporter.mutation("abandon", path=root, detail=f"paused save ended; work is recorded locally as {summary['commit']}")
        if human:
            ok(f"The paused save is ended. Your work is recorded on this computer as {summary['commit']} and nothing was sent.")
        return finish(0)

    if rebase_in_progress(root):
        return resume_paused_save(root, args, summary, block, share, finish, reporter, human)

    state = upstream_state(root, fetch=not args.no_fetch)
    summary.update({k: state[k] for k in ("branch", "upstream", "ahead", "behind")})
    if state.get("fetch_error"):
        reporter.message("warning", f"could not reach the remote while checking for everyone else's changes: {state['fetch_error']}")

    if human:
        if changes:
            info(f"{len(changes)} change(s) on branch {state['branch']}:")
            for item in changes[:60]:
                print(f"      {item['status']:<10} {item['path']}")
            if len(changes) > 60:
                print(f"      ... and {len(changes) - 60} more")
        else:
            info(f"No local changes on branch {state['branch']}.")
        if state["upstream"]:
            info(f"Upstream {state['upstream']}: {state['ahead']} to share, {state['behind']} to receive")
        elif state["remote"]:
            info("Remote 'origin' exists but this branch has no upstream yet; the save will set it.")
        else:
            info("No remote configured; the save will commit locally only.")

    if not changes and state["ahead"] == 0:
        reporter.set_status("noop")
        if human:
            ok("Nothing to save.")
        return finish(0)

    passed, detail = validation_passes(root)
    if not passed:
        return block(f"validation failed, fix it before saving: {detail}")
    reporter.message("info", "validation passed")

    if not args.apply:
        reporter.set_status("noop")
        if human:
            ok("Plan only. Re-run with --apply and a --message to save.")
        return finish(0)

    name, email = git_identity(root)
    if not name or not email:
        return block("git does not know who you are yet; run: git config --global user.name \"Your Name\" && git config --global user.email \"you@example.com\"")

    if changes:
        if not args.message.strip():
            return block("--message is required to commit")
        code, _, err = run_git(root, "add", "-A")
        if code != 0:
            return block(f"git add failed: {err.strip()}")
        code, _, err = run_git(root, "commit", "-q", "-m", args.message.strip())
        if code != 0:
            return block(f"git commit failed: {err.strip()}")
        summary["commit"] = run_git(root, "rev-parse", "--short", "HEAD")[1].strip()
        if human:
            ok(f"Committed {summary['commit']}")

    if state["upstream"]:
        code, _, err = run_git(root, "pull", "--rebase", "--quiet", timeout=GIT_TIMEOUT)
        if code != 0:
            conflicts = conflicted_files(root)
            if conflicts:
                return block(conflict_text(conflicts, summary["commit"]))
            if rebase_in_progress(root):
                run_git(root, "rebase", "--abort")
            return block(f"could not bring the branch up to date: {err.strip()[-300:]}; your work is kept locally")
        if summary["commit"]:
            summary["commit"] = run_git(root, "rev-parse", "--short", "HEAD")[1].strip()
        if human and state["behind"]:
            ok(f"Brought in {state['behind']} change(s) from {state['upstream']}")

    return share(state)


def resume_paused_save(root, args, summary, block, share, finish, reporter, human) -> int:
    """Continue a rebase that an earlier save left paused on conflicts, then share the result."""
    pending = conflicted_files(root)
    unresolved = [page for page in pending if holds_conflict_marker(root, page)]
    if unresolved:
        return block(conflict_text(unresolved, ""))
    passed, detail = validation_passes(root)
    if not passed:
        return block(f"validation failed, fix it before saving: {detail}")
    reporter.message("info", "validation passed")
    if not args.apply:
        reporter.set_status("noop")
        if human:
            ok("The conflicts are resolved. Re-run with --apply to finish the save.")
        return finish(0)
    name, email = git_identity(root)
    if not name or not email:
        return block("git does not know who you are yet; run: git config --global user.name \"Your Name\" && git config --global user.email \"you@example.com\"")
    if pending:
        code, _, err = run_git(root, "add", "-A", "--", *pending)
        if code != 0:
            return block(f"git add failed: {err.strip()}")
    code, _, err = run_git(root, "-c", "core.editor=true", "rebase", "--continue", timeout=GIT_TIMEOUT)
    if code != 0:
        more = conflicted_files(root)
        if more:
            return block(conflict_text(more, ""))
        return block(f"could not finish bringing the branch up to date: {err.strip()[-300:]}; your work is kept locally")
    state = upstream_state(root, fetch=False)
    summary.update({k: state[k] for k in ("branch", "upstream", "ahead", "behind")})
    summary["commit"] = run_git(root, "rev-parse", "--short", "HEAD")[1].strip()
    if human:
        ok("Brought in everyone else's changes")
    return share(state)


if __name__ == "__main__":
    sys.exit(main())
