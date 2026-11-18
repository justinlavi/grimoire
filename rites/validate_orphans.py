#!/usr/bin/env python3
"""Detect orphan pages in a grimoire.

A page is an orphan when no other markdown file in the grimoire reaches it
through a valid layer-specific page link: Markdown links in public docs and
full-path wikilinks in vault/AI surfaces. A page that links to itself is still
an orphan.

The page set is the one the link validator checks (`_lib.iter_link_pages`)
without `skills/` and `plugins/`. These pages need no inbound link:
  * the root hub: `<name>.md` at the root, where `<name>` is the manifest
    `name` of `grimoire.json` (or of `framework.json` for the framework) and
    falls back to the root folder's name, so a checkout under any folder name
    keeps its hub
  * `README.md`, `UPDATE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SKILL.md`
  * source wrappers under chapter-local `sources/` folders
Folder hubs (`<folder>/<folder>.md`) are checked like any page: a hub nothing
links to is a pointer missing from its parent hub.

A page that is not valid UTF-8 contributes no links; `validate_links` and
`validate_encoding` report it.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_orphans [--grimoire <path>] [--format human|json|jsonl]
Exit codes: 0 = no orphans, 1 = orphans found, 2 = `--grimoire` is not a directory
"""

import argparse
import json
import sys

from _lib import (
    LINK_RE,
    WIKILINK_RE,
    add_grimoire_arg,
    is_external_url,
    is_skipped,
    iter_link_pages,
    markdown_link_path,
    public_document,
    read_utf8,
    resolve_grimoire_arg,
    resolve_wikilink_path,
    root_hub_path,
    strip_code_blocks,
    wikilink_target_body,
)
from diagnostics import DiagnosticReporter, add_output_format_arg

EXEMPT_FILENAMES = {"README.md", "UPDATE.md", "CHANGELOG.md", "CONTRIBUTING.md", "SKILL.md"}
# Root-level folders whose pages are neither checked nor counted as link sources.
SKIP_DIRS = {"skills", "plugins"}


def collect_pages(root):
    return [
        path for path in iter_link_pages(root)
        if not is_skipped(path.relative_to(root), SKIP_DIRS)
    ]


def resolve_markdown_page_link(link, src, root):
    """Resolve a public-doc Markdown link to an internal Markdown page."""
    if is_external_url(link):
        return None
    target_path = markdown_link_path(link)
    if not target_path:
        return None
    if target_path.startswith("/"):
        target = root / target_path.lstrip("/")
    else:
        target = src.parent / target_path
    try:
        target = target.resolve()
        target.relative_to(root)
    except (OSError, ValueError):
        return None
    if target.is_file() and target.suffix == ".md":
        return target
    return None


def collect_inbound(pages, root):
    """Return the set of pages that another page links to."""
    inbound = set()
    for src in pages:
        try:
            content = read_utf8(src)
        except (OSError, UnicodeDecodeError):
            continue
        scanable = strip_code_blocks(content)
        own = src.resolve()
        found = []

        if public_document(src, root):
            for m in LINK_RE.finditer(scanable):
                found.append(resolve_markdown_page_link(m.group(1), src, root))

        for m in WIKILINK_RE.finditer(scanable):
            found.append(resolve_wikilink_path(wikilink_target_body(m.group(1)), root))

        inbound.update(
            target.resolve() for target in found
            if target is not None and target.resolve() != own
        )
    return inbound


def main():
    parser = argparse.ArgumentParser(description="Detect orphan pages in a grimoire")
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()
    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_orphans", root)

    if human:
        print()
        print("Validating Orphans")
        print("==================================")
        print(f"Grimoire root: {root}")
        print()

    pages = collect_pages(root)
    inbound = collect_inbound(pages, root)
    hub = root_hub_path(root).resolve()

    orphans = []
    for p in pages:
        if p.name in EXEMPT_FILENAMES or p.resolve() == hub:
            continue
        if p.resolve() in inbound:
            continue
        orphans.append(p.relative_to(root))
        reporter.error(
            "ORPHAN_PAGE",
            "no other page links to this page",
            path=p.relative_to(root).as_posix(),
        )

    if not human:
        reporter.emit(args.format, checked={"pages": len(pages), "orphans": len(orphans)})
        return reporter.exit_code()

    if not orphans:
        print("  OK    No orphan pages found")
    else:
        print(f"  {len(orphans)} orphan page(s): no other page links to them")
        for o in sorted(orphans):
            print(f"  ORPHAN  {o}")

    print()
    print("==================================")
    return reporter.exit_code()


if __name__ == "__main__":
    sys.exit(main())
