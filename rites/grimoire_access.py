#!/usr/bin/env python3
"""Show or change whether a grimoire is set up for reading or editing on this computer.

A library entry in `~/grimoires/library.json` may carry `"access": "read"` or
`"access": "edit"`. A grimoire set up for reading never collects local changes:
the rites that change its content (save, move, remove, new page, link repair)
refuse, and the update leaves its managed files alone. A missing field, or any
other value, means editing. The setting belongs to this computer's library; the
grimoire's own files do not carry it.

The rite reports the access of a grimoire, plans a change, or writes it through
`sync_library.update_library`, the compare-and-swap writer of `library.json`.
Only a grimoire that is in the library can be switched; `/grm-update library`
registers one that is not.

Mutation profile: plan_apply. Without `--set` the rite only reports. With
`--set` and no `--apply` it plans the change and writes nothing.

Usage:
    python rites/grimoire_access.py [--grimoire <path>] [--set read|edit] [--apply]
        [--library <path>] [--format human|json|jsonl]

The envelope summary holds `key`, `access`, `registered` and `library`.

Exit codes: 0 = reported, planned, applied, or already set; 1 = blocked (the
grimoire is not in the library, or the library cannot be read or keeps
changing); 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import sync_library
from _lib import (
    default_library_path,
    info,
    library_entry_for,
    ok,
    resolve_grimoire_arg,
    warn,
)
from diagnostics import ResultReporter, add_output_format_arg


def main() -> int:
    parser = argparse.ArgumentParser(description="Show or change a grimoire's access on this computer")
    parser.add_argument("--grimoire", type=Path, default=Path("."),
                        help="Grimoire root (default: the current directory)")
    parser.add_argument("--set", dest="target", choices=("read", "edit"), default=None,
                        help="Access to record for the grimoire (default: report only)")
    parser.add_argument("--apply", action="store_true", help="Write the change (default: plan only)")
    parser.add_argument("--library", type=Path, default=None,
                        help="Library file (default: ~/grimoires/library.json)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    root = resolve_grimoire_arg(args.grimoire)
    library_path = (args.library or default_library_path()).expanduser()
    reporter = ResultReporter("grimoire_access", root=root, mode="apply" if args.apply else "plan")

    key, entry = library_entry_for(root, library_path)
    current = "read" if entry is not None and entry.get("access") == "read" else "edit"
    summary = {"key": key, "access": current, "registered": key is not None, "library": str(library_path)}

    def finish(code: int) -> int:
        if not human:
            reporter.emit(args.format, summary=summary)
        return code

    if args.target is None:
        reporter.set_status("noop")
        if human:
            if key is None:
                info(f"{root.name} is not in the library; it is treated as editable.")
            else:
                ok(f"{key} is set up for {'reading' if current == 'read' else 'editing'} on this computer.")
        return finish(0)

    if key is None:
        text = (f"{root} is not in the library {library_path}, so its access cannot be set; "
                "/grm-update library registers it")
        reporter.message("error", text, path=library_path)
        reporter.set_status("error")
        if human:
            warn(text)
        return finish(1)

    if current == args.target:
        reporter.message("info", f"access is already {args.target}")
        reporter.set_status("noop")
        if human:
            ok(f"{key} is already set up for {'reading' if current == 'read' else 'editing'}.")
        return finish(0)

    if not args.apply:
        reporter.message("info", f"would set access to {args.target} for {key}")
        reporter.set_status("noop")
        if human:
            info(f"Would set {key} to {args.target} in {library_path}. Re-run with --apply to write it.")
        return finish(0)

    def build(library):
        existing = library["grimoires"].get(key)
        if not isinstance(existing, dict):
            return None
        library["grimoires"][key] = {**existing, "access": args.target}
        return library

    try:
        wrote = sync_library.update_library(library_path, build)
    except (sync_library.LibraryUnreadable, sync_library.LibraryWriteConflict) as exc:
        reporter.message("error", f"the library was not changed: {exc}", path=library_path)
        reporter.set_status("error")
        if human:
            warn(f"The library was not changed: {exc}")
        return finish(1)

    summary["access"] = args.target
    if wrote:
        reporter.mutation("write", path=library_path, detail=f"{key}.access = {args.target}")
        if human:
            ok(f"{key} is set up for {'reading' if args.target == 'read' else 'editing'} on this computer.")
    else:
        reporter.set_status("noop")
        if human:
            ok(f"{key} is already set up for {'reading' if args.target == 'read' else 'editing'}.")
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
