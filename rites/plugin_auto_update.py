#!/usr/bin/env python3
"""Turn on automatic updates for the Grimoire plugins in Claude Code.

Claude Code updates the plugins of a marketplace by itself only when that
marketplace's entry in a settings file carries `"autoUpdate": true`; a
marketplace a user adds is off by default. This rite sets that key on the
entry `claude plugin marketplace add` wrote into the user's settings file,
`~/.claude/settings.json`, and leaves every other setting as it is.

The marketplace name comes from `.claude-plugin/marketplace.json`. The rite
changes only an entry that already exists: a marketplace declared by an
administrator in managed settings is theirs to configure, and one that was
never added has nothing to update.

Mutation profile: plan_apply. Without `--apply` the rite reports what it would
change and writes nothing.

Usage:
    python rites/plugin_auto_update.py [--apply] [--settings <path>]
        [--marketplace <name>] [--format human|json|jsonl]

Exit codes: 0 = already on, planned, or applied; 1 = blocked (no settings
file, settings that cannot be read or written or are not UTF-8 JSON,
marketplace not declared there); 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _lib import info, ok, read_utf8, warn, write_json
from diagnostics import ResultReporter, add_output_format_arg

FRAMEWORK_PATH = Path(__file__).resolve().parent.parent
MARKETPLACES_KEY = "extraKnownMarketplaces"
AUTO_UPDATE_KEY = "autoUpdate"


def default_settings_path() -> Path:
    """The user's Claude Code settings file: `CLAUDE_CONFIG_DIR` when set, else `~/.claude`."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base).expanduser() if base else Path.home() / ".claude") / "settings.json"


def marketplace_name(root: Path = FRAMEWORK_PATH) -> str:
    """The name the framework's own marketplace declares, or an empty string."""
    try:
        manifest = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    name = manifest.get("name")
    return name if isinstance(name, str) else ""


def inspect(settings_path: Path, name: str) -> tuple[str, dict | None, str]:
    """Classify the settings file for `name`.

    Returns `(state, settings, reason)` where state is `on`, `off`, or
    `blocked`; `settings` is the parsed file except when blocked.
    """
    try:
        raw = read_utf8(settings_path)
    except FileNotFoundError:
        return "blocked", None, f"no settings file at {settings_path}"
    except UnicodeDecodeError:
        return "blocked", None, f"{settings_path} is not UTF-8"
    except OSError as exc:
        return "blocked", None, f"could not read {settings_path}: {exc.strerror or exc}"
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as exc:
        return "blocked", None, f"{settings_path} is not valid JSON: {exc}"
    marketplaces = settings.get(MARKETPLACES_KEY) if isinstance(settings, dict) else None
    entry = marketplaces.get(name) if isinstance(marketplaces, dict) else None
    if not isinstance(entry, dict):
        return "blocked", None, (
            f"the '{name}' marketplace is not declared in {settings_path}; "
            "turn auto-update on under /plugin, Marketplaces, or ask your administrator"
        )
    return ("on" if entry.get(AUTO_UPDATE_KEY) is True else "off"), settings, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Turn on automatic updates for the Grimoire plugins")
    parser.add_argument("--apply", action="store_true", help="Write the setting (default: plan only)")
    parser.add_argument("--settings", type=Path, default=None, help="Settings file (default: the user's Claude Code settings)")
    parser.add_argument("--marketplace", default=None, help="Marketplace name (default: the framework's own)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    settings_path = (args.settings or default_settings_path()).expanduser()
    name = args.marketplace or marketplace_name()
    reporter = ResultReporter("plugin_auto_update", root=None, mode="apply" if args.apply else "plan")
    summary = {"settings": str(settings_path), "marketplace": name, "auto_update": False}

    def finish(code: int) -> int:
        if not human:
            reporter.emit(args.format, summary=summary)
        return code

    if not name:
        reporter.message("error", "the framework declares no marketplace name")
        reporter.set_status("blocked")
        if human:
            warn("The framework declares no marketplace name (.claude-plugin/marketplace.json).")
        return finish(1)

    state, settings, reason = inspect(settings_path, name)
    if state == "blocked":
        reporter.message("error", reason, path=settings_path)
        reporter.set_status("blocked")
        if human:
            warn(reason)
        return finish(1)

    if state == "on":
        summary["auto_update"] = True
        reporter.set_status("noop")
        if human:
            ok(f"Automatic updates are already on for the '{name}' marketplace.")
        return finish(0)

    if not args.apply:
        reporter.message("info", f"would set {AUTO_UPDATE_KEY} on the '{name}' marketplace", path=settings_path)
        reporter.set_status("noop")
        if human:
            info(f"Would turn on automatic updates for the '{name}' marketplace in {settings_path}.")
            info("Re-run with --apply to write it.")
        return finish(0)

    settings[MARKETPLACES_KEY][name][AUTO_UPDATE_KEY] = True
    try:
        write_json(settings_path, settings)
    except OSError as exc:
        reporter.message("error", f"could not write {settings_path}: {exc.strerror or exc}", path=settings_path)
        reporter.set_status("blocked")
        if human:
            warn(f"Could not write {settings_path}: {exc.strerror or exc}")
        return finish(1)
    summary["auto_update"] = True
    reporter.mutation("write", path=settings_path, detail=f"{MARKETPLACES_KEY}.{name}.{AUTO_UPDATE_KEY} = true")
    if human:
        ok(f"Automatic updates are on for the '{name}' marketplace. They take effect in the next session.")
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
