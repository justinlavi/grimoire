#!/usr/bin/env python3
"""Validates Markdown rendering rules and the shape of invocations, hubs and formulae.

Checks, in one scan of the Markdown files under the root:
- an invocation page (anything under invocations/ that is not a hub) opens with a title,
  and a `type: playbook` page also carries the six sections of a deterministic procedure;
- a hub under invocations/ is at most 200 lines (a hub's existence is checked by
  validate_structure.py and validate_grimoire_structure.py);
- a formula under formulae/ has a title;
- table delimiter rows use three or more hyphens, code fences close, and tree examples use
  pipe branch markers.

A Markdown file that is not valid UTF-8 is reported as a warning and skipped;
validate_encoding.py reports it as an error.

Usage:
    python rites/validate_format.py
    python rites/validate_format.py --grimoire ~/grimoires/cooking-grimoire

Mutation profile: read-only.
Exit codes: 0 = no format errors, 1 = format errors found
"""

import argparse
import re
import sys

from _lib import (
    FENCE_RE,
    add_grimoire_arg,
    is_hub,
    is_inside_colocated_source_dir,
    ok,
    page_type,
    read_utf8,
    resolve_grimoire_arg,
    walk_files,
    warn,
)
from diagnostics import DiagnosticReporter, add_output_format_arg

# Every invocation page opens with a title. A playbook (`type: playbook`) also
# carries the six parts of a deterministic procedure (docs/writing_standard.md).
INVOCATION_TITLE = (r"^# ", "Title heading (# ...)")
PLAYBOOK_REQUIRED_SECTIONS = [
    (r"^## Trigger\s*$", "## Trigger section"),
    (r"^## Inputs\s*$", "## Inputs section"),
    (r"^## Never\s*$", "## Never section"),
    (r"^## Steps\s*$", "## Steps section"),
    (r"^## Evidence and checks\s*$", "## Evidence and checks section"),
    (r"^## Outputs\s*$", "## Outputs section"),
]

# Pattern templates and shared fragments are not standalone invocations.
INVOCATION_EXEMPT = {
    "grimoire_directory_guard.md",
    "subagent_lanes.md",
}

HUB_MAX_LINES = 200
SHORT_TABLE_DELIMITER_RE = re.compile(
    r"^\|?\s*:?-{1,2}:?\s*(\|\s*:?-{1,2}:?\s*)+\|?\s*$"
)
BACKTICK_TREE_BRANCH_RE = re.compile(r"^\s*(?:\|\s*)*`--\s+\S")


def required_invocation_sections(content: str) -> list[tuple[str, str]]:
    """The sections an invocation page must carry, by its frontmatter `type`."""
    if page_type(content) == "playbook":
        return [INVOCATION_TITLE, *PLAYBOOK_REQUIRED_SECTIONS]
    return [INVOCATION_TITLE]


def short_table_delimiter_rows(content):
    """Return lines where a Markdown table delimiter uses fewer than 3 hyphens."""
    in_fence = False
    fence = None

    for line_number, line in enumerate(content.splitlines(), 1):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence = marker
            elif marker == fence:
                in_fence = False
                fence = None
            continue

        if not in_fence and SHORT_TABLE_DELIMITER_RE.match(line):
            yield line_number, line


def unclosed_code_fences(content):
    """Return the opening line if a fenced code block is never closed."""
    in_fence = False
    fence = None
    start_line = None

    for line_number, line in enumerate(content.splitlines(), 1):
        fence_match = FENCE_RE.match(line)
        if not fence_match:
            continue

        marker = fence_match.group(1)
        if not in_fence:
            in_fence = True
            fence = marker
            start_line = line_number
        elif marker == fence:
            in_fence = False
            fence = None
            start_line = None

    if in_fence:
        return start_line, fence
    return None


def backtick_tree_branches(content):
    """Return pipe-tree lines that use backtick branch markers."""
    for line_number, line in enumerate(content.splitlines(), 1):
        if BACKTICK_TREE_BRANCH_RE.match(line):
            yield line_number, line


def read_pages(root, reporter, human):
    """Return `[(path, relative path, text)]` for every Markdown file under root.

    A file that does not decode is reported as a warning and left out.
    """
    pages = []
    for path in walk_files(root, "*.md"):
        rel = path.relative_to(root)
        try:
            pages.append((path, rel, read_utf8(path)))
        except (OSError, UnicodeDecodeError) as exc:
            reporter.warning(
                "FORMAT_READ_ERROR",
                f"could not read as UTF-8, so format was not checked: {exc}",
                path=path,
                hint="Run /grm-dev-validate encoding or /grm-check encoding.",
            )
            if human:
                warn(f"Not checked, unreadable: {rel}")
    return pages


def check_invocations(pages, reporter, human):
    """Rules 1 and 2: invocation pages carry a title, and playbooks their six sections."""
    if human:
        print("Checking invocation format compliance...")
    violations = 0
    for path, rel, content in pages:
        if rel.parts[0] != "invocations" or path.name in INVOCATION_EXEMPT or is_hub(path):
            continue
        file_errors = 0
        for pattern, label in required_invocation_sections(content):
            if re.search(pattern, content, re.MULTILINE):
                continue
            if human and file_errors == 0:
                warn(f"Format violations in: {rel}")
            reporter.error(
                "FORMAT_MISSING_INVOCATION_SECTION",
                f"missing section: {label}",
                path=path,
            )
            if human:
                print(f"          Missing section: {label}")
            file_errors += 1
            violations += 1
    if human and violations == 0:
        ok("All invocations have required sections")
    if human:
        print()
    return violations


def check_hubs(pages, reporter, human):
    """Rule 3: hubs under invocations/ stay thin routers."""
    if human:
        print(f"Checking hub files are thin routers (at most {HUB_MAX_LINES} lines)...")
    violations = 0
    for path, rel, content in pages:
        if rel.parts[0] != "invocations" or not is_hub(path):
            continue
        lines = len(content.splitlines())
        if lines > HUB_MAX_LINES:
            reporter.error(
                "FORMAT_HUB_TOO_LONG",
                f"hub too long ({lines} lines, at most {HUB_MAX_LINES})",
                path=path,
            )
            if human:
                warn(f"Hub too long ({lines} lines, at most {HUB_MAX_LINES}): {rel}")
            violations += 1
    if human and violations == 0:
        ok("All hub files are appropriately sized")
    if human:
        print()
    return violations


def check_formulae(pages, reporter, human):
    """Rule 4: formulae have a title heading."""
    if human:
        print("Checking formula format...")
    violations = 0
    for path, rel, content in pages:
        if rel.parts[0] != "formulae":
            continue
        if not re.search(r"^# ", content, re.MULTILINE):
            reporter.error(
                "FORMAT_FORMULA_MISSING_TITLE",
                "formula missing title heading",
                path=path,
            )
            if human:
                warn(f"Formula missing title heading: {rel}")
            violations += 1
    if human and violations == 0:
        ok("All formulae have proper format")
    if human:
        print()
    return violations


def check_table_delimiters(pages, reporter, human):
    """Rule 5: Markdown table delimiter rows use 3+ hyphens per cell."""
    if human:
        print("Checking markdown table delimiter rows...")
    violations = 0
    for path, rel, content in pages:
        for line_number, line in short_table_delimiter_rows(content):
            reporter.error(
                "FORMAT_SHORT_TABLE_DELIMITER",
                f"short table delimiter row: `{line}`",
                path=path,
                line=line_number,
            )
            if human:
                warn(f"Short table delimiter row: {rel}:{line_number} `{line}`")
            violations += 1
    if human and violations == 0:
        ok("All markdown table delimiter rows use 3+ hyphens")
    if human:
        print()
    return violations


def check_fences(pages, reporter, human):
    """Rule 6: fenced code blocks close."""
    if human:
        print("Checking fenced code blocks...")
    violations = 0
    for path, rel, content in pages:
        violation = unclosed_code_fences(content)
        if violation:
            line_number, fence = violation
            reporter.error(
                "FORMAT_UNCLOSED_CODE_FENCE",
                f"unclosed code fence `{fence}`",
                path=path,
                line=line_number,
            )
            if human:
                warn(f"Unclosed code fence: {rel}:{line_number} `{fence}`")
            violations += 1
    if human and violations == 0:
        ok("All fenced code blocks are closed")
    if human:
        print()
    return violations


def check_tree_markers(pages, reporter, human):
    """Rule 7: directory tree examples use pipe branch markers, not backticks."""
    if human:
        print("Checking Markdown tree branch markers...")
    violations = 0
    for path, rel, content in pages:
        for line_number, line in backtick_tree_branches(content):
            reporter.error(
                "FORMAT_TREE_BACKTICK_MARKER",
                f"backtick tree branch marker: `{line}`",
                path=path,
                line=line_number,
            )
            if human:
                warn(f"Backtick tree branch marker: {rel}:{line_number} `{line}`")
            violations += 1
    if human and violations == 0:
        ok("All Markdown tree examples use pipe branch markers")
    if human:
        print()
    return violations


def main():
    parser = argparse.ArgumentParser(description="Validate Markdown, invocation, formula and hub format")
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()

    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_format", root)

    if human:
        print()
        print("Validating Markdown, Invocation, Formula, and Hub Format")
        print("==================================")
        print(f"Root: {root}")
        print()

    pages = read_pages(root, reporter, human)
    # Rules 5 to 7 skip chapter-local sources: imported material keeps its own formatting.
    rendered_pages = [page for page in pages if not is_inside_colocated_source_dir(page[1])]

    checked = {
        "invocation_violations": check_invocations(pages, reporter, human),
        "hub_violations": check_hubs(pages, reporter, human),
        "formula_violations": check_formulae(pages, reporter, human),
        "table_violations": check_table_delimiters(rendered_pages, reporter, human),
        "fence_violations": check_fences(rendered_pages, reporter, human),
        "tree_violations": check_tree_markers(rendered_pages, reporter, human),
    }
    if not human:
        reporter.emit(args.format, checked=checked)
        return reporter.exit_code()

    print("==================================")
    if reporter.error_count() == 0:
        print("Format validation passed")
        return 0
    print(f"Format validation failed with {reporter.error_count()} issues")
    return 1


if __name__ == "__main__":
    sys.exit(main())
