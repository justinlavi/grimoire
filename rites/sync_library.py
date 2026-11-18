#!/usr/bin/env python3
"""Grimoire Library Sync - scan ~/grimoires/ and reconcile against the library.

Walks the grimoire home directory, identifies every valid grimoire (any
subdirectory containing a well-formed grimoire.json), and compares the result
against the local library at ~/grimoires/library.json.

Reports four kinds of drift:
  * Missing      - grimoire on disk but absent from the library
  * Stale        - library entry whose local_path no longer exists, is empty,
                   or is relative (a relative path names no one folder)
  * Mismatched   - library entry whose local_path differs from where the
                   grimoire actually lives
  * Unmanaged    - directory under ~/grimoires/ with no grimoire.json
                   (cannot be auto-registered; reported for cleanup)

Also surfaces structural issues that don't block sync but warrant attention:
  * Skill prefix collisions across grimoires
  * grimoire.json `name` differing from the directory name

This module owns the one writer of library.json, `update_library`: it reads the
file, builds the new library, and writes only when the file is unchanged since
the read (compare-and-swap), retrying on a conflict. `summon --reconcile` and
the installer write the library through it. A library file that cannot be read
is never overwritten.

Mutation profile: plan_apply. The default reports drift and writes nothing;
`--apply` writes the reconciled library.

Usage:
    python rites/sync_library.py [--apply] [--home PATH] [--format human|json|jsonl]

Exit codes: 0 = report printed, or library written (or already current);
1 = library.json cannot be read, or kept changing during the write;
2 = argparse invalid arguments.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _lib import (
    format_local_path,
    info,
    is_usable_local_path,
    load_manifest,
    ok,
    read_library,
    resolve_local_path,
    warn,
    write_json,
)
from diagnostics import ResultReporter, add_output_format_arg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HOME = Path.home() / "grimoires"
# A folder that holds a framework checkout (it has framework.json) is never a grimoire.
FRAMEWORK_MANIFEST = "framework.json"


# ---------------------------------------------------------------------------
# Disk discovery
# ---------------------------------------------------------------------------


def detect_origin_url(directory):
    """Return the git origin URL for a directory, or '' if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""

    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def scan_grimoire_home(home):
    """Walk home, classify each subdirectory.

    Returns a dict with three lists:
        grimoires:  [{key, path, manifest, online_path}]   - grimoires
        unmanaged:  [path]                                  - dirs without grimoire.json
        warnings:   [str]                                   - non-fatal issues
    """
    grimoires = []
    unmanaged = []
    warnings = []

    try:
        home_is_dir = home.is_dir()
    except OSError as exc:
        return {"grimoires": [], "unmanaged": [], "warnings": [f"{home}: could not access ({exc})"]}
    if not home_is_dir:
        return {"grimoires": [], "unmanaged": [], "warnings": [f"{home} does not exist"]}

    try:
        children = sorted(home.iterdir())
    except OSError as exc:
        return {"grimoires": [], "unmanaged": [], "warnings": [f"{home}: could not list ({exc})"]}

    for child in children:
        # An unstattable child (e.g. a restricted /tmp mount) must not crash the
        # whole scan; skip it with a warning and keep discovering the rest.
        try:
            if not child.is_dir():
                continue
            if (child / FRAMEWORK_MANIFEST).is_file():
                continue
        except OSError as exc:
            warnings.append(f"{child.name}: could not access ({exc}); skipped")
            continue

        manifest, errors = load_manifest(child)
        if manifest is None:
            unmanaged.append(child)
            continue

        if errors:
            for e in errors:
                warnings.append(f"{child.name}: {e}")
            continue

        # Surface name/directory mismatches as warnings (use directory as key).
        if manifest.get("name") != child.name:
            warnings.append(
                f"{child.name}: grimoire.json name='{manifest.get('name')}' "
                f"differs from directory name (library will use directory name)"
            )

        grimoires.append(
            {
                "key": child.name,
                "path": child,
                "manifest": manifest,
                "online_path": detect_origin_url(child),
            }
        )

    # Detect skill_prefix collisions across grimoires.
    seen = {}
    for g in grimoires:
        ns = g["manifest"].get("skill_prefix")
        if ns in seen:
            warnings.append(
                f"skill_prefix collision: '{ns}' used by both "
                f"'{seen[ns]}' and '{g['key']}' - skill registration blocks that prefix "
                "until one grimoire changes it"
            )
        else:
            seen[ns] = g["key"]

    return {"grimoires": grimoires, "unmanaged": unmanaged, "warnings": warnings}


# ---------------------------------------------------------------------------
# Library operations
# ---------------------------------------------------------------------------


def expected_local_path(home, key):
    """Return the `local_path` the library records for the grimoire `key` under `home`."""
    return format_local_path(Path(home) / key)


def _entry_local_path(entry):
    return entry.get("local_path", "") if isinstance(entry, dict) else ""


def _resolves_to_grimoire(raw):
    """True when a library `local_path` names an existing folder that holds a valid grimoire.

    An empty or relative path names no one folder, so it never resolves.
    """
    if not is_usable_local_path(raw):
        return False
    try:
        resolved = resolve_local_path(raw, resolve=True)
        if not resolved.is_dir():
            return False
    except OSError:
        return False
    manifest, errors = load_manifest(resolved)
    return manifest is not None and not errors


def diff_library(scan, library, home):
    """Compute drift between disk state and library.

    Returns a dict of lists:
        missing     - keys on disk but not in library
        stale       - keys in library whose path doesn't exist
        mismatched  - keys whose library local_path differs from disk
        ok          - keys present in both with matching paths
    """
    disk_keys = {g["key"] for g in scan["grimoires"]}
    library_keys = set(library["grimoires"].keys())

    missing = sorted(disk_keys - library_keys)
    stale = []
    mismatched = []
    ok_keys = []

    for key in sorted(library_keys):
        raw = _entry_local_path(library["grimoires"][key])

        if key in disk_keys:
            # Physically present under the active home: never stale. Correct the
            # recorded path when it differs from the canonical form.
            expected = expected_local_path(home, key)
            if raw != expected:
                mismatched.append(
                    {"key": key, "raw_path": raw, "expected_path": expected}
                )
            else:
                ok_keys.append(key)
        elif _resolves_to_grimoire(raw):
            ok_keys.append(key)  # a valid grimoire outside the home
        else:
            stale.append({"key": key, "raw_path": raw})

    return {
        "missing": missing,
        "stale": stale,
        "mismatched": mismatched,
        "ok": ok_keys,
    }


def build_synced_library(scan, library, home):
    """Produce a new library dict reflecting current disk state.

    Preserves any unknown fields on existing entries; updates local_path and
    online_path; drops entries whose paths no longer resolve to valid grimoires;
    sorts entries alphabetically by key.
    """
    new_entries = {}
    disk_index = {g["key"]: g for g in scan["grimoires"]}

    # Carry forward library entries that still resolve to a valid grimoire,
    # whether or not they live under home (allows out-of-home grimoires).
    for key, entry in library["grimoires"].items():
        if key in disk_index:
            continue  # handled below from disk
        if isinstance(entry, dict) and _resolves_to_grimoire(entry.get("local_path", "")):
            new_entries[key] = dict(entry)

    # Add/update entries from disk scan.
    for key in sorted(disk_index):
        g = disk_index[key]
        existing = library["grimoires"].get(key)
        entry = dict(existing) if isinstance(existing, dict) else {}
        entry["local_path"] = expected_local_path(home, key)
        # Prefer existing online_path if present and non-empty; otherwise use
        # the detected git origin (or null).
        if not entry.get("online_path"):
            entry["online_path"] = g["online_path"] or None
        new_entries[key] = entry

    return {**library, "grimoires": dict(sorted(new_entries.items()))}


class LibraryWriteConflict(Exception):
    """Raised when library.json keeps changing under a write, so the result
    can't be written without clobbering a concurrent writer."""


class LibraryUnreadable(Exception):
    """Raised when library.json exists and cannot be used, so a write would
    destroy entries its owner could still recover."""


def render_library_bytes(library):
    """Serialize the library exactly as `write_library` persists it."""
    return (json.dumps(library, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_library(library, library_path):
    """Write the library atomically, with the formatting `render_library_bytes` produces."""
    write_json(library_path, library)


def library_from_bytes(raw):
    """Parse library bytes. Returns `(library, "")`, or `(None, reason)` when they cannot be used.

    Empty bytes are an empty library, and an object without `grimoires` gains an
    empty one. Not UTF-8, not JSON, not an object, or a `grimoires` value that is
    not an object give `(None, reason)`. This is the contract of `_lib.read_library`
    over bytes already read, so the compare-and-swap compares what it parsed.
    """
    if not raw.strip():
        return {"grimoires": {}}, ""
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        return None, f"not UTF-8: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, "must hold a JSON object"
    if "grimoires" not in data:
        data["grimoires"] = {}
    elif not isinstance(data["grimoires"], dict):
        return None, "'grimoires' must be an object"
    return data, ""


def compare_and_swap_write(library_path, expected_bytes, library):
    """Write `library` only if the on-disk file still matches `expected_bytes`.

    Returns True on success, False when the file changed since it was read (a
    concurrent writer won the race) so the caller can re-read and retry instead
    of silently overwriting that writer's changes.
    """
    current = library_path.read_bytes() if library_path.is_file() else b""
    if current != expected_bytes:
        return False
    write_library(library, library_path)
    return True


def update_library(library_path, build, retries=5):
    """Read the library, let `build` change it, and write it under compare-and-swap.

    The one writer of `library.json`. `build(library)` receives the parsed
    library and returns the new one, or None for no change. Each attempt re-reads
    the file and writes only if it is unchanged since that read; a conflict
    re-reads and retries, so a concurrent change is incorporated rather than lost.

    Returns True when a write occurred, False when nothing needed writing.
    Raises `LibraryUnreadable` when the file exists and cannot be used (it is
    left as it is) and `LibraryWriteConflict` when the file keeps changing across
    `retries` attempts.
    """
    library_path = Path(library_path)
    for _ in range(retries):
        try:
            current = library_path.read_bytes() if library_path.is_file() else b""
        except OSError as exc:
            raise LibraryUnreadable(f"{library_path} could not be read: {exc}") from exc
        library, reason = library_from_bytes(current)
        if library is None:
            raise LibraryUnreadable(f"{library_path} is {reason}")
        new_library = build(library)
        if new_library is None or render_library_bytes(new_library) == current:
            return False
        if compare_and_swap_write(library_path, current, new_library):
            return True
    raise LibraryWriteConflict(
        f"{library_path} kept changing during {retries} write attempts; "
        "re-run /grm-update library"
    )


def apply_synced_library(scan, library_path, home, retries=5):
    """Reconcile the library against disk and write it through `update_library`.

    Returns True when a write occurred, False when the library was already in
    sync (possibly reconciled by a concurrent process).
    """
    return update_library(
        library_path, lambda library: build_synced_library(scan, library, home), retries=retries,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(scan, diff, home, library_path, apply_mode, human=True, reporter=None):
    if human:
        print()
        print(f"  Grimoire home:  {home}")
        print(f"  Library file:   {library_path}")
        print(f"  Mode:           {'apply' if apply_mode else 'dry-run (use --apply to write changes)'}")
        print()

    if scan["warnings"]:
        if human:
            print("  Structural warnings:")
        for w in scan["warnings"]:
            if human:
                warn(w)
            if reporter is not None:
                reporter.message("warning", w)
        if human:
            print()

    if scan["unmanaged"]:
        if human:
            print("  Unmanaged directories (no grimoire.json - won't be added):")
        for path in scan["unmanaged"]:
            if human:
                info(f"{path.name}/  -> register with /grm-setup {path.name}, or move it out of {home}")
            if reporter is not None:
                reporter.message(
                    "warning",
                    f"unmanaged: {path.name}/ (no grimoire.json - register with /grm-setup {path.name})",
                    path=path,
                )
        if human:
            print()

    if human:
        print(f"  Found {len(scan['grimoires'])} valid grimoire(s) on disk.")
        print(f"  Library currently lists {len(diff['ok']) + len(diff['mismatched']) + len(diff['stale'])} entry(ies).")
        print()

    drift_count = len(diff["missing"]) + len(diff["stale"]) + len(diff["mismatched"])

    if diff["missing"]:
        if human:
            print("  Missing from library (will be added):")
        for key in diff["missing"]:
            if human:
                ok(f"+ {key}")
            if reporter is not None:
                reporter.message("info", f"missing: {key} (will be added)")
        if human:
            print()

    if diff["stale"]:
        if human:
            print("  Stale library entries (will be removed):")
        for s in diff["stale"]:
            if human:
                warn(f"- {s['key']}  (path no longer resolves: {s['raw_path']})")
            if reporter is not None:
                reporter.message(
                    "warning",
                    f"stale: {s['key']} (path no longer resolves: {s['raw_path']})",
                )
        if human:
            print()

    if diff["mismatched"]:
        if human:
            print("  Mismatched local_path (will be corrected):")
        for m in diff["mismatched"]:
            if human:
                warn(
                    f"~ {m['key']}  current='{m['raw_path']}'  expected='{m['expected_path']}'"
                )
            if reporter is not None:
                reporter.message(
                    "warning",
                    f"mismatched: {m['key']} current='{m['raw_path']}' "
                    f"expected='{m['expected_path']}'",
                )
        if human:
            print()

    if drift_count == 0:
        if human:
            ok("Library is in sync with disk. No changes needed.")
            print()
        return False

    if not apply_mode:
        if human:
            print(f"  {drift_count} drift item(s) detected. Re-run with --apply to write changes.")
            print()
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Grimoire Library Sync")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the reconciled library (default: dry-run / report only)",
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=DEFAULT_HOME,
        help=f"Override grimoire home directory (default: {DEFAULT_HOME})",
    )
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    home = args.home.expanduser().resolve() if args.home else DEFAULT_HOME
    library_path = home / "library.json"

    reporter = ResultReporter(
        "sync_library", root=home, mode="apply" if args.apply else "plan"
    )

    if human:
        print()
        print("  Grimoire Library Sync")
        print("  ----------------------------")

    scan = scan_grimoire_home(home)
    library, unreadable = read_library(library_path)
    if library is None:
        reporter.message("error", f"{unreadable}; the file is left as it is", path=library_path)
        library = {"grimoires": {}}
    diff = diff_library(scan, library, home)

    has_drift = print_report(
        scan, diff, home, library_path, args.apply, human=human, reporter=reporter
    )

    applied = False
    conflict = None
    if unreadable:
        conflict = f"{unreadable}; the file is left as it is"
        if human:
            print(f"  [ERROR] {conflict}", file=sys.stderr)
            print()
    elif args.apply and has_drift:
        try:
            applied = apply_synced_library(scan, library_path, home)
        except (LibraryWriteConflict, LibraryUnreadable) as exc:
            conflict = str(exc)
            reporter.message("error", conflict)
            if human:
                print(f"  [ERROR] {conflict}", file=sys.stderr)
                print()
        if applied:
            reporter.mutation("write", path=library_path, detail="reconciled library")
            if human:
                ok(f"Library written: {library_path}")
                print()
                print("  Sync skills to pick up any new grimoires:")
                print("    /grm-update skills")
                print()
        elif not conflict and human:
            ok("Library already reconciled by a concurrent process; nothing to write.")
            print()

    if not human:
        reporter.emit(
            args.format,
            summary={
                "missing": len(diff["missing"]),
                "stale": len(diff["stale"]),
                "mismatched": len(diff["mismatched"]),
                "ok": len(diff["ok"]),
                "unmanaged": len(scan["unmanaged"]),
                "applied": applied,
            },
        )

    sys.exit(1 if conflict else 0)


if __name__ == "__main__":
    main()
