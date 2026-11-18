#!/usr/bin/env python3
"""Audit staged or built publishing output before it goes anywhere.

Publishing makes whatever is staged reachable, so this read-only check runs
over the staged content (`--mode content`, the default) or the generated
static site (`--mode static-output`) and reports:

- BLOCKER: authoring roots that must never be published (`.git/`,
  `.obsidian/`, `chapters/`, `inbox/`, `private/`, `publish/`, `skills/`, and
  asset folders unless `include_asset_folders` is true in
  `publish/publish.json`), assets whose names mark identity, payment, or
  credential material, possible full payment-card numbers (Luhn-checked),
  credentials, private keys, national identity numbers, bank details, seed
  phrases, identity document scans, and frontmatter `sources:` paths that do
  not resolve in the staged tree; in static mode, broken asset references in
  the built HTML.
- WARNING: published documents and images (fine behind access control,
  worth a look), unresolved wikilinks or asset links, unlinked source asset
  paths, any pattern the grimoire adds in `publish/publish.json`, and any
  blocker the grimoire waives there.

A grimoire extends the audit in `publish/publish.json`:

    {
      "audit": {
        "warning_patterns": {"booking-reference": "\\\\b(?:confirmation code|record locator)\\\\b"},
        "known_identifier_patterns": ["airbnb\\\\.com/rooms/{digits}\\\\b"],
        "allow": [{"risk": "bank-account-data", "path": "travel/money/*"}]
      }
    }

`known_identifier_patterns` name number formats that look like card numbers
but are not; `{digits}` stands for the candidate digits. `allow` waives a
blocker: a blocker whose risk name equals `risk` and whose staged path matches
`path` (`*` matches any characters, including `/`) is reported as a warning
that names the waiver.

The staging rite owns `publish.json` loading and the asset constants; this
rite imports them.

Mutation profile: none.

Usage:
    python rites/audit_publish.py --grimoire <path> [--target <dir>] [--mode content|static-output]
        [--verbose-warnings] [--format human|json|jsonl]

Exit codes: 0 = no blockers, 1 = blockers found, 2 = target missing, unusable
publish.json, or invalid arguments.
"""

from __future__ import annotations

import argparse
import fnmatch
import html
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from _lib import (
    FRONTMATTER_RE,
    add_grimoire_arg,
    frontmatter_sources,
    is_external_url,
    mask_code,
    markdown_link_path,
    resolve_grimoire_arg,
    wikilink_target_body,
)
from diagnostics import DiagnosticReporter, add_output_format_arg
from stage_publish import ASSET_EXTS, ASSET_FOLDERS, MD_LINK_RE, WIKI_RE, load_config

BLOCKED_ROOTS = (".git", ".obsidian", "chapters", "inbox", "private", "publish", "skills")
TEXT_EXTS = {".md", ".html", ".htm", ".txt", ".json", ".js", ".css", ".xml", ".yaml", ".yml"}
BLOCKER_PATTERNS = [
    ("cvv-or-security-code", re.compile(r"\b(?:cvv|cvc|security\s+code|card\s+security\s+code)\b", re.I)),
    ("bank-account-data", re.compile(r"\b(?:bank\s+account|routing\s+number|iban|swift\s+code)\b", re.I)),
    ("national-identity-number", re.compile(r"\b(?:ssn|social\s+security\s+number|mynumber|my\s+number)\b", re.I)),
    ("api-key-or-token", re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret[_ -]?key)\b", re.I)),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", re.I)),
    ("password-or-credential", re.compile(r"\b(?:password|passphrase|recovery\s+code|backup\s+code)\b\s*[:=]", re.I)),
    ("seed-phrase", re.compile(r"\b(?:seed\s+phrase|mnemonic\s+phrase)\b", re.I)),
    ("identity-document-scan", re.compile(r"\b(?:passport|driver'?s?\s+licen[cs]e|identity\s+document|id\s+card).{0,40}\b(?:scan|photo|image|front|back)\b", re.I)),
    ("passport-number", re.compile(r"\bpassport\s+number\b", re.I)),
]
ASSET_WARNING_TYPES = {
    ".pdf": "published-document", ".png": "published-image", ".jpg": "published-image",
    ".jpeg": "published-image", ".heic": "published-image", ".eml": "email-export",
}
IDENTITY_ASSET_RE = re.compile(
    r"(passport|driver.?s.?licen[cs]e|identity.?document|id.?card|ssn|social.?security|credit.?card|password|private.?key|token|seed.?phrase)",
    re.I,
)
HTML_REF_RE = re.compile(r"\b(?:href|src)=['\"]([^'\"]+)['\"]", re.I)
SOURCE_PATH_RE = re.compile(r"(?<!\]\()(?P<target>(?:\.\./)*sources/[^\s`)>,]+|chapters/[^\s`)>,]*/sources/[^\s`)>,]+)")
DETAILED_WARNINGS = {
    "unresolved-wikilink", "unresolved-asset-reference", "unlinked-source-asset-path",
    "broken-static-asset-reference",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    risk: str
    action: str


@dataclass
class Audit:
    """What one audit run needs to examine a file."""

    scan_root: Path
    mode: str
    config: dict
    stats: Counter
    external_hosts: Counter


def load_audit_config(root: Path) -> dict:
    """Return the audit settings from `publish/publish.json`; raise ValueError when they are unusable."""
    config = load_config(root)
    audit = config["audit"]
    try:
        warnings = [(name, re.compile(pattern, re.I)) for name, pattern in (audit.get("warning_patterns") or {}).items()]
    except (re.error, TypeError, AttributeError) as exc:
        raise ValueError(f"publish/publish.json: audit.warning_patterns is not a map of valid patterns: {exc}") from exc
    allow = audit.get("allow") or []
    if not isinstance(allow, list) or not all(
        isinstance(item, dict) and isinstance(item.get("risk"), str) and isinstance(item.get("path"), str) for item in allow
    ):
        raise ValueError('publish/publish.json: audit.allow must be a list of {"risk": "<risk name>", "path": "<staged path or glob>"}')
    return {
        "content_dir": config["content_dir"],
        "include_asset_folders": bool(config["include_asset_folders"]),
        "warning_patterns": warnings,
        "known_identifier_patterns": [str(p) for p in (audit.get("known_identifier_patterns") or [])],
        "allow": allow,
    }


def waiver(config: dict, risk: str, rel: str) -> str | None:
    """The `path` of the first `audit.allow` entry that waives `risk` at `rel`, or None."""
    for item in config["allow"]:
        if item["risk"] == risk and fnmatch.fnmatchcase(rel, item["path"]):
            return item["path"]
    return None


def resolve_staged(scan_root: Path, target: str, source: Path) -> Path | None:
    target = target.strip().replace("\\", "/")
    if not target or target.startswith("#") or is_external_url(target):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0].lstrip("/")
    candidates = [scan_root / target, source.parent / target]
    if not Path(target).suffix:
        candidates += [scan_root / f"{target}.md", source.parent / f"{target}.md"]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def resolve_static(scan_root: Path, target: str, source: Path) -> Path | None:
    target = html.unescape(target).strip().replace("\\", "/")
    if not target or target.startswith("#") or is_external_url(target):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None
    candidate = (scan_root / target.lstrip("/")) if target.startswith("/") else (source.parent / target)
    if candidate.exists():
        return candidate.resolve()
    if not candidate.suffix:
        for page in (candidate / "index.html", candidate.with_suffix(".html")):
            if page.exists():
                return page.resolve()
    return None


def luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def has_payment_card_number(text: str, known_patterns: list[str]) -> bool:
    for match in re.finditer(r"\b(?:\d[ -]*?){13,19}\b", text):
        digits = re.sub(r"\D", "", match.group(0))
        if not (13 <= len(digits) <= 19 and luhn_ok(digits)):
            continue
        start, end = max(0, match.start() - 160), min(len(text), match.end() + 160)
        context = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text[start:end])))
        raw_context = html.unescape(text[start:end])
        if any(re.search(p.replace("{digits}", re.escape(digits)), raw_context, re.I) or re.search(p.replace("{digits}", re.escape(digits)), context, re.I) for p in known_patterns):
            continue
        return True
    return False


def is_source_description(entry: str) -> bool:
    """True for a `sources:` entry that names an origin in words, not a path."""
    return bool(re.search(r"\s", entry)) and "/" not in entry and "\\" not in entry


def audit_location(rel: str, include_asset_folders: bool) -> list[Finding]:
    """Findings for a content-mode path that sits in an authoring root or an asset folder."""
    parts = rel.split("/")
    folder = parts[0] if parts[0] in BLOCKED_ROOTS and len(parts) > 1 else ""
    if not folder and not include_asset_folders:
        for index, part in enumerate(parts[:-1]):
            if part.casefold() in ASSET_FOLDERS:
                folder = "/".join(parts[: index + 1])
                break
    if not folder:
        return []
    return [Finding("BLOCKER", "authoring root staged", f"remove {folder}/ from the published output")]


def audit_markdown(path: Path, text: str, audit: Audit) -> list[Finding]:
    """Findings for the sources and links of one staged page."""
    scan_root, stats, hosts = audit.scan_root, audit.stats, audit.external_hosts
    findings: list[Finding] = []
    for entry in frontmatter_sources(text):
        if is_external_url(entry):
            hosts[urlparse(entry).netloc.lower()] += 1
            stats["external_frontmatter_sources"] += 1
        elif is_source_description(entry):
            continue
        else:
            stats["frontmatter_sources"] += 1
            if resolve_staged(scan_root, entry, path) is None:
                findings.append(Finding("BLOCKER", "unresolved-frontmatter-source", f"the cited source is not in the staged tree: {entry}"))
    prose = mask_code(text)
    for match in WIKI_RE.finditer(prose):
        target = wikilink_target_body(text[match.start(2):match.end(2)])
        if resolve_staged(scan_root, target, path) is None:
            if target.startswith(("chapters/", "sources/", "inbox/")):
                findings.append(Finding("WARNING", "unresolved-wikilink", f"review whether the target should be staged or the link updated: {target}"))
            continue
        stats["internal_wikilinks"] += 1
    for match in MD_LINK_RE.finditer(prose):
        raw = text[match.start(2):match.end(2)].strip()
        if is_external_url(raw):
            hosts[urlparse(raw.lstrip("<").split()[0].rstrip(">")).netloc.lower()] += 1
            continue
        target = markdown_link_path(raw)
        if target and Path(target).suffix.lower() in ASSET_EXTS:
            if resolve_staged(scan_root, target, path) is None:
                findings.append(Finding("WARNING", "unresolved-asset-reference", f"review whether the asset should be staged or the link updated: {target}"))
            else:
                stats["asset_links"] += 1
    body = FRONTMATTER_RE.sub("", text, count=1)
    for match in SOURCE_PATH_RE.finditer(MD_LINK_RE.sub("", body)):
        target = match.group("target").rstrip(".,;:")
        if Path(target.split("#", 1)[0].split("?", 1)[0]).suffix.lower() in ASSET_EXTS:
            findings.append(Finding("WARNING", "unlinked-source-asset-path", f"turn this path into a Markdown link so the build can check it: {target}"))
    return findings


def audit_html(path: Path, text: str, audit: Audit) -> list[Finding]:
    """Findings for the asset references in one generated page."""
    findings: list[Finding] = []
    for match in HTML_REF_RE.finditer(text):
        target = match.group(1)
        if is_external_url(target):
            continue
        if Path(target.split("#", 1)[0].split("?", 1)[0]).suffix.lower() not in ASSET_EXTS:
            continue
        if resolve_static(audit.scan_root, target, path) is None:
            findings.append(Finding("BLOCKER", "broken-static-asset-reference", f"fix the published asset link: {target}"))
        else:
            audit.stats["static_asset_links"] += 1
    return findings


def audit_file(path: Path, rel: str, audit: Audit) -> list[Finding]:
    """Every finding for one file under the scan root."""
    suffix = path.suffix.lower()
    findings: list[Finding] = []
    if audit.mode == "content":
        findings += audit_location(rel, audit.config["include_asset_folders"])
    if suffix in ASSET_WARNING_TYPES:
        if IDENTITY_ASSET_RE.search(rel):
            findings.append(Finding("BLOCKER", "identity, payment, or credential asset", "move this asset outside the publish boundary"))
        else:
            findings.append(Finding("WARNING", ASSET_WARNING_TYPES[suffix], "publishable only behind access control; confirm it holds no permanent secret"))
    if suffix not in TEXT_EXTS:
        return findings
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings + [Finding("BLOCKER", "unreadable file", "inspect file permissions before publishing")]
    if has_payment_card_number(text, audit.config["known_identifier_patterns"]):
        findings.append(Finding("BLOCKER", "possible full payment card number", "remove full card numbers before publishing"))
    for name, pattern in BLOCKER_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("BLOCKER", name, "move severe identity, payment, credential, or permanent-secret material outside the publish boundary"))
    for name, pattern in audit.config["warning_patterns"]:
        if pattern.search(text):
            findings.append(Finding("WARNING", name, "private operational detail; publishable only behind access control"))
    if audit.mode == "static-output" and suffix in {".html", ".htm"}:
        findings += audit_html(path, text, audit)
    if audit.mode == "content" and suffix == ".md":
        findings += audit_markdown(path, text, audit)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit staged or built publishing output")
    add_grimoire_arg(parser)
    parser.add_argument("--target", help="Directory to audit (default: the configured content_dir)")
    parser.add_argument("--mode", choices=["content", "static-output"], default="content")
    parser.add_argument("--verbose-warnings", action="store_true", help="Print every routine warning")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    root = resolve_grimoire_arg(args.grimoire)
    try:
        config = load_audit_config(root)
    except ValueError as exc:
        reporter = DiagnosticReporter("audit_publish", root)
        if human:
            print(str(exc), file=sys.stderr)
        else:
            reporter.error("PUBLISH_CONFIG_INVALID", str(exc), path="publish/publish.json")
            reporter.emit(args.format)
        return 2
    scan_root = Path(args.target).expanduser().resolve() if args.target else (root / config["content_dir"]).resolve()
    reporter = DiagnosticReporter("audit_publish", scan_root)
    if not scan_root.exists():
        if human:
            print(f"Audit target does not exist: {scan_root}", file=sys.stderr)
        else:
            reporter.error("PUBLISH_TARGET_MISSING", f"audit target does not exist: {scan_root}")
            reporter.emit(args.format)
        return 2

    audit = Audit(scan_root, args.mode, config, Counter(), Counter())
    findings: list[tuple[str, str, str, str, bool]] = []  # severity, path, risk, action, waived
    files = sorted(p for p in scan_root.rglob("*") if p.is_file())
    for path in files:
        try:
            rel = path.resolve().relative_to(scan_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        for finding in audit_file(path, rel, audit):
            severity, action, waived = finding.severity, finding.action, False
            pattern = waiver(config, finding.risk, rel) if severity == "BLOCKER" else None
            if pattern is not None:
                severity, waived = "WARNING", True
                action = f"waived by audit.allow ({finding.risk} at {pattern}); {action}"
            findings.append((severity, rel, finding.risk, action, waived))
            if severity == "BLOCKER":
                reporter.error("PUBLISH_BLOCKER", f"{finding.risk}: {action}", path=rel)
            else:
                reporter.warning("PUBLISH_WARNING", f"{finding.risk}: {action}", path=rel)

    stats, external_hosts = audit.stats, audit.external_hosts
    counts = Counter(severity for severity, *_ in findings)
    if not human:
        reporter.emit(args.format, checked={"files": len(files), "mode": args.mode, **stats})
        return 1 if counts["BLOCKER"] else 0

    print("Grimoire publish audit")
    print(f"Target: {scan_root}")
    print(f"Mode: {args.mode}")
    for key, value in sorted(stats.items()):
        print(f"{key.replace('_', ' ').capitalize()}: {value}")
    if external_hosts:
        print("External URL domains: " + ", ".join(f"{h}={c}" for h, c in sorted(external_hosts.items()) if h))
    print(f"Findings: BLOCKER={counts['BLOCKER']}, WARNING={counts['WARNING']}")
    if findings:
        print()
        for risk, count in sorted(Counter(f[2] for f in findings).items()):
            print(f"- {risk}: {count}")
        print()
        shown = [f for f in findings if f[0] == "BLOCKER" or f[4] or args.verbose_warnings or f[2] in DETAILED_WARNINGS]
        for severity, rel, risk, action, _waived in shown:
            print(f"{severity}: {risk}\nFile: {rel}\nAction: {action}\n")
        suppressed = len(findings) - len(shown)
        if suppressed:
            print(f"Suppressed {suppressed} routine warning detail line(s); pass --verbose-warnings to print them.\n")
    if counts["BLOCKER"]:
        print(f"Audit failed with {counts['BLOCKER']} blocker finding(s).", file=sys.stderr)
        return 1
    print("Audit passed with warnings; keep access control in front of the site." if counts["WARNING"] else "Audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
