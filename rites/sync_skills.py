#!/usr/bin/env python3
"""Grimoire Skill Registration - cross-platform skill installer.

Discovers skills from the framework and, by default, every grimoire in the local
library (or the one named by --grimoire), then renders each as a self-contained
skill folder in the skill directory of every installed agent (`--agent` names
one, installed or not), as the agent registry defines them. Each
generated SKILL.md carries provenance metadata, and a folder under a managed
prefix that is not in the current catalog is removed.

Mutation profile: plan_apply. `--dry-run` reports the planned creates, updates,
stale cleanups, resets and collisions without writing. The default mode applies
the same plan.

Usage:
    python rites/sync_skills.py [--agent all|TARGET] [--grimoire PATH] [--dry-run]
                           [--reset-managed] [--format human|json|jsonl]

`--format json` (or `jsonl`) keeps stdout to the result envelope. Its `summary`
carries `registered`, `cleaned`, `reset` and `blocked`; every warning (a skipped
skill, an unreadable library, a directive that could not be inlined) is a
`warning` message, and every collision an `error` message.

Exit codes: 0 = plan completed or apply completed, 1 = apply blocked by
collision, 2 = invalid arguments (argparse, or an unknown --agent).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from diagnostics import ResultReporter, add_output_format_arg
from agent_targets import installed_skill_targets, skill_registration_targets
from _lib import (
    SKILL_PREFIX_PLACEHOLDER,
    SKILL_SLUG_RE,
    frontmatter_bounds,
    info,
    is_usable_local_path,
    load_manifest,
    load_skill_families_checked,
    ok,
    read_frontmatter_name,
    read_library,
    read_utf8,
    resolve_local_path,
    warn,
)


FRAMEWORK_PATH = Path(__file__).resolve().parent.parent
LOCAL_LIBRARY = Path.home() / "grimoires" / "library.json"

# Provenance stamped into each generated SKILL.md; no decision reads it.
OWNERSHIP_MARKER = "FRAMEWORK_SKILL_OWNERSHIP"
OWNERSHIP_SCHEMA_VERSION = 1
REGISTER_GENERATION = 1

# Receives each warning; the default prints it, `main` also records it in the envelope.
WarnFn = Callable[[str], None]


@dataclass(frozen=True)
class SkillSpec:
    """One renderable source skill."""

    command_name: str
    command_slug: str
    skill_prefix: str
    source_dir: Path
    source_label: str
    source_kind: str
    source_key: str
    source_repo: str
    grimoire_path: str = ""


@dataclass(frozen=True)
class PlanAction:
    """One planned registration action."""

    action: str
    command_name: str
    target_dir: Path
    spec: SkillSpec | None = None
    reason: str = ""


@dataclass(frozen=True)
class Catalog:
    """What one run registers: the desired skills and the prefixes it owns."""

    specs: list[SkillSpec]
    prefixes: tuple[str, ...]


def is_valid_skill_slug(slug: str) -> bool:
    """Return True when a skill slug uses lowercase hyphenated command syntax."""
    return bool(SKILL_SLUG_RE.fullmatch(slug))


def load_framework_skill_families(on_warning: WarnFn = warn) -> list[dict[str, Any]]:
    """Return the framework's command families, reporting every problem in framework.json."""
    families, problems = load_skill_families_checked(FRAMEWORK_PATH)
    for problem in problems:
        on_warning(f"Framework: {problem} (skipping)")
    return families


def load_grimoire_metadata(grimoire_root: Path, label: str, on_warning: WarnFn = warn) -> dict[str, Any] | None:
    """Return a grimoire's valid manifest, or None after reporting why it is unusable."""
    metadata, errors = load_manifest(grimoire_root)
    if metadata is None or errors:
        on_warning(f"{label}: {errors[0]} (skipping)")
        return None
    return metadata


def build_skill_spec(
    skill_dir: Path,
    skill_prefix: str,
    command_slug: str,
    source_label: str,
    source_kind: str,
    source_key: str,
    source_repo: str,
    grimoire_path: str = "",
    on_warning: WarnFn = warn,
) -> SkillSpec | None:
    """Validate a source skill folder and return a renderable spec."""
    source_file = skill_dir / "SKILL.md"
    if not source_file.is_file():
        on_warning(f"No SKILL.md found in {skill_dir} (skipping)")
        return None

    expected_template = f"{SKILL_PREFIX_PLACEHOLDER}-{command_slug}"
    declared_name_template = read_frontmatter_name(source_file)
    if declared_name_template != expected_template:
        on_warning(
            f"{skill_dir}: SKILL.md name must be '{expected_template}' "
            f"(found '{declared_name_template or '<missing>'}')"
        )
        return None

    return SkillSpec(
        command_name=f"{skill_prefix}-{command_slug}",
        command_slug=command_slug,
        skill_prefix=skill_prefix,
        source_dir=skill_dir,
        source_label=source_label,
        source_kind=source_kind,
        source_key=source_key,
        source_repo=source_repo,
        grimoire_path=grimoire_path,
    )


def collect_framework_skill_specs(on_warning: WarnFn = warn) -> list[SkillSpec]:
    """Collect the framework's skills from its command families."""
    specs: list[SkillSpec] = []
    for family in load_framework_skill_families(on_warning):
        skills_dir = family["path"]
        if not skills_dir.is_dir():
            on_warning(f"Framework: no skills directory for family '{family['name']}' at {skills_dir}")
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not is_valid_skill_slug(skill_dir.name):
                on_warning(f"{skill_dir}: invalid skill directory slug (skipping)")
                continue
            command_slug = (
                f"{family['slug_prefix']}-{skill_dir.name}"
                if family["slug_prefix"]
                else skill_dir.name
            )
            spec = build_skill_spec(
                skill_dir,
                family["skill_prefix"],
                command_slug,
                source_label=f"Framework/{family['name']}",
                source_kind="framework",
                source_key=family["name"],
                source_repo="framework",
                on_warning=on_warning,
            )
            if spec:
                specs.append(spec)
    return specs


def collect_one_grimoire_skill_specs(grimoire_root: Path, label: str, on_warning: WarnFn = warn) -> list[SkillSpec]:
    """Collect skills from one grimoire root."""
    if not grimoire_root.is_dir():
        info(f"{label}: directory not found at {grimoire_root} (skipping)")
        return []

    skills_dir = grimoire_root / "skills"
    if not skills_dir.is_dir():
        info(f"{label}: no skills/ directory (skipping)")
        return []

    metadata = load_grimoire_metadata(grimoire_root, label, on_warning)
    if metadata is None:
        return []

    source_label = metadata.get("name") or label
    specs: list[SkillSpec] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if not is_valid_skill_slug(skill_dir.name):
            on_warning(f"{skill_dir}: invalid skill directory slug (skipping)")
            continue
        spec = build_skill_spec(
            skill_dir,
            metadata["skill_prefix"],
            skill_dir.name,
            source_label=source_label,
            source_kind="grimoire",
            source_key=label,
            source_repo=source_label,
            grimoire_path=str(grimoire_root),
            on_warning=on_warning,
        )
        if spec:
            specs.append(spec)
    return specs


def grimoire_roots(grimoire_path: str | None, on_warning: WarnFn = warn) -> list[tuple[str, Path]]:
    """Return (label, folder) for each grimoire a run covers.

    `--grimoire PATH` covers that folder alone; otherwise every library entry
    whose `local_path` names one folder. An entry with an empty or relative
    `local_path` would resolve to the working directory, so it is reported and
    skipped.
    """
    if grimoire_path:
        root = resolve_local_path(str(grimoire_path), resolve=True)
        return [(root.name, root)]

    if not LOCAL_LIBRARY.is_file():
        info(f"No local library at {LOCAL_LIBRARY} - skipping grimoire skills")
        return []
    library, reason = read_library(LOCAL_LIBRARY)
    if library is None:
        on_warning(f"could not read library: {reason} (treating as empty)")
        return []

    roots: list[tuple[str, Path]] = []
    for key in sorted(library["grimoires"]):
        entry = library["grimoires"][key]
        raw = entry.get("local_path") if isinstance(entry, dict) else None
        if not is_usable_local_path(raw):
            on_warning(f"{key}: library local_path is empty or relative (skipping)")
            continue
        roots.append((key, resolve_local_path(raw, resolve=True)))
    return roots


def managed_prefixes(roots: Iterable[Path], on_warning: WarnFn = warn) -> tuple[str, ...]:
    """Return the folder-name prefixes (`grm-`, `cook-`) this rite owns in a skills folder.

    Prefix membership is ownership: every folder whose name starts with one of
    these is a generated skill, and when it is not in the current catalog it is
    stale and is removed (reset, stale cleanup and deprecated-location cleanup
    all use this set, and no ownership marker is read). The set is the
    framework's family prefixes and the `skill_prefix` of
    every grimoire manifest in `roots`, whether or not that grimoire still ships
    skills. A manifest that cannot be read adds nothing; collection reports it.
    """
    prefixes = {family["skill_prefix"] for family in load_framework_skill_families(on_warning)}
    for root in roots:
        metadata, errors = load_manifest(root)
        if metadata is not None and not errors:
            prefixes.add(metadata["skill_prefix"])
    return tuple(f"{prefix}-" for prefix in sorted(prefixes))


def collect_catalog(grimoire_path: str | None = None, on_warning: WarnFn = warn) -> Catalog:
    """Collect the desired skills and managed prefixes for one invocation."""
    roots = grimoire_roots(grimoire_path, on_warning)
    specs = collect_framework_skill_specs(on_warning)
    for label, root in roots:
        specs.extend(collect_one_grimoire_skill_specs(root, label, on_warning))
    return Catalog(specs, managed_prefixes((root for _label, root in roots), on_warning))


def ownership_payload(spec: SkillSpec) -> dict[str, Any]:
    """Return the ownership metadata embedded in generated SKILL.md files."""
    return {
        "schema_version": OWNERSHIP_SCHEMA_VERSION,
        "generation": REGISTER_GENERATION,
        "registered_by": "framework",
        "command": f"/{spec.command_name}",
        "source_kind": spec.source_kind,
        "source_key": spec.source_key,
        "source_label": spec.source_label,
        "source_repo": spec.source_repo,
        "source_path": str((spec.source_dir / "SKILL.md").resolve()),
        "grimoire_path": spec.grimoire_path,
    }


def ownership_comment(payload: dict[str, Any]) -> str:
    """Render a single-line ownership comment for SKILL.md."""
    return f"<!-- {OWNERSHIP_MARKER} {json.dumps(payload, sort_keys=True)} -->"


def insert_after_frontmatter(content: str, block: str) -> str:
    """Return `content` with `block` on the lines that follow its frontmatter (or at the top)."""
    bounds = frontmatter_bounds(content)
    if bounds is None:
        return f"{block}\n{content}"
    insert_at = bounds[1] + len("\n---")
    return f"{content[:insert_at]}\n{block}\n{content[insert_at:]}"


def insert_ownership_comment(content: str, spec: SkillSpec) -> str:
    """Insert generated ownership metadata after frontmatter."""
    marker = ownership_comment(ownership_payload(spec))
    provenance = (
        f"<!-- GENERATED - source: {spec.source_dir}/SKILL.md | "
        "DO NOT EDIT this file. Edit the source and run /grm-update skills. -->"
    )
    return insert_after_frontmatter(content, f"{marker}\n{provenance}")


# A source skill pulls in its invocation (or a grimoire playbook) with a
# dynamic-context line: !`cat <path>`. Agents only honour that directive for
# files inside the session's working directories, so a skill registered in
# ~/.claude/skills fails to load whenever the framework or grimoire is outside the
# repository the user opened - which is every project-repo session. The rite
# therefore inlines the file at registration: the generated skill is
# self-contained, no shell runs when it loads, and no working directory matters.
INLINE_DIRECTIVE_RE = re.compile(r'^!`cat\s+"?([^"`]+?)"?`\s*$', re.MULTILINE)
INLINE_MAX_DEPTH = 3


def strip_frontmatter(content: str) -> str:
    """Return a Markdown document without its leading YAML frontmatter block."""
    bounds = frontmatter_bounds(content)
    if bounds is None:
        return content
    return content[bounds[1] + len("\n---"):].lstrip("\n")


def substitute_placeholders(text: str, spec: SkillSpec, *, skill_prefix: bool) -> str:
    """Resolve the placeholders a source skill may carry, for the framework checkout it runs from.

    `{{FRAMEWORK_PATH}}`, `FRAMEWORK_HOME/` and (for a grimoire skill)
    `{{GRIMOIRE_PATH}}` become concrete paths, so the agent needs no lookup and
    a directive written with them resolves at registration. `{{SKILL_PREFIX}}`
    is resolved only when `skill_prefix` is true: a skill's own text names its
    command with it, and text inlined from an invocation keeps the token so a
    playbook can show it.
    """
    framework_path = FRAMEWORK_PATH.as_posix()
    if skill_prefix:
        text = text.replace(SKILL_PREFIX_PLACEHOLDER, spec.skill_prefix)
    text = text.replace("{{FRAMEWORK_PATH}}", framework_path)
    text = text.replace("FRAMEWORK_HOME/", f"{framework_path}/")
    if spec.grimoire_path:
        text = text.replace("{{GRIMOIRE_PATH}}", Path(spec.grimoire_path).as_posix())
    return text


def inline_dynamic_context(
    content: str,
    origin: Path,
    substitute: Callable[[str], str],
    depth: int = 0,
    seen: set[str] | None = None,
    on_warning: WarnFn = warn,
) -> str:
    """Replace every !`cat <path>` line with the file it names.

    `substitute` is applied to each inlined text, because an invocation may
    itself carry a directive written with `{{FRAMEWORK_PATH}}`. The inlined text
    is wrapped in BEGIN/END INLINED comments naming the file so a reader can
    trace it to its source; its own frontmatter is dropped. A directive whose
    file cannot be read is left in place with a warning, so the failure shows at
    registration rather than at load.
    """
    if seen is None:
        seen = set()

    def replace(match: re.Match[str]) -> str:
        target = Path(match.group(1).strip())
        label = target.as_posix()
        if label in seen:
            # A skill and its invocation may both pull in the same fragment
            # (the grimoire directory guard); one copy is enough.
            return f"<!-- INLINED ABOVE: {label} -->"
        try:
            text = read_utf8(target)
        except (OSError, UnicodeDecodeError) as exc:
            on_warning(f"{origin}: cannot inline {label} ({exc}); directive left in place")
            return match.group(0)
        seen.add(label)
        text = substitute(strip_frontmatter(text)).rstrip("\n")
        if depth + 1 < INLINE_MAX_DEPTH:
            text = inline_dynamic_context(text, target, substitute, depth + 1, seen, on_warning)
        return f"<!-- BEGIN INLINED: {label} -->\n{text}\n<!-- END INLINED: {label} -->"

    return INLINE_DIRECTIVE_RE.sub(replace, content)


def render_skill_body(spec: SkillSpec, on_warning: WarnFn = warn) -> str:
    """Return a skill's SKILL.md with placeholders resolved and every invocation inlined."""
    source = spec.source_dir / "SKILL.md"
    content = substitute_placeholders(read_utf8(source), spec, skill_prefix=True)
    return inline_dynamic_context(
        content,
        source,
        lambda text: substitute_placeholders(text, spec, skill_prefix=False),
        on_warning=on_warning,
    )


def render_skill_files(spec: SkillSpec, pointer_only: bool, on_warning: WarnFn = warn) -> dict[str, str]:
    """Render files for one installed skill."""
    rendered: dict[str, str] = {}
    for source in sorted(spec.source_dir.iterdir()):
        if not source.is_file():
            continue
        if source.name == "SKILL.md":
            rendered[source.name] = insert_ownership_comment(render_skill_body(spec, on_warning), spec)
        elif not pointer_only:
            rendered[source.name] = substitute_placeholders(read_utf8(source), spec, skill_prefix=True)
    return rendered


def detect_prefix_collisions(specs: list[SkillSpec]) -> list[PlanAction]:
    """Return blocking actions for source-level prefix collisions."""
    actions: list[PlanAction] = []
    framework_prefixes = {
        spec.skill_prefix
        for spec in specs
        if spec.source_kind == "framework"
    }
    grimoire_sources: dict[tuple[str, str], SkillSpec] = {}
    for spec in specs:
        if spec.source_kind != "grimoire":
            continue
        key = (spec.skill_prefix, spec.source_key)
        grimoire_sources.setdefault(key, spec)

    by_prefix: dict[str, list[SkillSpec]] = {}
    for (prefix, _source_key), spec in grimoire_sources.items():
        by_prefix.setdefault(prefix, []).append(spec)

    for prefix, prefix_specs in sorted(by_prefix.items()):
        if prefix in framework_prefixes:
            labels = ", ".join(sorted({spec.source_label for spec in prefix_specs}))
            actions.append(PlanAction(
                action="collision",
                command_name=f"{prefix}-*",
                target_dir=Path(),
                reason=f"grimoire prefix {prefix!r} conflicts with framework command families ({labels})",
            ))
        if len(prefix_specs) > 1:
            labels = ", ".join(sorted({spec.source_label for spec in prefix_specs}))
            actions.append(PlanAction(
                action="collision",
                command_name=f"{prefix}-*",
                target_dir=Path(),
                reason=f"grimoire prefix {prefix!r} is used by multiple grimoires: {labels}",
            ))
    return actions


def detect_command_collisions(specs: list[SkillSpec]) -> list[PlanAction]:
    """Return blocking actions for duplicate desired command names."""
    by_command: dict[str, list[SkillSpec]] = {}
    for spec in specs:
        by_command.setdefault(spec.command_name, []).append(spec)

    actions: list[PlanAction] = []
    for command_name, command_specs in sorted(by_command.items()):
        if len(command_specs) <= 1:
            continue
        labels = ", ".join(
            f"{spec.source_label} ({spec.source_dir})"
            for spec in command_specs
        )
        actions.append(PlanAction(
            action="collision",
            command_name=command_name,
            target_dir=Path(),
            reason=f"multiple sources want /{command_name}: {labels}",
        ))
    return actions


def build_registration_plan(
    skills_target: Path,
    specs: list[SkillSpec],
    prefixes: tuple[str, ...],
    after_reset: bool = False,
) -> dict[str, Any]:
    """Build the create/update/cleanup plan for a collision-free catalog.

    `after_reset` plans as if every managed folder had been removed first: no
    stale scan, and every desired skill is a create.
    """
    desired = {spec.command_name: spec for spec in specs}
    actions: list[PlanAction] = []
    blocking: list[PlanAction] = []

    if skills_target.is_dir() and not after_reset:
        for skill_dir in sorted(skills_target.iterdir()):
            if not skill_dir.is_dir() or not skill_dir.name.startswith(prefixes):
                continue
            if skill_dir.name in desired:
                continue
            actions.append(PlanAction(
                action="cleanup",
                command_name=skill_dir.name,
                target_dir=skill_dir,
                reason="stale skill in a managed namespace (not in the current catalog)",
            ))

    for command_name, spec in sorted(desired.items()):
        target_dir = skills_target / command_name
        if target_dir.exists() and not target_dir.is_dir():
            blocking.append(PlanAction(
                action="collision",
                command_name=command_name,
                target_dir=target_dir,
                spec=spec,
                reason="target path exists but is not a directory",
            ))
            continue
        actions.append(PlanAction(
            action="update" if target_dir.is_dir() and not after_reset else "create",
            command_name=command_name,
            target_dir=target_dir,
            spec=spec,
        ))

    return {"actions": actions, "blocked": blocking}


def reset_managed_skill_dirs(
    skills_target: Path,
    prefixes: tuple[str, ...],
    dry_run: bool,
    on_warning: WarnFn = warn,
) -> int:
    """Remove every folder under a managed prefix before registering; return the count."""
    if not skills_target.is_dir():
        return 0

    reset_count = 0
    for skill_dir in sorted(skills_target.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith(prefixes):
            continue
        verb = "Would reset managed namespace" if dry_run else "Reset managed namespace"
        info(f"{verb}: /{skill_dir.name}")
        if dry_run or remove_managed_skill_dir(skill_dir, skills_target, on_warning):
            reset_count += 1
    return reset_count


def print_plan(plan: dict[str, Any], dry_run: bool) -> None:
    """Print the registration plan in stable, greppable language."""
    for action in plan["blocked"]:
        target = f" at {action.target_dir}" if str(action.target_dir) not in {"", "."} else ""
        warn(f"Collision: /{action.command_name}{target} - {action.reason}")

    for action in plan["actions"]:
        if action.action == "cleanup":
            verb = "Would clean stale" if dry_run else "Clean stale"
            info(f"{verb}: /{action.command_name}")
        elif action.action in {"create", "update"}:
            verb = (
                f"Would {action.action}"
                if dry_run
                else f"Plan {action.action}"
            )
            label = action.spec.source_label if action.spec else "unknown"
            info(f"{verb}: /{action.command_name} ({label})")


def is_direct_child(skill_dir: Path, skills_target: Path, on_warning: WarnFn = warn) -> bool:
    """Return True when `skill_dir` sits directly under `skills_target`, symbolic links resolved."""
    try:
        if skill_dir.resolve().parent != skills_target.resolve():
            on_warning(f"Refusing to touch out-of-scope skill directory: {skill_dir}")
            return False
    except OSError as exc:
        on_warning(f"Could not resolve {skill_dir}: {exc}")
        return False
    return True


def remove_managed_skill_dir(skill_dir: Path, skills_target: Path, on_warning: WarnFn = warn) -> bool:
    """Remove a managed skill folder that sits directly under the skills target."""
    if not is_direct_child(skill_dir, skills_target, on_warning):
        return False
    shutil.rmtree(skill_dir)
    return True


def write_rendered_skill(
    spec: SkillSpec,
    target_dir: Path,
    skills_target: Path,
    pointer_only: bool,
    on_warning: WarnFn = warn,
) -> bool:
    """Write one generated skill folder, replacing any folder already there.

    The new folder is written beside the target and swapped in by renaming: the
    previous folder is renamed aside first and put back when the swap fails, so
    a failure leaves the old skill in place. Returns False when nothing was
    replaced.
    """
    if target_dir.exists() and not is_direct_child(target_dir, skills_target, on_warning):
        return False

    staging = target_dir.with_name(target_dir.name + ".tmp")
    previous = target_dir.with_name(target_dir.name + ".old")
    try:
        for leftover in (staging, previous):
            if leftover.exists():
                shutil.rmtree(leftover)
        staging.mkdir(parents=True)
        for filename, content in render_skill_files(spec, pointer_only, on_warning).items():
            with open(staging / filename, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)

        moved_aside = target_dir.exists()
        if moved_aside:
            os.replace(target_dir, previous)
        try:
            os.replace(staging, target_dir)
        except OSError:
            if moved_aside:
                os.replace(previous, target_dir)
            raise
    except OSError as exc:
        on_warning(f"Could not register /{spec.command_name}: {exc}")
        shutil.rmtree(staging, ignore_errors=True)
        return False

    shutil.rmtree(previous, ignore_errors=True)
    ok(f"Registered: /{spec.command_name} ({spec.source_label})")
    return True


def apply_registration_plan(
    plan: dict[str, Any],
    skills_target: Path,
    pointer_only: bool,
    reporter: ResultReporter | None = None,
    label: str = "",
    on_warning: WarnFn = warn,
) -> tuple[int, int]:
    """Apply a collision-free registration plan. Returns (registered, cleaned).

    When a reporter is supplied, each successful clean/register is recorded as a
    mutation so the JSON envelope reflects exactly what was written.
    """
    if plan["blocked"]:
        return 0, 0

    skills_target.mkdir(parents=True, exist_ok=True)

    cleaned = 0
    registered = 0
    for action in plan["actions"]:
        if action.action == "cleanup":
            if remove_managed_skill_dir(action.target_dir, skills_target, on_warning):
                cleaned += 1
                if reporter is not None:
                    reporter.mutation("remove", path=action.target_dir, detail=f"/{action.command_name} ({label})")

    for action in plan["actions"]:
        if action.action not in {"create", "update"} or action.spec is None:
            continue
        if write_rendered_skill(
            action.spec,
            action.target_dir,
            skills_target,
            pointer_only,
            on_warning,
        ):
            registered += 1
            if reporter is not None:
                reporter.mutation("register", path=action.target_dir, detail=f"/{action.command_name} ({label})")

    return registered, cleaned


def clean_deprecated_targets(
    config: dict[str, Any],
    prefixes: tuple[str, ...],
    dry_run: bool,
    reporter: ResultReporter | None = None,
    label: str = "",
    on_warning: WarnFn = warn,
) -> int:
    """Remove managed-prefix skills from a target's secondary skill directories.

    Codex reads ~/.codex/skills as well as ~/.agents/skills, so a managed copy
    left there would shadow or duplicate the registered one. A folder outside
    every managed prefix is never removed.
    """
    cleaned = 0
    for old_root in config.get("deprecated_paths", []) or []:
        if not old_root.is_dir():
            continue
        for skill_dir in sorted(old_root.iterdir()):
            if not skill_dir.is_dir() or not skill_dir.name.startswith(prefixes):
                continue
            if dry_run:
                info(f"Would clean deprecated location: {skill_dir}")
                if reporter is not None:
                    reporter.message("info", f"would clean deprecated /{skill_dir.name} ({label})", path=skill_dir)
                cleaned += 1
            elif remove_managed_skill_dir(skill_dir, old_root, on_warning):
                info(f"Cleaned deprecated location: {skill_dir}")
                if reporter is not None:
                    reporter.mutation("remove", path=skill_dir, detail=f"/{skill_dir.name} ({label}, deprecated location)")
                cleaned += 1
    return cleaned


def selected_targets(agent: str) -> list[tuple[str, dict[str, Any]]]:
    """Return (id, configuration) for the requested agent.

    "all" is every agent installed on this machine, read when asked. An id names
    its target whether or not that agent is installed; an unknown id raises KeyError.
    """
    if agent == "all":
        return list(installed_skill_targets(FRAMEWORK_PATH).items())
    return [(agent, skill_registration_targets(FRAMEWORK_PATH)[agent])]


def register_target(
    agent_name: str,
    config: dict[str, Any],
    dry_run: bool = False,
    grimoire_path: str | None = None,
    reset_managed: bool = False,
    reporter: ResultReporter | None = None,
    catalog: Catalog | None = None,
    on_warning: WarnFn = warn,
):
    """Plan and optionally register all skills for one agent target."""
    label = config["label"]
    skills_target = config["path"]
    pointer_only = config["pointer_only"]

    print(f"  Target: {label} ({skills_target})")
    if pointer_only:
        info("Pointer-only registration - copying SKILL.md files only")

    if catalog is None:
        catalog = collect_catalog(grimoire_path, on_warning)
    specs = catalog.specs
    # An agent that has a framework plugin installed gets framework commands
    # from plugins only: flat copies would duplicate /grimoire:* as /grm-*, and a
    # family without its plugin (the maintainer verbs) stays off that agent until
    # its plugin is installed. Flat framework skills that exist are cleaned as stale.
    if config.get("plugin_families"):
        specs = [spec for spec in specs if spec.source_kind != "framework"]
        info("Plugin mode: framework commands are served by the Claude Code plugins; registering grimoire skills only")

    blocking = detect_prefix_collisions(specs) + detect_command_collisions(specs)
    reset_count = 0
    if blocking:
        plan = {"actions": [], "blocked": blocking}
    else:
        if reset_managed:
            reset_count = reset_managed_skill_dirs(skills_target, catalog.prefixes, dry_run, on_warning)
        plan = build_registration_plan(skills_target, specs, catalog.prefixes, after_reset=reset_managed)
    print_plan(plan, dry_run)

    # Record collisions as messages on every run; in dry-run, also record the
    # planned creates/updates/cleanups as messages (plan mode writes nothing, so
    # they are not mutations). Apply-mode mutations are recorded inside
    # apply_registration_plan.
    if reporter is not None:
        for action in plan["blocked"]:
            target = action.target_dir if str(action.target_dir) not in {"", "."} else None
            reporter.message("error", f"collision /{action.command_name} ({label}): {action.reason}", path=target)
        if dry_run:
            for action in plan["actions"]:
                if action.action in {"create", "update", "cleanup"}:
                    reporter.message("info", f"would {action.action} /{action.command_name} ({label})", path=action.target_dir)

    planned_registered = sum(
        1 for action in plan["actions"] if action.action in {"create", "update"}
    )
    planned_cleaned = sum(1 for action in plan["actions"] if action.action == "cleanup")
    blocked = len(plan["blocked"])

    applied_registered = 0
    applied_cleaned = 0
    if not dry_run and not blocked:
        applied_registered, applied_cleaned = apply_registration_plan(
            plan,
            skills_target,
            pointer_only,
            reporter=reporter,
            label=label,
            on_warning=on_warning,
        )

    deprecated_cleaned = 0
    if not blocked:
        deprecated_cleaned = clean_deprecated_targets(
            config, catalog.prefixes, dry_run, reporter=reporter, label=label, on_warning=on_warning
        )

    registered = planned_registered if dry_run else applied_registered
    cleaned = (planned_cleaned if dry_run else applied_cleaned) + deprecated_cleaned
    action = "would register" if dry_run else "registered"
    cleanup_action = "would clean" if dry_run else "cleaned"

    print()
    print(f"  {label}: {action} {registered} skill(s)")
    if cleaned > 0:
        print(f"  {label}: {cleanup_action} {cleaned} stale skill(s)")
    if reset_count > 0:
        reset_action = "would reset" if dry_run else "reset"
        print(f"  {label}: {reset_action} {reset_count} managed namespace skill dir(s)")
    if blocked > 0:
        print(f"  {label}: blocked by {blocked} collision(s)")
    print()

    return {
        "agent": agent_name,
        "label": label,
        "registered": registered,
        "cleaned": cleaned,
        "reset": reset_count,
        "blocked": blocked,
        "mode": "plan" if dry_run else "apply",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grimoire Skill Registration")
    parser.add_argument(
        "--agent",
        default="all",
        help=(
            "Agent skill target id from rites/data/agent_targets.json; an id is used "
            "even when that agent is not installed (default: all, the installed agents)"
        ),
    )
    parser.add_argument(
        "--grimoire",
        help="Register only this grimoire's skills, plus the framework's own",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--reset-managed",
        action="store_true",
        help=(
            "Remove every skill dir in the managed framework and grimoire namespaces "
            "before registering, then write the current catalog fresh. "
            "Use after major framework command-family changes."
        ),
    )
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    known = skill_registration_targets(FRAMEWORK_PATH)
    if args.agent != "all" and args.agent not in known:
        parser.error(f"unknown --agent {args.agent!r} (choose from: all, {', '.join(sorted(known))})")

    reporter = (
        None if human
        else ResultReporter("sync_skills", mode="plan" if args.dry_run else "apply")
    )
    reported: set[str] = set()

    def on_warning(text: str) -> None:
        if text in reported:
            return
        reported.add(text)
        warn(text)
        if reporter is not None:
            reporter.message("warning", text)

    # In json/jsonl mode the rite's human prose is suppressed so stdout carries
    # only the envelope; the structured outcome is captured into the reporter.
    sink = contextlib.nullcontext() if human else contextlib.redirect_stdout(io.StringIO())
    with sink:
        print()
        print("  Grimoire Skill Registration")
        print("  ----------------------------")
        print()

        if args.dry_run:
            info("Dry run mode - no files will be written")
            print()
        if args.grimoire:
            info(f"Grimoire scope: {resolve_local_path(args.grimoire, resolve=True)}")
            print()
        if args.reset_managed:
            info("Reset managed mode - managed namespace skill dirs will be replaced")
            print()

        catalog = collect_catalog(args.grimoire, on_warning)
        results = [
            register_target(
                agent_name,
                config,
                args.dry_run,
                args.grimoire,
                args.reset_managed,
                reporter=reporter,
                catalog=catalog,
                on_warning=on_warning,
            )
            for agent_name, config in selected_targets(args.agent)
        ]

        print()
        print("  ----------------------------")
        total_registered = sum(result["registered"] for result in results)
        total_cleaned = sum(result["cleaned"] for result in results)
        total_reset = sum(result["reset"] for result in results)
        total_blocked = sum(result["blocked"] for result in results)
        if args.dry_run:
            print(f"  Planned registrations: {total_registered} skill(s)")
            print(f"  Planned cleanups: {total_cleaned} stale skill(s)")
        else:
            print(f"  Registered: {total_registered} skill registration(s)")
            print(f"  Cleaned:    {total_cleaned} stale skill registration(s)")
        if total_reset:
            reset_label = "Planned reset" if args.dry_run else "Reset"
            print(f"  {reset_label}:      {total_reset} managed namespace skill dir(s)")
        if total_blocked:
            print(f"  Blocked:    {total_blocked} collision(s)")
        print()

        if not args.dry_run and total_registered > 0:
            labels = ", ".join(result["label"] for result in results)
            print(f"  Skills are now available for: {labels}.")
            print("  Try: /grm-help inside a grimoire, or /grm-create to start one")
            print()

    if reporter is not None:
        reporter.emit(args.format, summary={
            "registered": total_registered,
            "cleaned": total_cleaned,
            "reset": total_reset,
            "blocked": total_blocked,
        })

    if total_blocked and not args.dry_run:
        if human:
            print("  Resolve collisions before registration can write those targets.")
            print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
