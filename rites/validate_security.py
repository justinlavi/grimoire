#!/usr/bin/env python3
"""Security scanning for credentials and unsafe patterns in framework files.

Scans the framework's Markdown and Python files for credential-shaped assignments and
private keys (outside rites/, invocations/validators/ and invocations/dev/quality/, which
describe the patterns), and scans rites/*.py for calls to eval() and exec(). A file that
is not valid UTF-8 is reported as a warning and skipped; validate_encoding.py reports it
as an error.

Usage: python rites/validate_security.py
Mutation profile: read-only.
Exit codes: 0 = no security errors, 1 = security issues found
"""

import re
import sys

from _lib import default_framework_root, is_skipped, ok, read_utf8, walk_files, warn
from diagnostics import DiagnosticReporter, add_output_format_arg

FRAMEWORK_ROOT = default_framework_root()

FORBIDDEN_PATTERNS = [
    (re.compile(r"""password\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "password assignment"),
    (re.compile(r"""api[_-]?key\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "API key assignment"),
    (re.compile(r"""secret\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "secret assignment"),
    (re.compile(r"""token\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "token assignment"),
    (re.compile(r"BEGIN.*PRIVATE KEY"), "private key"),
]

# `\b` keeps `ast.literal_eval(` and `cursor.execute(` out of the match.
EVAL_CALL_RE = re.compile(r"\beval\(")
EXEC_CALL_RE = re.compile(r"\bexec\(")

SKIP_DIRS = {"rites", "invocations/validators", "invocations/dev/quality"}


def read_or_report(path, reporter, human):
    """Return a file's text, or None after reporting that it does not decode."""
    try:
        return read_utf8(path)
    except (OSError, UnicodeDecodeError) as exc:
        rel = path.relative_to(FRAMEWORK_ROOT).as_posix()
        reporter.warning(
            "SECURITY_READ_ERROR",
            f"could not read as UTF-8, so it was not scanned: {exc}",
            path=rel,
            hint="Run /grm-dev-validate encoding.",
        )
        if human:
            warn(f"Not scanned, unreadable: {rel}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Security scanning for framework files")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_security", FRAMEWORK_ROOT)

    if human:
        print()
        print("Validating Framework Security")
        print("==================================")
        print(f"Framework root: {FRAMEWORK_ROOT}")
        print()

    if human:
        print("Scanning for potential credentials...")
    cred_found = 0

    for path in walk_files(FRAMEWORK_ROOT):
        if path.suffix not in (".md", ".py"):
            continue

        rel = path.relative_to(FRAMEWORK_ROOT).as_posix()
        if is_skipped(rel, SKIP_DIRS):
            continue

        content = read_or_report(path, reporter, human)
        if content is None:
            continue

        for pattern, label in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(content):
                reporter.error(
                    "SECURITY_CREDENTIAL_PATTERN",
                    f"found potential {label}",
                    path=rel,
                    hint=f"Match: {match.group()[:80]}",
                )
                if human:
                    print()
                    print(f"  CRED   Found potential {label}: {rel}")
                    print(f"         Match: {match.group()[:80]}")
                cred_found += 1

    if human and cred_found == 0:
        ok("No potential credentials found")
    if human:
        print()

    if human:
        print("Checking for unsafe script patterns...")
    unsafe = 0

    rites_dir = FRAMEWORK_ROOT / "rites"
    if rites_dir.is_dir():
        for path in sorted(rites_dir.glob("*.py")):
            if path.name == "validate_security.py":
                continue

            content = read_or_report(path, reporter, human)
            if content is None:
                continue

            if EVAL_CALL_RE.search(content):
                reporter.error(
                    "SECURITY_EVAL",
                    "script uses eval()",
                    path=path,
                    hint="Use explicit parsing or dispatch instead.",
                )
                if human:
                    warn(f"Script uses eval() (security risk): {path.relative_to(FRAMEWORK_ROOT)}")
                unsafe += 1

            if EXEC_CALL_RE.search(content):
                reporter.error(
                    "SECURITY_EXEC",
                    "script uses exec()",
                    path=path,
                    hint="Use explicit APIs instead.",
                )
                if human:
                    warn(f"Script uses exec() (security risk): {path.relative_to(FRAMEWORK_ROOT)}")
                unsafe += 1

    if human and unsafe == 0:
        ok("No unsafe script patterns found")
    if human:
        print()

    if not human:
        reporter.emit(args.format, checked={"credential_hits": cred_found, "unsafe_hits": unsafe})
        return reporter.exit_code()

    print("==================================")
    if reporter.error_count() == 0:
        print("Security validation passed")
        return 0
    print(f"Security validation failed with {reporter.error_count()} issues")
    return 1


if __name__ == "__main__":
    sys.exit(main())
