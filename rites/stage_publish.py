#!/usr/bin/env python3
"""Stage a grimoire's publishable content for a static-site generator.

The authoring layout (`chapters/`, `inbox/`, `skills/`, `publish/`, editor
dotfiles) is not the layout readers should see. This rite copies just the
publishable content into a content directory the generator reads:

- the root hub becomes `index.md`;
- every top-level folder under `chapters/` lands at the content root
  (readers see `travel/`, not `chapters/travel/`), with chapter-local
  `sources/` folders carried along;
- asset folders (`templates/`, `snippets/`, `scripts/`, `configs/`,
  `assets/`, `media/`) and anything listed under `exclude` in
  `publish/publish.json` are left out; `.gitkeep` files are dropped;
- wikilinks, Markdown asset links, and frontmatter `sources:` paths are
  rewritten so they resolve against the flattened tree, and aliases equal to
  a page's own slug are removed (they would make a generator emit redirect
  loops). Text inside code is left alone. A wikilink to a page outside
  `chapters/` that is not the root hub (`[[README]]`) becomes its plain label,
  because that page is not staged.

This module owns the publishing constants and the `publish/publish.json`
loader; `audit_publish.py` imports them.

Configuration (all optional) lives in `<grimoire>/publish/publish.json`:

    {
      "generator": "quartz",
      "content_dir": "publish/content",
      "exclude": ["chapters/travel/templates"],
      "include_asset_folders": false,
      "audit": {}
    }

`content_dir` must be a folder below `publish/` that holds no publishing
settings (`publish.json`, `build.sh`, `quartz.config.yaml`). The `audit` key is
read by `audit_publish.py`.

Mutation profile: plan_apply. Without `--apply` the rite lists what it would
stage and writes nothing; with `--apply` it empties the content directory and
writes the staged copy. It deletes nothing outside the content directory.

Usage:
    python rites/stage_publish.py --grimoire <path> [--apply] [--format human|json|jsonl]

The JSON summary names the content directory relative to the grimoire root, in
`content_dir`.

Exit codes: 0 = planned or staged, 1 = refused (invalid publish.json, no root
hub, no chapters, unusable content directory), 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from _lib import (
    add_grimoire_arg,
    frontmatter_bounds,
    frontmatter_sources,
    info,
    is_external_url,
    load_manifest,
    mask_code,
    ok,
    read_utf8,
    rebuild_wikilink,
    resolve_grimoire_arg,
    resolve_wikilink_path,
    root_hub_path,
    warn,
    wikilink_target_body,
    write_utf8,
)
from diagnostics import ResultReporter, add_output_format_arg

ASSET_FOLDERS = {"templates", "snippets", "scripts", "configs", "assets", "media"}
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf",
    ".heic", ".avif", ".mp4", ".mov", ".m4v", ".webm", ".eml",
}
PUBLISH_SETTINGS_FILES = ("publish.json", "build.sh", "quartz.config.yaml")
WIKI_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")
MD_LINK_RE = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")
DEFAULT_CONFIG = {
    "generator": "quartz",
    "content_dir": "publish/content",
    "exclude": [],
    "include_asset_folders": False,
    "audit": {},
}


def load_config(root: Path) -> dict:
    """Return `publish/publish.json` over the defaults; raise ValueError when it is unusable."""
    config = dict(DEFAULT_CONFIG)
    path = root / "publish" / "publish.json"
    if path.is_file():
        try:
            loaded = json.loads(read_utf8(path))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"publish/publish.json is not valid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError("publish/publish.json must hold a JSON object")
        config.update(loaded)
    if not isinstance(config["content_dir"], str) or not config["content_dir"].strip():
        raise ValueError("publish/publish.json: content_dir must be a path")
    if not isinstance(config["exclude"], list):
        raise ValueError("publish/publish.json: exclude must be a list of paths")
    if not isinstance(config["audit"], dict):
        raise ValueError("publish/publish.json: audit must be an object")
    return config


def content_dir_error(root: Path, content_dir: Path, configured: str) -> str:
    """Return why `content_dir` cannot be emptied and rewritten, or "" when it can."""
    publish = (root / "publish").resolve()
    try:
        content_dir.relative_to(publish)
    except ValueError:
        return f"content_dir must sit under publish/: {configured}"
    if content_dir == publish:
        return f"content_dir must be a folder below publish/, not publish/ itself: {configured}"
    held = [name for name in PUBLISH_SETTINGS_FILES if (content_dir / name).exists()]
    if held:
        return f"content_dir holds publishing settings ({', '.join(held)}), which staging would delete: {configured}"
    return ""


def split_target(target: str) -> tuple[str, str, str]:
    query = anchor = ""
    if "#" in target:
        target, anchor = target.split("#", 1)
        anchor = "#" + anchor
    if "?" in target:
        target, query = target.split("?", 1)
        query = "?" + query
    return target, query, anchor


class Rewriter:
    """Rewrites authoring paths into published paths for one grimoire."""

    def __init__(self, root: Path, content_dir: Path, hub_stem: str) -> None:
        self.root = root.resolve()
        self.root_targets = {hub_stem, f"{hub_stem}.md"}
        self.content_dir = content_dir.resolve()

    def target(self, target: str) -> str:
        """The published spelling of an authoring path, without query or anchor."""
        if target in self.root_targets:
            return "index"
        if target.startswith("chapters/"):
            return target[len("chapters/"):]
        return target

    def authoring_dir(self, page: Path) -> Path:
        """The folder the staged `page` came from, in the authoring tree."""
        rel = page.resolve().relative_to(self.content_dir)
        return self.root if rel.as_posix() == "index.md" else self.root / "chapters" / rel.parent

    def unpublished_page(self, body: str) -> bool:
        """True when a wikilink body names an existing page outside `chapters/` that is not the root hub."""
        if body in self.root_targets:
            return False
        resolved = resolve_wikilink_path(body, self.root)
        return resolved is not None and resolved.relative_to(self.root).parts[0] != "chapters"

    def wikilinks(self, text: str) -> str:
        masked = mask_code(text)
        pieces: list[str] = []
        last = 0
        for match in WIKI_RE.finditer(masked):
            embed = match.group(1)
            inner = text[match.start(2):match.end(2)]
            body = wikilink_target_body(inner)
            if not embed and self.unpublished_page(body):
                label = inner.partition("|")[2].strip()
                replacement = label or body
            else:
                replacement = f"{embed}[[{rebuild_wikilink(inner, self.target(body))}]]"
            pieces.append(text[last:match.start()])
            pieces.append(replacement)
            last = match.end()
        pieces.append(text[last:])
        return "".join(pieces)

    def frontmatter(self, path: Path, text: str) -> str:
        bounds = frontmatter_bounds(text)
        if bounds is None:
            return text
        start, end = bounds
        own = ("index" if path.name == "index.md" else path.stem).replace("_", "-").lower()
        lines = self._aliases(text[start:end].split("\n"), own)
        lines = self._sources(lines)
        return text[:start] + "\n".join(lines) + text[end:]

    @staticmethod
    def _aliases(lines: list[str], own: str) -> list[str]:
        out = []
        for line in lines:
            match = re.match(r"^(\s*)aliases:\s*\[(.*)\]\s*$", line)
            if match:
                kept = [a.strip() for a in match.group(2).split(",") if a.strip() and a.strip().strip("\"'").replace("_", "-").lower() != own]
                line = f"{match.group(1)}aliases: [{', '.join(kept)}]"
            out.append(line)
        return out

    def _sources(self, lines: list[str]) -> list[str]:
        """Rewrite every path in the `sources:` field, whatever form the field takes."""
        span = sources_span(lines)
        if span is None:
            return lines
        first, last = span
        entries = frontmatter_sources("---\n" + "\n".join(lines) + "\n---\n")
        replacements = {}
        for entry in entries:
            path = entry.replace("\\", "/")
            while path.startswith("./"):
                path = path[2:]
            if is_external_url(path):
                continue
            published = self.target(path)
            if published != path:
                replacements[entry] = published
        for number in range(first, last):
            line = lines[number]
            head, tail = (line[: line.index(":") + 1], line[line.index(":") + 1:]) if number == first else ("", line)
            for old, new in replacements.items():
                tail = re.sub(rf"(?<![\w/.%~-]){re.escape(old)}(?![\w/.%~-])", lambda _m, new=new: new, tail)
            lines[number] = head + tail
        return lines

    def published_asset(self, page: Path, body: str) -> str | None:
        """The rooted published path of the staged asset a link in `page` points at, or None."""
        base = self.root if body.startswith("/") else self.authoring_dir(page)
        target = Path(os.path.normpath(base / body.lstrip("/")))
        try:
            parts = target.relative_to(self.root).parts
        except ValueError:
            return None
        if len(parts) < 2 or parts[0] != "chapters":
            return None
        staged = Path(*parts[1:])
        return "/" + staged.as_posix() if (self.content_dir / staged).is_file() else None

    def asset_links(self, path: Path, text: str) -> str:
        masked = mask_code(text)
        pieces: list[str] = []
        last = 0
        for match in MD_LINK_RE.finditer(masked):
            prefix = text[match.start(1):match.end(1)]
            inner = text[match.start(2):match.end(2)]
            suffix = text[match.start(3):match.end(3)]
            replacement = self._asset_link(path, prefix, inner, suffix)
            if replacement is None:
                continue
            pieces.append(text[last:match.start()])
            pieces.append(replacement)
            last = match.end()
        pieces.append(text[last:])
        return "".join(pieces)

    def _asset_link(self, page: Path, prefix: str, inner: str, suffix: str) -> str | None:
        """The rewritten link, or None when the link stays as written."""
        raw = inner.strip()
        if not raw or is_external_url(raw):
            return None
        angle = raw.startswith("<") and ">" in raw
        if angle:
            target, rest = raw[1:].split(">", 1)
        else:
            parts = raw.split(maxsplit=1)
            target, rest = parts[0], (" " + parts[1] if len(parts) > 1 else "")
        if not target or target.startswith("#"):
            return None
        body, query, anchor = split_target(target.replace("\\", "/"))
        encoded = "%" in body
        body = unquote(body)
        if not body or Path(body).suffix.lower() not in ASSET_EXTS:
            return None
        published = self.published_asset(page, body)
        if published is None:
            return None
        if encoded:
            published = quote(published, safe="/")
        published += query + anchor
        if angle or re.search(r"[ ()]", published):
            published = f"<{published}>"
        return f"{prefix}{published}{rest}{suffix}"


def sources_span(lines: list[str]) -> tuple[int, int] | None:
    """The `[first, last)` line range of the `sources:` field in frontmatter lines, or None."""
    for first, line in enumerate(lines):
        match = re.match(r"^sources\s*:(.*)$", line)
        if match:
            break
    else:
        return None
    value = match.group(1).strip()
    last = first + 1
    if value.startswith("["):
        while "]" not in lines[last - 1] and last < len(lines):
            last += 1
    elif not value or value.startswith("#"):
        while last < len(lines) and (not lines[last].strip() or lines[last].lstrip().startswith(("-", "#"))):
            last += 1
    return first, last


def excluded(rel_parts: tuple[str, ...], config: dict) -> bool:
    """True when a path under chapters/ is left out of the staged copy."""
    rel = "/".join(rel_parts)
    for item in config.get("exclude", []):
        item = str(item).replace("\\", "/").strip("/")
        if rel == item or rel.startswith(item + "/"):
            return True
    if not config.get("include_asset_folders"):
        if any(part.casefold() in ASSET_FOLDERS for part in rel_parts[:-1]) or (
            len(rel_parts) and rel_parts[-1].casefold() in ASSET_FOLDERS
        ):
            return True
    return rel_parts[-1] == ".gitkeep"


def plan_files(root: Path, config: dict, hub: Path) -> list[tuple[Path, Path]]:
    """(source, destination relative to content dir) for every file to stage."""
    chapters = root / "chapters"
    pairs = [(hub, Path("index.md"))]
    for path in sorted(chapters.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).parts  # ('chapters', ...)
        if excluded(rel, config):
            continue
        pairs.append((path, Path(*rel[1:])))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage a grimoire's publishable content")
    add_grimoire_arg(parser)
    parser.add_argument("--apply", action="store_true", help="Write the staged copy (default: plan only)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    root = resolve_grimoire_arg(args.grimoire)
    mode = "apply" if args.apply else "plan"
    reporter = ResultReporter("stage_publish", root=root, mode=mode)
    summary: dict = {"files": 0, "content_dir": "", "generator": ""}

    def finish(code: int) -> int:
        if not human:
            reporter.emit(args.format, summary=summary)
        return code

    def refuse(text: str) -> int:
        reporter.message("error", text)
        reporter.set_status("blocked")
        if human:
            warn(text)
        return finish(1)

    try:
        config = load_config(root)
    except ValueError as exc:
        return refuse(str(exc))
    content_dir = (root / config["content_dir"]).resolve()
    summary["generator"] = str(config.get("generator", "quartz"))
    problem = content_dir_error(root, content_dir, config["content_dir"])
    if problem:
        return refuse(problem)
    summary["content_dir"] = content_dir.relative_to(root.resolve()).as_posix()
    manifest, _errors = load_manifest(root)
    hub = root_hub_path(root, manifest)
    if not hub.is_file():
        return refuse(f"root hub not found: {hub.name} (grimoire.json name or directory name)")
    if not (root / "chapters").is_dir():
        return refuse("chapters/ not found")

    pairs = plan_files(root, config, hub)
    summary["files"] = len(pairs)
    if human:
        print()
        print(f"Stage {root.name} for {summary['generator']} ({mode})")
        info(f"{len(pairs)} file(s) -> {content_dir}")
        if config.get("exclude"):
            info("excluded: " + ", ".join(str(e) for e in config["exclude"]))

    if not args.apply:
        reporter.set_status("noop")
        if human:
            ok("Plan only. Re-run with --apply to stage.")
        return finish(0)

    if content_dir.exists():
        shutil.rmtree(content_dir)
    content_dir.mkdir(parents=True, exist_ok=True)
    for source, rel in pairs:
        destination = content_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    rewriter = Rewriter(root, content_dir, hub.stem)
    for page in sorted(content_dir.rglob("*.md")):
        try:
            text = read_utf8(page)
        except UnicodeDecodeError:
            reporter.message("warning", "not valid UTF-8, staged without rewriting its links", path=page.relative_to(content_dir))
            if human:
                warn(f"{page.relative_to(content_dir).as_posix()} is not valid UTF-8; staged without rewriting its links")
            continue
        text = rewriter.frontmatter(page, text)
        text = rewriter.wikilinks(text)
        text = rewriter.asset_links(page, text)
        write_utf8(page, text)

    reporter.mutation("stage", path=content_dir, detail=f"{len(pairs)} file(s)")
    if human:
        ok(f"Staged {len(pairs)} file(s) into {content_dir}")
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
