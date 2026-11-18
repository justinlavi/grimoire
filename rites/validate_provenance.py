#!/usr/bin/env python3
"""Validate that external/hybrid pages and source wrappers cite real sources.

Walks every page in a grimoire (skipping templates and exempt files) and
checks each page whose `authority:` is `external` or `hybrid`:

  1. `sources:` is a list with at least one entry.
  2. No entry points at transient `inbox/` (error) or at `publish/`, which is
     disposable build output and not a content layer (warning).
  3. A local source path under `chapters/**/sources/` exists (error).
  4. Any other entry is a URL or names a file or folder that exists under the
     root; one that names nothing is a warning. This catches a typo such as
     `chapters/recipes/source/typo.pdf`. No URL is fetched.

Also checks Markdown source wrappers under `chapters/**/sources/`:

  1. A wrapper declaring `type: source` must use `authority: external`.
  2. It must have non-empty `sources:`.
  3. It must not cite itself.
  4. Rules 2 and 3 above hold for each entry, except that a wrapper may name
     its capture origin in words, so an entry that is no path is not a warning.

A page that is not valid UTF-8 is reported as `PROVENANCE_READ_ERROR` and
skipped.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_provenance [--grimoire <path>] [--format human|json|jsonl]
Exit codes: 0 = no error (warnings allowed), 1 = errors found,
2 = `--grimoire` is not a directory
"""

import argparse
import sys

from _lib import (
    add_grimoire_arg,
    frontmatter_sources,
    is_colocated_source_path,
    is_external_url,
    iter_pages,
    iter_colocated_source_markdown,
    parse_frontmatter,
    read_utf8,
    resolve_grimoire_arg,
    resolve_local_source_path,
    warn,
)
from diagnostics import DiagnosticReporter, add_output_format_arg

SCAN_DIRS = ["chapters", "docs", "invocations"]
EXEMPT_FILENAMES = {"README.md", "CHANGELOG.md"}
SKIP_DIRS = {"formulae", ".git"}


def names_existing_path(root, cited):
    """Return True when `cited`, a root-relative path, names a file or folder inside `root`."""
    try:
        target = (root / cited).resolve()
        target.relative_to(root)
        return target.exists()
    except (OSError, ValueError):
        return False


def report(reporter, human, severity, code, message, rel, hint=None):
    """Add one diagnostic, and print it for a human reader."""
    layer_rule = code in ("PROVENANCE_INBOX_SOURCE", "PROVENANCE_PUBLISH_SOURCE")
    add = reporter.error if severity == "error" else reporter.warning
    add(
        code,
        message,
        path=rel,
        hint=hint,
        docs_reference="docs/operating_model.md" if layer_rule else "docs/page_schema.md",
    )
    if human:
        warn(f"{rel}: {message}")


def check_source_reference(src, rel, root, reporter, human, *, path_required=True):
    """Add diagnostics for one `sources:` entry.

    `path_required` is False for a source wrapper, whose entry may name the
    capture origin in words instead of a path.
    """
    if not isinstance(src, str) or not src:
        return
    if src.startswith("inbox/"):
        report(
            reporter, human, "error", "PROVENANCE_INBOX_SOURCE",
            f"source '{src}' points at inbox/ (transient: cite a chapter-local source artifact instead)",
            rel, hint="Pages must cite chapter-local source artifacts or external URLs.",
        )
        return
    if is_external_url(src):
        return
    cited = src.replace("\\", "/")
    while cited.startswith("./"):
        cited = cited[2:]
    if cited.split("/", 1)[0].casefold() == "publish":
        report(
            reporter, human, "warning", "PROVENANCE_PUBLISH_SOURCE",
            f"source '{src}' points at publish/ (disposable build output, not a content layer)",
            rel, hint="Cite the chapter-local source the published file was built from.",
        )
        return
    if is_colocated_source_path(src):
        target = resolve_local_source_path(root, src)
        if target is None or not target.exists():
            report(
                reporter, human, "error", "PROVENANCE_SOURCE_MISSING",
                f"source '{src}' does not resolve under chapters/**/sources/",
                rel,
            )
        return
    if path_required and not names_existing_path(root, cited):
        report(
            reporter, human, "warning", "PROVENANCE_SOURCE_UNRESOLVED",
            f"source '{src}' is not a URL and names no file or folder under the grimoire",
            rel, hint="Correct the path, or cite the source's URL.",
        )


def read_page(path, rel, reporter, human):
    """Return a page's text, or None after reporting a file that cannot be read as UTF-8."""
    try:
        return read_utf8(path)
    except (OSError, UnicodeDecodeError) as exc:
        reporter.error(
            "PROVENANCE_READ_ERROR",
            f"page could not be read as UTF-8, so its sources were not checked ({exc})",
            path=rel,
        )
        if human:
            warn(f"{rel}: could not be read as UTF-8")
        return None


def is_scalar_sources(fields):
    """Return True when `sources:` holds one value where a list is required."""
    value = fields.get("sources")
    return isinstance(value, str) and bool(value) and not value.startswith("[")


def main():
    parser = argparse.ArgumentParser(description="Validate page provenance")
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()
    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_provenance", root)

    if human:
        print()
        print("Validating Provenance")
        print("==================================")
        print(f"Grimoire root: {root}")
        print()

    pages_checked = 0
    source_wrappers_checked = 0

    for path in iter_pages(root, SCAN_DIRS, exempt_filenames=EXEMPT_FILENAMES, skip_dirs=SKIP_DIRS):
        rel = path.relative_to(root).as_posix()
        if is_colocated_source_path(rel):
            continue
        content = read_page(path, rel, reporter, human)
        if content is None:
            continue
        fm = parse_frontmatter(content)
        authority = fm.get("authority", "")
        if authority not in ("external", "hybrid"):
            continue
        pages_checked += 1
        if is_scalar_sources(fm):
            report(reporter, human, "error", "PROVENANCE_SOURCES_LIST_REQUIRED",
                   "`sources:` must be a YAML list", rel)
            continue
        sources = frontmatter_sources(content)
        if not sources:
            report(reporter, human, "error", "PROVENANCE_MISSING_SOURCES",
                   f"authority='{authority}' but no `sources:` listed", rel)
            continue
        for src in sources:
            check_source_reference(src, rel, root, reporter, human)

    for path in iter_colocated_source_markdown(root):
        rel = path.relative_to(root).as_posix()
        content = read_page(path, rel, reporter, human)
        if content is None:
            continue
        fm = parse_frontmatter(content)
        if fm.get("type") != "source":
            continue
        source_wrappers_checked += 1
        if fm.get("authority", "") != "external":
            report(reporter, human, "error", "PROVENANCE_SOURCE_WRAPPER_AUTHORITY",
                   "source wrappers must declare authority='external'", rel,
                   hint="Source wrappers capture external material; authored synthesis belongs in chapters/.")

        if is_scalar_sources(fm):
            report(reporter, human, "error", "PROVENANCE_SOURCES_LIST_REQUIRED",
                   "`sources:` must be a YAML list", rel)
            continue
        sources = frontmatter_sources(content)
        if not sources:
            report(reporter, human, "error", "PROVENANCE_SOURCE_WRAPPER_MISSING_SOURCES",
                   "source wrapper must list its original URL, capture origin, or sibling raw artifact", rel)
            continue
        for src in sources:
            if src == rel:
                report(reporter, human, "error", "PROVENANCE_SOURCE_WRAPPER_SELF_REFERENCE",
                       "source wrapper must not cite itself", rel,
                       hint="Cite the original URL, capture origin, or sibling raw artifact instead.")
                continue
            check_source_reference(src, rel, root, reporter, human, path_required=False)

    checked = {
        "external_or_hybrid_pages": pages_checked,
        "source_wrappers": source_wrappers_checked,
    }
    if not human:
        reporter.emit(args.format, checked=checked)
        return reporter.exit_code()

    print()
    print(f"Pages with external/hybrid authority: {pages_checked}")
    print(f"Source wrappers checked:             {source_wrappers_checked}")
    print(f"Provenance violations:               {reporter.error_count()}")
    print(f"Provenance warnings:                 {reporter.warning_count()}")
    print()

    if reporter.error_count() == 0:
        print("Provenance validation passed")
        return 0
    print("Provenance validation failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
