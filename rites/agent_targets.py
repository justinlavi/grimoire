#!/usr/bin/env python3
"""Load and validate the framework's agent target registry.

The module also says which agents are installed on this machine
(`installed_agent_ids`). `rites/summon.sh` downloads it with
`data/agent_targets.json` before the framework exists on disk, so it imports
only the standard library.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path("rites/data/agent_targets.json")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
INSTRUCTION_MODES = {"auto", "manual"}
SKILL_MODES = {"full", "pointer", "none"}
REQUIRED_FIELDS = {
    "id",
    "label",
    "instruction_target",
    "instruction_mode",
    "skill_mode",
    "auto_configured",
    "supports_model_invocation",
    "summary",
    "limitations",
}


def load_agent_targets(root: Path) -> dict[str, Any]:
    """Load the agent target registry JSON."""
    return json.loads((Path(root) / CONTRACT_PATH).read_text(encoding="utf-8"))


def target_entries(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return agent target entries from the registry, or an empty list."""
    entries = contract.get("targets", [])
    return entries if isinstance(entries, list) else []


def resolve_user_path(path_text: str | None, home: Path | None = None) -> Path | None:
    """Resolve a registry path rooted at `home` (default: the user's home directory)."""
    if not path_text:
        return None
    if path_text.startswith("~/"):
        return (Path(home) if home else Path.home()) / path_text[2:]
    return Path(path_text).expanduser()


def plugin_install_record(claude_home: Path | None = None) -> dict[str, Any]:
    """Return the Claude Code plugin install record, or {} when none is readable.

    `claude_home` is the folder that holds `plugins/installed_plugins.json`
    (default: `~/.claude`).
    """
    base = Path(claude_home) if claude_home else Path.home() / ".claude"
    path = base / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    return plugins if isinstance(plugins, dict) else {}


def family_plugins(root: Path) -> dict[str, str]:
    """Map each Claude Code plugin name to the command family it carries (framework.json)."""
    try:
        manifest = json.loads((Path(root) / "framework.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    families = manifest.get("skill_families", {}) if isinstance(manifest, dict) else {}
    if not isinstance(families, dict):
        return {}
    return {
        str(config.get("plugin", name)): name
        for name, config in families.items()
        if isinstance(config, dict)
    }


def installed_plugin_names(marketplace: str, claude_home: Path | None = None) -> set[str]:
    """Names of the plugins installed from `marketplace`, read from the install record.

    A record key reads `<plugin>@<marketplace>`; a plugin of another marketplace
    does not count.
    """
    names = set()
    for key in plugin_install_record(claude_home):
        name, _, source = str(key).partition("@")
        if source == marketplace:
            names.add(name)
    return names


def installed_framework_plugins(root: Path, marketplace: str, claude_home: Path | None = None) -> set[str]:
    """Command families (by family name) installed as Claude Code plugins from `marketplace`."""
    by_plugin = family_plugins(root)
    return {by_plugin[name] for name in installed_plugin_names(marketplace, claude_home) if name in by_plugin}


# The plugin whose session hook prints the routing block.
ROUTING_PLUGIN = "grimoire"


def agent_home(entry: dict[str, Any], home: Path | None = None) -> Path | None:
    """The folder an agent keeps its files in: the parent of its instruction target.

    Falls back to the parent of the skill target for an entry with no
    user-relative instruction target, and returns None when neither is.
    """
    for field in ("instruction_target", "skill_target"):
        value = entry.get(field)
        if isinstance(value, str) and value.startswith("~/"):
            path = resolve_user_path(value, home)
            return path.parent if path else None
    return None


def _configured_entries(root: Path) -> list[dict[str, Any]]:
    """Registry entries the framework writes for: automatic instruction targets and skill targets."""
    return [
        entry for entry in target_entries(load_agent_targets(root))
        if entry.get("instruction_mode") == "auto" or entry.get("skill_mode") in {"full", "pointer"}
    ]


def installed_agent_ids(root: Path, home: Path | None = None) -> list[str]:
    """Ids of the agents the framework configures on this machine, in registry order.

    An agent that is not installed is not configured: it counts only when its
    home folder exists (`~/.claude`, `~/.codex`). When no agent's home exists,
    every agent counts, so a machine with no assistant yet is still set up.
    `home` is the user's home directory (default: `Path.home()`).
    """
    entries = _configured_entries(root)
    present = []
    for entry in entries:
        folder = agent_home(entry, home)
        if folder is None or folder.is_dir():
            present.append(entry["id"])
    return present or [entry["id"] for entry in entries]


def skill_registration_targets(root: Path, home: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return the skill target config of every agent that has one, keyed by agent id.

    This is the unfiltered set: `sync_skills --agent <id>` can target any agent
    here, installed or not. `installed_skill_targets` is the set a run on this
    machine configures.
    """
    contract = load_agent_targets(root)
    targets: dict[str, dict[str, Any]] = {}
    for entry in target_entries(contract):
        if entry.get("skill_mode") not in {"full", "pointer"}:
            continue
        skill_path = resolve_user_path(entry.get("skill_target"), home)
        if skill_path is None:
            continue
        deprecated = [
            resolve_user_path(item, home)
            for item in entry.get("deprecated_skill_targets", [])
            if isinstance(item, str) and item
        ]
        marketplace = entry.get("plugin_marketplace")
        targets[entry["id"]] = {
            "label": entry["label"],
            "path": skill_path,
            "pointer_only": entry["skill_mode"] == "pointer",
            "deprecated_paths": [path for path in deprecated if path is not None],
            "plugin_families": (
                installed_framework_plugins(root, marketplace, agent_home(entry, home))
                if marketplace else set()
            ),
        }
    return targets


def automatic_instruction_targets(root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    """Return every auto-configured instruction target with resolved paths.

    This is the unfiltered set; `installed_instruction_targets` is the set a run
    on this machine configures. `plugin_serves_routing` is True when the plugin
    that prints the routing block is installed for the agent.
    """
    contract = load_agent_targets(root)
    targets = []
    for entry in target_entries(contract):
        if entry.get("instruction_mode") != "auto":
            continue
        instruction_path = resolve_user_path(entry.get("instruction_target"), home)
        if instruction_path is None:
            continue
        marketplace = entry.get("plugin_marketplace")
        targets.append({
            "id": entry["id"],
            "label": entry["label"],
            "path": instruction_path,
            "title": instruction_path.name,
            "skill_mode": entry.get("skill_mode"),
            "skill_target": resolve_user_path(entry.get("skill_target"), home),
            "plugin_serves_routing": bool(
                marketplace and ROUTING_PLUGIN in installed_plugin_names(marketplace, agent_home(entry, home))
            ),
        })
    return targets


def installed_instruction_targets(root: Path, home: Path | None = None) -> list[dict[str, Any]]:
    """The auto-configured instruction targets of the agents installed on this machine."""
    installed = set(installed_agent_ids(root, home))
    return [target for target in automatic_instruction_targets(root, home) if target["id"] in installed]


def installed_skill_targets(root: Path, home: Path | None = None) -> dict[str, dict[str, Any]]:
    """The skill targets of the agents installed on this machine, keyed by agent id."""
    installed = set(installed_agent_ids(root, home))
    return {
        agent: config for agent, config in skill_registration_targets(root, home).items()
        if agent in installed
    }


def _error(code: str, message: str, path: str, hint: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "path": path,
        "hint": hint,
    }


def validate_agent_targets(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Return the loaded registry and structured validation errors."""
    try:
        contract = load_agent_targets(root)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_error(
            "AGENT_TARGETS_READ",
            f"could not read agent target registry: {exc}",
            CONTRACT_PATH.as_posix(),
            "Create valid JSON at rites/data/agent_targets.json.",
        )]

    errors: list[dict[str, str]] = []
    if contract.get("schema_version") != 1:
        errors.append(_error(
            "AGENT_TARGETS_SCHEMA",
            "agent target registry must declare schema_version 1",
            CONTRACT_PATH.as_posix(),
            "Set schema_version to 1.",
        ))

    entries = target_entries(contract)
    if not isinstance(contract.get("targets"), list):
        errors.append(_error(
            "AGENT_TARGETS_LIST",
            "agent target registry must contain a targets list",
            CONTRACT_PATH.as_posix(),
            "Add a top-level targets array.",
        ))

    seen: dict[str, int] = {}
    for index, entry in enumerate(entries):
        path = f"{CONTRACT_PATH.as_posix()}#/targets/{index}"
        if not isinstance(entry, dict):
            errors.append(_error(
                "AGENT_TARGETS_ENTRY",
                "agent target entry must be an object",
                path,
                "Replace this entry with an object keyed by target metadata.",
            ))
            continue

        target_id = entry.get("id") if isinstance(entry.get("id"), str) else f"<target {index}>"
        if isinstance(entry.get("id"), str):
            seen[target_id] = seen.get(target_id, 0) + 1
            if not ID_RE.fullmatch(target_id):
                errors.append(_error(
                    "AGENT_TARGETS_ID",
                    f"{target_id} is not a valid target id",
                    path,
                    "Use lowercase kebab-case ids.",
                ))

        for field in sorted(REQUIRED_FIELDS):
            value = entry.get(field)
            if field in {"auto_configured", "supports_model_invocation"}:
                if not isinstance(value, bool):
                    errors.append(_error(
                        "AGENT_TARGETS_FIELD",
                        f"{target_id} must declare boolean {field}",
                        path,
                        f"Set {field} to true or false.",
                    ))
            elif field == "limitations":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    errors.append(_error(
                        "AGENT_TARGETS_FIELD",
                        f"{target_id} must declare limitations as a string list",
                        path,
                        "Use an empty list when there are no limitations.",
                    ))
            elif not isinstance(value, str) or not value.strip():
                errors.append(_error(
                    "AGENT_TARGETS_FIELD",
                    f"{target_id} must declare non-empty {field}",
                    path,
                    f"Add {field} to this target.",
                ))

        if "skill_target" not in entry:
            errors.append(_error(
                "AGENT_TARGETS_FIELD",
                f"{target_id} must declare skill_target",
                path,
                "Use null when the target has no local skill directory.",
            ))

        instruction_mode = entry.get("instruction_mode")
        if isinstance(instruction_mode, str) and instruction_mode not in INSTRUCTION_MODES:
            errors.append(_error(
                "AGENT_TARGETS_INSTRUCTION_MODE",
                f"{target_id} uses unsupported instruction_mode {instruction_mode}",
                path,
                f"Use one of: {', '.join(sorted(INSTRUCTION_MODES))}.",
            ))

        skill_mode = entry.get("skill_mode")
        if isinstance(skill_mode, str) and skill_mode not in SKILL_MODES:
            errors.append(_error(
                "AGENT_TARGETS_SKILL_MODE",
                f"{target_id} uses unsupported skill_mode {skill_mode}",
                path,
                f"Use one of: {', '.join(sorted(SKILL_MODES))}.",
            ))

        deprecated_targets = entry.get("deprecated_skill_targets", [])
        if not isinstance(deprecated_targets, list) or not all(
            isinstance(item, str) and item.startswith("~/") for item in deprecated_targets
        ):
            errors.append(_error(
                "AGENT_TARGETS_FIELD",
                f"{target_id} deprecated_skill_targets must be a list of ~/... paths",
                path,
                "List former skill directories as user-relative paths, or omit the field.",
            ))

        skill_target = entry.get("skill_target")
        if skill_mode in {"full", "pointer"}:
            if not isinstance(skill_target, str) or not skill_target.strip():
                errors.append(_error(
                    "AGENT_TARGETS_SKILL_TARGET",
                    f"{target_id} must declare skill_target when skill_mode is {skill_mode}",
                    path,
                    "Set skill_target to a user-relative directory.",
                ))
        elif skill_target is not None:
            errors.append(_error(
                "AGENT_TARGETS_SKILL_TARGET",
                f"{target_id} must use null skill_target when skill_mode is none",
                path,
                "Set skill_target to null.",
            ))

        marketplace = entry.get("plugin_marketplace")
        if "plugin_marketplace" in entry and (not isinstance(marketplace, str) or not marketplace.strip()):
            errors.append(_error(
                "AGENT_TARGETS_FIELD",
                f"{target_id} plugin_marketplace must be a non-empty marketplace name",
                path,
                "Name the marketplace the framework's plugins install from, or omit the field.",
            ))

        if entry.get("auto_configured") is True and instruction_mode != "auto":
            errors.append(_error(
                "AGENT_TARGETS_AUTO_CONFIG",
                f"{target_id} is auto_configured but instruction_mode is not auto",
                path,
                "Use instruction_mode auto for automatic agent configuration.",
            ))

        instruction_target = entry.get("instruction_target")
        if instruction_mode == "auto":
            if not isinstance(instruction_target, str) or not instruction_target.startswith("~/"):
                errors.append(_error(
                    "AGENT_TARGETS_INSTRUCTION_TARGET",
                    f"{target_id} automatic instruction targets must be user-relative",
                    path,
                    "Use a ~/... instruction path for automatic writes.",
                ))

    for target_id, count in sorted(seen.items()):
        if count > 1:
            errors.append(_error(
                "AGENT_TARGETS_DUPLICATE",
                f"{target_id} appears {count} times in the agent target registry",
                CONTRACT_PATH.as_posix(),
                "Keep exactly one entry per target id.",
            ))

    if contract.get("targets") == []:
        errors.append(_error(
            "AGENT_TARGETS_EMPTY",
            "agent target registry must declare at least one target",
            CONTRACT_PATH.as_posix(),
            "Add supported or documented agent targets.",
        ))

    try:
        auto_targets = automatic_instruction_targets(root)
        skill_targets = skill_registration_targets(root)
    except (KeyError, TypeError):
        auto_targets = []
        skill_targets = {}
    if not auto_targets:
        errors.append(_error(
            "AGENT_TARGETS_NO_AUTO",
            "agent target registry must declare at least one automatic instruction target",
            CONTRACT_PATH.as_posix(),
            "Set instruction_mode auto and auto_configured true for local instruction-file targets.",
        ))
    if not skill_targets:
        errors.append(_error(
            "AGENT_TARGETS_NO_SKILLS",
            "agent target registry must declare at least one skill registration target",
            CONTRACT_PATH.as_posix(),
            "Set skill_mode full or pointer with a skill_target.",
        ))

    return contract, errors
