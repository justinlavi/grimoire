#!/usr/bin/env python3
"""Unified validation orchestrator: runs the framework or grimoire validators.

Writes nothing: every validator is read-only and the orchestrator only reports.
Mutation profile: none.

Usage:
    FRAMEWORK_HOME/bin/grimoire validate                          # every validator in order
    FRAMEWORK_HOME/bin/grimoire validate --parallel               # validators at the same time
    FRAMEWORK_HOME/bin/grimoire validate --summary                # one line per validator
    FRAMEWORK_HOME/bin/grimoire validate --smart                  # list the validators the git changes call for
    FRAMEWORK_HOME/bin/grimoire validate --auto                   # run the validators --smart lists
    FRAMEWORK_HOME/bin/grimoire validate --grimoire <path>        # a grimoire instead of the framework
    FRAMEWORK_HOME/bin/grimoire validate links frontmatter        # named validators
    FRAMEWORK_HOME/bin/grimoire validate --only links,frontmatter
    FRAMEWORK_HOME/bin/grimoire validate --exclude orphans
    FRAMEWORK_HOME/bin/grimoire validate ... --format {human,json,jsonl}

A mode word (all, parallel, smart, auto, summary) may replace its flag.

Exit codes: 0 = every selected validator passed (or --smart listed its
selection), 1 = a validator failed or emitted no valid report, 2 = invalid
usage (unknown selector, conflicting modes, empty selection, or a --grimoire
path that is not a directory).
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _lib import (
    add_grimoire_arg,
    default_framework_root,
    is_colocated_source_path,
    load_skill_families,
    read_utf8,
    resolve_grimoire_arg,
    run_git,
)
from diagnostics import add_output_format_arg, human_label, human_location

RITE_DIR = Path(__file__).resolve().parent
FRAMEWORK_ROOT = default_framework_root()

VALIDATORS_CONTRACT = RITE_DIR / "data" / "validators.json"


def _load_validator_lists():
    """Return the framework and grimoire validator sequences from validators.json."""
    data = json.loads(read_utf8(VALIDATORS_CONTRACT))
    return data["framework"], data["grimoire"]


FRAMEWORK_RITES, GRIMOIRE_RITES = _load_validator_lists()

MODE_SELECTORS = {"all", "parallel", "smart", "auto", "summary"}


def run_rite(name, profile="framework", target_root=None):
    """Run a single validation rite. Returns (name, success, report)."""
    target_root = target_root or FRAMEWORK_ROOT
    command = [sys.executable, str(RITE_DIR / name)]
    if profile == "grimoire":
        command.extend(["--grimoire", str(target_root)])
    command.extend(["--format", "json"])

    result = subprocess.run(
        command,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "FRAMEWORK_HOME": str(FRAMEWORK_ROOT)},
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = None
    if not isinstance(report, dict):
        report = {
            "validator": Path(name).stem,
            "status": "fail",
            "root": str(target_root),
            "checked": {},
            "summary": {"errors": 1, "warnings": 0, "diagnostics": 1},
            "diagnostics": [
                {
                    "code": "VALIDATE_INVALID_VALIDATOR_REPORT",
                    "severity": "error",
                    "path": str(RITE_DIR / name),
                    "line": None,
                    "message": "validator did not emit a valid JSON diagnostic report",
                    "hint": (result.stdout + result.stderr)[-2000:],
                    "validator": "validate",
                    "docs_reference": "invocations/validators/validators.md",
                }
            ],
        }
    report["returncode"] = result.returncode
    return name, report_passed(report), report


def report_passed(report):
    """True when the validator exited 0 and its own report says it passed."""
    return report.get("returncode") == 0 and report.get("status") == "pass"


def _selector_forms(value):
    """Return normalized selector forms for a validator or user token."""
    stem = Path(value).stem
    if stem.startswith("validate_grimoire_"):
        base = stem.removeprefix("validate_grimoire_")
    elif stem.startswith("validate_"):
        base = stem.removeprefix("validate_")
    else:
        base = stem

    forms = {
        base,
        base.replace("_", "-"),
        stem,
        stem.replace("_", "-"),
    }
    return {form.lower() for form in forms if form}


def _short_selector(value):
    """Return the one canonical short selector token for a validator (e.g. 'links')."""
    stem = Path(value).stem
    for prefix in ("validate_grimoire_", "validate_"):
        if stem.startswith(prefix):
            return stem[len(prefix):].replace("_", "-")
    return stem.replace("_", "-")


def validator_selector_map(profile="framework"):
    """Map human selector names to validator rite filenames."""
    rites = GRIMOIRE_RITES if profile == "grimoire" else FRAMEWORK_RITES
    selectors = {}
    for rite in rites:
        for form in _selector_forms(rite):
            selectors[form] = rite
    return selectors


def split_selector_tokens(values):
    """Split comma/space separated selector arguments into normalized tokens."""
    tokens = []
    for value in values or []:
        for part in str(value).split(","):
            token = part.strip().lower().replace("_", "-")
            if token:
                tokens.append(token)
    return tokens


def apply_validator_selection(rites, profile="framework", only=None, exclude=None):
    """Return rites filtered by selector tokens, preserving canonical order."""
    selector_map = validator_selector_map(profile)
    only_tokens = split_selector_tokens(only)
    exclude_tokens = split_selector_tokens(exclude)

    def resolve(tokens, label):
        selected = set()
        unknown = []
        for token in tokens:
            if token in {"all", "*"}:
                selected.update(rites)
                continue
            rite = selector_map.get(token)
            if rite is None:
                unknown.append(token)
            else:
                selected.add(rite)
        if unknown:
            known = ", ".join(sorted({_short_selector(r) for r in rites}))
            raise ValueError(
                f"unknown {label} selector(s): {', '.join(unknown)}. "
                f"Known selectors: all, {known}"
            )
        return selected

    selected = resolve(only_tokens, "validator") if only_tokens else set(rites)
    excluded = resolve(exclude_tokens, "excluded validator") if exclude_tokens else set()
    return [rite for rite in rites if rite in selected and rite not in excluded]


def parse_positional_selectors(selectors):
    """Separate mode words from validator selectors."""
    mode_tokens = []
    validator_tokens = []
    for token in split_selector_tokens(selectors):
        if token in MODE_SELECTORS:
            mode_tokens.append(token)
        else:
            validator_tokens.append(token)
    return mode_tokens, validator_tokens


def _split_nul(output):
    """Split `git ... -z` output into its fields."""
    return [field for field in output.split("\0") if field]


def git_changed_files(root):
    """Return [(status, path)] for changes vs HEAD, else all tracked files.

    status is a single letter: 'A' added (an untracked file counts as added),
    'M' modified, 'D' deleted. A rename is expanded into a 'D' for the old path
    and an 'A' for the new path so deletions are never lost. Paths are relative
    to `root`, spelled as on disk. With no change at all, or with no commit to
    compare against, every tracked file is reported as present ('M'); outside a
    git repository the result is empty.
    """
    changes = []
    code, out, _ = run_git(root, "diff", "--name-status", "-z", "--relative", "HEAD")
    if code == 0:
        fields = _split_nul(out)
        index = 0
        while index < len(fields):
            status = fields[index][:1]
            if status in ("R", "C") and index + 2 < len(fields):
                changes.append(("D", fields[index + 1]))
                changes.append(("A", fields[index + 2]))
                index += 3
            elif index + 1 < len(fields):
                changes.append((status, fields[index + 1]))
                index += 2
            else:
                break
    code, out, _ = run_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if code == 0:
        changes.extend(("A", path) for path in _split_nul(out))
    if changes:
        return changes
    code, out, _ = run_git(root, "ls-files", "-z")
    return [("M", path) for path in _split_nul(out)] if code == 0 else []


# Contract files and the validators that check them. `None` selects the whole
# profile: validators.json is the list of validators itself.
CONTRACT_VALIDATORS = {
    "framework.json": (
        "validate_structure.py", "validate_naming.py", "validate_skill_refs.py",
    ),
    "formulae/grimoire/scaffold_contract.json": ("validate_structure.py",),
    "rites/data/agent_targets.json": ("validate_structure.py",),
    "rites/data/command_surface.json": ("validate_skill_refs.py",),
    "rites/data/rite_profiles.json": ("validate_structure.py", "validate_skill_refs.py"),
    "rites/data/summon_contract.json": ("validate_structure.py",),
    "rites/data/validators.json": None,
}

FRAMEWORK_CONTENT_DIRS = ("docs", "invocations", "formulae", "rites")


def _read_text(path):
    """Return a file's text, or None when it cannot be read as UTF-8."""
    try:
        return read_utf8(path)
    except (OSError, UnicodeDecodeError):
        return None


def _command_markers(target_root):
    """Return the `/<prefix>-` strings that open a framework command reference."""
    prefixes = {family["skill_prefix"] for family in load_skill_families(target_root)}
    return tuple(f"/{prefix}-" for prefix in sorted(prefixes or {"grm"}))


def determine_smart_rites(profile="framework", target_root=None):
    """Determine which validators to run based on changed files."""
    target_root = target_root or FRAMEWORK_ROOT
    changes = git_changed_files(target_root)
    if not changes:
        return list(GRIMOIRE_RITES if profile == "grimoire" else FRAMEWORK_RITES)

    if profile == "grimoire":
        return determine_smart_grimoire_rites(changes, target_root)
    return determine_smart_framework_rites(changes, target_root)


def determine_smart_framework_rites(changes, target_root):
    """Determine framework validators to run based on changed files."""
    # Portability and encoding scan path and content globally.
    needed = {"validate_portability.py", "validate_encoding.py"}
    markers = _command_markers(target_root)

    for status, f in changes:
        if f in CONTRACT_VALIDATORS:
            checkers = CONTRACT_VALIDATORS[f]
            if checkers is None:
                return list(FRAMEWORK_RITES)
            needed.update(checkers)

        # A tree diagram anywhere lists directories; adding or removing a file
        # can make one stale.
        if status in ("A", "D"):
            needed.add("validate_doc_trees.py")

        if status == "D":
            # A deleted file can't be read, but its removal must still trigger the
            # structure check (it may be required) and reference checks (a removed
            # page can break inbound links or orphan others).
            needed.add("validate_structure.py")
            if f.endswith(".md"):
                needed.add("validate_links.py")
                needed.add("validate_orphans.py")
            if f.startswith("skills/"):
                needed.add("validate_skill_refs.py")
            continue

        path = target_root / f
        if not path.exists():
            continue

        if f.split("/", 1)[0] in FRAMEWORK_CONTENT_DIRS:
            needed.add("validate_structure.py")

        if f.endswith((".md", ".py")):
            needed.add("validate_naming.py")
            needed.add("validate_semantics.py")
            needed.add("validate_security.py")

        if f.split("/", 1)[0] in ("invocations", "formulae") and f.endswith(".md"):
            needed.add("validate_format.py")

        if f.endswith(".md"):
            content = _read_text(path)
            if content is None or "](" in content or "[[" in content:
                needed.add("validate_links.py")
            if content is None or any(marker in content for marker in markers):
                needed.add("validate_skill_refs.py")
            if content is None or content.startswith("---\n"):
                needed.add("validate_frontmatter.py")
                if content is None or "authority:" in content:
                    needed.add("validate_provenance.py")

            # Any markdown change can affect orphan reachability and tree diagrams.
            needed.add("validate_orphans.py")
            needed.add("validate_doc_trees.py")

        # Adding or removing a skill changes which references are valid.
        if f.startswith("skills/"):
            needed.add("validate_skill_refs.py")

    return [r for r in FRAMEWORK_RITES if r in needed]


def determine_smart_grimoire_rites(changes, target_root):
    """Determine grimoire validators to run based on changed files."""
    needed = {"validate_portability.py", "validate_encoding.py"}

    for status, f in changes:
        if status in ("A", "D"):
            needed.add("validate_doc_trees.py")

        if status == "D":
            # A deleted file still needs the structure check (it may be required)
            # and link/orphan checks (a removed page can break references).
            needed.add("validate_grimoire_structure.py")
            if f.endswith(".md"):
                needed.add("validate_links.py")
                needed.add("validate_orphans.py")
            if is_colocated_source_path(f):
                needed.add("validate_provenance.py")
            continue

        path = target_root / f
        if not path.exists():
            continue

        if (
            f in {"grimoire.json", "README.md"}
            or f.startswith((".obsidian/", "chapters/", "inbox/"))
        ):
            needed.add("validate_grimoire_structure.py")

        if f.endswith(".md"):
            needed.add("validate_format.py")
            needed.add("validate_frontmatter.py")
            needed.add("validate_links.py")
            needed.add("validate_orphans.py")
            needed.add("validate_provenance.py")
            needed.add("validate_doc_trees.py")

        if is_colocated_source_path(f):
            needed.add("validate_provenance.py")

    return [r for r in GRIMOIRE_RITES if r in needed]


def render_diagnostics(report):
    for diagnostic in report.get("diagnostics", []):
        label = human_label(diagnostic.get("severity", "error"))
        location = human_location(diagnostic)
        code = diagnostic.get("code", "UNKNOWN")
        print(f"  [{label}] {code} {location}: {diagnostic.get('message', '')}")
        hint = diagnostic.get("hint")
        if hint:
            print(f"          hint: {hint}")


def empty_suite_report(rites, reports, profile, target_root):
    failed = sum(1 for report in reports if not report_passed(report))
    errors = sum(report.get("summary", {}).get("errors", 0) for report in reports)
    warnings = sum(report.get("summary", {}).get("warnings", 0) for report in reports)
    diagnostics = sum(report.get("summary", {}).get("diagnostics", 0) for report in reports)
    return {
        "validator": "validate",
        "profile": profile,
        "status": "fail" if failed else "pass",
        "root": str(target_root),
        "checked": {"validators": len(rites)},
        "summary": {
            "failed_validators": failed,
            "errors": errors,
            "warnings": warnings,
            "diagnostics": diagnostics,
        },
        "reports": reports,
    }


def emit_suite_report(report, output_format):
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if output_format == "jsonl":
        for validator_report in report["reports"]:
            for diagnostic in validator_report.get("diagnostics", []):
                print(json.dumps(diagnostic, sort_keys=True))
        print(json.dumps({"type": "summary", **report["summary"]}, sort_keys=True))


def profile_label(profile):
    """Return a human-facing validation target label."""
    return "Grimoire" if profile == "grimoire" else "Framework"


def run_sequential(rites, summary_only=False, output_format="human", profile="framework", target_root=None):
    """Run rites sequentially. Returns number of failures."""
    target_root = target_root or FRAMEWORK_ROOT
    failed = 0
    reports = []
    human = output_format == "human"

    if human and not summary_only:
        print(f"Running {profile_label(profile)} Validations")
        print("=======================================")
        print(f"Target: {target_root}")
        print()

    for rite in rites:
        if human and not summary_only:
            print(f"Running {rite}...")
            print("----------------------------------------")

        name, ok, report = run_rite(rite, profile=profile, target_root=target_root)
        reports.append(report)

        if human and not summary_only:
            render_diagnostics(report)
        else:
            if human:
                if ok:
                    print(f"  {rite}")
                else:
                    print(f"  {rite} FAILED")

        if not ok:
            failed += 1

    suite_report = empty_suite_report(rites, reports, profile, target_root)
    if not human:
        emit_suite_report(suite_report, output_format)

    if human and not summary_only:
        print()
        print("=======================================")

    return failed


def run_parallel(rites, output_format="human", profile="framework", target_root=None):
    """Run rites in parallel. Returns number of failures."""
    target_root = target_root or FRAMEWORK_ROOT
    failed = 0
    reports = []
    human = output_format == "human"

    if human:
        print(f"Running {profile_label(profile)} Validations in Parallel")
        print("==========================================")
        print(f"Target: {target_root}")
        print()

    # Each validator runs in its own subprocess; threads only wait on them.
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(run_rite, r, profile, target_root) for r in rites]
        for future in futures:
            name, ok, report = future.result()
            reports.append(report)

            if human:
                if ok:
                    print(f"  {name}")
                else:
                    print(f"  {name} FAILED")
                    render_diagnostics(report)
            if not ok:
                failed += 1

    reports.sort(key=lambda report: report.get("validator", ""))
    suite_report = empty_suite_report(rites, reports, profile, target_root)
    if not human:
        emit_suite_report(suite_report, output_format)

    if human:
        print()
        print("==========================================")
    return failed


def _resolve_selection(rite_list, *, profile, only, exclude, explicit):
    """Apply a selector filter to a validator list.

    Returns ``(rites, error)``. ``error`` is a stderr-ready message (and ``rites``
    is None) when a selector is unknown or an explicit selection resolves to no
    validators; otherwise ``error`` is None.
    """
    try:
        selected = apply_validator_selection(
            rite_list, profile=profile, only=only, exclude=exclude
        )
    except ValueError as exc:
        return None, str(exc)
    if explicit and not selected:
        return None, "selection resolved to zero validators"
    return selected, None


def main():
    parser = argparse.ArgumentParser(description="Unified framework and grimoire validation orchestrator")
    parser.add_argument(
        "selectors",
        nargs="*",
        help=(
            "Optional validator or mode selectors, e.g. links frontmatter, "
            "smart, auto, summary, parallel, or all"
        ),
    )
    add_grimoire_arg(parser)
    # Without --grimoire the framework profile runs.
    parser.set_defaults(grimoire=None)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Comma-separated validator selectors to run, e.g. links,frontmatter",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Comma-separated validator selectors to skip, e.g. orphans",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--parallel", action="store_true", help="Run validators in parallel")
    group.add_argument("--smart", action="store_true", help="Show which validators are relevant")
    group.add_argument("--auto", action="store_true", help="Smart + auto-execute")
    group.add_argument("--summary", action="store_true", help="Summary-only output")
    add_output_format_arg(parser)
    args = parser.parse_args()
    profile = "grimoire" if args.grimoire else "framework"
    target_root = resolve_grimoire_arg(args.grimoire) if args.grimoire else FRAMEWORK_ROOT
    rites = GRIMOIRE_RITES if profile == "grimoire" else FRAMEWORK_RITES
    mode_tokens, selector_tokens = parse_positional_selectors(args.selectors)

    explicit_modes = [
        name
        for name, enabled in {
            "parallel": args.parallel,
            "smart": args.smart,
            "auto": args.auto,
            "summary": args.summary,
        }.items()
        if enabled
    ]
    requested_modes = [mode for mode in mode_tokens if mode != "all"]
    all_modes = explicit_modes + requested_modes
    if len(set(all_modes)) > 1:
        print(f"Conflicting validation modes: {', '.join(all_modes)}", file=sys.stderr)
        return 2
    if requested_modes:
        selected_mode = requested_modes[0]
        args.parallel = selected_mode == "parallel"
        args.smart = selected_mode == "smart"
        args.auto = selected_mode == "auto"
        args.summary = selected_mode == "summary"

    explicit_selection = bool(args.only or args.exclude or selector_tokens)
    only = [*args.only, *selector_tokens]
    if not (args.smart or args.auto):
        rites, error = _resolve_selection(
            rites, profile=profile, only=only, exclude=args.exclude, explicit=explicit_selection
        )
        if error:
            print(error, file=sys.stderr)
            return 2

    if args.smart:
        smart = determine_smart_rites(profile, target_root)
        smart, error = _resolve_selection(
            smart, profile=profile, only=only, exclude=args.exclude, explicit=explicit_selection
        )
        if error:
            print(error, file=sys.stderr)
            return 2
        if args.format == "human":
            print("Smart Validation - Recommended:")
            for r in smart:
                print(f"  {r}")
            print()
            print("Run with --auto to execute, or one validator: <framework>/bin/grimoire <validator>")
        else:
            report = {
                "validator": "validate",
                "profile": profile,
                "status": "pass",
                "root": str(target_root),
                "checked": {"selected_validators": len(smart)},
                "summary": {
                    "failed_validators": 0,
                    "errors": 0,
                    "warnings": 0,
                    "diagnostics": 0,
                },
                "selected_validators": smart,
                "reports": [],
            }
            emit_suite_report(report, args.format)
        return 0

    if args.auto:
        smart = determine_smart_rites(profile, target_root)
        smart, error = _resolve_selection(
            smart, profile=profile, only=only, exclude=args.exclude, explicit=explicit_selection
        )
        if error:
            print(error, file=sys.stderr)
            return 2
        if args.format == "human":
            print(f"Smart Validation - Running {len(smart)} relevant validator(s)")
            print()
        failed = run_sequential(smart, output_format=args.format, profile=profile, target_root=target_root)
    elif args.parallel:
        failed = run_parallel(rites, output_format=args.format, profile=profile, target_root=target_root)
    elif args.summary:
        failed = run_sequential(rites, summary_only=True, output_format=args.format, profile=profile, target_root=target_root)
    else:
        failed = run_sequential(rites, output_format=args.format, profile=profile, target_root=target_root)

    if failed == 0:
        if args.format == "human":
            print("All validations passed")
        return 0
    else:
        if args.format == "human":
            print(f"{failed} validation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
