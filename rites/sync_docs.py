#!/usr/bin/env python3
"""Generate docs/skills.md, the skill catalog, from the skills and the command-surface contract.

The catalog lists every framework skill, from its `SKILL.md` frontmatter, and
the command-surface metadata of each, from `rites/data/command_surface.json`.
Its `last_verified` is the date of the newest release entry in `CHANGELOG.md`.

Mutation profile: plan_apply. The default run prints the diff and writes
nothing; `--apply` writes docs/skills.md.

Usage:
    FRAMEWORK_HOME/bin/grimoire sync_docs                        # print the diff
    FRAMEWORK_HOME/bin/grimoire sync_docs --apply                # write docs/skills.md
    FRAMEWORK_HOME/bin/grimoire sync_docs --format {human,json,jsonl}

Exit codes: 0 = the catalog is up to date or was written, 1 = the catalog is
stale (without --apply) or the command-surface contract is invalid,
2 = invalid arguments.
"""

import argparse
import difflib
import re
import sys
import textwrap
from pathlib import PurePosixPath

from _lib import (
    default_framework_root,
    discover_skill_commands,
    load_skill_families,
    read_utf8,
    write_utf8,
)
from command_surface import command_entries, validate_command_surface
from diagnostics import ResultReporter, add_output_format_arg

FRAMEWORK_PATH = default_framework_root()
SKILLS_DIR = FRAMEWORK_PATH / "skills"
SKILLS_DOC = FRAMEWORK_PATH / "docs" / "skills.md"
RELEASE_DATE_RE = re.compile(r"^## \[[^\]]+\] - (\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)

# What each family's commands do, for the catalog's introduction.
FAMILY_PURPOSE = {
    "grm": "work with grimoires",
    "dev": "maintain the framework",
}


def load_framework_skill_families():
    """Return the command families declared in framework.json, in declaration order."""
    return load_skill_families(FRAMEWORK_PATH)


def collect_skills():
    """Return skill metadata for every framework-shipped public skill."""
    return [
        {
            "name": command.lstrip("/"),
            "family": entry["family"],
            "description": entry["description"],
            "argument_hint": entry["argument_hint"],
            "source": entry["skill_source"],
        }
        for command, entry in discover_skill_commands(FRAMEWORK_PATH).items()
    ]


def load_command_metadata():
    """Return command-surface metadata keyed by registered skill name."""
    contract, errors = validate_command_surface(FRAMEWORK_PATH)
    if errors:
        messages = [
            f"{error['code']}: {error['message']} ({error['path']})"
            for error in errors
        ]
        raise RuntimeError(
            "command-surface contract is invalid:\n  " + "\n  ".join(messages)
        )
    if contract is None:
        raise RuntimeError("command-surface contract could not be loaded")

    metadata = {}
    for entry in command_entries(contract):
        metadata[entry["command"].lstrip("/")] = entry
    return metadata


def command_pattern(family):
    """Return how a family's commands are typed, for example `/grm-dev-<verb>`."""
    slug_prefix = f"{family['slug_prefix']}-" if family["slug_prefix"] else ""
    return f"/{family['skill_prefix']}-{slug_prefix}<verb>"


def group_skills(skills):
    """Group skills by command family, in the order framework.json declares them.

    Returns `[(family, members)]` for every family that has a skill.
    """
    members_of = {}
    for skill in skills:
        members_of.setdefault(skill["family"], []).append(skill)
    return [
        (family, members_of[family["name"]])
        for family in load_framework_skill_families()
        if family["name"] in members_of
    ]


def catalog_date():
    """Return the date of the newest release entry in CHANGELOG.md, as YYYY-MM-DD.

    The catalog is verified against the framework as of its newest release, so
    that date is the page's `last_verified`.
    """
    match = RELEASE_DATE_RE.search(read_utf8(FRAMEWORK_PATH / "CHANGELOG.md"))
    if match is None:
        raise RuntimeError("CHANGELOG.md has no release entry of the form '## [x.y.z] - YYYY-MM-DD'")
    return match.group(1)


def escape_table_cell(value):
    """Escape table delimiters and normalize whitespace in a Markdown cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def code_cell(value):
    """Render a short metadata value in a Markdown table cell."""
    if value is None or value == "":
        return "`none`"
    return f"`{escape_table_cell(value)}`"


def path_link(path, label=None):
    """Render a repository-relative path as a docs-relative Markdown link."""
    if not path:
        return "`none`"
    display = label or PurePosixPath(path).name
    return f"[`{escape_table_cell(display)}`](../{path})"


def render_catalog_row(skill):
    """Render one user-facing catalog row: command, what it does, and input."""
    hint = skill.get("argument_hint") or ""
    input_cell = code_cell(hint) if hint else "none"
    return (
        f"| [`/{skill['name']}`](../{skill['source']}) "
        f"| {escape_table_cell(skill['description'])} "
        f"| {input_cell} |"
    )


def render_contract_row(skill, metadata):
    """Render one maintainer-facing command-contract row."""
    name = skill["name"]
    entry = metadata[name]
    return (
        f"| [`/{name}`](../{skill['source']}) "
        f"| {path_link(entry['invocation'])} "
        f"| {code_cell(entry['owner_type'])} "
        f"| {code_cell(entry['mutation_profile'])} "
        f"| {path_link(entry.get('rite_owner'))} "
        f"| {path_link(entry.get('guard'))} "
        f"| {code_cell(entry['validation_profile'])} |"
    )


def render_skills_doc(skills, command_metadata):
    """Render the canonical docs/skills.md content."""
    missing = sorted(
        skill["name"]
        for skill in skills
        if skill["name"] not in command_metadata
    )
    if missing:
        raise RuntimeError(
            "skills missing command-surface metadata: "
            + ", ".join(f"/{name}" for name in missing)
        )

    groups = group_skills(skills)
    purposes = [
        f"`{command_pattern(family)}` commands {FAMILY_PURPOSE[family['name']]}"
        for family, _ in groups
        if family["name"] in FAMILY_PURPOSE
    ]
    lines = [
        "---",
        "type: reference",
        'title: "Grimoire Skill Catalog"',
        'aliases: ["skill-catalog", "skills-list"]',
        "tags: [type/reference, framework/docs, generated]",
        "authority: grimoire",
        f"last_verified: {catalog_date()}",
        "---",
        "",
        "<!-- GENERATED by rites/sync_docs.py - do not edit by hand. -->",
        "<!-- Source of truth: skills/<family>/<slug>/SKILL.md frontmatter",
        "     and rites/data/command_surface.json. -->",
        "<!-- Regenerate with: FRAMEWORK_HOME/bin/grimoire sync_docs --apply -->",
        "",
        "# Grimoire Skill Catalog",
        "",
        *textwrap.wrap(
            "Every command the framework ships, grouped by family. "
            + "; ".join(purposes)
            + ". Each command links to its source `SKILL.md`.",
            width=76,
        ),
        "",
        "A grimoire's own commands (for example `/cook-<verb>` in a cooking grimoire)",
        "are declared in that grimoire's `skills/` directory and are not listed here.",
        "`/grm-help all` lists the commands of every registered grimoire.",
        "",
        "The [Command contract](#command-contract) at the end lists each command's",
        "workflow, owner, mutation profile, rite, guard and validation profile,",
        "generated from [command_surface.json](../rites/data/command_surface.json).",
        "",
        "---",
        "",
    ]

    for family, members in groups:
        lines.append(f"## `{command_pattern(family)}` commands")
        lines.append("")
        lines.append("| Command | What it does | Input |")
        lines.append("|---|---|---|")
        for skill in members:
            lines.append(render_catalog_row(skill))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Command contract",
        "",
        "The workflow, owner type, mutation profile, rite owner, guard and validation",
        "profile of each command, generated from",
        "[command_surface.json](../rites/data/command_surface.json).",
        "",
    ])
    for family, members in groups:
        lines.append(f"### `{command_pattern(family)}` commands")
        lines.append("")
        lines.append(
            "| Command | Workflow | Owner | Mutation | Rite | Guard | Validation |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for skill in members:
            lines.append(render_contract_row(skill, command_metadata))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Adding a new skill",
        "",
        "1. Choose the command family in [skill_schema.md](skill_schema.md).",
        "2. Create `skills/<family>/<slug>/SKILL.md` with frontmatter:",
        "   `name: {{SKILL_PREFIX}}-<registered-slug>` and a one-line `description`.",
        "3. Add or update the command entry in `rites/data/command_surface.json`.",
        "4. Run `FRAMEWORK_HOME/bin/grimoire validate skill-refs` to validate public",
        "   command metadata.",
        "5. Run `FRAMEWORK_HOME/bin/grimoire sync_docs --apply` to refresh this catalog.",
        "6. Run `FRAMEWORK_HOME/bin/grimoire sync_skills` to install the skill into",
        "   agent skill directories.",
        "",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Sync auto-generated docs from source files")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry-run / show diff)",
    )
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    doc_label = SKILLS_DOC.relative_to(FRAMEWORK_PATH).as_posix()
    reporter = ResultReporter(
        "sync_docs", root=FRAMEWORK_PATH, mode="apply" if args.apply else "plan"
    )

    if human:
        print()
        print("  Sync Docs")
        print("  ----------------------------")

    skills = collect_skills()
    if human:
        print(f"  Discovered {len(skills)} framework skill(s) under {SKILLS_DIR}")
    try:
        command_metadata = load_command_metadata()
        new_content = render_skills_doc(skills, command_metadata)
    except RuntimeError as exc:
        if human:
            print()
            print(f"  [FAIL] {exc}", file=sys.stderr)
            print()
        else:
            reporter.message("error", str(exc))
            reporter.emit(args.format)
        return 1
    if human:
        print(f"  Loaded {len(command_metadata)} command-surface entries")

    summary = {"skills": len(skills), "commands": len(command_metadata)}
    old_content = read_utf8(SKILLS_DOC) if SKILLS_DOC.is_file() else ""

    if new_content == old_content:
        if human:
            print(f"  [OK]  {doc_label} is up to date.")
            print()
        else:
            reporter.emit(args.format, summary=summary)
        return 0

    if human:
        print(f"  [DIFF] {doc_label}")
        print()
        sys.stdout.writelines(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{doc_label}",
            tofile=f"b/{doc_label}",
        ))
        print()

    if args.apply:
        write_utf8(SKILLS_DOC, new_content)
        reporter.mutation("write", path=SKILLS_DOC)
        if human:
            print(f"  [OK]  Wrote {SKILLS_DOC}")
            print()
        else:
            reporter.emit(args.format, summary=summary)
        return 0

    reporter.message("warning", f"{doc_label} is out of date", path=SKILLS_DOC)
    reporter.set_status("blocked")
    if human:
        print(f"  Re-run with --apply to write {doc_label}.")
        print()
    else:
        reporter.emit(args.format, summary=summary)
    return 1


if __name__ == "__main__":
    sys.exit(main())
