#!/usr/bin/env python3
r"""Repair filename-only and wrongly cased wikilinks to canonical full-path form.

Scans the pages that `_lib.iter_link_pages` yields, the same set the link
validator checks, for two kinds of wikilink:

  * a broken filename-only link, ``[[basename]]`` or ``[[basename|label]]``
    (Obsidian shorthand that does not resolve under the full-path rule), rewritten
    as ``[[chapters/<path>/<basename>|<label>]]``;
  * a full-path link whose casing differs from the file on disk, rewritten to
    the on-disk spelling (such a link resolves only on a case-insensitive
    filesystem and breaks on Linux and in site builds).

A rewrite keeps the link's ``#section`` and its label. A filename-only link
with no label gets the filename as its label, except in a table row, where
the added pipe would split the cell.

A filename-only link resolves in this order, first hit wins:

  (a) sibling in the source file's own directory
  (b) unique descendant of the source file's directory
  (c) unique descendant of the source file's chapter root
  (d) globally unique match anywhere under ``chapters/``

Ambiguous and unresolvable links are reported and left alone, never guessed.
A link whose own name matches nothing but whose display label names a page
is reported as ambiguous with that page as the candidate. A link that looks
like a template placeholder is reported and skipped. A page that does not
decode as UTF-8 is reported as unreadable and left untouched; the rite goes
on with the other pages.

A grimoire registered for reading on this computer (`"access": "read"` in the
library) is refused with ``--apply``; a dry run stays allowed.

Mutation profile: plan_apply. The default is a dry run that writes nothing;
``--apply`` rewrites the affected pages as UTF-8 with LF line endings.

Usage:
    FRAMEWORK_HOME/bin/grimoire repair_links --grimoire ROOT [--apply] \
        [--format human|json|jsonl]

Exit codes: ``--apply`` returns 0 when it completes, with ambiguous,
unresolvable and unreadable pages reported for follow-up. A dry run returns 1
when there is actionable work (repairs to apply, or links and pages needing
attention) and 0 when the grimoire is already clean. 2 = invalid arguments.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from _lib import (
    WIKILINK_RE,
    add_grimoire_arg,
    info,
    is_placeholder_target,
    is_skipped,
    iter_link_pages,
    mask_code,
    ok,
    read_only_refusal,
    read_utf8,
    rebuild_wikilink,
    resolve_grimoire_arg,
    resolve_wikilink_path,
    spell_on_disk,
    walk_files,
    warn,
    wikilink_target_body,
    write_utf8,
)
from diagnostics import ResultReporter, add_output_format_arg

# Kinds of finding, grouped by how the report presents them.
REPAIR_KINDS = ("fix", "case")
UNRESOLVED_KINDS = ("missing", "partial")


@dataclass(frozen=True)
class Finding:
    """One wikilink the rite repaired, skipped or could not resolve."""

    kind: str  # fix | case | ambiguous | missing | partial | placeholder
    rel: str
    line: int
    target: str
    new: str = ""
    detail: str = ""

    def human(self) -> str:
        where = f"{self.rel}:{self.line}: [[{self.target}]]"
        if self.kind == "fix":
            return f"  [FIX]   {where} -> {self.new}"
        if self.kind == "case":
            return f"  [CASE]  {where} -> {self.new}"
        if self.kind == "ambiguous":
            return f"  [AMBI] {where} - {self.detail}"
        if self.kind == "missing":
            return f"  [MISS] {where} - {self.detail}"
        return f"  [SKIP]  {where} - {self.detail}"


def wikilink_display(target: str) -> str:
    return target.partition("|")[2].strip()


def chapter_root_of(rel_path: Path) -> Optional[Path]:
    """For chapters/<chapter>/foo/bar.md return chapters/<chapter>; else None."""
    parts = rel_path.parts
    if len(parts) >= 2 and parts[0] == "chapters":
        return Path(parts[0]) / parts[1]
    return None


def build_basename_index(grimoire_root: Path) -> dict[str, list[Path]]:
    """Map every markdown basename (no .md) -> list of absolute paths."""
    index: dict[str, list[Path]] = {}
    chapters_dir = grimoire_root / "chapters"
    if not chapters_dir.is_dir():
        return index
    for path in walk_files(chapters_dir, "*.md"):
        index.setdefault(path.stem, []).append(path)
    return index


def resolve_basename(
    basename: str,
    source_abs: Path,
    grimoire_root: Path,
    index: dict[str, list[Path]],
) -> tuple[Optional[Path], list[Path]]:
    """Return (chosen, candidates). chosen=None means ambiguous or absent."""
    candidates = index.get(basename, [])
    if not candidates:
        return None, []

    src_dir = source_abs.parent
    src_chapter = chapter_root_of(source_abs.relative_to(grimoire_root))
    src_chapter_abs = (grimoire_root / src_chapter) if src_chapter else None

    siblings = [c for c in candidates if c.parent == src_dir and c != source_abs]
    if len(siblings) == 1:
        return siblings[0], candidates

    under_src_dir = [c for c in candidates if src_dir in c.parents]
    if len(under_src_dir) == 1:
        return under_src_dir[0], candidates

    if src_chapter_abs:
        under_chapter = [c for c in candidates if src_chapter_abs in c.parents or c.parent == src_chapter_abs]
        if len(under_chapter) == 1:
            return under_chapter[0], candidates

    if len(candidates) == 1:
        return candidates[0], candidates

    return None, candidates


def case_repair(body: str, grimoire_root: Path) -> Optional[str]:
    """The on-disk spelling of a full-path wikilink body when it differs only by case, else None."""
    if "/" not in body:
        return None
    expected = body if body.endswith(".md") else f"{body}.md"
    actual = spell_on_disk(expected, grimoire_root)
    if actual is None or actual == expected:
        return None
    return actual[:-3] if actual.endswith(".md") and not body.endswith(".md") else actual


def scan_page(
    text: str,
    source_path: Path,
    grimoire_root: Path,
    index: dict[str, list[Path]],
    rel: str,
) -> tuple[list[Finding], list[tuple[int, int, str]]]:
    """Return the findings for one page and the (start, end, replacement) edits that apply them.

    Code fences and inline code are masked, so the offsets found in the masked
    text are the offsets to edit in `text`.
    """
    findings: list[Finding] = []
    edits: list[tuple[int, int, str]] = []
    in_formula = is_skipped(rel, ("formulae",))
    lines = text.split("\n")

    for match in WIKILINK_RE.finditer(mask_code(text)):
        target = match.group(1)
        line_no = text.count("\n", 0, match.start()) + 1

        def found(kind: str, new: str = "", detail: str = "") -> None:
            findings.append(Finding(kind, rel, line_no, target, new, detail))

        if is_placeholder_target(target, in_formula=in_formula):
            found("placeholder", detail="looks like a template placeholder; not repaired")
            continue
        body = wikilink_target_body(target)
        respelled = case_repair(body, grimoire_root)
        if respelled is not None:
            new = f"[[{rebuild_wikilink(target, respelled)}]]"
            edits.append((match.start(), match.end(), new))
            found("case", new)
            continue
        if resolve_wikilink_path(body, grimoire_root) is not None:
            continue
        if "/" in body or not body:
            found("partial", detail="partial path or empty, not a simple basename")
            continue

        chosen, candidates = resolve_basename(body, source_path, grimoire_root, index)
        if chosen is not None:
            rel_target = chosen.relative_to(grimoire_root).with_suffix("").as_posix()
            in_table = lines[line_no - 1].lstrip().startswith("|")
            label = None if wikilink_display(target) else ("" if in_table else body)
            new = f"[[{rebuild_wikilink(target, rel_target, label=label)}]]"
            edits.append((match.start(), match.end(), new))
            found("fix", new)
        elif candidates:
            names = ", ".join(c.relative_to(grimoire_root).as_posix() for c in candidates)
            found("ambiguous", detail=f"{len(candidates)} candidates: {names}")
        else:
            label = wikilink_display(target)
            by_label = index.get(label, []) if label else []
            if by_label:
                names = ", ".join(c.relative_to(grimoire_root).as_posix() for c in by_label)
                found("ambiguous",
                      detail=f"no file named {body}.md; the display label names {len(by_label)} "
                             f"page(s): {names}")
            else:
                found("missing", detail=f"no file named {body}.md anywhere in chapters/")

    return findings, edits


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply (start, end, replacement) edits right to left so earlier offsets stay valid."""
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def repair_file(
    path: Path,
    grimoire_root: Path,
    index: dict[str, list[Path]],
    apply: bool,
    reporter: ResultReporter,
) -> Optional[list[Finding]]:
    """Return the findings for one page, rewriting it when `apply` and it has repairs.

    Returns None for a page that cannot be read as UTF-8; the page is untouched.
    """
    rel = path.relative_to(grimoire_root).as_posix()
    try:
        original = read_utf8(path)
    except (OSError, UnicodeDecodeError) as exc:
        reporter.message("warning", f"{rel}: not read, left untouched: {exc}", path=path)
        return None

    findings, edits = scan_page(original, path, grimoire_root, index, rel)
    for finding in findings:
        if finding.kind in REPAIR_KINDS:
            if apply:
                note = " (casing)" if finding.kind == "case" else ""
                reporter.mutation("repair", path=path,
                                  detail=f"[[{finding.target}]] -> {finding.new}{note}")
        elif finding.kind == "placeholder":
            reporter.message(
                "info", f"{rel}:{finding.line}: [[{finding.target}]] looks like a template placeholder; "
                        "not repaired", path=path)
        else:
            reporter.message(
                "warning", f"{rel}:{finding.line}: [[{finding.target}]] {finding.detail}", path=path)

    if apply and edits:
        write_utf8(path, apply_edits(original, edits))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair filename-only and wrongly cased wikilinks to full-path form"
    )
    add_grimoire_arg(parser)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry-run, report only)",
    )
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    grimoire_root = resolve_grimoire_arg(args.grimoire)

    reporter = ResultReporter(
        "repair_links",
        root=grimoire_root,
        mode="apply" if args.apply else "plan",
    )

    if human:
        print()
        print("Repairing Wikilinks")
        print("==================================")
        print(f"Grimoire root: {grimoire_root}")
        print(f"Mode:          {'apply' if args.apply else 'dry-run'}")
        print()

    refusal = read_only_refusal(grimoire_root) if args.apply else None
    if refusal:
        reporter.message("error", refusal)
        reporter.set_status("blocked")
        if human:
            warn(refusal)
        else:
            reporter.emit(args.format, summary={"access": "read"})
        return 1

    index = build_basename_index(grimoire_root)
    if human:
        info(f"Indexed {sum(len(v) for v in index.values())} chapter pages "
             f"under {len(index)} distinct basenames "
             f"({sum(1 for v in index.values() if len(v) > 1)} basename collisions)")
        print()

    findings: list[Finding] = []
    unreadable: list[str] = []
    files_touched = 0

    for path in iter_link_pages(grimoire_root):
        page_findings = repair_file(path, grimoire_root, index, args.apply, reporter)
        if page_findings is None:
            unreadable.append(path.relative_to(grimoire_root).as_posix())
            continue
        if any(f.kind in REPAIR_KINDS for f in page_findings):
            files_touched += 1
        findings.extend(page_findings)

    repairs = [f for f in findings if f.kind in REPAIR_KINDS]
    ambiguous = [f for f in findings if f.kind == "ambiguous"]
    unresolvable = [f for f in findings if f.kind in UNRESOLVED_KINDS]
    skipped = [f for f in findings if f.kind == "placeholder"]

    if human:
        for title, group in (
            ("Repairs", repairs),
            ("Ambiguous - needs human resolution", ambiguous),
            ("Unresolvable - no target found", unresolvable),
            ("Skipped - placeholder-like, not repaired", skipped),
        ):
            if group:
                print(f"{title} ({len(group)}):")
                for finding in group:
                    print(finding.human())
                print()
        if unreadable:
            print(f"Unreadable - not valid UTF-8, left untouched ({len(unreadable)}):")
            for rel in unreadable:
                print(f"  [SKIP]  {rel}")
            print()
        print("==================================")

        summary = (
            f"Repairs: {len(repairs)} across {files_touched} file(s); "
            f"ambiguous: {len(ambiguous)}; unresolvable: {len(unresolvable)}; "
            f"skipped: {len(skipped)}; unreadable: {len(unreadable)}"
        )
        if args.apply and repairs:
            ok(summary + " - applied")
        elif repairs:
            info(summary + " - dry-run, pass --apply to write")
        else:
            ok(summary)

    if unreadable:
        reporter.set_status("partial")
    if not human:
        reporter.emit(args.format, summary={
            "repairs": len(repairs),
            "ambiguous": len(ambiguous),
            "unresolvable": len(unresolvable),
            "skipped": len(skipped),
            "unreadable": len(unreadable),
            "unreadable_pages": unreadable,
            "files_touched": files_touched,
        })

    if args.apply:
        return 0
    return 1 if (repairs or ambiguous or unresolvable or unreadable) else 0


if __name__ == "__main__":
    sys.exit(main())
