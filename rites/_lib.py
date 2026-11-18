"""Shared library for framework rites.

Owns the primitives that more than one rite needs: strict UTF-8 file I/O,
frontmatter parsing, code-fence masking, link-target helpers, page discovery,
manifest and library loading, skill-family loading, path formatting and the git
wrapper. A rite imports these instead of restating them.

This module is the bottom of the import graph: it imports the standard library
only, and never another rite.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Optional
from urllib.parse import unquote


# ---------------------------------------------------------------------------
# Regexes - shared across validators
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK_RE = re.compile(r"\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
# A fence delimiter line: a backtick or tilde fence at any indentation.
FENCE_RE = re.compile(r"^\s*(```|~~~)")
CODE_FENCE_RE = FENCE_RE
SKILL_PREFIX_RE = re.compile(r"^[a-z][a-z0-9]*$")
SKILL_PREFIX_PLACEHOLDER = "{{SKILL_PREFIX}}"
SKILL_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# An inline code span: a run of backticks, the code, and a closing run of the
# same length.
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")


# ---------------------------------------------------------------------------
# Text and JSON I/O
# ---------------------------------------------------------------------------


def read_utf8(path: Path) -> str:
    """Return a file's text decoded as strict UTF-8, with line endings read as LF.

    Raises `UnicodeDecodeError` for a file that is not UTF-8 and `OSError` for one
    that cannot be read; no replacement character is ever substituted. A caller
    that writes the text back skips the file on either error, because a lossy
    read written back destroys the original bytes.
    """
    return Path(path).read_text(encoding="utf-8")


def _discard_file(path: str) -> None:
    """Remove a temporary file, including one that carries a read-only mode."""
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass


def write_utf8(path: Path, text: str) -> None:
    """Write text as UTF-8 with LF line endings, replacing the file atomically.

    The text goes to a temporary sibling that then replaces the file, so a
    failure at any step raises and leaves the existing file as it was. Missing
    parent directories are created, CRLF in `text` is written as LF, the file
    keeps its permission bits, and a symbolic link is written through so the
    link survives. Raises `UnicodeEncodeError` or `OSError`.
    """
    data = text.replace("\r\n", "\n").encode("utf-8")
    target = Path(os.path.realpath(path)) if os.path.islink(path) else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = str(target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp"))
    # O_BINARY exists on Windows only, where a descriptor opened without it
    # turns every LF into CRLF.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(temporary, flags, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        try:
            os.chmod(temporary, stat.S_IMODE(os.stat(target).st_mode))
        except OSError:
            pass
        os.replace(temporary, target)
    except BaseException:
        _discard_file(temporary)
        raise


def write_json(path: Path, data, *, indent: int = 2) -> None:
    """Write `data` as JSON through `write_utf8`: non-ASCII kept as is, one trailing newline."""
    write_utf8(path, json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def ensure_utf8_stdio() -> None:
    """Make `sys.stdout` and `sys.stderr` encode as UTF-8, replacing what cannot be encoded.

    A Windows console or pipe encodes with the system code page, where printing a
    path such as `日本.md` raises `UnicodeEncodeError` after the rite has already
    changed files. A stream without `reconfigure` (a test double, a closed
    stream) is left alone. `diagnostics` calls this at import, which covers
    every rite.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Source-layer paths
# ---------------------------------------------------------------------------

SOURCE_DIRNAME = "sources"

# Naming convention a grimoire records in grimoire.json (`naming`). Any casing is
# valid in page and folder names; the convention is what the AI applies to new
# material and what /grm-check naming reports deviations from. Absent means
# the default.
NAMING_DEFAULT = "snake_case"
NAMING_MAX_LEN = 40


def naming_convention(manifest) -> str:
    """Return the grimoire's recorded naming convention, or the default."""
    if isinstance(manifest, dict):
        value = manifest.get("naming")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return NAMING_DEFAULT


def _source_index(parts, start: int):
    """Index of the first chapter-local sources segment at or after ``start``.

    The folder is recognised case-insensitively (``sources``, ``Sources``), so a
    grimoire that keeps its own casing is still read correctly; new folders are
    always created as ``sources``.
    """
    for index in range(start, len(parts)):
        if parts[index].casefold() == SOURCE_DIRNAME:
            return index
    raise ValueError(SOURCE_DIRNAME)


def _path_parts(rel) -> tuple[str, ...]:
    if isinstance(rel, Path):
        return rel.parts
    return tuple(p for p in str(rel).replace("\\", "/").split("/") if p)


def is_colocated_source_path(rel) -> bool:
    """Return True for canonical local source paths.

    Source artifacts and wrappers live beside the chapter material they support:
    ``chapters/<chapter>/.../sources/<artifact>``. The first chapter segment is
    required so ``chapters/sources/...`` is not mistaken for a chapter-local
    source folder.
    """
    parts = _path_parts(rel)
    if len(parts) < 4 or parts[0] != "chapters":
        return False
    try:
        source_index = _source_index(parts, 2)
    except ValueError:
        return False
    return source_index < len(parts) - 1


def is_inside_colocated_source_dir(rel) -> bool:
    """Return True for any path inside a chapter-local ``sources`` directory."""
    parts = _path_parts(rel)
    if len(parts) < 3 or parts[0] != "chapters":
        return False
    try:
        _source_index(parts, 2)
    except ValueError:
        return False
    return True


def resolve_local_source_path(root: Path, ref: str) -> Optional[Path]:
    """Resolve a canonical local source ref under ``root`` without escaping it."""
    if not is_colocated_source_path(ref):
        return None
    candidate = Path(ref)
    if candidate.is_absolute():
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def iter_colocated_source_markdown(root: Path) -> Iterable[Path]:
    """Yield Markdown source-wrapper candidates under chapter-local sources dirs."""
    chapters = root / "chapters"
    if not chapters.is_dir():
        return
    for path in sorted(chapters.rglob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(root)
        if is_colocated_source_path(rel):
            yield path


# ---------------------------------------------------------------------------
# Logging - uniform `[LEVEL]` prefix in 2-space indent
# ---------------------------------------------------------------------------


def info(msg: str) -> None:
    print(f"  [INFO]  {msg}")


def ok(msg: str) -> None:
    print(f"  [OK]    {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN]  {msg}")


def err(msg: str) -> None:
    print(f"  [ERROR] {msg}")


# ---------------------------------------------------------------------------
# Grimoire root resolution
# ---------------------------------------------------------------------------


def default_framework_root() -> Path:
    """Return the framework root: FRAMEWORK_HOME env var, else this file's parent.parent.

    Validators and rites that operate on the framework itself use this as their fallback
    when no `--grimoire` flag is supplied.
    """
    return Path(os.environ.get("FRAMEWORK_HOME", Path(__file__).resolve().parent.parent))


def add_grimoire_arg(parser: argparse.ArgumentParser, flag: str = "--grimoire") -> None:
    """Register the standard `--grimoire <path>` flag on a parser.

    The default is `default_framework_root()`, so a script invoked without args
    operates on the framework itself; passing `--grimoire ~/grimoires/cooking-grimoire`
    points the same script at any grimoire.
    """
    parser.add_argument(
        flag,
        type=Path,
        default=default_framework_root(),
        help="Grimoire root (default: FRAMEWORK_HOME env var or rites parent)",
    )


def resolve_grimoire_arg(path: Path) -> Path:
    """Return the `--grimoire` value as an absolute path to an existing directory.

    A path that is not an existing directory ends the process: one line on
    stderr names the path, and the exit status is 2, the status argparse uses
    for a bad argument. A rite therefore never scans zero files and reports a
    pass for a mistyped path.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        print(
            f"error: {resolved} is not a directory; pass the path of an existing grimoire folder",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return resolved


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

# The values a page's frontmatter `type` and `authority` may take, in the order
# docs/page_schema.md lists them.
PAGE_TYPES = ("hub", "concept", "entity", "source", "playbook", "reference")
PAGE_AUTHORITIES = ("external", "grimoire", "hybrid")


def frontmatter_bounds(text: str) -> Optional[tuple[int, int]]:
    """Return the character offsets of the frontmatter body, or None without frontmatter.

    `text[start:end]` is what lies between the opening and closing `---` lines,
    without the newline that ends its last line. The closing `---` line starts
    at `end + 1`.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    return match.start(1), match.end(1)


def parse_frontmatter(text: str) -> dict:
    """Parse a markdown file's YAML frontmatter into a dict.

    Returns `{}` when no frontmatter block is present.

    Supported syntax (the subset the framework uses):

        key: value
        key: "quoted value"
        key: [a, b, "c"]
        key:
          - item
        key:
        - item

    Returns `dict[str, str | list[str]]`. Lines that match no form are ignored:
    this is a linter helper, not a full YAML implementation. `frontmatter_sources`
    reads the `sources` field in every form a page may use, comments included.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    fields: dict = {}
    current_list_key: Optional[str] = None

    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            current_list_key = None
            continue

        # Block-list item under the open key, indented or at column 0.
        if current_list_key is not None and re.match(r"^\s*-\s+", raw_line):
            value = raw_line.split("-", 1)[1].strip().strip("'\"")
            fields[current_list_key].append(value)
            continue

        current_list_key = None

        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if not value:
            # Empty value may be followed by a multi-line list.
            fields[key] = []
            current_list_key = key
            continue

        # Inline list: [a, b, "c"]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                fields[key] = []
            else:
                fields[key] = [
                    piece.strip().strip("'\"") for piece in re.split(r",\s*", inner)
                ]
            continue

        fields[key] = value.strip("'\"")

    return fields


def page_type(text: str) -> str:
    """Return the frontmatter `type` of a page's text, or `""` when it has none."""
    value = parse_frontmatter(text).get("type", "")
    return value if isinstance(value, str) else ""


def _outside_quotes(value: str) -> list[bool]:
    """Flag each character of a YAML value that lies outside a quoted scalar.

    A quote opens a scalar only at the start of the value or of a flow-list
    item, so an apostrophe inside an unquoted path is ordinary text.
    """
    outside = [True] * len(value)
    quote = ""
    at_item_start = True
    index = 0
    while index < len(value):
        char = value[index]
        if quote:
            outside[index] = False
            escaped_pair = (quote == '"' and char == "\\") or (
                quote == "'" and char == "'" and value[index + 1:index + 2] == "'"
            )
            if escaped_pair and index + 1 < len(value):
                outside[index + 1] = False
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'" and at_item_start:
            quote = char
            outside[index] = False
            at_item_start = False
        elif char in "[,":
            at_item_start = True
        elif not char.isspace():
            at_item_start = False
        index += 1
    return outside


def _strip_yaml_comment(value: str) -> str:
    """Drop a trailing YAML comment: an unquoted `#` at the start or after whitespace."""
    outside = _outside_quotes(value)
    for index, char in enumerate(value):
        if char == "#" and outside[index] and (index == 0 or value[index - 1] in " \t"):
            return value[:index]
    return value


def _unquote_yaml(value: str) -> str:
    """Return a YAML scalar without its surrounding quotes and quote escapes."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            return re.sub(r'\\(["\\])', r"\1", inner)
        return inner.replace("''", "'")
    return value


def _flow_list_end(value: str) -> int:
    """Index of the `]` that closes a YAML flow list, or -1 while it is still open."""
    outside = _outside_quotes(value)
    return next(
        (index for index, char in enumerate(value) if char == "]" and outside[index]),
        -1,
    )


def _flow_list_items(value: str) -> list[str]:
    """Return the items of a YAML flow list (`[a, "b", 'c']`), unquoted."""
    outside = _outside_quotes(value)
    end = _flow_list_end(value)
    if end == -1:
        end = len(value)
    items: list[str] = []
    start = 1
    for index in range(1, end + 1):
        if index == end or (value[index] == "," and outside[index]):
            item = _unquote_yaml(value[start:index])
            if item:
                items.append(item)
            start = index + 1
    return items


def frontmatter_sources(text: str) -> list[str]:
    """Return every entry of a page's frontmatter `sources:` field, in order.

    Reads each form a page may use: an inline list with quoted or unquoted items
    (on one line or wrapped over several), a block list whose items are indented
    or at column 0, and a single scalar. Quotes and a trailing ` # comment` are
    not part of an entry; a `#` inside a URL is. Returns `[]` when the page has
    no frontmatter, no `sources:` key, or an empty one.
    """
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return []
    lines = text[bounds[0]:bounds[1]].splitlines()
    for number, line in enumerate(lines):
        match = re.match(r"^sources\s*:(.*)$", line)
        if not match:
            continue
        value = _strip_yaml_comment(match.group(1)).strip()
        following = lines[number + 1:]

        if value.startswith("["):
            for extra in following:
                if _flow_list_end(value) != -1:
                    break
                value += " " + _strip_yaml_comment(extra).strip()
            return _flow_list_items(value)

        if value:
            entry = _unquote_yaml(value)
            return [] if value in ("null", "~") or not entry else [entry]

        entries: list[str] = []
        for extra in following:
            stripped = extra.strip()
            if not stripped or stripped.startswith("#"):
                continue
            item = re.match(r"^\s*-(?:\s+(.*))?$", extra)
            if not item:
                break
            entry = _unquote_yaml(_strip_yaml_comment(item.group(1) or ""))
            if entry:
                entries.append(entry)
        return entries
    return []


# ---------------------------------------------------------------------------
# Code fences and masking
# ---------------------------------------------------------------------------


def _fenced_lines(lines: Iterable[str]) -> list[bool]:
    """Flag each line that is a fence delimiter or lies inside a fenced code block.

    A block closes only on a fence of the character that opened it, at least as
    long as the opening fence and followed by nothing, so a `~~~` line inside a
    backtick block and a shorter backtick fence inside a longer one are code. A
    block that is never closed runs to the end. A backtick line with another
    backtick after the fence is an inline code span, not a fence.
    """
    flags: list[bool] = []
    open_char = ""
    open_length = 0
    for line in lines:
        match = FENCE_RE.match(line)
        body = line.strip()
        if not open_char:
            if not match:
                flags.append(False)
                continue
            char = match.group(1)[0]
            run = len(body) - len(body.lstrip(char))
            if char == "`" and "`" in body[run:]:
                flags.append(False)
                continue
            open_char, open_length = char, run
            flags.append(True)
            continue
        flags.append(True)
        if match and match.group(1)[0] == open_char:
            run = len(body) - len(body.lstrip(open_char))
            if run >= open_length and not body[run:]:
                open_char = ""
    return flags


def _blank(match: re.Match) -> str:
    return " " * len(match.group())


def strip_code_blocks(content: str) -> str:
    """Return `content` with fenced code blocks emptied and inline code spans blanked.

    Link scanners read the result so that a link inside a code sample is not a
    link. The line count is unchanged, so a line number found in the result is
    the line number in `content`; character offsets are not, because a fenced
    line becomes an empty line. `mask_code` keeps offsets.
    """
    lines = content.splitlines()
    out = []
    for line, fenced in zip(lines, _fenced_lines(lines)):
        out.append("" if fenced else _INLINE_CODE_RE.sub(_blank, line))
    return "\n".join(out)


def mask_code(text: str) -> str:
    """Return `text` with fenced code blocks and inline code spans replaced by spaces.

    The result has the same length as `text` and the same line breaks, so a
    match found in it sits at the same offsets in `text`: a rewriter searches
    the masked text and edits the original. Fences follow the same rules as
    `strip_code_blocks`.
    """
    lines = text.split("\n")
    out = []
    for line, fenced in zip(lines, _fenced_lines(lines)):
        if fenced:
            out.append(re.sub(r"[^\r]", " ", line))
        else:
            out.append(_INLINE_CODE_RE.sub(_blank, line))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def wikilink_target_body(target: str) -> str:
    """Return the target portion of a wikilink, without display text or section.

    Examples:
      ``page|Label`` -> ``page``
      ``chapters/places/places#Routes|Places`` -> ``chapters/places/places``
      ``chapters/places/places\\|Places`` -> ``chapters/places/places``

    The last form is a wikilink in a table cell, where the pipe is escaped; the
    backslash belongs to the table syntax, not to the path.
    """
    body, pipe, _label = target.partition("|")
    if pipe and body.endswith("\\"):
        body = body[:-1]
    return body.split("#", 1)[0].strip()


def rebuild_wikilink(target: str, new_body: str, *, label: Optional[str] = None) -> str:
    """Return the inner text of a wikilink (no brackets) that points at `new_body`.

    `target` is the inner text of the existing link. Its `#section` is kept. Its
    `|label` is kept when `label` is None, replaced when `label` is given, and
    dropped when `label` is `""`. A pipe escaped for a table cell (`\\|`) stays
    escaped; a label added to a link that had none gets a plain pipe, which a
    table cell does not accept.
    """
    left, pipe, old_label = target.partition("|")
    escaped = bool(pipe) and left.endswith("\\")
    if escaped:
        left = left[:-1]
    section = "#" + left.split("#", 1)[1] if "#" in left else ""
    if label is None:
        label = old_label
    separator = "\\|" if escaped else "|"
    suffix = f"{separator}{label}" if label else ""
    return f"{new_body}{section}{suffix}"


def resolve_wikilink_path(body: str, root: Path) -> Optional[Path]:
    """Resolve a full-path wikilink target against a grimoire root.

    Wikilinks are repository-root relative paths, with the ``.md`` suffix
    optional for Obsidian compatibility. Aliases and global filename-stem
    matches are intentionally not resolved.

    Multi-dot filenames are supported: ``[[path/to/plugin_ICD.template]]``
    resolves to ``path/to/plugin_ICD.template.md``. The convention covers
    capitalized acronym suffixes (ICD, IDD, SDK) and role suffixes
    (``.template``, ``.example``) that grimoires use deliberately.
    """
    if not body:
        return None

    candidate = Path(body)
    if candidate.is_absolute():
        return None

    # The `.md` suffix is appended, never swapped in, so a multi-dot name keeps
    # every part of its stem.
    if candidate.suffix != ".md":
        candidate = Path(str(candidate) + ".md")

    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() and resolved.suffix == ".md" else None


# A URL scheme has two or more characters, so a Windows drive path (`C:/notes`)
# is a local path.
_URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")
_LINK_TITLE_RE = re.compile(r"""^(\S+)\s+(?:"[^"]*"|'[^']*'|\([^)]*\))$""")


def is_external_url(target: str) -> bool:
    """Return True for a link target that leaves the grimoire: `scheme:` or `//host`.

    `https://…`, `mailto:…` and `obsidian://…` are external; a relative path, a
    rooted path and a Windows drive path are not.
    """
    target = target.strip().lstrip("<")
    return target.startswith("//") or bool(_URL_SCHEME_RE.match(target))


def markdown_link_path(raw: str) -> str:
    """Return the path part of a Markdown link target, as the file is named on disk.

    `raw` is what stands between the parentheses of `[label](…)`. The optional
    title (`path "Title"`), the angle brackets of `<path with spaces>`, the
    `#anchor` and the `?query` are removed, then percent-encoding is decoded
    (`my%20file.md` names `my file.md`). Returns `""` for a link that is only an
    anchor. An external URL is not a path: test `is_external_url` first.
    """
    target = raw.strip()
    if target.startswith("<"):
        end = target.find(">")
        target = target[1:end] if end != -1 else target[1:]
    else:
        titled = _LINK_TITLE_RE.match(target)
        if titled:
            target = titled.group(1)
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target)


# A link target that holds one of these is a template slot, not a path.
PLACEHOLDER_MARKERS = ("{", "<")
# Example names that formulae use as link targets for the author to replace.
PLACEHOLDER_PROSE_TOKENS = (
    "invocation_name", "chapter_name", "file_name",
    "FRAMEWORK_HOME", "GRIMOIRE_PATH", "FRAMEWORK_PATH",
    "Chapter Name", "Title", "Sub-topic", "filename",
    "related_page", "sub_topic", "related_chapter",
    "path/to/related", "path/url/system", "Source title",
)
PLACEHOLDER_TOKENS = PLACEHOLDER_MARKERS + PLACEHOLDER_PROSE_TOKENS


def is_placeholder_target(target: str, *, in_formula: bool) -> bool:
    """Return True when a link target is a template placeholder, not a real path.

    A target holding `{` or `<` is a placeholder on any page. The prose tokens
    (`Title`, `filename`, `chapter_name`, …) count only when `in_formula` is
    true, which the caller sets for a page under `formulae/`: on any other page
    they are ordinary words that a real page name may contain, and the link is
    validated.
    """
    if any(marker in target for marker in PLACEHOLDER_MARKERS):
        return True
    return in_formula and any(token in target for token in PLACEHOLDER_PROSE_TOKENS)


# ---------------------------------------------------------------------------
# Manifest / library
# ---------------------------------------------------------------------------

_MANIFEST_STRING_FIELDS = ("name", "skill_prefix", "description")


def load_manifest(directory: Path) -> tuple[Optional[dict], list]:
    """Load and shallow-validate a grimoire's `grimoire.json` manifest.

    Returns `(manifest, errors)` and never raises for a bad file. `manifest` is
    None when the file is missing, unreadable, not UTF-8, not JSON or not a JSON
    object; otherwise it is the parsed object, whatever `errors` holds, so a
    caller can still inspect partial data. A caller that uses a field checks
    `errors` first: a field named there may hold a value of the wrong type.

    Validation covers the universal fields: `name` and `skill_prefix` are
    required strings (`skill_prefix` matches `SKILL_PREFIX_RE`), `description`
    and `naming` are strings when present. Stricter checks, such as
    `skill_prefix` collisions across grimoires, belong to the caller.
    """
    manifest_file = directory / "grimoire.json"
    try:
        has_manifest = manifest_file.is_file()
    except OSError as exc:
        return None, [f"could not access grimoire.json: {exc}"]
    if not has_manifest:
        return None, ["missing grimoire.json"]

    try:
        metadata = json.loads(read_utf8(manifest_file))
    except UnicodeDecodeError as exc:
        return None, [f"could not parse grimoire.json: not UTF-8 ({exc})"]
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"could not parse grimoire.json: {exc}"]
    if not isinstance(metadata, dict):
        return None, ["could not parse grimoire.json: the file must hold a JSON object"]

    errors = []
    for field in _MANIFEST_STRING_FIELDS:
        if field in metadata and not isinstance(metadata[field], str):
            errors.append(f"grimoire.json '{field}' must be a string")
    name = metadata.get("name", "")
    skill_prefix = metadata.get("skill_prefix", "")
    if not name:
        errors.append("grimoire.json missing 'name' field")
    if not skill_prefix:
        errors.append("grimoire.json missing 'skill_prefix' field")
    elif isinstance(skill_prefix, str) and not SKILL_PREFIX_RE.fullmatch(skill_prefix):
        errors.append(
            f"invalid skill_prefix '{skill_prefix}' (must match {SKILL_PREFIX_RE.pattern})"
        )
    if "naming" in metadata:
        naming = metadata.get("naming")
        if not isinstance(naming, str) or not naming.strip():
            errors.append("grimoire.json 'naming' must be a non-empty string (for example snake_case)")
        elif len(naming.strip()) > NAMING_MAX_LEN:
            errors.append(f"grimoire.json 'naming' must be at most {NAMING_MAX_LEN} characters")

    return metadata, errors


def read_library(library_path: Path) -> tuple[Optional[dict], str]:
    """Read a `library.json` file and say whether it can be used.

    Returns `(library, "")` when the file is absent or empty (the library is then
    `{"grimoires": {}}`) or holds a JSON object; an object without a `grimoires`
    key gains an empty one. Returns `(None, reason)` when the file exists and
    cannot be used: unreadable, not UTF-8, not JSON, not an object, or with a
    `grimoires` value that is not an object. A writer that gets `None` leaves the
    file alone, because writing a fresh library over it loses every entry the
    owner could still recover.
    """
    library_path = Path(library_path)
    try:
        text = read_utf8(library_path)
    except FileNotFoundError:
        return {"grimoires": {}}, ""
    except UnicodeDecodeError as exc:
        return None, f"{library_path} is not UTF-8: {exc}"
    except OSError as exc:
        return None, f"{library_path} could not be read: {exc}"
    if not text.strip():
        return {"grimoires": {}}, ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"{library_path} is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"{library_path} must hold a JSON object"
    if "grimoires" not in data:
        data["grimoires"] = {}
    elif not isinstance(data["grimoires"], dict):
        return None, f"{library_path}: 'grimoires' must be an object"
    return data, ""


def load_library(library_path: Path) -> dict:
    """Read a `library.json` file. Always returns a dict with a `grimoires` object.

    A missing file is an empty library. A file that exists and cannot be used
    is also returned as `{"grimoires": {}}`, with a warning printed, so a reader
    can carry on. A caller that writes the library back uses `read_library`
    instead, which tells the two cases apart.
    """
    library, reason = read_library(library_path)
    if library is None:
        warn(f"could not read library: {reason} (treating as empty)")
        return {"grimoires": {}}
    return library


_HOME_TOKEN = "$HOME"


def resolve_local_path(raw: str, *, resolve: bool = False) -> Path:
    """Expand the `$HOME` token that opens a library `local_path` entry.

    `resolve=True` also expands `~` and resolves to an absolute path, the form
    skill registration and filesystem operations need. The default leaves the
    rest of the path as written so library reconciliation can compare against
    the stored form.

    `$HOME/grimoires/x` is the form `format_local_path` writes. `$HOME\\grimoires\\x`
    is the form in a library written on Windows by a release that predates
    `format_local_path`; both name the same folder on every platform.

    An empty or relative entry resolves against the working directory, which is
    never the grimoire the entry means: test `is_usable_local_path` first.
    """
    if not raw:
        return Path().resolve() if resolve else Path()
    text = str(raw)
    if text == _HOME_TOKEN or text.startswith((_HOME_TOKEN + "/", _HOME_TOKEN + "\\")):
        rest = text[len(_HOME_TOKEN):].replace("\\", "/").strip("/")
        path = Path.home() / rest if rest else Path.home()
    else:
        path = Path(text)
    return path.expanduser().resolve() if resolve else path


def is_usable_local_path(raw: str) -> bool:
    """Return True when a library `local_path` names one folder wherever the rite runs.

    False for an empty value, a value that is not a string, and a path that is
    still relative after `$HOME` and `~` expansion. Such an entry would resolve
    to the working directory, so a rite treats it as a missing grimoire.
    """
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        return resolve_local_path(raw.strip()).expanduser().is_absolute()
    except (OSError, RuntimeError, ValueError):
        return False


READ_ONLY_REFUSAL = (
    "this grimoire is set up for reading on this computer, so nothing was changed; "
    "switch it to editing with the grimoire_access rite (--set edit --apply)"
)


def default_library_path() -> Path:
    """The user's library file, `~/grimoires/library.json`, with the home read at call time."""
    return Path.home() / "grimoires" / "library.json"


def library_entry_for(root: Path, library_path: Optional[Path] = None) -> tuple[Optional[str], Optional[dict]]:
    """Find the library key and entry whose `local_path` names the folder `root`.

    Entries whose path is not usable are skipped. Returns `(None, None)` when the
    library is missing or unreadable or holds no entry for the folder; never raises.
    """
    try:
        library, _reason = read_library(library_path if library_path is not None else default_library_path())
        if library is None:
            return None, None
        target = os.path.normcase(str(Path(root).expanduser().resolve()))
        for key, entry in library["grimoires"].items():
            if not isinstance(entry, dict):
                continue
            raw = entry.get("local_path")
            if not is_usable_local_path(raw):
                continue
            if os.path.normcase(str(resolve_local_path(raw.strip(), resolve=True))) == target:
                return key, entry
    except (OSError, RuntimeError, ValueError):
        pass
    return None, None


def grimoire_access(root: Path, library_path: Optional[Path] = None) -> str:
    """`"read"` when the library registers the folder for reading on this computer, else `"edit"`."""
    _key, entry = library_entry_for(root, library_path)
    return "read" if entry is not None and entry.get("access") == "read" else "edit"


def read_only_refusal(root: Path, library_path: Optional[Path] = None) -> Optional[str]:
    """The refusal text for a read-only grimoire, or None when it can be changed."""
    return READ_ONLY_REFUSAL if grimoire_access(root, library_path) == "read" else None


def format_local_path(path: Path) -> str:
    """Return the `local_path` value that `library.json` records for a grimoire folder.

    A folder inside the user's home is written as `$HOME/<relative path>`, so the
    library reads the same for every user; any other folder is written as its
    absolute path. Both use forward slashes on every platform, and
    `resolve_local_path` reads back what this writes. Every writer of
    `local_path` formats through this function: two spellings of one folder
    make library reconciliation report a mismatch.
    """
    absolute = Path(os.path.abspath(Path(path).expanduser()))
    home = Path.home()
    for candidate, base in (
        (absolute, home),
        (Path(os.path.realpath(absolute)), Path(os.path.realpath(home))),
    ):
        try:
            relative = candidate.relative_to(base).as_posix()
        except ValueError:
            continue
        return _HOME_TOKEN if relative == "." else f"{_HOME_TOKEN}/{relative}"
    return absolute.as_posix()


# ---------------------------------------------------------------------------
# Root hub and hub predicate
# ---------------------------------------------------------------------------


def root_hub_stem(root: Path, manifest: Optional[dict] = None) -> str:
    """Return the stem of the root hub file of a grimoire or of the framework.

    The stem is the manifest `name` when `<root>/<name>.md` exists, else the
    name of the root directory. A checkout may sit in a folder with any name (a
    CI runner clones into `repo`; the framework installs at `~/.grimoire`), so
    the directory name is the fallback, not the rule. The manifest is
    `grimoire.json`, loaded from `root` when not given; a root without one is
    read as the framework, whose manifest is `framework.json`.
    """
    root = Path(root)
    if manifest is None:
        manifest, _errors = load_manifest(root)
    if not isinstance(manifest, dict):
        try:
            manifest = json.loads(read_utf8(root / "framework.json"))
        except (OSError, ValueError):
            manifest = None
    name = manifest.get("name") if isinstance(manifest, dict) else None
    if isinstance(name, str):
        name = name.strip()
        if name and "/" not in name and "\\" not in name and (root / f"{name}.md").is_file():
            return name
    return root.name or root.resolve().name


def root_hub_path(root: Path, manifest: Optional[dict] = None) -> Path:
    """Return the path of a grimoire's root hub file, which may not exist.

    The file name follows `root_hub_stem`.
    """
    root = Path(root)
    return root / f"{root_hub_stem(root, manifest)}.md"


def is_hub(path: Path) -> bool:
    """Return True for a folder hub: a file whose stem is its parent folder's name.

    The comparison ignores case. The root hub of a grimoire checked out under
    another folder name does not match; `root_hub_path` finds that one.
    """
    path = Path(path)
    return bool(path.parent.name) and path.stem.casefold() == path.parent.name.casefold()


# ---------------------------------------------------------------------------
# Skill families and commands
# ---------------------------------------------------------------------------


def read_frontmatter_name(skill_file: Path) -> str:
    """Return the frontmatter `name:` declared in a SKILL.md (empty if absent)."""
    try:
        text = Path(skill_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    value = parse_frontmatter(text).get("name", "")
    return value if isinstance(value, str) else ""


def _is_relative_inside(value) -> bool:
    """True for a non-empty relative path with no drive, root or `..` segment."""
    if not isinstance(value, str) or not value.strip():
        return False
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value.replace("\\", "/"))
    if windows.drive or windows.root or posix.is_absolute():
        return False
    return ".." not in posix.parts


def load_skill_families_checked(root: Path) -> tuple[list[dict], list[str]]:
    """Return the framework's command families and every problem found reading them.

    Reads `skill_families` from `<root>/framework.json`. Each family is
    `{name, skill_prefix, path, slug_prefix, plugin}`: `path` is absolute,
    `skill_prefix` falls back to the manifest's own, and `plugin`, the Claude
    Code plugin that carries the family, falls back to the family name.

    The second value lists, in words a person can act on, what is wrong: an
    unreadable or non-object manifest, a missing or malformed `skill_families`,
    and each family whose `skill_prefix`, `slug_prefix`, `plugin` or relative
    `path` is invalid. A family with a problem is left out of the first value,
    so a caller never registers or documents a command under an invalid name.
    """
    root = Path(root)
    try:
        metadata = json.loads(read_utf8(root / "framework.json"))
    except (OSError, ValueError) as exc:
        return [], [f"could not read framework.json: {exc}"]
    if not isinstance(metadata, dict):
        return [], ["framework.json must hold a JSON object"]
    raw = metadata.get("skill_families")
    if raw is None:
        return [], ["framework.json has no skill_families"]
    if not isinstance(raw, dict) or not raw:
        return [], ["framework.json skill_families must be a non-empty object of family definitions"]

    default_prefix = metadata.get("skill_prefix", "grm")
    families: list[dict] = []
    problems: list[str] = []
    for name, config in raw.items():
        label = f"skill_families.{name}"
        if not isinstance(config, dict):
            problems.append(f"{label} must be an object")
            continue
        skill_prefix = config.get("skill_prefix", default_prefix)
        rel_path = config.get("path", "")
        slug_prefix = config.get("slug_prefix", "")
        plugin = config.get("plugin", name)

        found = []
        if not isinstance(skill_prefix, str) or not SKILL_PREFIX_RE.fullmatch(skill_prefix):
            found.append(
                f"{label} has an invalid skill_prefix {skill_prefix!r} "
                f"(must match {SKILL_PREFIX_RE.pattern})"
            )
        if not _is_relative_inside(rel_path):
            found.append(
                f"{label} has an invalid path {rel_path!r} "
                "(must be a relative path inside the framework)"
            )
        if not isinstance(slug_prefix, str) or (slug_prefix and not SKILL_SLUG_RE.fullmatch(slug_prefix)):
            found.append(
                f"{label} has an invalid slug_prefix {slug_prefix!r} "
                f"(must be empty or match {SKILL_SLUG_RE.pattern})"
            )
        if not isinstance(plugin, str) or not plugin.strip():
            found.append(f"{label} has an invalid plugin {plugin!r} (must be a plugin name)")
        if found:
            problems.extend(found)
            continue

        families.append({
            "name": name,
            "skill_prefix": skill_prefix,
            "path": root / rel_path,
            "slug_prefix": slug_prefix,
            "plugin": plugin,
        })
    return families, problems


def load_skill_families(root: Path, *, with_fallback: bool = False) -> list[dict]:
    """Return the framework's command families from framework.json.

    The families are the first value of `load_skill_families_checked`, the one
    reader of `skill_families`: `[]` when framework.json is unreadable or
    declares none, and never a family with an invalid field. A caller that
    reports why a family is missing calls the checked form. `with_fallback` is
    accepted and has no effect.
    """
    families, _problems = load_skill_families_checked(root)
    return families


def discover_skill_commands(root: Path) -> dict:
    """Return every framework-shipped public command keyed by slash command.

    Value: `{family, skill_prefix, skill_source, slug, description,
    argument_hint}`. `slug` is the skill's folder name; `description` and
    `argument_hint` come from the SKILL.md frontmatter and are `""` when absent.
    A SKILL.md that cannot be read as UTF-8, or that declares no `name`, is not
    a command.
    """
    root = Path(root)
    commands: dict = {}
    for family in load_skill_families(root):
        family_dir = family["path"]
        if not family_dir.is_dir():
            continue
        for skill_file in sorted(family_dir.glob("*/SKILL.md")):
            try:
                fields = parse_frontmatter(read_utf8(skill_file))
            except (OSError, UnicodeDecodeError):
                continue
            templated_name = fields.get("name", "")
            if not isinstance(templated_name, str) or not templated_name:
                continue
            description = fields.get("description", "")
            argument_hint = fields.get("argument-hint", "")
            # An unquoted bracket hint (`argument-hint: [topic]`) parses as a
            # list; the hint a user sees is the bracketed text.
            if isinstance(argument_hint, list):
                argument_hint = "[" + ", ".join(str(item) for item in argument_hint) + "]"
            command = "/" + templated_name.replace(SKILL_PREFIX_PLACEHOLDER, family["skill_prefix"])
            commands[command] = {
                "family": family["name"],
                "skill_prefix": family["skill_prefix"],
                "skill_source": skill_file.relative_to(root).as_posix(),
                "slug": skill_file.parent.name,
                "description": description if isinstance(description, str) else "",
                "argument_hint": str(argument_hint).strip(),
            }
    return commands


# ---------------------------------------------------------------------------
# Page discovery
# ---------------------------------------------------------------------------

# Root-level folders whose Markdown is outside the link graph: `inbox/` holds
# unclassified drops, `tests/` holds fixtures with deliberately broken links.
LINK_SKIP_DIRS = frozenset({"inbox", "tests"})

# Append-only history files: an entry keeps the names and trees that were
# current when it was written.
HISTORY_FILENAMES = frozenset({"CHANGELOG.md"})


def iter_pages(
    root: Path,
    scan_dirs: Iterable[str],
    exempt_filenames: Iterable[str] = (),
    skip_dirs: Iterable[str] = (),
    include_root_md: bool = True,
) -> Iterable[Path]:
    """Yield markdown files a validator should consider.

    Walks each `scan_dirs` subtree under `root` with `walk_files`, so nothing
    under a pruned directory (`PRUNED_DIRS`) is yielded. Skips any path whose
    relative parts include a `skip_dirs` entry, and any file whose name is in
    `exempt_filenames`. Optionally also yields any `*.md` directly under
    `root` (the grimoire root hub plus any peer-level docs).

    Yields each path at most once, in deterministic sorted order per scan dir.
    """
    seen: set = set()
    skip_set = set(skip_dirs)
    exempt_set = set(exempt_filenames)

    for d in scan_dirs:
        sub = root / d
        if not sub.is_dir():
            continue
        for path in walk_files(sub, "*.md"):
            if path.name in exempt_set:
                continue
            rel_parts = path.relative_to(root).parts
            if any(part in skip_set for part in rel_parts):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path

    if include_root_md:
        for path in sorted(root.glob("*.md")):
            if path in seen or path.name in exempt_set:
                continue
            yield path


def iter_link_pages(root: Path) -> Iterable[Path]:
    """Yield the Markdown pages whose links the framework validates and rewrites.

    Every `*.md` under `root`, in sorted order, except what `walk_files` prunes
    (`publish/`, `.git/`, `node_modules/` at any depth), the root-level folders
    in `LINK_SKIP_DIRS`, and pages inside a chapter-local `sources/` folder,
    which are immutable source wrappers. The link validator and every rite that
    rewrites links iterate with this, so a rite never rewrites a page the
    validator does not check.
    """
    for path in walk_files(root, "*.md"):
        rel = path.relative_to(root)
        if is_skipped(rel, LINK_SKIP_DIRS) or is_inside_colocated_source_dir(rel):
            continue
        yield path


# ---------------------------------------------------------------------------
# Path skip / public-doc classification
# ---------------------------------------------------------------------------

PUBLIC_DOC_DIRS = {"docs"}
PUBLIC_DOC_FILENAMES = {"README.md", "UPDATE.md", "CONTRIBUTING.md", "CHANGELOG.md"}


def is_skipped(rel, skip_dirs: Iterable[str]) -> bool:
    """Return True when a root-relative path falls inside a skip directory.

    `rel` may be a Path or a string. A skip entry matches as a leading path
    prefix at segment boundaries: a single-segment entry like ``sources`` skips
    ``sources/...`` but never a sibling like ``sources_extra/...``, and a
    multi-segment entry like ``invocations/validators`` skips only that
    subtree.
    """
    if isinstance(rel, Path):
        parts = rel.parts
    else:
        parts = tuple(p for p in str(rel).replace("\\", "/").split("/") if p)
    folded = tuple(p.casefold() for p in parts)
    for sd in skip_dirs:
        sd_parts = tuple(p.casefold() for p in str(sd).replace("\\", "/").split("/") if p)
        if sd_parts and folded[: len(sd_parts)] == sd_parts:
            return True
    return False


def public_document(path: Path, root: Path) -> bool:
    """Return True when a Markdown file is meant to render portably on Git hosts.

    Public docs - the top-level README/UPDATE/CONTRIBUTING/CHANGELOG and the
    ``docs/`` tree - use standard Markdown links; vault and AI-routing surfaces
    use full-path wikilinks.
    """
    if path.name in PUBLIC_DOC_FILENAMES:
        return True
    rel = path.relative_to(root)
    return bool(rel.parts and rel.parts[0] in PUBLIC_DOC_DIRS)


# ----------------------------------------------------------------------------
# On-disk spelling
# ----------------------------------------------------------------------------

_LISTDIR_CACHE: dict = {}


def _listdir_cached(directory: Path) -> list:
    key = str(directory)
    if key not in _LISTDIR_CACHE:
        try:
            _LISTDIR_CACHE[key] = os.listdir(directory)
        except OSError:
            _LISTDIR_CACHE[key] = []
    return _LISTDIR_CACHE[key]


def spell_on_disk(rel: str, root: Path) -> Optional[str]:
    """Return ``rel`` (a root-relative POSIX path) spelled as it is stored on disk.

    Segments are matched case-insensitively, so one helper answers two
    questions: on a case-insensitive filesystem (Windows, macOS), whether a link
    that resolved really matches the on-disk casing; on a case-sensitive one
    (Linux, CI, site builds), what the author probably meant when a link did not
    resolve at all. Returns None when no case-insensitive match exists.
    """
    parts = [p for p in rel.replace("\\", "/").split("/") if p and p != "."]
    current = root
    spelled = []
    for part in parts:
        if part == "..":
            current = current.parent
            spelled.append("..")
            continue
        entries = _listdir_cached(current)
        if part in entries:
            actual = part
        else:
            folded = part.casefold()
            matches = [entry for entry in entries if entry.casefold() == folded]
            if not matches:
                return None
            actual = matches[0]
        spelled.append(actual)
        current = current / actual
    return "/".join(spelled)


# ----------------------------------------------------------------------------
# Tree walking that never descends into generated or foreign trees
# ----------------------------------------------------------------------------

# Folders no validator or rewriter descends into, at any depth: version-control
# metadata, installed packages, and the editor's own configuration.
PRUNED_DIRS = {".git", "node_modules", ".obsidian"}
# Folders pruned only directly under the root: a grimoire's `publish/` layer holds
# configuration and disposable build output. A folder of that name deeper in the
# tree (the framework's `formulae/publish/`) is ordinary content.
ROOT_PRUNED_DIRS = {"publish"}


def walk_files(
    root: Path,
    pattern: str = "*",
    prune: Iterable[str] = PRUNED_DIRS,
    root_prune: Iterable[str] = ROOT_PRUNED_DIRS,
):
    """Return a sorted list of the files under ``root`` whose name matches
    ``pattern`` (fnmatch), without descending into pruned directories.

    ``prune`` names are skipped at any depth; ``root_prune`` names are skipped
    only as direct children of ``root``. A grimoire that has built its site
    carries thousands of generator files under ``publish/``, so the walk stops
    at the directory instead of filtering afterwards.
    """
    pruned = set(prune)
    root_pruned = set(root_prune)
    root_str = os.path.normpath(str(root))
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        at_root = os.path.normpath(dirpath) == root_str
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in pruned and not (at_root and d in root_pruned)
        )
        for name in filenames:
            if fnmatch.fnmatch(name, pattern):
                results.append(Path(dirpath) / name)
    return sorted(results)


# ----------------------------------------------------------------------------
# Git
# ----------------------------------------------------------------------------


def run_git(root: Path, *args: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run `git <args>` in `root` and return `(returncode, stdout, stderr)`.

    Paths in the output are spelled as on disk: `core.quotepath` is off, so a
    non-ASCII name is not octal-escaped, and output is decoded as UTF-8 with
    undecodable bytes replaced. A name holding a space, a quote or a control
    character is still quoted unless the caller passes `-z`. Git never prompts
    (`GIT_TERMINAL_PROMPT=0`, no stdin). This function does not raise for a git
    failure: a missing git binary returns `(127, "", "git is not installed")`
    and a run longer than `timeout` seconds returns `(124, "", "timed out")`, so
    the caller checks the return code before it trusts stdout.
    """
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError:
        return 127, "", "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    return proc.returncode, proc.stdout, proc.stderr
