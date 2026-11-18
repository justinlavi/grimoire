#!/usr/bin/env python3
r"""Restructure grimoire content - move/rename or remove a page or chapter.

The mechanical, deterministic core of content reorganization. It does exactly
two things and does them safely:

  --move SRC DST   Rename or move a page or a whole chapter under `chapters/`,
                   rewriting every full-path wikilink and every frontmatter
                   `sources:` entry that targets the moved file(s) to their new
                   location. Moving a chapter folder also renames its
                   folder-named hub so the hub convention holds.

  --remove PATH    Delete a page or chapter under `chapters/` and report every
                   inbound wikilink that would break, so the caller can repair
                   or reconsider. A chapter folder is deleted with every file in
                   it; the plan lists the pages and the other files.

Every path argument is resolved before use. A path that does not resolve to a
location inside the grimoire's `chapters/` folder, or that passes through a
symbolic link, is refused, so no argument can reach a file outside it.

A move validates everything first (existence, collisions in the move map,
destination extension, destination parents) and only then changes anything.
Plan mode and apply mode run the same validation. Pages are read and written as
UTF-8; a page that does not decode is left untouched and reported, and the rite
continues with the other pages.

What stays judgment (handled by the /grm-move and /grm-remove invocations, not
here): wiring the destination chapter hub, dropping the pointer from a parent
hub, deciding what to do with broken inbound references, and re-validating.
This rite never edits hubs or guesses intent; it moves or deletes files and
rewrites the links it can resolve exactly.

A grimoire registered for reading on this computer (`"access": "read"` in the
library) is refused in plan and apply mode alike, with nothing changed.

Mutation profile: plan_apply. The default prints the plan (moves, link
rewrites, or inbound breaks) without writing; `--apply` performs it.

Usage:
    FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire ROOT \
        --move SRC DST [--apply] [--format human|json|jsonl]
    FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire ROOT \
        --remove PATH [--apply] [--format human|json|jsonl]

Exit codes: 0 = plan or apply completed, 1 = refused (invalid target) or an
error while applying, 2 = invalid arguments.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Optional

from _lib import (
    WIKILINK_RE,
    add_grimoire_arg,
    err,
    frontmatter_bounds,
    frontmatter_sources,
    is_hub,
    iter_link_pages,
    mask_code,
    read_only_refusal,
    read_utf8,
    rebuild_wikilink,
    resolve_grimoire_arg,
    wikilink_target_body,
    write_utf8,
)
from diagnostics import ResultReporter, add_output_format_arg

_FRONTMATTER_KEY_RE = re.compile(r"^[A-Za-z_][\w-]*\s*:")


class Refusal(Exception):
    """A request the rite declines; the message says why and nothing was changed."""


@dataclass(frozen=True)
class MovePlan:
    """A validated move: the paths and the old-to-new path of every moved page."""

    src: str
    dst: str
    is_dir: bool
    move: dict[str, str]
    other_files: list[str]

    def link_remap(self) -> dict[str, str]:
        """Old -> new wikilink target bodies (paths without the .md suffix)."""
        return {strip_md(old): strip_md(new) for old, new in self.move.items()}

    def new_source_path(self, entry: str) -> Optional[str]:
        """The new path of a frontmatter `sources:` entry that points at moved content, else None."""
        if entry in self.move:
            return self.move[entry]
        if self.is_dir and (entry == self.src or entry.startswith(self.src + "/")):
            return self.dst + entry[len(self.src):]
        return None


@dataclass(frozen=True)
class Rewrite:
    """New text for one page, to be written at `dest` (its location after the move)."""

    dest: str
    text: str
    links: int
    sources: int


def strip_md(target: str) -> str:
    return target[:-3] if target.endswith(".md") else target


def is_link(path: Path) -> bool:
    """True for a symbolic link or, on Windows, a junction."""
    junction = getattr(os.path, "isjunction", None)
    return path.is_symlink() or bool(junction and junction(path))


def is_folder_hub(rel: str) -> bool:
    """True when rel is a folder-named hub file (chapters/<c>/<c>.md)."""
    path = PurePosixPath(rel)
    return path.suffix == ".md" and path.parent.name != "chapters" and is_hub(path)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_target(root: Path, raw: str, *, must_exist: bool) -> str:
    """Return the grimoire-relative POSIX path `raw` names, or raise Refusal.

    `root` is a resolved grimoire root. The path must lie strictly inside
    `<root>/chapters` and reach it through no symbolic link, so nothing outside
    that folder can be read, moved or deleted through it. A path that differs
    from the on-disk spelling only by case is accepted where the filesystem
    ignores case, and returned with the on-disk spelling for an existing path.
    """
    text = raw.strip().replace("\\", "/")
    if not text or "\0" in text:
        raise Refusal("the path is empty")
    if text.startswith("/") or PureWindowsPath(text).drive:
        raise Refusal(f"{raw} is not relative to the grimoire root - give a path under chapters/")
    chapters = root / "chapters"
    try:
        inner = Path(os.path.normpath(root / text)).relative_to(chapters)
    except ValueError:
        raise Refusal(f"{raw} is not under chapters/ - this rite reorganizes chapter content only")
    if not inner.parts:
        raise Refusal("chapters/ itself cannot be moved or removed")
    parent = (chapters / inner.parent).resolve()
    if os.path.normcase(str(parent)) != os.path.normcase(str(chapters / inner.parent)):
        raise Refusal(f"{raw} passes through a symbolic link - this rite does not follow links")
    full = parent / inner.name
    if must_exist:
        if not os.path.lexists(full):
            raise Refusal(f"chapters/{inner.as_posix()} does not exist")
        if is_link(full):
            raise Refusal(f"chapters/{inner.as_posix()} is a symbolic link - this rite does not follow links")
        full = Path(os.path.realpath(full))
        return full.relative_to(root).as_posix()
    return (parent / inner.name).relative_to(root).as_posix()


def list_tree(root: Path, rel: str) -> tuple[list[str], list[str]]:
    """Return the Markdown pages and the other files under `rel`, as sorted grimoire-relative paths.

    A folder is walked without following links; a symbolic link inside it counts
    as an other file. A file is its own single entry.
    """
    base = root / rel
    if not base.is_dir():
        return ([rel], []) if rel.endswith(".md") else ([], [rel])
    pages: list[str] = []
    others: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        here = Path(dirpath)
        for name in list(dirnames):
            if is_link(here / name):
                dirnames.remove(name)
                others.append((here / name).relative_to(root).as_posix())
        for name in filenames:
            path = (here / name).relative_to(root).as_posix()
            (pages if name.endswith(".md") else others).append(path)
    return sorted(pages), sorted(others)


# ---------------------------------------------------------------------------
# Move: validate, plan, apply
# ---------------------------------------------------------------------------


def build_move_map(src: str, dst: str, pages: list[str], is_dir: bool) -> dict[str, str]:
    """Map every moved page's old grimoire-relative path to its new path.

    For a chapter folder, the folder-named hub (`<src>/<src>.md`) is remapped to
    `<dst>/<dst>.md` so the hub convention survives a rename; every other page
    keeps its name and only its path prefix changes.
    """
    if not is_dir:
        return {src: dst}
    src_hub = f"{PurePosixPath(src).name}.md".casefold()
    dst_hub = f"{PurePosixPath(dst).name}.md"
    move = {}
    for old in pages:
        new = dst + old[len(src):]
        if old == f"{src}/{PurePosixPath(old).name}" and PurePosixPath(old).name.casefold() == src_hub:
            new = f"{dst}/{dst_hub}"
        move[old] = new
    return move


def plan_move(root: Path, src_arg: str, dst_arg: str) -> MovePlan:
    """Validate a move completely and return its plan, or raise Refusal.

    Plan mode and apply mode both call this, so a plan that succeeds is never
    followed by an apply that refuses.
    """
    src = resolve_target(root, src_arg, must_exist=True)
    dst = resolve_target(root, dst_arg, must_exist=False)
    src_abs, dst_abs = root / src, root / dst

    if src == dst:
        raise Refusal(f"{src} is already at that path")
    case_only = src.casefold() == dst.casefold()
    if os.path.lexists(dst_abs) and not (case_only and os.path.samefile(src_abs, dst_abs)):
        raise Refusal(f"{dst} already exists - choose a destination that does not exist")
    if not case_only and ((dst.casefold() + "/").startswith(src.casefold() + "/")
                          or (src.casefold() + "/").startswith(dst.casefold() + "/")):
        raise Refusal(f"cannot move {src} into itself or its own subpath ({dst})")

    ancestor = dst_abs.parent
    while not os.path.lexists(ancestor):
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        raise Refusal(f"{ancestor.relative_to(root).as_posix()} exists but is not a directory")

    is_dir = src_abs.is_dir()
    if not is_dir and src.endswith(".md") and not dst.endswith(".md"):
        raise Refusal(f"{dst} must end in .md - a page keeps its extension when it moves")
    if not is_dir and is_folder_hub(src):
        raise Refusal(f"{src} is a chapter hub - move the whole chapter folder "
                      f"({PurePosixPath(src).parent.as_posix()}) instead of the hub file alone")

    pages, others = list_tree(root, src)
    move = build_move_map(src, dst, pages, is_dir)
    landing: dict[str, str] = {}
    for old, new in move.items():
        if new in landing:
            raise Refusal(f"{landing[new]} and {old} would both land at {new} - "
                          "rename one of them first")
        landing[new] = old
    return MovePlan(src, dst, is_dir, move, others)


def rewrite_wikilinks(text: str, remap: dict[str, str]) -> tuple[str, int]:
    """Retarget wikilinks whose body is in `remap`, leaving code fences and inline code alone."""
    edits = []
    for match in WIKILINK_RE.finditer(mask_code(text)):
        body = wikilink_target_body(match.group(1))
        if body in remap:
            edits.append((match.start(), match.end(),
                          f"[[{rebuild_wikilink(match.group(1), remap[body])}]]"))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, len(edits)


def rewrite_sources(text: str, new_path: Callable[[str], Optional[str]]) -> tuple[str, int]:
    """Retarget frontmatter `sources:` entries for which `new_path` names a new location.

    Only the `sources:` field is edited, and only an entry that equals an old
    path exactly; a longer path that merely starts with it is not an entry.
    """
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return text, 0
    changes = {}
    for entry in frontmatter_sources(text):
        new = new_path(entry)
        if new is not None and new != entry:
            changes[entry] = new
    if not changes:
        return text, 0
    start, end = bounds
    lines = text[start:end].split("\n")
    first = next((i for i, line in enumerate(lines) if re.match(r"^sources\s*:", line)), None)
    if first is None:
        return text, 0
    last = first + 1
    while last < len(lines) and not _FRONTMATTER_KEY_RE.match(lines[last]):
        last += 1
    pattern = re.compile(r"(?<![\w./-])(" + "|".join(
        re.escape(old) for old in sorted(changes, key=len, reverse=True)) + r")(?![\w./-])")
    field, count = pattern.subn(lambda m: changes[m.group(1)], "\n".join(lines[first:last]))
    lines[first:last] = field.split("\n")
    return text[:start] + "\n".join(lines) + text[end:], count


def plan_rewrites(root: Path, plan: MovePlan, reporter: ResultReporter) -> tuple[list[Rewrite], list[str]]:
    """Compute the new text of every page that links to or cites moved content.

    Returns the rewrites and the pages skipped because they do not decode as
    UTF-8. Nothing is written.
    """
    remap = plan.link_remap()
    rewrites: list[Rewrite] = []
    skipped: list[str] = []
    for path in iter_link_pages(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = read_utf8(path)
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append(rel)
            reporter.message("warning", f"{rel}: not valid UTF-8 ({exc}); left untouched, "
                                        "so its links to moved content are not updated", path=rel)
            continue
        new_text, links = rewrite_wikilinks(text, remap)
        new_text, sources = rewrite_sources(new_text, plan.new_source_path)
        if links or sources:
            rewrites.append(Rewrite(plan.move.get(rel, rel), new_text, links, sources))
    return rewrites, skipped


def relocate(root: Path, plan: MovePlan) -> None:
    """Rename the source to the destination, then give a moved chapter's hub its new name.

    Raises OSError after restoring the original location when a step fails.
    """
    src_abs, dst_abs = root / plan.src, root / plan.dst
    try:
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        src_abs.rename(dst_abs)
        for old, new in plan.move.items():
            moved_to = plan.dst + old[len(plan.src):] if plan.is_dir else new
            if moved_to != new:
                (root / moved_to).rename(root / new)
    except OSError:
        if dst_abs.exists() and not src_abs.exists():
            dst_abs.rename(src_abs)
        raise


def refuse(reporter: ResultReporter, human: bool, fmt: str, message: str) -> int:
    reporter.message("error", message)
    reporter.set_status("blocked")
    if human:
        err(message)
        print()
    else:
        reporter.emit(fmt)
    return 1


def do_move(root: Path, src: str, dst: str, *, apply: bool, reporter: ResultReporter,
            human: bool, fmt: str) -> int:
    root = root.resolve()
    try:
        plan = plan_move(root, src, dst)
    except Refusal as exc:
        return refuse(reporter, human, fmt, str(exc))
    rewrites, skipped = plan_rewrites(root, plan, reporter)

    failures = 0
    if apply:
        try:
            relocate(root, plan)
        except OSError as exc:
            return refuse(reporter, human, fmt, f"could not move {plan.src} to {plan.dst}: {exc}")
        for old, new in sorted(plan.move.items()):
            reporter.mutation("move", path=new, detail=f"{old} -> {new}")
        for rewrite in rewrites:
            try:
                write_utf8(root / rewrite.dest, rewrite.text)
            except (OSError, UnicodeEncodeError) as exc:
                failures += 1
                reporter.message("error", f"{rewrite.dest}: links not updated: {exc}", path=rewrite.dest)
                continue
            parts = []
            if rewrite.links:
                parts.append(f"{rewrite.links} wikilink(s)")
            if rewrite.sources:
                parts.append(f"{rewrite.sources} source reference(s)")
            reporter.mutation("repair", path=rewrite.dest, detail=" and ".join(parts) + " retargeted")
    if skipped and not failures:
        reporter.set_status("partial")

    total_links = sum(r.links for r in rewrites)
    total_sources = sum(r.sources for r in rewrites)
    if human:
        verb = "Moved" if apply else "Would move"
        print(f"  {verb} {len(plan.move)} file(s):")
        for old, new in sorted(plan.move.items()):
            print(f"    {old} -> {new}")
        if plan.other_files:
            print(f"  {verb} {len(plan.other_files)} other file(s) with the folder:")
            for name in plan.other_files:
                print(f"    {name}")
        link_verb = "Rewrote" if apply else "Would rewrite"
        print(f"  {link_verb} {total_links} wikilink(s) across {len(rewrites)} file(s).")
        if total_sources:
            print(f"  {link_verb} {total_sources} source reference(s).")
        for name in skipped:
            print(f"  Skipped {name}: not valid UTF-8, left untouched.")
        if not apply:
            print("  Re-run with --apply to perform the move.")
        print()
    else:
        reporter.emit(fmt, summary={
            "moved": len(plan.move), "other_files": len(plan.other_files),
            "link_rewrites": total_links, "source_rewrites": total_sources,
            "files_relinked": len(rewrites), "skipped": skipped, "applied": apply})
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def find_inbound_links(root: Path, bodies: set[str], exclude: set[str],
                       reporter: ResultReporter) -> tuple[list[tuple[str, int, str]], list[str]]:
    """Return the (file_rel, line_no, target) wikilinks that point at `bodies`, and the pages skipped.

    A page that does not decode as UTF-8 is skipped and reported.
    """
    hits: list[tuple[str, int, str]] = []
    skipped: list[str] = []
    for path in iter_link_pages(root):
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        try:
            text = read_utf8(path)
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append(rel)
            reporter.message("warning", f"{rel}: not valid UTF-8 ({exc}); its links to the "
                                        "removed content were not checked", path=rel)
            continue
        for match in WIKILINK_RE.finditer(mask_code(text)):
            if wikilink_target_body(match.group(1)) in bodies:
                hits.append((rel, text.count("\n", 0, match.start()) + 1, match.group(1)))
    return hits, skipped


def do_remove(root: Path, target: str, *, apply: bool, reporter: ResultReporter,
              human: bool, fmt: str) -> int:
    root = root.resolve()
    try:
        rel = resolve_target(root, target, must_exist=True)
        if is_folder_hub(rel):
            raise Refusal(f"{rel} is a chapter hub - remove the whole chapter folder "
                          f"({PurePosixPath(rel).parent.as_posix()}) instead of the hub file alone")
    except Refusal as exc:
        return refuse(reporter, human, fmt, str(exc))

    pages, others = list_tree(root, rel)
    inbound, skipped = find_inbound_links(root, {strip_md(p) for p in pages}, set(pages), reporter)
    for src_rel, line_no, tgt in inbound:
        reporter.message("warning",
                         f"{src_rel}:{line_no}: [[{tgt}]] points at content being removed",
                         path=src_rel)

    if apply:
        try:
            if (root / rel).is_dir():
                shutil.rmtree(root / rel)
            else:
                (root / rel).unlink()
        except OSError as exc:
            return refuse(reporter, human, fmt, f"could not remove {rel}: {exc}")
        reporter.mutation("remove", path=rel,
                          detail=f"removed {len(pages)} page(s) and {len(others)} other file(s)")
    if skipped:
        reporter.set_status("partial")

    if human:
        verb = "Removed" if apply else "Would remove"
        print(f"  {verb} {rel} ({len(pages)} page(s)).")
        for name in pages:
            print(f"    {name}")
        if others:
            print(f"  {verb} {len(others)} other file(s):")
            for name in others:
                print(f"    {name}")
        if inbound:
            print(f"  {len(inbound)} inbound wikilink(s) point at removed content "
                  f"and will break - repair or reconsider:")
            for src_rel, line_no, tgt in inbound:
                print(f"    {src_rel}:{line_no}: [[{tgt}]]")
        else:
            print("  No inbound wikilinks point at the removed content.")
        for name in skipped:
            print(f"  Skipped {name}: not valid UTF-8, its links were not checked.")
        if not apply:
            print("  Re-run with --apply to perform the removal.")
        print()
    else:
        reporter.emit(fmt, summary={
            "removed_pages": len(pages), "removed_other_files": len(others),
            "pages": pages, "other_files": others,
            "inbound_breaks": len(inbound), "skipped": skipped, "applied": apply})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restructure grimoire content (move/remove)")
    add_grimoire_arg(parser)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--move", nargs=2, metavar=("SRC", "DST"),
                       help="Move or rename a page or chapter under chapters/")
    group.add_argument("--remove", metavar="PATH",
                       help="Delete a page or chapter under chapters/")
    parser.add_argument("--apply", action="store_true",
                        help="Perform the change (default: plan only)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    root = resolve_grimoire_arg(args.grimoire)

    reporter = ResultReporter(
        "restructure_grimoire", root=root, mode="apply" if args.apply else "plan"
    )

    if human:
        print()
        print("  Restructure Grimoire")
        print("  ----------------------------")
        print(f"  Grimoire: {root}")
        print(f"  Mode:     {'apply' if args.apply else 'plan (use --apply to write)'}")
        print()

    refusal = read_only_refusal(root)
    if refusal:
        reporter.message("error", refusal)
        reporter.set_status("blocked")
        if human:
            err(refusal)
            print()
        else:
            reporter.emit(args.format, summary={"access": "read"})
        return 1

    if args.move:
        return do_move(root, args.move[0], args.move[1], apply=args.apply,
                       reporter=reporter, human=human, fmt=args.format)
    return do_remove(root, args.remove, apply=args.apply, reporter=reporter,
                     human=human, fmt=args.format)


if __name__ == "__main__":
    sys.exit(main())
