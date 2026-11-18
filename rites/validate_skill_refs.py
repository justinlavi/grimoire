#!/usr/bin/env python3
"""Validates framework skill references and the public command-surface contract.

Scans all markdown files in the framework for slash-command references matching
the framework's declared command families (for example `grm-` and `grm-dev-`) and
ensures each reference resolves to a source `SKILL.md`. Catches drift like:

 - A doc mentioning `/grm-foo` after the skill was deleted/renamed.
 - A new skill mentioned in prose before its `skills/` folder is created.

Grimoire skill references (e.g. `/dnd-...`) are NOT validated here;
they live in their own grimoire repos. This is a framework-internal check.

Also validates `rites/data/command_surface.json`, the public contract that
connects every framework-shipped command to its skill source, invocation home,
workflow owner, safety posture, and validation profile.

Usage: python rites/validate_skill_refs.py
Mutation profile: read-only.
Exit codes: 0 = all references resolve and the contract is valid, 1 = a dangling
reference or a command-surface contract error
"""

import json
import re
import sys

from _lib import (
    default_framework_root,
    discover_skill_commands,
    is_skipped,
    load_skill_families_checked,
    ok,
    walk_files,
    warn,
)
import command_surface as command_surface_contract
import rite_profiles as rite_profiles_contract
from diagnostics import DiagnosticReporter, add_output_format_arg

FRAMEWORK_ROOT = default_framework_root()
SKILLS_DIR = FRAMEWORK_ROOT / "skills"

# Match slash-command references for framework-shipped command-family prefixes.
SKILL_REF_RE = re.compile(r"(?<![A-Za-z0-9_/-])/([a-z][a-z0-9]*)-([a-z][a-z0-9-]*)\b")

# Tokens that, when they immediately follow the matched slug, indicate a
# wildcard/placeholder rather than a concrete skill reference. Examples:
#   /grm-dev-example-*       (wildcard summary)
#   /grm-dev-example-<name>  (placeholder for prose)
#   /grm-example-{slug}  (variable substitution)
PLACEHOLDER_SUFFIXES = ("-*", "-<", "-{")

# Files whose command names are not references to check.
SKIP_FILES = {
    "CHANGELOG.md",  # release notes name commands in prose
}

SKIP_DIRS = {
    "formulae",  # template placeholders
}


def load_command_families(reporter, human):
    """Return the framework's command families, reporting an unreadable framework.json.

    Invalid families are left out and are reported by validate_naming.py.
    """
    families, problems = load_skill_families_checked(FRAMEWORK_ROOT)
    for problem in problems:
        if problem.startswith("could not read") or "must hold a JSON object" in problem:
            reporter.error("SKILL_REFS_MANIFEST_READ", problem, path="framework.json")
            if human:
                warn(problem)
    return families


def scan_for_skill_refs(prefixes):
    """Yield (file_rel, lineno, full_command) for each framework skill reference."""
    for path in walk_files(FRAMEWORK_ROOT, "*.md"):
        if path.name in SKIP_FILES:
            continue
        rel = path.relative_to(FRAMEWORK_ROOT).as_posix()
        if is_skipped(rel, SKIP_DIRS):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            for match in SKILL_REF_RE.finditer(line):
                if match.group(1) not in prefixes:
                    continue
                # A wildcard or placeholder form is prose, not a reference.
                tail = line[match.end() : match.end() + 2]
                if any(tail.startswith(s) for s in PLACEHOLDER_SUFFIXES):
                    continue
                yield rel, lineno, match.group(0)


def mutation_profile_mismatches(surface_entries, rite_profile_entries):
    """Return rite-owned commands whose mutation_profile disagrees with the rite.

    A command's rite_owner that has a rite-profile entry must share that entry's
    profile; a rite_owner with no profile entry is not write-capable (the
    rite-profile contract requires every write-capable rite to be profiled), so
    the command must be read_only. Returns tuples of
    (command, rite_owner, command_mutation_profile, expected_profile).
    """
    rp_by_path = {entry.get("path"): entry for entry in rite_profile_entries}
    mismatches = []
    for entry in surface_entries:
        if entry.get("owner_type") != "rite":
            continue
        owner = entry.get("rite_owner")
        actual = entry.get("mutation_profile")
        profile = rp_by_path.get(owner)
        expected = profile.get("profile") if profile else "read_only"
        if actual != expected:
            mismatches.append((entry.get("command"), owner, actual, expected))
    return mismatches


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate framework skill references")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_skill_refs", FRAMEWORK_ROOT)

    if human:
        print()
        print("Validate Skill References")
        print("====================================")
        print(f"Framework root:    {FRAMEWORK_ROOT}")
        print(f"Skills dir:     {SKILLS_DIR}")
        print()

    prefixes = {family["skill_prefix"] for family in load_command_families(reporter, human)}
    valid_commands = set(discover_skill_commands(FRAMEWORK_ROOT))
    if human:
        print(f"Skill prefixes: {', '.join(f'{prefix}-' for prefix in sorted(prefixes))}")
        print(f"Discovered {len(valid_commands)} valid framework-shipped skill(s).")
        print()

    if human:
        print("Scanning markdown for framework-shipped slash-command references...")
    dangling = []
    seen_pairs = set()
    reference_count = 0
    for rel, lineno, full in scan_for_skill_refs(prefixes):
        reference_count += 1
        if full in valid_commands:
            continue
        # Deduplicate (file, slug) pairs - one report per file per slug.
        key = (rel, full)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        dangling.append((rel, lineno, full))
        reporter.error(
            "SKILL_REFS_DANGLING",
            f"references {full} with no source SKILL.md",
            path=rel,
            line=lineno,
            hint="Create the source skill or update the reference.",
        )
        if human:
            warn(f"{rel}:{lineno}  references {full}  (no source SKILL.md)")

    if human and not dangling:
        ok("All framework-shipped skill references resolve to existing skills.")
    if human:
        print()

    if human:
        print("Checking public command-surface contract...")
    surface_contract, surface_errors = command_surface_contract.validate_command_surface(FRAMEWORK_ROOT)
    for error in surface_errors:
        reporter.error(
            error["code"],
            error["message"],
            path=error.get("path"),
            hint=error.get("hint"),
        )
        if human:
            warn(f"{error.get('path', '-')}: {error['message']}")

    surface_entries = (
        len(command_surface_contract.command_entries(surface_contract))
        if surface_contract is not None
        else 0
    )
    if human and not surface_errors:
        ok(f"Command-surface contract covers {surface_entries} public command(s).")
    if human:
        print()

    mutation_drift = 0
    if surface_contract is not None:
        try:
            rite_profile_list = rite_profiles_contract.profile_entries(
                rite_profiles_contract.load_rite_profiles(FRAMEWORK_ROOT)
            )
        except (OSError, json.JSONDecodeError) as exc:
            rite_profile_list = []
            reporter.error(
                "COMMAND_SURFACE_RITE_PROFILES_READ",
                f"could not read rite-profile contract: {exc}",
                path="rites/data/rite_profiles.json",
                hint="Ensure rites/data/rite_profiles.json is valid JSON.",
            )
        for command, owner, actual, expected in mutation_profile_mismatches(
            command_surface_contract.command_entries(surface_contract), rite_profile_list
        ):
            mutation_drift += 1
            reporter.error(
                "COMMAND_SURFACE_MUTATION_PROFILE_DRIFT",
                f"{command} mutation_profile {actual!r} disagrees with {owner} (expected {expected!r})",
                path="rites/data/command_surface.json",
                hint="Align command_surface.mutation_profile with the rite's profile in rite_profiles.json.",
            )
            if human:
                warn(f"{command}: mutation_profile {actual!r} != expected {expected!r}")
    if human and not mutation_drift:
        ok("Command mutation profiles agree with the rite-profile contract.")
    if human:
        print()

    if not human:
        reporter.emit(
            args.format,
            checked={
                "valid_commands": len(valid_commands),
                "references": reference_count,
                "dangling_references": len(dangling),
                "command_surface_entries": surface_entries,
                "command_surface_errors": len(surface_errors),
                "mutation_profile_drift": mutation_drift,
            },
        )
        return reporter.exit_code()

    print("====================================")
    print(f"Dangling skill references: {len(dangling)}")
    print(f"Command-surface errors:    {len(surface_errors)}")
    print()

    if not dangling and reporter.error_count() == 0:
        return 0
    print("Either create the missing skill, update the reference, or repair the command-surface contract.")
    print("If a skill was renamed, update the docs and command-surface entry that reference it.")
    print("After adding/removing a skill, also run:")
    print(f"   {FRAMEWORK_ROOT}/bin/grimoire sync_docs --apply")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
