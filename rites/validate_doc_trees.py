#!/usr/bin/env python3
"""Validates that ASCII directory-tree diagrams in markdown match the filesystem.

Many grimoire and framework pages embed file-tree diagrams in fenced code blocks
using the box-drawing characters:

    project/
    ├── README.md
    ├── chapters/
    │   ├── glossary/
    │   └── standards/
    └── grimoire.json

These diagrams drift when folders are renamed, added, or removed and the doc
isn't updated to match. This validator parses every such diagram in the
grimoire (or the framework), resolves it to a real filesystem anchor when possible,
and reports:

- DOC_TREE_MISSING_ENTRY     — the diagram lists a path that doesn't exist
- DOC_TREE_UNLISTED_ENTRY    — the actual directory has visible children that
                                the diagram (when it claims to be exhaustive)
                                doesn't mention

A diagram is treated as illustrative (and skipped) when ANY of the following
apply, because illustration cannot be diffed against reality:

- The root line contains a placeholder (`<name>`, `{name}`, `[name]`, `...`)
- The diagram lives under a `templates/` folder
- The doc itself sits inside `sources/`, `inbox/`, or `templates/`
- No anchor (a real directory) can be resolved for the diagram's root

The anchor is resolved once per diagram, in this order: the root line names the
root being validated (its name is the manifest `name` of `grimoire.json` or
`framework.json`, so the checkout folder's own name does not matter); the root
line is a path relative to the root; the root line is a single name and the
first directory of that name in a `walk_files` walk is the anchor, so pruned
folders (`publish/` at the root, `.git/`, `node_modules/`, `.obsidian/`) are
never anchors.

An entry without a trailing `/` is a directory when the entry below it sits
deeper (the output of `tree`), and otherwise any existing path satisfies it.

Entries inside an otherwise-real diagram that are themselves placeholders
(`<...>`, `{...}`, `...`, `…`) are skipped per-line; the rest of the diagram
is still validated. A file that is not valid UTF-8 is reported as
`DOC_TREE_PARSE_FAILED` and skipped.

Mutation profile: none.

Usage: FRAMEWORK_HOME/bin/grimoire validate_doc_trees [--grimoire <path>] [--format human|json|jsonl]
Without `--grimoire` the validator checks the framework.
Exit codes: 0 = clean (warnings allowed), 1 = drift found, 2 = `--grimoire` is not a directory
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from _lib import (
    FENCE_RE,
    HISTORY_FILENAMES,
    add_grimoire_arg,
    read_utf8,
    root_hub_stem,
    resolve_grimoire_arg,
    walk_files,
)
from diagnostics import DiagnosticReporter, add_output_format_arg


# Box-drawing markers that introduce a child entry.
BRANCH_RE = re.compile(r"^(?P<indent>.*?)(?P<marker>├──|└──|`--|\|--)\s+(?P<rest>\S.*)$")
# Leading-only indentation prefix (continuation columns).
INDENT_RE = re.compile(r"^(?:[│|]\s*|\s{4})*")
PLACEHOLDER_RE = re.compile(r"[<{\[]|\.\.\.|…|\*")
TRAILING_COMMENT_RE = re.compile(r"\s+#.*$")

# Folders inside which any tree diagram is treated as illustrative.
ILLUSTRATIVE_PARENT_DIRS = {"templates", "snippets", "scripts", "examples"}

# Directories never listed as real children of an anchor.
SCAFFOLD_DIRS_SKIPPED = {".git", ".obsidian", "__pycache__", ".venv", "venv", "node_modules"}

# Files at the directory root treated as routine: a complete diagram may omit them.
ROUTINE_ROOT_ENTRIES = {".gitignore", ".gitattributes", ".editorconfig", ".gitkeep"}


@dataclass(frozen=True)
class TreeEntry:
    """A single line inside a tree diagram, fully resolved to a relative path."""

    line_number: int
    relative_path: str        # path relative to the diagram's anchor
    is_directory: bool        # written with a trailing `/`, or followed by deeper entries
    placeholder: bool


@dataclass
class TreeDiagram:
    """One contiguous tree diagram inside one markdown file."""

    file_path: Path
    start_line: int           # 1-indexed line of the root entry
    anchor_label: str         # raw root line content (without trailing comment)
    entries: list[TreeEntry]
    has_placeholder_root: bool
    has_ellipsis: bool        # diagram contains `...` somewhere = "not exhaustive"


def strip_trailing_comment(text: str) -> str:
    return TRAILING_COMMENT_RE.sub("", text).rstrip()


def looks_like_placeholder(text: str) -> bool:
    if not text:
        return True
    return bool(PLACEHOLDER_RE.search(text))


def build_entries(items: list[tuple[int, str, int]]) -> list[TreeEntry]:
    """Turn `(marker_column, text, line_number)` branch lines into entries with full relative paths.

    The parent of an entry is the nearest earlier entry whose marker sits in a
    smaller column. An entry is a directory when its text ends in `/` or when
    the next line sits in a deeper column, which is how `tree` prints a folder.
    """
    entries: list[TreeEntry] = []
    parents: list[tuple[int, str]] = []  # (marker column, relative path) of the open directories
    for index, (column, text, line_number) in enumerate(items):
        while parents and parents[-1][0] >= column:
            parents.pop()
        has_children = index + 1 < len(items) and items[index + 1][0] > column
        is_dir = text.endswith("/") or has_children
        bare = text.rstrip("/")
        rel = f"{parents[-1][1]}/{bare}" if parents else bare
        entries.append(
            TreeEntry(
                line_number=line_number,
                relative_path=rel,
                is_directory=is_dir,
                placeholder=looks_like_placeholder(bare),
            )
        )
        if is_dir:
            parents.append((column, rel))
    return entries


def parse_tree(lines: list[str], start_index: int, fence_start_line: int) -> tuple[TreeDiagram | None, int]:
    """Parse one contiguous tree whose root is `lines[start_index]`.

    The root line is a non-blank line that is not itself a branch; the tree
    runs until a blank line or a line that is neither a branch nor bare
    box-drawing indentation. Returns `(diagram or None, next_index_to_consider)`.
    """
    root_raw = lines[start_index].rstrip()
    root_clean = strip_trailing_comment(root_raw).strip()
    if not root_clean:
        return None, start_index + 1

    items: list[tuple[int, str, int]] = []
    has_ellipsis = False
    next_index = start_index + 1
    while next_index < len(lines):
        raw = lines[next_index].rstrip()
        if not raw.strip():
            break
        branch = BRANCH_RE.match(raw)
        if not branch:
            indent_match = INDENT_RE.match(raw)
            if indent_match and not raw[indent_match.end():].strip():
                next_index += 1
                continue
            break

        entry_text = strip_trailing_comment(branch.group("rest")).strip()
        if entry_text in ("...", "…"):
            has_ellipsis = True
        else:
            if "..." in entry_text or "…" in entry_text:
                has_ellipsis = True
            items.append((branch.start("marker"), entry_text, fence_start_line + next_index + 1))
        next_index += 1

    diagram = TreeDiagram(
        file_path=Path(),  # filled in by the caller
        start_line=fence_start_line + start_index + 1,
        anchor_label=root_clean,
        entries=build_entries(items),
        has_placeholder_root=looks_like_placeholder(root_clean.rstrip("/").strip()),
        has_ellipsis=has_ellipsis,
    )
    return diagram, next_index


def extract_tree_diagrams(file_path: Path) -> Iterator[TreeDiagram]:
    """Yield every tree diagram inside the fenced code blocks of `file_path`.

    Raises `UnicodeDecodeError` or `OSError` for a file that cannot be read.
    A block closes on a fence of the marker that opened it.
    """
    lines = read_utf8(file_path).splitlines()
    fence_marker: str | None = None
    fence_lines: list[str] = []
    fence_start_line = 0  # 1-indexed line of the opening fence

    for line_index, raw_line in enumerate(lines):
        fence_match = FENCE_RE.match(raw_line)
        if fence_match and fence_marker is None:
            fence_marker = fence_match.group(1)
            fence_lines = []
            fence_start_line = line_index + 1
        elif fence_match and fence_match.group(1) == fence_marker:
            fence_marker = None
            for diagram in _scan_fence(fence_lines, fence_start_line):
                diagram.file_path = file_path
                yield diagram
        elif fence_marker is not None:
            fence_lines.append(raw_line)


def _scan_fence(fence_lines: list[str], fence_start_line: int) -> Iterator[TreeDiagram]:
    """Walk fence content and emit each tree diagram found.

    A tree is a non-blank line that is not a branch, followed by a branch line
    within the next three lines.
    """
    i = 0
    while i < len(fence_lines):
        if not fence_lines[i].strip() or BRANCH_RE.match(fence_lines[i]):
            i += 1
            continue
        lookahead = 1
        found_branch = False
        while lookahead < 4 and i + lookahead < len(fence_lines):
            if BRANCH_RE.match(fence_lines[i + lookahead]):
                found_branch = True
                break
            if not fence_lines[i + lookahead].strip():
                break
            lookahead += 1
        if not found_branch:
            i += 1
            continue
        diagram, next_i = parse_tree(fence_lines, i, fence_start_line)
        if diagram is not None and diagram.entries:
            yield diagram
        i = next_i if next_i > i else i + 1


def directory_index(root: Path) -> dict[str, list[Path]]:
    """Map a directory name to the directories of that name under `root`, in sorted order.

    The directories come from a `walk_files` walk, so a pruned folder (`.git`,
    `node_modules`, `.obsidian`, and `publish` at the root) is never listed. A
    directory that holds no file does not appear.
    """
    directories: set[Path] = set()
    for file in walk_files(root):
        parent = file.parent
        while parent != root and parent not in directories:
            directories.add(parent)
            parent = parent.parent
    index: dict[str, list[Path]] = {}
    for directory in sorted(directories, key=lambda d: d.relative_to(root).as_posix()):
        index.setdefault(directory.name, []).append(directory)
    return index


def resolve_anchor(
    diagram: TreeDiagram, root: Path, root_name: str, directories: dict[str, list[Path]]
) -> Path | None:
    """Return the on-disk directory the diagram is rooted at, or None.

    The root line anchors to `root` when its last segment is `root_name`; else
    to `root / <root line>`; else, for a single name, to the first directory of
    that name in `directories`.
    """
    label = diagram.anchor_label.rstrip("/").strip()
    if not label or diagram.has_placeholder_root:
        return None
    name = label.split("/")[-1]
    if name == root_name:
        return root
    relative = label.removeprefix("./")
    if relative:
        candidate = (root / relative).resolve()
        if candidate.is_dir() and candidate.is_relative_to(root):
            return candidate
    if "/" not in label and directories.get(name):
        return directories[name][0]
    return None


def doc_is_illustrative(path: Path, root: Path) -> bool:
    """Return True if the doc itself is in an illustrative context."""
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return False
    for part in rel_parts:
        if part.casefold() in ILLUSTRATIVE_PARENT_DIRS:
            return True
        if part.casefold() in {"sources", "inbox"}:
            return True
        if "<" in part or "{" in part or "[" in part:
            return True
    return False


def real_children(directory: Path) -> set[str]:
    """Return the immediate children of `directory` as `name` or `name/` strings.

    Scaffold directories and dotfiles are left out, except the routine ones.
    """
    out: set[str] = set()
    if not directory.is_dir():
        return out
    for entry in directory.iterdir():
        name = entry.name
        if name in SCAFFOLD_DIRS_SKIPPED:
            continue
        if name.startswith(".") and name not in ROUTINE_ROOT_ENTRIES:
            continue
        out.add(name + "/" if entry.is_dir() else name)
    return out


def listed_names(diagram: TreeDiagram) -> set[str]:
    """Return the names of the diagram's top-level entries, without a trailing `/`.

    An entry whose path holds `/` sits below another entry. A placeholder entry
    names nothing.
    """
    return {
        entry.relative_path
        for entry in diagram.entries
        if not entry.placeholder and "/" not in entry.relative_path
    }


def validate_diagram(
    diagram: TreeDiagram,
    root: Path,
    anchor: Path,
    reporter: DiagnosticReporter,
    human: bool,
) -> None:
    """Apply the drift checks to one diagram anchored at `anchor`."""
    shown = diagram.file_path.relative_to(root)
    label = diagram.anchor_label.rstrip("/")
    anchor_rel = anchor.relative_to(root).as_posix()

    for entry in diagram.entries:
        if entry.placeholder:
            continue
        target = anchor / entry.relative_path
        if entry.is_directory:
            exists, kind, written = target.is_dir(), "directory", f"{entry.relative_path}/"
        else:
            exists, kind, written = target.exists(), "path", entry.relative_path
        if exists:
            continue
        reporter.error(
            "DOC_TREE_MISSING_ENTRY",
            f"diagram lists `{written}` under `{label}` but the {kind} does not exist on disk",
            path=diagram.file_path,
            line=entry.line_number,
            hint=f"Either create `{anchor_rel}/{written}` or remove the entry from the diagram.",
        )
        if human:
            print(f"  MISSING  {shown}:{entry.line_number} lists `{written}` not on disk")

    # A complete diagram lists every immediate child of its anchor: no
    # ellipsis marker, no placeholder entry, at least one named child that
    # exists on disk.
    if diagram.has_ellipsis or any(e.placeholder for e in diagram.entries):
        return
    listed = listed_names(diagram)
    actual = real_children(anchor)
    if not any(name.rstrip("/") in listed for name in actual):
        return
    for name in sorted(actual):
        if name.rstrip("/") in listed or name in ROUTINE_ROOT_ENTRIES:
            continue
        reporter.warning(
            "DOC_TREE_UNLISTED_ENTRY",
            f"`{anchor_rel}/{name}` exists on disk but is not listed in the diagram",
            path=diagram.file_path,
            line=diagram.start_line,
            hint="Add it to the diagram or add `...` to mark the diagram as non-exhaustive.",
        )
        if human:
            print(f"  EXTRA    {shown}:{diagram.start_line} `{name}` exists but not listed")


def collect_markdown_files(root: Path) -> Iterable[Path]:
    """Yield the Markdown files to scan: every one `walk_files` finds except history files and `inbox/`."""
    for path in walk_files(root, "*.md"):
        if path.name in HISTORY_FILENAMES or path.relative_to(root).parts[0] == "inbox":
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ASCII directory-tree diagrams against the filesystem.",
    )
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()

    root = resolve_grimoire_arg(args.grimoire)
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_doc_trees", root)

    files = list(collect_markdown_files(root))
    if human:
        print()
        print("Validating Documented File Trees")
        print("================================")
        print(f"Root: {root}")
        print()

    root_name = root_hub_stem(root)
    directories = directory_index(root)
    diagrams_total = 0
    diagrams_validated = 0
    for path in files:
        illustrative = doc_is_illustrative(path, root)
        try:
            for diagram in extract_tree_diagrams(path):
                diagrams_total += 1
                if illustrative or diagram.has_placeholder_root:
                    continue
                anchor = resolve_anchor(diagram, root, root_name, directories)
                if anchor is None:
                    continue
                diagrams_validated += 1
                validate_diagram(diagram, root, anchor, reporter, human)
        except (OSError, UnicodeDecodeError) as exc:
            reporter.error(
                "DOC_TREE_PARSE_FAILED",
                f"failed to scan tree diagrams: {exc}",
                path=path,
            )
            if human:
                print(f"  ERROR    {path.relative_to(root)}: parse failed: {exc}")

    if args.format != "human":
        reporter.emit(args.format, checked={"files": len(files), "diagrams": diagrams_total, "validated": diagrams_validated})
        return reporter.exit_code()

    print()
    print(f"Files scanned:      {len(files)}")
    print(f"Diagrams found:     {diagrams_total}")
    print(f"Diagrams validated: {diagrams_validated}")
    print(f"Drift errors:       {reporter.error_count()}")
    print(f"Drift warnings:     {reporter.warning_count()}")
    print()
    print("================================")
    if reporter.error_count():
        print(f"  [FAIL]  Doc-tree drift found ({reporter.error_count()} errors)")
    elif reporter.warning_count():
        print(f"  [WARN]  Doc-tree drift hints ({reporter.warning_count()} warnings)")
    else:
        print("  [OK]    Doc-tree validation passed")
    return reporter.exit_code()


if __name__ == "__main__":
    sys.exit(main())
