#!/usr/bin/env python3
"""Validates internal links with layer-aware Markdown/wikilink policy.

Resolves two link forms:

  1. Standard Markdown links: `[text](path/to/file.md)` - required in
     public documentation such as README files and docs/.
  2. Wikilinks: `[[path/to/page|display text]]` - required in vault and
     AI-routing surfaces, resolved as root-relative paths.

External URLs, same-page anchors, and non-Markdown local artifacts use
standard Markdown links in every layer. A link that does not resolve is an
error, including one whose target spells a template word such as `Title`; only
a target holding `{` or `<`, or (under `formulae/`) one of the template words
in `_lib.PLACEHOLDER_PROSE_TOKENS`, is a placeholder and is not checked.

Warns when wikilink display text repeats ancestor context instead of matching
the target filename stem. The path carries location; the label should name the
target page.

A page that is not valid UTF-8 is reported as `LINK_READ_ERROR` and skipped.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_links [--grimoire <path>] [--format human|json|jsonl]
Exit codes: 0 = no error (label warnings allowed), 1 = errors found,
2 = `--grimoire` is not a directory
"""

import os
import re
import sys
from pathlib import Path

from _lib import (
    LINK_RE,
    WIKILINK_RE,
    add_grimoire_arg,
    is_external_url,
    is_placeholder_target,
    iter_link_pages,
    markdown_link_path,
    public_document,
    read_utf8,
    resolve_grimoire_arg,
    resolve_wikilink_path,
    spell_on_disk,
    strip_code_blocks,
    wikilink_target_body,
)
from diagnostics import DiagnosticReporter, add_output_format_arg

def resolve_wikilink(target, root):
    """Return the resolved Path of a wikilink's inner text, or None."""
    return resolve_wikilink_path(wikilink_target_body(target), root)


def wikilink_display_text(target):
    """Return display text after `|`, or empty string if no display is present."""
    if "|" not in target:
        return ""
    return target.split("|", 1)[1].strip()


def label_key(text):
    """Normalize a filename stem or display label for comparison."""
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def rel_posix(path, root):
    """Return a repository-root relative path using POSIX separators."""
    return path.relative_to(root).as_posix()


def expected_markdown_rel(target_path, source_path, root):
    """Return the root-relative POSIX path a Markdown link spells, as written."""
    normalized = target_path.replace("\\", "/")
    if normalized.startswith("/"):
        combined = normalized.lstrip("/")
    else:
        source_dir = source_path.parent.relative_to(root).as_posix()
        combined = f"{source_dir}/{normalized}" if source_dir != "." else normalized
    return os.path.normpath(combined).replace("\\", "/")


def case_mismatch(expected_rel, root):
    """Return the on-disk spelling when it differs from ``expected_rel`` only by case."""
    actual = spell_on_disk(expected_rel, root)
    if actual is None or actual == expected_rel:
        return None
    return actual


def resolve_markdown_link(target_path, source_path, root):
    """Resolve a standard Markdown link target relative to its source page."""
    if target_path.startswith("/"):
        resolved = root / target_path.lstrip("/")
    else:
        resolved = (source_path.parent / target_path).resolve()

    try:
        return resolved.resolve()
    except OSError:
        return resolved


def markdown_page_reference(target_path, resolved):
    """Return True when a standard Markdown link points at an internal page."""
    normalized = target_path.replace("\\", "/").rstrip("/")
    if normalized.endswith(".md"):
        return True
    if resolved.is_file() and resolved.suffix == ".md":
        return True
    if resolved.is_dir() and (resolved / "README.md").is_file():
        return True
    if not Path(normalized).suffix and resolved.with_suffix(".md").is_file():
        return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate internal links with layer-aware style rules")
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()
    grimoire_root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_links", grimoire_root)

    files_checked = 0

    if human:
        print()
        print("Validating Internal Links and Wikilinks")
        print("==================================")
        print(f"Grimoire root: {grimoire_root}")
        print()

        print("Scanning markdown files for broken links and layer-specific link styles...")

    for path in iter_link_pages(grimoire_root):
        rel = rel_posix(path, grimoire_root)

        try:
            content = read_utf8(path)
        except UnicodeDecodeError as exc:
            reporter.error(
                "LINK_READ_ERROR",
                f"page is not valid UTF-8, so its links were not checked ({exc})",
                path=rel,
                hint="Save the file as UTF-8; validate_encoding reports the same file.",
            )
            if human:
                print(f"  ERROR   {rel}: not valid UTF-8, links not checked")
            continue
        except OSError as exc:
            reporter.error(
                "LINK_READ_ERROR",
                f"page could not be read, so its links were not checked ({exc})",
                path=rel,
            )
            if human:
                print(f"  ERROR   {rel}: could not be read, links not checked")
            continue
        if not content.splitlines():
            continue
        files_checked += 1

        scanable = strip_code_blocks(content)
        public_page = public_document(path, grimoire_root)
        in_formula = rel.startswith("formulae/")


        for link_match in LINK_RE.finditer(scanable):
            link = link_match.group(1)
            line_number = scanable.count("\n", 0, link_match.start()) + 1

            if is_external_url(link) or is_placeholder_target(link, in_formula=in_formula):
                continue

            target_path = markdown_link_path(link)
            if not target_path:
                continue

            resolved = resolve_markdown_link(target_path, path, grimoire_root)
            try:
                resolved.relative_to(grimoire_root)
                internal = True
            except ValueError:
                internal = False

            if internal and markdown_page_reference(target_path, resolved) and not public_page:
                reporter.error(
                    "LINK_MARKDOWN_INTERNAL",
                    f"vault/AI surface uses a markdown link instead of a wikilink: {link}",
                    path=rel,
                    line=line_number,
                    hint="Use a repository-root relative wikilink, e.g. [[path/to/page|page]].",
                    docs_reference="docs/obsidian.md",
                )
                if human:
                    print(f"  STYLE   {rel}:{line_number}:")
                    print(f"          Markdown page link: {link}")
                    print("          Use a full-path wikilink in vault and AI-routing surfaces.")

            expected_rel = expected_markdown_rel(target_path, path, grimoire_root)
            if not resolved.exists():
                guess = spell_on_disk(expected_rel, grimoire_root) if internal else None
                hint = f"Resolved to: {resolved}"
                if guess:
                    hint = f"Did you mean {guess}? Links must match on-disk casing exactly."
                reporter.error(
                    "LINK_MARKDOWN_BROKEN",
                    f"markdown link does not resolve: {link}",
                    path=rel,
                    line=line_number,
                    hint=hint,
                )
                if human:
                    print(f"  BROKEN  {rel}:{line_number}:")
                    print(f"          Link: {link}")
                    print(f"          {hint}")
            elif internal:
                actual = case_mismatch(expected_rel, grimoire_root)
                if actual:
                    reporter.error(
                        "LINK_MARKDOWN_CASE_MISMATCH",
                        f"markdown link casing differs from the file on disk: {link}",
                        path=rel,
                        line=line_number,
                        hint=(
                            f"On disk: {actual}. The link resolves here only because this "
                            "filesystem ignores case; it breaks on Linux and in site builds."
                        ),
                        docs_reference="docs/obsidian.md",
                    )
                    if human:
                        print(f"  CASE    {rel}:{line_number}:")
                        print(f"          Link: {link}")
                        print(f"          On disk: {actual}")

        for wl_match in WIKILINK_RE.finditer(scanable):
            target = wl_match.group(1)
            line_number = scanable.count("\n", 0, wl_match.start()) + 1
            if is_placeholder_target(target, in_formula=in_formula):
                continue
            resolved = resolve_wikilink(target, grimoire_root)
            body = wikilink_target_body(target).replace("\\", "/")
            expected_rel = body if body.endswith(".md") else f"{body}.md"
            if public_page:
                reporter.error(
                    "LINK_WIKILINK_PUBLIC_DOC",
                    f"public documentation uses a wikilink instead of a Markdown link: [[{target}]]",
                    path=rel,
                    line=line_number,
                    hint="Use a relative Markdown link so README/docs pages remain clickable on Git hosts.",
                    docs_reference="docs/operating_model.md",
                )
                if human:
                    print(f"  STYLE   {rel}:{line_number}:")
                    print(f"          Public-doc wikilink: [[{target}]]")
                    print("          Use a relative Markdown link for public documentation.")
                continue
            if resolved is None:
                guess = spell_on_disk(expected_rel, grimoire_root)
                hint = "Use a full-path wikilink target relative to the grimoire root."
                if guess:
                    hint = f"Did you mean [[{guess[:-3]}]]? Wikilinks must match on-disk casing exactly."
                reporter.error(
                    "LINK_WIKILINK_BROKEN",
                    f"wikilink does not resolve as a repository path: [[{target}]]",
                    path=rel,
                    line=line_number,
                    hint=hint,
                    docs_reference="docs/obsidian.md",
                )
                if human:
                    print(f"  BROKEN  {rel}:{line_number}:")
                    print(f"          Wikilink: [[{target}]] (must resolve as a repository path; aliases and filename-only targets are invalid)")
                    if guess:
                        print(f"          {hint}")
                continue

            actual = case_mismatch(expected_rel, grimoire_root)
            if actual:
                reporter.error(
                    "LINK_CASE_MISMATCH",
                    f"wikilink casing differs from the file on disk: [[{target}]]",
                    path=rel,
                    line=line_number,
                    hint=(
                        f"On disk: {actual}. The link resolves here only because this "
                        "filesystem ignores case; it breaks on Linux, in Obsidian on Linux, "
                        "and in site builds."
                    ),
                    docs_reference="docs/obsidian.md",
                )
                if human:
                    print(f"  CASE    {rel}:{line_number}:")
                    print(f"          Wikilink: [[{target}]]")
                    print(f"          On disk: {actual}")
                continue

            display = wikilink_display_text(target)
            if display and label_key(display) != label_key(resolved.stem):
                expected = resolved.stem.replace("_", " ").replace("-", " ")
                reporter.warning(
                    "LINK_LABEL_VERBOSE",
                    f"display label should be target filename only: \"{expected}\"",
                    path=rel,
                    line=line_number,
                    hint=f"Wikilink: [[{target}]]",
                    docs_reference="docs/obsidian.md",
                )
                if human:
                    print(f"  WARN    {rel}:{line_number}:")
                    print(f"          Wikilink: [[{target}]]")
                    print(f"          Display label should be target filename only: \"{expected}\"")

    checked = {"files": files_checked}
    if not human:
        reporter.emit(args.format, checked=checked)
        return reporter.exit_code()

    print()
    print("==================================")
    if reporter.error_count() == 0:
        print("Link validation passed (no broken links or layer-style violations found)")
        if reporter.warning_count():
            print(f"Link label warnings: {reporter.warning_count()}")
        return 0
    print(f"Link validation failed with {reporter.error_count()} error(s)")
    if reporter.warning_count():
        print(f"Link label warnings: {reporter.warning_count()}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
