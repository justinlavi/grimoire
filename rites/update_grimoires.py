#!/usr/bin/env python3
"""Bring every grimoire in the library current, then heal only the current ones.

This is the network- and branch-aware half of `/grm-update`. `summon_state.py`
stays offline; this module owns the fetch, the pull and the gated heal, and
`summon.py --update [--apply]` composes it.

Per grimoire it runs a read-only classification ladder, fast-forwards a clean
branch that is behind its upstream, and heals only a grimoire confirmed current
(`CURRENT_STATUSES`). A grimoire that could not be brought current (dirty,
diverged, detached, no upstream, a pull that failed on a private host's auth) is
reported and left untouched: healing a stale tree re-derives work that already
exists upstream and causes divergence. A grimoire kept on this computer only (a
plain folder, or a git repository with no remote) has nothing to pull; its
status is `local_only` and it is healed like any other current grimoire.

Each grimoire is pulled from whatever remote it tracks, public or private; a
private host (a self-hosted GitLab, say) needs a token. A fetch or pull failure
never aborts the run: it is classified (auth_failed / offline / fetch_error),
collected into `needs_manual_pull`, and the run continues.

Mutation profile: plan_apply, default plan. A plan run fetches (which updates
remote-tracking refs only) and classifies; it pulls and heals nothing. `--apply`
fast-forwards each behind grimoire and heals each current one: it re-syncs the
managed scaffold, seeds absent seeded files, moves cited root `sources/` files
into the chapter that cites them, refreshes the README update block, and runs
`repair_links.py --apply`.

A grimoire registered for reading on this computer (`"access": "read"` in the
library) is classified and fast-forwarded like any other, and never healed or
re-validated: its managed files come from the shared copy. Its record carries
`access: "read"` and a heal of `not_applicable`.

Usage:
    python rites/update_grimoires.py [--home DIR] [--framework-root DIR] [--apply]
                                [--format human|json|jsonl]

Exit codes: 0 = no grimoire needs a manual pull and no heal failed, 1 = a
grimoire needs a manual pull or a heal reported an error, 2 = argparse invalid
arguments.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import summon_core
from diagnostics import ResultReporter, add_output_format_arg
from _lib import (
    frontmatter_bounds,
    frontmatter_sources,
    is_usable_local_path,
    read_library,
    read_utf8,
    resolve_local_path,
    write_utf8,
)
from scaffold_contract import file_entries, load_scaffold_contract, managed_scaffold_files

# The statuses that mean nothing newer than the local copy exists anywhere: the
# grimoire is confirmed current with its upstream, or it has no shared copy. Only
# such a grimoire is healed; every other status is reported and left untouched.
CURRENT_STATUSES = frozenset({"up_to_date", "fast_forwarded", "ahead", "local_only"})

LOCAL_ONLY_REASON = "kept on this computer only; there is nothing to pull"

READ_ONLY_HEAL_REASON = "read-only copy; its managed files come from the shared copy"
READ_ONLY_DIRTY_REASON = (
    "local changes in a read-only copy; switch it to editing and save them, or discard them, then update"
)

# Statuses that need the user to pull by hand (private-host auth, offline, etc.).
NEEDS_MANUAL_PULL = frozenset({"auth_failed", "offline", "fetch_error", "behind_blocked", "diverged"})

# README update-block markers.
UPDATE_BEGIN = "<!-- BEGIN GRIMOIRE UPDATE -->"
UPDATE_END = "<!-- END GRIMOIRE UPDATE -->"
ROOT_SOURCE_SCAFFOLD_FILES = {"README.md", ".gitkeep"}

_AUTH_MARKERS = (
    "403", "insufficient_scope", "authentication failed", "could not read username",
    "permission denied", "fatal: authentication", "access denied", "401",
)
_OFFLINE_MARKERS = (
    "could not resolve host", "connection timed out", "timed out", "network is unreachable",
    "could not connect", "ssl", "unable to access",
)


# ---------------------------------------------------------------------------
# Classification ladder (read-only)
# ---------------------------------------------------------------------------


def _host(online_path: str | None) -> str:
    if not online_path:
        return ""
    return urlparse(online_path).hostname or ""


def classify_fetch_error(stderr: str) -> str:
    """Map a failed fetch's stderr to auth_failed / offline / fetch_error."""
    low = (stderr or "").lower()
    if any(m in low for m in _AUTH_MARKERS):
        return "auth_failed"
    if any(m in low for m in _OFFLINE_MARKERS):
        return "offline"
    return "fetch_error"


def _parse_ahead_behind(out: str) -> tuple[int, int] | None:
    """`rev-list --left-right --count @{u}...HEAD` -> (behind, ahead), or None for other output."""
    parts = out.split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def classify_grimoire(
    local_path: Path,
    *,
    fetch: bool,
    git: Callable = summon_core.git_capture,
    credential_probe: Callable = summon_core.git_credential_token,
    host: str = "",
) -> dict[str, Any]:
    """Read-only ladder: resolve repo state and (optionally) fetch to learn currency.

    Never pulls or heals. Returns a partial grimoire record with `status`,
    `branch`, `upstream`, `ahead`, `behind`, and `creds_present`/`reason` when
    relevant. `fetch=False` keeps it fully offline (the `--check` snapshot).
    """
    rec: dict[str, Any] = {
        "branch": None, "upstream": None, "ahead": 0, "behind": 0,
        "status": None, "reason": None, "creds_present": None,
    }
    g = str(local_path)

    if not local_path.is_dir():
        rec["status"] = "missing_local"
        rec["reason"] = "no directory at local_path (clone it via the summon rite)"
        return rec
    if not (local_path / ".git").exists():
        if host:
            rec["status"] = "not_a_repo"
            rec["reason"] = "the library records a shared copy, and the directory is not a git repository"
        else:
            rec["status"] = "local_only"
            rec["reason"] = LOCAL_ONLY_REASON
        return rec

    rc, branch, _ = git("-C", g, "symbolic-ref", "--quiet", "--short", "HEAD")
    if rc != 0 or not branch:
        rec["status"] = "detached"
        rec["reason"] = "detached HEAD; check out a branch first"
        return rec
    rec["branch"] = branch

    rc, upstream, _ = git("-C", g, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if rc != 0 or not upstream:
        rc, remotes, _ = git("-C", g, "remote")
        if rc == 0 and not remotes.strip():
            rec["status"] = "local_only"
            rec["reason"] = LOCAL_ONLY_REASON
            return rec
        rec["status"] = "no_upstream"
        rec["reason"] = f"branch '{branch}' has no upstream; git branch --set-upstream-to"
        return rec
    rec["upstream"] = upstream
    remote = upstream.split("/", 1)[0]

    rc, dirty, _ = git("-C", g, "status", "--porcelain")
    if rc == 0 and dirty.strip():
        rec["status"] = "dirty"
        rec["reason"] = "uncommitted changes; commit/stash/discard before updating (never auto-discarded)"
        return rec

    if fetch:
        rc, _, err = git("-C", g, "fetch", "--prune", remote)
        if rc != 0:
            rec["status"] = classify_fetch_error(err)
            rec["reason"] = (err or "fetch failed").splitlines()[0][:200] if err else "fetch failed"
            if rec["status"] == "auth_failed" and host:
                rec["creds_present"] = bool(credential_probe(host))
            return rec

    rc, ab, err = git("-C", g, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    counts = _parse_ahead_behind(ab) if rc == 0 else None
    if counts is None:
        rec["status"] = "compare_failed"
        rec["reason"] = ((err or "").strip().splitlines() or ["could not compare with the upstream"])[0][:200]
        return rec
    behind, ahead = counts
    rec["behind"], rec["ahead"] = behind, ahead
    if behind == 0 and ahead == 0:
        rec["status"] = "up_to_date"
    elif behind > 0 and ahead == 0:
        rec["status"] = "behind"  # fast-forwardable; bring_current resolves it
    elif ahead > 0 and behind == 0:
        rec["status"] = "ahead"
        rec["reason"] = f"{ahead} local commit(s) not pushed"
    else:
        rec["status"] = "diverged"
        rec["reason"] = f"{ahead} ahead / {behind} behind; reconcile by hand (rebase/merge)"
    return rec


def bring_current(local_path: Path, rec: dict[str, Any], *, git: Callable = summon_core.git_capture) -> None:
    """Fast-forward a clean, behind branch. Mutates `rec` in place."""
    if rec["status"] != "behind":
        return
    rc, _, err = git("-C", str(local_path), "pull", "--ff-only")
    if rc == 0:
        rec["status"] = "fast_forwarded"
        rec["behind"] = 0
    else:
        rec["status"] = "behind_blocked"
        rec["reason"] = (err or "fast-forward refused").splitlines()[0][:200] if err else "fast-forward refused"


# ---------------------------------------------------------------------------
# Heal (only ever called for a heal-eligible, confirmed-current grimoire)
# ---------------------------------------------------------------------------


def _formula_update_block(framework_root: Path) -> str | None:
    """Extract the marked update block from the grimoire formula README."""
    path = framework_root / "formulae" / "grimoire" / "README.md"
    try:
        text = read_utf8(path)
    except (OSError, UnicodeDecodeError):
        return None
    start = text.find(UPDATE_BEGIN)
    end = text.find(UPDATE_END)
    if start == -1 or end == -1:
        return None
    return text[start:end + len(UPDATE_END)]


def _replace_readme_block(text: str, block: str) -> str:
    """Return README text with the update block present exactly once.

    Replaces the marked block in place when present; otherwise inserts it before
    the first second-level heading (or appends). Idempotent.
    """
    s = text.find(UPDATE_BEGIN)
    e = text.find(UPDATE_END)
    if s != -1 and e != -1 and e > s:
        return text[:s] + block + text[e + len(UPDATE_END):]

    first = text.find("\n## ")
    if first != -1:
        return text[:first + 1] + block + "\n\n" + text[first + 1:]
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + block + "\n"


def inject_update_readme_block(readme_path: Path, block: str) -> bool:
    """Idempotently ensure the grimoire README carries the current update block.

    Returns True if the file changed. Raises `OSError` for a README that cannot
    be read or written and `UnicodeDecodeError` for one that is not UTF-8.
    """
    text = read_utf8(readme_path)
    new = _replace_readme_block(text, block)
    if new != text:
        write_utf8(readme_path, new)
        return True
    return False


_KEY_LINE_RE = re.compile(r"^[A-Za-z_][\w-]*\s*:")


def _citation_index(local_path: Path) -> tuple[dict[str, list[Path]], list[str]]:
    """Index the chapter pages' `sources:` entries as {entry: [citing pages]}.

    The second value holds the text of every chapter page that is not UTF-8: such
    a page cannot be read or rewritten, so a source it may cite stays in place.
    """
    index: dict[str, list[Path]] = {}
    undecodable: list[str] = []
    chapters = local_path / "chapters"
    if not chapters.is_dir():
        return index, undecodable
    for page in sorted(chapters.rglob("*.md")):
        if not page.is_file() or "sources" in page.relative_to(local_path).parts:
            continue
        try:
            text = read_utf8(page)
        except UnicodeDecodeError:
            try:
                undecodable.append(page.read_bytes().decode("latin-1"))
            except OSError:
                pass
            continue
        except OSError:
            continue
        for entry in set(frontmatter_sources(text)):
            index.setdefault(entry, []).append(page)
    return index, undecodable


def _rewrite_citation(text: str, old_ref: str, new_ref: str) -> str:
    """Return `text` with `old_ref` replaced by `new_ref` where it is an entry of `sources:`.

    Only the `sources:` field of the frontmatter changes, and only an entry that
    is exactly `old_ref`: `chapters/y/sources/a.pdf` keeps its text when
    `sources/a.pdf` moves.
    """
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return text
    entry = re.compile(r"(?<![^\s\"'\[,])" + re.escape(old_ref) + r"(?![^\s\"'\],])")
    lines = text[bounds[0]:bounds[1]].split("\n")
    in_sources = False
    for number, line in enumerate(lines):
        if re.match(r"^sources\s*:", line):
            in_sources = True
        elif _KEY_LINE_RE.match(line):
            in_sources = False
        if in_sources:
            lines[number] = entry.sub(lambda _match: new_ref, line)
    return text[:bounds[0]] + "\n".join(lines) + text[bounds[1]:]


def relocate_root_sources(local_path: Path) -> dict[str, Any]:
    """Move cited root source artifacts into the chapter package that cites them.

    The move is intentionally conservative: a source is relocated only when at
    least one authored chapter page cites it and all citing pages live in the
    same folder. Ambiguous or uncited artifacts stay in place for validation and
    human review.
    """
    sources = local_path / "sources"
    if not sources.exists():
        return {"status": "absent", "moved": [], "left_for_review": []}
    if not sources.is_dir():
        return {"status": "left_for_review", "moved": [], "left_for_review": ["sources"]}

    citations, undecodable = _citation_index(local_path)
    moved: list[dict[str, str]] = []
    left_for_review: list[str] = []

    for source_file in sorted(p for p in sources.rglob("*") if p.is_file()):
        source_rel_under_root = source_file.relative_to(sources).as_posix()
        if source_rel_under_root in ROOT_SOURCE_SCAFFOLD_FILES:
            continue

        old_ref = f"sources/{source_rel_under_root}"
        citing_pages = citations.get(old_ref, [])
        citing_dirs = {p.parent for p in citing_pages}
        if len(citing_dirs) != 1 or any(old_ref in text for text in undecodable):
            left_for_review.append(old_ref)
            continue

        destination_dir = next(iter(citing_dirs)) / "sources"
        destination = destination_dir / source_rel_under_root
        if destination.exists():
            left_for_review.append(old_ref)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_file), str(destination))
        new_ref = destination.relative_to(local_path).as_posix()

        for page in citing_pages:
            write_utf8(page, _rewrite_citation(read_utf8(page), old_ref, new_ref))

        moved.append({"from": old_ref, "to": new_ref})

    for scaffold_name in ROOT_SOURCE_SCAFFOLD_FILES:
        scaffold_file = sources / scaffold_name
        if scaffold_file.is_file():
            scaffold_file.unlink()

    for directory in sorted((p for p in sources.rglob("*") if p.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass

    try:
        sources.rmdir()
        status = "removed"
    except OSError:
        status = "left_for_review" if left_for_review else "partially_relocated"

    return {"status": status, "moved": moved, "left_for_review": left_for_review}


def default_heal(local_path: Path, framework_root: Path) -> dict[str, Any]:
    """Mechanical, idempotent grimoire heal: managed scaffold, README block, links.

    Only called for a confirmed-current grimoire. Re-sync the framework-owned managed
    scaffold (never the customized README/hub/manifest/log), refresh the README
    update block, then promote wikilinks. Re-validation is left to the caller.
    """
    result: dict[str, Any] = {
        "scaffold_synced": [],
        "root_sources": "unchanged",
        "readme_block": "unchanged",
        "status": "ok",
        "messages": [],
    }

    # 1. Managed scaffold: copy framework formula over the grimoire's copy (safe -
    #    managed_scaffold_files excludes README/hub/grimoire.json).
    try:
        contract = load_scaffold_contract(framework_root)
        formula_dir = framework_root / "formulae" / "grimoire"
        for rel in managed_scaffold_files(contract):
            src = formula_dir / rel
            dst = local_path / rel
            if not src.is_file():
                continue
            if (not dst.exists()) or dst.read_bytes() != src.read_bytes():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                result["scaffold_synced"].append(rel)
        # Seeded files are copied in only when absent; a grimoire that has
        # customised its copy keeps it.
        for entry in file_entries(contract):
            if not entry.get("seed_if_absent") or entry.get("managed"):
                continue
            src = formula_dir / entry["source"]
            dst = local_path / entry["target"]
            if src.is_file() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                result["scaffold_synced"].append(entry["target"])
    except Exception as exc:  # contract load / IO
        result["status"] = "error"
        result["messages"].append(f"scaffold sync failed: {exc}")

    # 2. Relocate root source artifacts only when citations identify one clear
    #    chapter package; leave ambiguous artifacts for validation and review.
    try:
        result["root_sources"] = relocate_root_sources(local_path)
    except OSError as exc:
        result["status"] = "error"
        result["messages"].append(f"root sources relocation failed: {exc}")

    # 3. Ensure the README carries the current update block from the formula.
    block = _formula_update_block(framework_root)
    readme = local_path / "README.md"
    if block and readme.is_file():
        try:
            if inject_update_readme_block(readme, block):
                result["readme_block"] = "updated"
        except (OSError, UnicodeDecodeError) as exc:
            result["status"] = "error"
            result["messages"].append(f"README block injection failed: {exc}")

    # 4. Promote/repair wikilinks a structural change may have broken.
    repair = _run_repair_links(framework_root, local_path)
    if repair.get("status") == "error":
        result["status"] = "error"
        result["messages"].append(repair.get("message", "repair_links failed"))

    return result


def _run_repair_links(framework_root: Path, local_path: Path) -> dict[str, Any]:
    """Run repair_links.py --apply against a grimoire; report a small result."""
    script = framework_root / "rites" / "repair_links.py"
    if not script.is_file():
        return {"status": "skipped", "message": "repair_links.py not found"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--grimoire", str(local_path), "--apply"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=summon_core.GIT_TIMEOUT,
        )
    except Exception as exc:
        return {"status": "error", "message": f"repair_links failed: {exc}"}
    return {"status": "ok" if proc.returncode == 0 else "error",
            "message": (proc.stderr or proc.stdout or "").strip()[-200:] if proc.returncode else ""}


def revalidate(framework_root: Path, local_path: Path) -> tuple[bool, str]:
    """Re-run grimoire validation; return (ok, short detail)."""
    script = framework_root / "rites" / "validate.py"
    if not script.is_file():
        return False, "validate.py not found"
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--grimoire", str(local_path), "--summary"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=summon_core.GIT_TIMEOUT,
        )
    except Exception as exc:
        return False, f"validate failed: {exc}"
    return proc.returncode == 0, (proc.stdout or "")[-300:]


# ---------------------------------------------------------------------------
# Per-grimoire + library orchestration
# ---------------------------------------------------------------------------

# Heal statuses that mean the managed files were brought current.
HEALED_STATUSES = frozenset({"ok", "needs_check"})


def heal_wrote(record: dict[str, Any]) -> bool:
    """True when the heal of this grimoire record changed a file."""
    heal = record.get("heal") or {}
    if heal.get("status") == "not_applicable":
        return False
    return bool(heal.get("scaffold_synced") or heal.get("readme_block") == "updated")


def heal_finding(record: dict[str, Any]) -> tuple[str, str] | None:
    """Return `(severity, text)` for a heal that needs the user's attention, else None.

    `needs_check` is a warning: the managed files are current and the grimoire's
    own content fails validation, which `/grm-check` owns. `error` is a heal
    step that failed.
    """
    heal = record.get("heal") or {}
    key = record["key"]
    if heal.get("status") == "not_applicable":
        return None
    if heal.get("status") == "needs_check":
        return ("warning", f"grimoire {key}: its managed files are current, and its content does not "
                           "pass validation; run /grm-check in it")
    if heal.get("status") == "error":
        detail = "; ".join(str(m) for m in heal.get("messages", []) if m)
        return ("error", f"grimoire {key}: heal failed" + (f": {detail}" if detail else ""))
    return None


def needs_attention(result: dict[str, Any] | None) -> bool:
    """True when any grimoire's heal failed or left content that fails validation."""
    if not result:
        return False
    return any(heal_finding(r) is not None for r in result["grimoires"])


def process_grimoire(
    key: str,
    entry: dict[str, Any],
    framework_root: Path,
    *,
    apply: bool,
    fetch: bool = True,
    git: Callable = summon_core.git_capture,
    heal_fn: Callable = default_heal,
    revalidate_fn: Callable = revalidate,
) -> dict[str, Any]:
    """Classify, (apply) fast-forward, then (apply + eligible) heal one grimoire.

    `fetch=False` keeps it fully offline (the read-only `--check` snapshot):
    currency is read from already-fetched refs and nothing is pulled or healed.
    """
    entry = entry if isinstance(entry, dict) else {}
    raw = entry.get("local_path", "")
    online = entry.get("online_path")
    usable = is_usable_local_path(raw)
    local_path = resolve_local_path(raw, resolve=True) if usable else Path(str(raw or ""))
    host = _host(online)

    rec: dict[str, Any] = {
        "key": key,
        "local_path": str(local_path),
        "host": host,
        "online_path": online,
        "access": "read" if entry.get("access") == "read" else "edit",
        "pulled": False,
        "heal_eligible": False,
        "heal": None,
    }
    if usable:
        rec.update(classify_grimoire(local_path, fetch=fetch, git=git, host=host))
    else:
        rec.update(
            status="missing_local", branch=None, upstream=None, ahead=0, behind=0, creds_present=None,
            reason="the library entry's local_path is empty or relative (set it to the grimoire's folder)",
        )

    if apply and rec["status"] == "behind":
        bring_current(local_path, rec, git=git)
        rec["pulled"] = rec["status"] == "fast_forwarded"

    if rec["access"] == "read":
        # A read-only copy takes its managed files from the shared copy; nothing local is rewritten.
        if rec["status"] == "dirty":
            rec["reason"] = READ_ONLY_DIRTY_REASON
        rec["heal_eligible"] = False
        rec["heal"] = {"status": "not_applicable", "reason": READ_ONLY_HEAL_REASON}
        rec["suggested_command"] = (
            f"git -C {local_path} pull --ff-only" if rec["status"] in NEEDS_MANUAL_PULL else None
        )
        return rec

    rec["heal_eligible"] = rec["status"] in CURRENT_STATUSES
    if rec["heal_eligible"]:
        rec["suggested_command"] = None
        if apply:
            heal = heal_fn(local_path, framework_root)
            ok, detail = revalidate_fn(framework_root, local_path)
            heal["validate"] = "ok" if ok else "fail"
            if not ok:
                if heal.get("status") == "ok":
                    heal["status"] = "needs_check"
                heal.setdefault("messages", []).append(detail.strip()[-200:])
            rec["heal"] = heal
        else:
            rec["heal"] = {"status": "planned"}
    else:
        rec["heal"] = {"status": "skipped", "reason": rec.get("reason")}
        if rec["status"] in NEEDS_MANUAL_PULL:
            rec["suggested_command"] = f"git -C {local_path} pull --ff-only"

    return rec


def process_all(
    home: Path,
    framework_root: Path,
    *,
    apply: bool,
    fetch: bool = True,
    library: dict[str, Any] | None = None,
    git: Callable = summon_core.git_capture,
    heal_fn: Callable = default_heal,
    revalidate_fn: Callable = revalidate,
) -> dict[str, Any]:
    """Process every grimoire in the library; return the structured result block.

    `fetch=False` produces an offline currency snapshot (no network, no writes);
    `apply=True` fast-forwards and heals the grimoires confirmed current.
    """
    home = Path(home)
    framework_root = Path(framework_root)
    warnings: list[str] = []
    if library is None:
        library, reason = read_library(home / "library.json")
        if library is None:
            warnings.append(f"could not read library: {reason} (treating as empty)")
            library = {"grimoires": {}}
    grimoires_map = library.get("grimoires", {})

    results: list[dict[str, Any]] = []
    for key in sorted(grimoires_map):
        results.append(process_grimoire(
            key, grimoires_map[key], framework_root,
            apply=apply, fetch=fetch, git=git, heal_fn=heal_fn, revalidate_fn=revalidate_fn,
        ))

    needs_manual = [
        {"key": r["key"], "host": r["host"], "online_path": r["online_path"],
         "status": r["status"], "creds_present": r.get("creds_present"),
         "suggested_command": r.get("suggested_command")}
        for r in results if r["status"] in NEEDS_MANUAL_PULL
    ]
    summary = {
        "total": len(results),
        "already_current": sum(1 for r in results if r["status"] == "up_to_date"),
        "brought_current": sum(1 for r in results if r["status"] == "fast_forwarded"),
        "ahead": sum(1 for r in results if r["status"] == "ahead"),
        "local_only": sum(1 for r in results if r["status"] == "local_only"),
        "healed": sum(1 for r in results if (r.get("heal") or {}).get("status") in HEALED_STATUSES),
        "needs_check": sum(1 for r in results if (r.get("heal") or {}).get("status") == "needs_check"),
        "heal_skipped": sum(1 for r in results if r["access"] != "read" and not r["heal_eligible"]),
        "read_only": sum(1 for r in results if r["access"] == "read"),
        "needs_manual_pull": len(needs_manual),
    }
    return {"grimoires": results, "needs_manual_pull": needs_manual, "summary": summary, "warnings": warnings}


# ---------------------------------------------------------------------------
# CLI (also reachable as `summon.py --update`; see summon_state.run_state_command)
# ---------------------------------------------------------------------------


def _build_reporter(home: Path, result: dict[str, Any], *, apply: bool) -> ResultReporter:
    reporter = ResultReporter("update_grimoires", root=home, mode="apply" if apply else "plan")
    for text in result.get("warnings", []):
        reporter.message("warning", text)
    for r in result["grimoires"]:
        if r["status"] in NEEDS_MANUAL_PULL:
            reporter.message("warning", f"{r['key']}: {r['status']} - {r.get('reason') or 'pull manually'}",
                             path=r["local_path"])
        if r["pulled"]:
            reporter.mutation("pull", path=r["local_path"], detail="fast-forwarded to upstream")
        if heal_wrote(r):
            reporter.mutation("heal", path=r["local_path"], detail="re-synced managed scaffold / README block")
        finding = heal_finding(r)
        if finding:
            reporter.message(finding[0], finding[1], path=r["local_path"])
    return reporter


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull and heal every grimoire in the library")
    parser.add_argument("--home", default=None, help="Grimoires home (default: ~/grimoires)")
    parser.add_argument("--framework-root", default=None, help="Framework root (default: detected)")
    parser.add_argument("--apply", action="store_true", help="Pull and heal (default: plan only)")
    add_output_format_arg(parser)
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve() if args.home else summon_core.GRIMOIRES_HOME
    framework_root = Path(args.framework_root).expanduser().resolve() if args.framework_root else summon_core.REPO_ROOT

    result = process_all(home, framework_root, apply=args.apply)
    reporter = _build_reporter(home, result, apply=args.apply)
    summary = {**result["summary"], "grimoires": result["grimoires"],
               "needs_manual_pull": result["needs_manual_pull"], "applied": args.apply}

    if args.format == "human":
        _print_human(result, apply=args.apply)
    else:
        reporter.emit(args.format, summary=summary)

    return 1 if result["needs_manual_pull"] or needs_attention(result) else 0


def _print_human(result: dict[str, Any], *, apply: bool) -> None:
    s = result["summary"]
    print()
    print("  Grimoire update " + ("(apply)" if apply else "(plan)"))
    for text in result.get("warnings", []):
        print(f"  [WARN]  {text}")
    for r in result["grimoires"]:
        mark = "OK " if r["status"] in CURRENT_STATUSES else "!! "
        line = f"  [{mark}] {r['key']}: {r['status']}"
        if r.get("access") == "read":
            line += " (read-only)"
        if r["behind"] or r["ahead"]:
            line += f" (behind {r['behind']}, ahead {r['ahead']})"
        print(line)
        if r.get("suggested_command"):
            print(f"          pull manually: {r['suggested_command']}")
        finding = heal_finding(r)
        if finding:
            print(f"          {finding[1]}")
    print(f"  current={s['already_current'] + s['brought_current'] + s['ahead'] + s['local_only']}/{s['total']}  "
          f"healed={s['healed']}  needs-manual-pull={s['needs_manual_pull']}")
    print()


if __name__ == "__main__":
    sys.exit(main())
