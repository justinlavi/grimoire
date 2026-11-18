#!/usr/bin/env python3
"""Adopt an unmanaged directory under ~/grimoires/ as a grimoire.

Writes a `grimoire.json` manifest into the target directory so the
registration and library rites recognize it. Refuses a skill_prefix that
another grimoire already uses, and one the framework owns (the prefixes of its
command families), because skill registration blocks every target while two
sources claim a prefix.

After adopting, run `/grm-update library` to register the grimoire in the
local library, then `/grm-update skills` if it ships skills.

Mutation profile: apply_only. The rite writes `grimoire.json` into the target
and nothing else; it never overwrites an existing manifest.

Usage:
    python rites/adopt_grimoire.py <directory> --skill-prefix <prefix> [--description "<desc>"]
                                          [--name <name>] [--naming <convention>] [--home <path>]
                                          [--format human|json|jsonl]

Args:
    <directory>   - directory name under ~/grimoires/ (e.g. "dnd-grimoire")
                    or absolute path
    --skill-prefix   - short lowercase slug for the skill prefix (^[a-z][a-z0-9]*$)
    --description - one-line description (defaults to a placeholder)
    --name        - canonical name (defaults to the directory name)
    --naming      - naming convention the grimoire records (default: snake_case;
                    `preserve` for material that keeps its own casing)
    --home        - override grimoire home (default: ~/grimoires)
    --format      - output format: human (default), json, or jsonl

Exit codes: 0 = manifest written; 1 = validation failed (the directory is
missing, the prefix is malformed, taken by another grimoire or owned by the
framework, or a manifest already exists); 2 = argparse invalid arguments.
"""

import argparse
import sys
from pathlib import Path

from _lib import SKILL_PREFIX_RE, err, info, load_manifest, load_skill_families, ok, write_json
from diagnostics import ResultReporter, add_output_format_arg

DEFAULT_HOME = Path.home() / "grimoires"
FRAMEWORK_PATH = Path(__file__).resolve().parent.parent


def find_existing_skill_prefixes(home):
    """Return {skill_prefix: directory_name} for every grimoire already manifested."""
    found = {}
    if not home.is_dir():
        return found
    for child in sorted(home.iterdir()):
        manifest, _errors = load_manifest(child)
        if manifest is None:
            continue
        prefix = manifest.get("skill_prefix")
        if isinstance(prefix, str) and prefix:
            found[prefix] = child.name
    return found


def framework_skill_prefixes():
    """Skill prefixes the framework owns: those of its command families."""
    return {family["skill_prefix"] for family in load_skill_families(FRAMEWORK_PATH)}


def main():
    parser = argparse.ArgumentParser(description="Adopt an unmanaged grimoire")
    parser.add_argument("directory", help="Directory name under home (e.g. dnd-grimoire) or absolute path")
    parser.add_argument(
        "--skill-prefix",
        dest="skill_prefix",
        required=True,
        help="Short lowercase slug for the skill prefix",
    )
    parser.add_argument("--description", default="", help="One-line description")
    parser.add_argument("--name", default="", help="Canonical name (defaults to directory name)")
    parser.add_argument(
        "--naming",
        default="snake_case",
        help="Naming convention the grimoire records (default: snake_case; use preserve for material that keeps its own casing)",
    )
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME, help=f"Grimoire home (default: {DEFAULT_HOME})")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    home = args.home.expanduser().resolve()
    reporter = ResultReporter("adopt_grimoire", root=home, mode="apply")

    if human:
        print()
        print("  Adopt Grimoire")
        print("  ----------------------------")
        print(f"  Home:        {home}")
        print()

    # Resolve the target directory.
    candidate = Path(args.directory)
    target = candidate if candidate.is_absolute() else home / args.directory
    target = target.resolve()

    if not target.is_dir():
        reporter.message("error", f"Directory does not exist: {target}", path=target)
        if human:
            err(f"Directory does not exist: {target}")
        else:
            reporter.emit(args.format)
        return 1

    if human:
        info(f"Target:      {target}")

    # Validate skill_prefix.
    if not SKILL_PREFIX_RE.fullmatch(args.skill_prefix):
        reporter.message(
            "error",
            f"Invalid skill_prefix '{args.skill_prefix}' (must match {SKILL_PREFIX_RE.pattern})",
        )
        if human:
            err(f"Invalid skill_prefix '{args.skill_prefix}' (must match {SKILL_PREFIX_RE.pattern})")
        else:
            reporter.emit(args.format)
        return 1
    if human:
        info(f"Skill prefix: {args.skill_prefix}")

    # Refuse to overwrite an existing manifest.
    manifest_path = target / "grimoire.json"
    if manifest_path.is_file():
        reporter.message("error", f"grimoire.json already exists at {manifest_path}", path=manifest_path)
        if human:
            err(f"grimoire.json already exists at {manifest_path}")
            info("To change an adopted grimoire's skill prefix, edit the manifest by hand.")
        else:
            reporter.emit(args.format)
        return 1

    # The framework owns its own prefixes.
    if args.skill_prefix in framework_skill_prefixes():
        message = (
            f"Skill prefix '{args.skill_prefix}' belongs to the framework. Pick a different skill prefix."
        )
        reporter.message("error", message)
        if human:
            err(message)
        else:
            reporter.emit(args.format)
        return 1

    # Detect skill_prefix collisions across home.
    existing = find_existing_skill_prefixes(home)
    if args.skill_prefix in existing:
        reporter.message(
            "error",
            f"Skill prefix '{args.skill_prefix}' is already used by '{existing[args.skill_prefix]}'. "
            "Pick a different skill prefix.",
        )
        if human:
            err(
                f"Skill prefix '{args.skill_prefix}' is already used by '{existing[args.skill_prefix]}'. "
                "Pick a different skill prefix."
            )
        else:
            reporter.emit(args.format)
        return 1

    name = args.name or target.name
    description = args.description or f"{name} grimoire"

    manifest = {
        "name": name,
        "skill_prefix": args.skill_prefix,
        "description": description,
        "naming": (args.naming or "snake_case").strip(),
    }

    write_json(manifest_path, manifest)
    reporter.mutation("write", path=manifest_path, detail="grimoire.json")
    if human:
        ok(f"Wrote {manifest_path}")
        print()

        print("  Next steps:")
        print("    1. Run /grm-update library to register it in the local library.")
        print("    2. If this grimoire ships skills, run /grm-update skills.")
        print()
    else:
        reporter.emit(args.format, summary={"name": name, "skill_prefix": args.skill_prefix})
    return 0


if __name__ == "__main__":
    sys.exit(main())
