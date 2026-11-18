#!/usr/bin/env python3
"""Load and validate the framework's public command-surface contract.

`rites/data/command_surface.json` carries one entry per public skill: its
family, skill source, invocation, owner type, mutation profile, log behaviour
and validation profile. `validate_command_surface` checks the entries against
the skills the framework ships and against the files they point to.

Mutation profile: none; the module only reads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from _lib import discover_skill_commands, read_utf8
from rite_profiles import ALLOWED_PROFILES, ContractSpec, _error, check_contract

CONTRACT_PATH = Path("rites/data/command_surface.json")

REQUIRED_STRING_FIELDS = {
    "command",
    "family",
    "skill_source",
    "invocation",
    "owner_type",
    "mutation_profile",
    "mutation_behavior",
    "log_behavior",
    "validation_profile",
}
REQUIRED_LIST_FIELDS = {"preconditions"}
OPTIONAL_PATH_FIELDS = {"guard", "rite_owner"}
ALLOWED_OWNER_TYPES = {"rite", "judgment", "hybrid"}
# A command that runs no rite, or only reads, has no rite profile of its own.
ALLOWED_MUTATION_PROFILES = ALLOWED_PROFILES | {"read_only", "judgment_gated"}
COMMAND_RE = re.compile(r"^/[a-z][a-z0-9]*-[a-z][a-z0-9-]*$")

SPEC = ContractSpec(
    path=CONTRACT_PATH,
    prefix="COMMAND_SURFACE",
    title="command-surface contract",
    list_key="commands",
    key_field="command",
    required_strings=frozenset(REQUIRED_STRING_FIELDS),
    required_lists=frozenset(REQUIRED_LIST_FIELDS),
    read_hint="Create valid UTF-8 JSON at rites/data/command_surface.json.",
    entry_hint="Replace this entry with an object keyed by command metadata.",
    list_item_hint="a list of strings",
    duplicate_hint="Keep exactly one command entry per public skill.",
    missing_message="{key} is missing from the command-surface contract",
    missing_hint="Add a command-surface entry for this skill.",
    extra_message="{key} is not backed by a framework-shipped SKILL.md",
    extra_hint="Create the skill or remove this command entry.",
)


def load_command_surface(root: Path) -> dict[str, Any]:
    """Load the command-surface contract JSON."""
    return json.loads(read_utf8(root / CONTRACT_PATH))


def command_entries(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return command entries from the contract, or an empty list."""
    entries = contract.get("commands", [])
    return entries if isinstance(entries, list) else []


def validate_command_surface(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return the loaded contract and structured validation errors."""
    discovered = discover_skill_commands(root)

    def check_entry(entry: dict[str, Any], label: str, path: str, errors: list) -> None:
        def add(kind: str, message: str, hint: str) -> None:
            errors.append(_error(SPEC, kind, message, path, hint))

        command = entry.get("command")
        if isinstance(command, str) and not COMMAND_RE.match(command):
            add("COMMAND", f"{command} is not a valid slash-command name",
                "Use /<prefix>-<kebab-slug>.")

        owner_type = entry.get("owner_type")
        if isinstance(owner_type, str) and owner_type not in ALLOWED_OWNER_TYPES:
            add("OWNER_TYPE", f"{label} uses unsupported owner_type {owner_type}",
                f"Use one of: {', '.join(sorted(ALLOWED_OWNER_TYPES))}.")

        mutation_profile = entry.get("mutation_profile")
        if isinstance(mutation_profile, str) and mutation_profile not in ALLOWED_MUTATION_PROFILES:
            add("MUTATION_PROFILE", f"{label} uses unsupported mutation_profile {mutation_profile}",
                f"Use one of: {', '.join(sorted(ALLOWED_MUTATION_PROFILES))}.")

        for field in ("skill_source", "invocation"):
            value = entry.get(field)
            if isinstance(value, str) and value.strip() and not (root / value).exists():
                add("PATH", f"{label} {field} does not exist: {value}",
                    "Point the contract at an existing repository-relative path.")

        for field in sorted(OPTIONAL_PATH_FIELDS):
            value = entry.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                add("FIELD", f"{label} {field} must be null or a non-empty path",
                    f"Set {field} to null when no {field} exists.")
            elif not (root / value).exists():
                add("PATH", f"{label} {field} does not exist: {value}",
                    "Point the contract at an existing repository-relative path.")

        discovered_entry = discovered.get(command)
        if discovered_entry:
            if entry.get("family") != discovered_entry["family"]:
                add("FAMILY", f"{label} family must be {discovered_entry['family']}",
                    "Match the family declared by framework.json.")
            if entry.get("skill_source") != discovered_entry["skill_source"]:
                add("SKILL_SOURCE", f"{label} skill_source must be {discovered_entry['skill_source']}",
                    "Match the discovered SKILL.md path.")

    return check_contract(root, SPEC, set(discovered), check_entry)
