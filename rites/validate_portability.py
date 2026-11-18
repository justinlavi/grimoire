#!/usr/bin/env python3
"""Validates filesystem portability - no Windows-reserved characters in paths.

On Windows, the characters < > : " | ? * are reserved and cannot appear in
file or directory names. `git checkout` aborts on encounter ("invalid path"),
leaving the working tree partially populated - a state the summon rite cannot
recover from on subsequent attempts. This validator catches the issue before
any Windows consumer attempts to clone the grimoire.

It also rejects Windows reserved basenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
and segments that end with `.` or ` ` (Windows trims/rejects those), and two
entries in one directory, files or folders, whose names differ only by case - a
tree that checks out on Linux but cannot be materialized on Windows or macOS.

Each path segment is checked once, however many files lie beneath it, so a
reserved folder name is one finding and a pair of folders that differ only by
case is one finding. `walk_files` prunes `.git/`, `node_modules/` and
`.obsidian/` at any depth and `publish/` at the root.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_portability [--grimoire <path>] [--format human|json|jsonl]
Exit codes: 0 = success, 1 = violations found, 2 = `--grimoire` is not a directory
"""

import argparse
import sys
from pathlib import PurePosixPath

from _lib import add_grimoire_arg, err, ok, resolve_grimoire_arg, walk_files
from diagnostics import DiagnosticReporter, add_output_format_arg

# Windows-reserved characters in filenames (path separators / and \ excluded
# since they're handled by the OS as separators, not as filename chars).
RESERVED_CHARS = set('<>:"|?*')

# Windows reserved basenames (case-insensitive), with or without extension.
RESERVED_BASENAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


def check_segments(rel_parts):
    """Return a list of (code, description) tuples for the path's segments."""
    issues = []
    for part in rel_parts:
        bad_chars = sorted({c for c in part if c in RESERVED_CHARS})
        if bad_chars:
            issues.append(
                (
                    "PORTABILITY_RESERVED_CHAR",
                    f"segment '{part}' contains Windows-reserved char(s): {''.join(bad_chars)}",
                )
            )
        stem = part.split(".", 1)[0].upper()
        if stem in RESERVED_BASENAMES:
            issues.append(
                (
                    "PORTABILITY_RESERVED_BASENAME",
                    f"segment '{part}' uses Windows-reserved basename '{stem}'",
                )
            )
        if part and part[-1] in ". ":
            issues.append(
                (
                    "PORTABILITY_TRAILING_DOT_SPACE",
                    f"segment '{part}' ends with '.' or ' ' (Windows trims / rejects)",
                )
            )
    return issues


def find_case_collisions(names):
    """Return groups of names in one directory that are equal under casefold()."""
    groups = {}
    for name in names:
        groups.setdefault(name.casefold(), []).append(name)
    return [sorted(group) for group in groups.values() if len(group) > 1]


def check_paths(paths):
    """Return `(code, message, path)` for every portability finding in `paths`.

    `paths` holds root-relative paths as tuples of segments. A segment that
    several paths share (a folder with many files) is checked once, and the
    entries of one folder are compared once.
    """
    findings = []
    children = {}
    seen = set()
    for parts in paths:
        for depth, part in enumerate(parts):
            segment_path = PurePosixPath(*parts[: depth + 1])
            if segment_path in seen:
                continue
            seen.add(segment_path)
            children.setdefault(segment_path.parent.as_posix(), []).append(part)
            for code, issue in check_segments((part,)):
                findings.append((code, issue, segment_path.as_posix()))
    for parent, names in sorted(children.items()):
        for group in find_case_collisions(names):
            issue = (
                f"entries differ only by case: {', '.join(group)} "
                "(cannot coexist on Windows or macOS)"
            )
            findings.append(("PORTABILITY_CASE_COLLISION", issue, parent))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()

    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_portability", root)

    if human:
        print()
        print("Validating Filesystem Portability (Windows-safe paths)")
        print("==================================")
        print(f"Grimoire root: {root}")
        print()

    paths = [p.relative_to(root).parts for p in walk_files(root)]
    for code, issue, path in check_paths(paths):
        reporter.error(code, issue, path=path)
        if human:
            err(f"{path}: {issue}")
    checked = len(paths)

    if not human:
        reporter.emit(args.format, checked={"paths": checked})
        return reporter.exit_code()

    print()
    print(f"Paths checked:    {checked}")
    print(f"Violations found: {reporter.error_count()}")
    print()
    print("==================================")
    if reporter.error_count() == 0:
        ok("Portability validation passed")
        return 0
    print(f"Portability validation failed with {reporter.error_count()} violation(s)")
    print()
    print("Windows reserves these filename characters: < > : \" | ? *")
    print("Replace them with portable alternatives, e.g. curly braces for")
    print("template placeholders ({target_app} instead of <target_app>).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
