#!/usr/bin/env python3
"""Validate text encoding, newline, and mojibake safety.

The framework and grimoires may use Unicode, but every text file must be UTF-8
without BOM, use LF line endings, and avoid mojibake artifacts. Mojibake is a
UTF-8 sequence read in a single-byte encoding and saved again: U+00C3, U+00C2
or U+00E2 followed by the character that completes such a pair, or the
replacement character U+FFFD. Those letters alone are valid text, as in the
French words for a pie crust and a castle.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_encoding [--grimoire <path>] [--format human|json|jsonl]
Exit codes: 0 = success, 1 = violations found, 2 = `--grimoire` is not a directory
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _lib import add_grimoire_arg, err, ok, resolve_grimoire_arg, walk_files
from diagnostics import Diagnostic, DiagnosticReporter, add_output_format_arg

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "VERSION",
}
# Folders skipped at any depth, beside the ones `walk_files` prunes: tool
# caches and leftover run output.
SKIP_DIRS = {".mypy_cache", ".pytest_cache", "__pycache__"}

# What cp1252 and Latin-1 show for the continuation byte of a UTF-8 pair: the
# C1 controls and the printable characters cp1252 puts at 0x80-0x9F.
_CONTINUATION = "\u0080-\u009f" + bytes(range(0x80, 0xA0)).decode("cp1252", errors="ignore")
MOJIBAKE_PATTERNS = (
    re.compile(f"\u00c3[\u00a0-\u00bf{_CONTINUATION}]"),
    re.compile("\u00c2[\u00a0-\u00bf]"),
    re.compile(f"\u00e2[{_CONTINUATION}]"),
    re.compile("\ufffd"),
)
ASCII_ARTIFACTS = ("A" + "a" + ",a", "A" + ",a", " a" + "' ")
NUMERIC_RANGE_RE = re.compile(r"\b\d+\?\d+\b")


def is_text_candidate(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def iter_text_files(root: Path):
    for path in walk_files(root):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if is_text_candidate(path):
            yield path


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def first_numeric_range_artifact(text: str):
    """Return the first digit-question-mark-digit match outside a URL or a path, or None.

    A `?` between two numbers is a range whose dash was lost. In a token that
    holds `/` or `=` it is the start of a URL query string.
    """
    for match in NUMERIC_RANGE_RE.finditer(text):
        start = max(text.rfind(" ", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
        ends = [i for i in (text.find(" ", match.end()), text.find("\n", match.end())) if i != -1]
        token = text[start:min(ends) if ends else len(text)]
        if "/" not in token and "=" not in token:
            return match
    return None


def check_file(path: Path, root: Path) -> list[Diagnostic]:
    rel = path.relative_to(root).as_posix()
    reporter = DiagnosticReporter("validate_encoding", root)
    try:
        data = path.read_bytes()
    except OSError as exc:
        reporter.error("ENCODING_READ_ERROR", f"could not read ({exc})", path=rel)
        return reporter.diagnostics

    if data.startswith(b"\xef\xbb\xbf"):
        reporter.error("ENCODING_BOM", "UTF-8 BOM is not allowed", path=rel)
    if b"\r" in data:
        reporter.error("ENCODING_CRLF", "CRLF/CR line endings found; use LF", path=rel)

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        reporter.error("ENCODING_UTF8", f"not valid UTF-8 ({exc})", path=rel)
        return reporter.diagnostics

    for pattern in MOJIBAKE_PATTERNS:
        match = pattern.search(text)
        if match:
            reporter.error(
                "ENCODING_MOJIBAKE",
                f"probable mojibake sequence {match.group()!r}",
                path=rel,
                line=line_for_offset(text, match.start()),
            )
            break

    for marker in ASCII_ARTIFACTS:
        idx = text.find(marker)
        if idx != -1:
            reporter.error(
                "ENCODING_REPAIR_ARTIFACT",
                f"probable mojibake repair artifact {marker!r}",
                path=rel,
                line=line_for_offset(text, idx),
            )
            break

    match = first_numeric_range_artifact(text)
    if match:
        reporter.error(
            "ENCODING_REPAIR_ARTIFACT",
            f"probable numeric range repair artifact {match.group()!r}",
            path=rel,
            line=line_for_offset(text, match.start()),
        )

    return reporter.diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()

    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_encoding", root)

    if human:
        print()
        print("Validating Encoding and Newlines")
        print("================================")
        print(f"Root: {root}")
        print()

    checked = 0
    for path in iter_text_files(root):
        checked += 1
        reporter.diagnostics.extend(check_file(path, root))

    if not human:
        reporter.emit(args.format, checked={"files": checked})
        return reporter.exit_code()

    for diagnostic in reporter.diagnostics:
        location = diagnostic.path
        if diagnostic.line:
            location = f"{location}:{diagnostic.line}"
        err(f"{location}: {diagnostic.message}")

    print()
    print(f"Files checked:     {checked}")
    print(f"Violations found:  {reporter.error_count()}")
    print()
    print("================================")
    if reporter.error_count():
        print("Encoding validation failed")
        print()
        print("Use UTF-8 without BOM and LF line endings. Unicode is allowed,")
        print("but mojibake and repair artifacts are not.")
        return 1

    ok("Encoding validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
