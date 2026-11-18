#!/usr/bin/env python3
r"""Stamp a new grimoire page from the page formula with validated frontmatter.

Renders `formulae/page.formula.md` into a target page under a grimoire's
`chapters/` tree, filling the frontmatter an author would otherwise hand-type:
`type`, `title`, `tags`, `authority`, `sources`, and `last_verified` (stamped
with today's date). The page body structure comes from the formula, which stays
the single source of page shape; this rite stamps the fields and the title.

Stamping `last_verified` with a real date is the mechanical half of page
authoring (the script-vs-AI split): the agent decides the path, type, title, and
tags; the rite guarantees schema-valid, sentinel-free frontmatter so a page
never ships with the formula's placeholder date.

Defaults to a dry-run that prints the rendered page; pass --apply to write it.
Refuses to overwrite an existing file, and a path that does not resolve to a
`.md` file inside the grimoire's `chapters/` folder.

A grimoire registered for reading on this computer (`"access": "read"` in the
library) is refused in plan and apply mode alike.

Mutation profile: plan_apply. Plan mode writes nothing; `--apply` creates one
page, as UTF-8 with LF line endings.

Usage:
    FRAMEWORK_HOME/bin/grimoire new_page --grimoire ROOT \
        --path chapters/<chapter>/<slug>.md \
        --type concept --title "<title>" \
        [--tags a,b] [--authority grimoire] [--sources s1,s2] [--apply] \
        [--format human|json|jsonl]

Exit codes: 0 = preview shown or page written; 1 = refusal (invalid type,
authority, sources or path, an existing file, an unreadable formula);
2 = invalid arguments.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from _lib import (
    PAGE_AUTHORITIES,
    PAGE_TYPES as SCHEMA_PAGE_TYPES,
    add_grimoire_arg,
    read_only_refusal,
    read_utf8,
    resolve_grimoire_arg,
    write_utf8,
)
from diagnostics import ResultReporter, add_output_format_arg

FRAMEWORK_PATH = Path(__file__).resolve().parent.parent
PAGE_FORMULA = FRAMEWORK_PATH / "formulae" / "page.formula.md"

# This rite stamps knowledge pages; hubs and source wrappers come from their own formulae.
PAGE_TYPES = tuple(t for t in SCHEMA_PAGE_TYPES if t not in ("hub", "source"))
VALID_AUTHORITIES = PAGE_AUTHORITIES

_PLAIN_TAG_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
# YAML reads these as line breaks inside a double-quoted scalar, so they are written escaped.
_YAML_LINE_BREAK_CODES = (0x85, 0x2028, 0x2029)

# Frontmatter keys this rite stamps; every other formula key passes through.
STAMPED_KEYS = {"type", "title", "tags", "sources", "authority", "last_verified"}


def split_csv(value):
    """Split a comma-separated option into a list of trimmed, non-empty items."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def default_tags(path_parts, type_, extra):
    """Build schema-aligned tags: chapter facet, type facet, then extras (deduped)."""
    tags = []
    if len(path_parts) >= 3 and path_parts[0] == "chapters":
        tags.append(f"chapter/{path_parts[1]}")
    tags.append(f"type/{type_}")
    tags.extend(extra)
    seen = set()
    ordered = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def strip_leading_comment(body):
    """Drop the formula's leading authoring-guidance HTML comment, if present."""
    stripped = body.lstrip("\n")
    if stripped.startswith("<!--"):
        close = stripped.find("-->")
        if close != -1:
            stripped = stripped[close + len("-->"):]
    return "\n" + stripped.lstrip("\n")


def yaml_quote(value):
    """Render a string as a YAML double-quoted scalar, escaping what the syntax reserves."""
    quoted = json.dumps(value, ensure_ascii=False)
    for code in _YAML_LINE_BREAK_CODES:
        quoted = quoted.replace(chr(code), "\\u" + format(code, "04x"))
    return quoted


def render_yaml_list(items):
    """Render a YAML inline list of double-quoted strings."""
    return "[" + ", ".join(yaml_quote(item) for item in items) + "]"


def render_tags(tags):
    """Render tags as a YAML inline list, quoting any tag that is not a plain path-like word."""
    return "[" + ", ".join(t if _PLAIN_TAG_RE.match(t) else yaml_quote(t) for t in tags) + "]"


def render_page(template_text, *, type_, title, tags, authority, sources, today):
    """Render the formula into a page, stamping frontmatter and the title."""
    if not template_text.startswith("---\n"):
        raise ValueError("page formula is missing opening frontmatter")
    close = template_text.find("\n---", 4)
    if close == -1:
        raise ValueError("page formula is missing closing frontmatter")
    frontmatter = template_text[4:close]
    body = template_text[close + len("\n---"):]

    overrides = {
        "type": type_,
        "title": yaml_quote(title),
        "tags": render_tags(tags),
        "sources": render_yaml_list(sources),
        "authority": authority,
        "last_verified": today,
    }

    new_lines = []
    for line in frontmatter.splitlines():
        key = line.split(":", 1)[0].strip() if ":" in line else None
        if key in overrides:
            new_lines.append(f"{key}: {overrides[key]}")
        else:
            new_lines.append(line)

    body = strip_leading_comment(body).replace("[Title]", " ".join(title.splitlines()))
    return "---\n" + "\n".join(new_lines) + "\n---\n" + body


def resolve_target(grimoire_root, rel_path):
    """Resolve and validate a target page path under the grimoire's chapters/.

    Returns (target_abs, error_message). error_message is None on success.
    """
    candidate = Path(rel_path)
    if candidate.is_absolute() or candidate.drive or candidate.root:
        return None, f"--path must be relative to the grimoire root, not '{rel_path}'"
    target = (grimoire_root / candidate).resolve()
    try:
        rel = target.relative_to(grimoire_root)
    except ValueError:
        return None, f"--path '{rel_path}' escapes the grimoire root"
    if rel.parts[:1] != ("chapters",) or len(rel.parts) < 2:
        return None, "--path must live under chapters/ (pages live in the chapters layer)"
    if target.suffix != ".md":
        return None, f"--path must end in .md, got '{rel_path}'"
    return target, None


def main():
    parser = argparse.ArgumentParser(
        description="Stamp a new grimoire page from the page formula"
    )
    add_grimoire_arg(parser)
    parser.add_argument("--path", required=True,
                        help="Target page path relative to the grimoire root, e.g. chapters/<chapter>/<slug>.md")
    parser.add_argument("--type", required=True, dest="type_",
                        help=f"Page type (one of: {', '.join(PAGE_TYPES)})")
    parser.add_argument("--title", required=True, help="Human-readable page title")
    parser.add_argument("--tags", default="", help="Extra tags, comma-separated")
    parser.add_argument("--authority", default="grimoire",
                        help=f"Authority model (one of: {', '.join(VALID_AUTHORITIES)})")
    parser.add_argument("--sources", default="",
                        help="Source paths/URLs, comma-separated (required for external/hybrid)")
    parser.add_argument("--apply", action="store_true",
                        help="Write the page (default: dry-run, print only)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    grimoire_root = resolve_grimoire_arg(args.grimoire)
    reporter = ResultReporter("new_page", root=grimoire_root,
                              mode="apply" if args.apply else "plan")

    def fail(message):
        reporter.message("error", message)
        if human:
            print(f"  [ERROR] {message}", file=sys.stderr)
        else:
            reporter.emit(args.format)
        return 1

    refusal = read_only_refusal(grimoire_root)
    if refusal:
        reporter.message("error", refusal)
        reporter.set_status("blocked")
        if human:
            print(f"  [ERROR] {refusal}", file=sys.stderr)
        else:
            reporter.emit(args.format, summary={"access": "read"})
        return 1

    if args.type_ not in PAGE_TYPES:
        return fail(f"invalid type '{args.type_}' (must be one of {list(PAGE_TYPES)})")
    if args.authority not in VALID_AUTHORITIES:
        return fail(f"invalid authority '{args.authority}' (must be one of {list(VALID_AUTHORITIES)})")

    sources = split_csv(args.sources)
    if args.authority in ("external", "hybrid") and not sources:
        return fail(f"authority '{args.authority}' requires at least one --sources entry")

    target, error = resolve_target(grimoire_root, args.path)
    if error:
        return fail(error)
    if target.exists():
        return fail(f"refusing to overwrite existing file: {target.relative_to(grimoire_root)}")

    rel = target.relative_to(grimoire_root)
    tags = default_tags(rel.parts, args.type_, split_csv(args.tags))
    today = datetime.date.today().isoformat()

    try:
        template_text = read_utf8(PAGE_FORMULA)
        content = render_page(
            template_text,
            type_=args.type_,
            title=args.title,
            tags=tags,
            authority=args.authority,
            sources=sources,
            today=today,
        )
    except (OSError, ValueError) as exc:
        return fail(f"could not render page from formula: {exc}")

    if not args.apply:
        if human:
            print()
            print(f"Would create: {rel}")
            print("----------------------------------")
            print(content, end="" if content.endswith("\n") else "\n")
            print("----------------------------------")
            print("  Dry-run. Re-run with --apply to write the page.")
            print()
        else:
            reporter.emit(args.format, summary={"target": rel.as_posix(), "would_create": True})
        return 0

    write_utf8(target, content)
    reporter.mutation("create", path=target, detail=f"{args.type_} | {args.title}")
    if human:
        print(f"  [OK]    Created {rel}")
    else:
        reporter.emit(args.format, summary={"target": rel.as_posix()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
