#!/usr/bin/env python3
"""Validates framework structure completeness.

Checks the required directories and files, that no grimoire layer sits at the framework
root, that each router folder has its hub, that every docs/*.md page (and CONTRIBUTING.md)
is linked from both grimoire.md and README.md, and that the rite-profile, summoning and
agent-target contracts are valid.

Hub convention: for any folder F that acts as a router, the hub file is
F/<basename(F)>.md. The framework root hub is grimoire.md; the grm/ invocation router is
invocations/grm/grm.md.

Usage: python rites/validate_structure.py
Mutation profile: read-only.
Exit codes: 0 = success, 1 = validation errors found
"""

import re
import sys
from pathlib import Path

from _lib import default_framework_root, load_skill_families_checked
from agent_targets import target_entries, validate_agent_targets
from diagnostics import DiagnosticReporter, add_output_format_arg
from rite_profiles import profile_entries, validate_rite_profiles
from summon_contract import mode_entries, validate_summon_contract

FRAMEWORK_ROOT = default_framework_root()

# Folders whose hub file must exist with the folder-name convention.
HUB_DIRS = [
    "invocations/grm",
    "invocations/validators",
    "invocations/dev",
    "invocations/dev/quality",
    "invocations/meta",
]

# Required folders besides the hub folders and the skill-family folders, which
# framework.json declares.
OTHER_REQUIRED_DIRS = [
    "docs",
    "formulae",
    "formulae/grimoire",
    "rites",
    "resources",
    "skills",
]

REQUIRED_FILES = [
    "grimoire.md",
    "README.md",
    "UPDATE.md",
    "CHANGELOG.md",
    "VERSION",
    "framework.json",
    "rites/summon.sh",
    "rites/sync_skills.py",
    "docs/installation.md",
    "docs/agent_targets.md",
    "docs/summoning_contract.md",
    "docs/agent_configuration.md",
    "docs/operating_model.md",
    "docs/governance.md",
    "docs/reference.md",
    "docs/page_schema.md",
]

FORBIDDEN_GRIMOIRE_LAYER_PATHS = [
    "chapters",
    "inbox",
    "grimoire.json",
]

# Each contract: (heading, validator, entry counter, human tag, noun, `checked` key).
CONTRACTS = [
    ("Checking mutating rite profiles...", validate_rite_profiles, profile_entries,
     "PROFILE", "mutating rite profile(s)", "rite_profiles"),
    ("Checking Summoning Rite contract...", validate_summon_contract, mode_entries,
     "CONTRACT", "Summoning Rite mode(s)", "summon_modes"),
    ("Checking agent target registry...", validate_agent_targets, target_entries,
     "AGENT", "agent target(s)", "agent_targets"),
]


def required_dirs(root):
    """Return the required folders: the fixed ones, the hub folders and each skill family's."""
    families, _problems = load_skill_families_checked(root)
    family_dirs = [family["path"].relative_to(root).as_posix() for family in families]
    return [*OTHER_REQUIRED_DIRS, *HUB_DIRS, *family_dirs]


def mentions(text, target):
    """True when `text` names `target` as a whole path, not as the start of a longer one."""
    return re.search(r"(?<![\w/.-])" + re.escape(target) + r"(?![\w.-])", text) is not None


def _docs_files(root):
    """Return every docs/*.md page, sorted; empty when docs/ is absent."""
    docs = root / "docs"
    return sorted(docs.glob("*.md")) if docs.is_dir() else []


def doc_index_violations(root):
    """Return (code, path, message) for any docs/ page or CONTRIBUTING.md the
    routing surfaces fail to reference.

    A docs/ page must be reachable from both routing surfaces: grimoire.md (the vault
    hub, which links docs as `[[docs/<stem>|...]]`) and README.md (the public doc, which
    links them as `(docs/<name>)`). A link to `docs/agent_targets` does not count as a
    link to `docs/agent`. tests/test_doc_indexes.py asserts the same coverage through
    this function.
    """
    hub = root / "grimoire.md"
    readme = root / "README.md"
    hub_text = hub.read_text(encoding="utf-8", errors="replace") if hub.is_file() else None
    readme_text = readme.read_text(encoding="utf-8", errors="replace") if readme.is_file() else None

    violations = []
    for doc in _docs_files(root):
        if hub_text is not None and not mentions(hub_text, f"docs/{doc.stem}"):
            violations.append(("STRUCTURE_DOC_NOT_IN_HUB", f"docs/{doc.name}",
                               f"docs/{doc.name} is not routed from grimoire.md"))
        if readme_text is not None and not mentions(readme_text, f"docs/{doc.name}"):
            violations.append(("STRUCTURE_DOC_NOT_IN_README", f"docs/{doc.name}",
                               f"docs/{doc.name} is not linked from README.md"))

    if (root / "CONTRIBUTING.md").is_file():
        if hub_text is not None and "CONTRIBUTING" not in hub_text:
            violations.append(("STRUCTURE_DOC_NOT_IN_HUB", "CONTRIBUTING.md",
                               "CONTRIBUTING.md is not referenced from grimoire.md"))
        if readme_text is not None and "CONTRIBUTING" not in readme_text:
            violations.append(("STRUCTURE_DOC_NOT_IN_README", "CONTRIBUTING.md",
                               "CONTRIBUTING.md is not referenced from README.md"))
    return violations


def check_paths(reporter, human, heading, paths, code, kind, is_present):
    """Report each path that `is_present` rejects as an error with `code`."""
    if human:
        print(heading)
    for rel in paths:
        if not is_present(FRAMEWORK_ROOT / rel):
            reporter.error(code, f"missing {kind}: {rel}", path=rel)
            if human:
                print(f"  MISSING  {kind}: {rel}")
        elif human:
            print(f"  OK       {rel}")
    if human:
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate framework structure completeness")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_structure", FRAMEWORK_ROOT)

    if human:
        print()
        print("Validating Framework Structure")
        print("==================================")
        print(f"Framework root: {FRAMEWORK_ROOT}")
        print()

    directories = required_dirs(FRAMEWORK_ROOT)
    check_paths(reporter, human, "Checking required directories...", directories,
                "STRUCTURE_MISSING_DIR", "directory", Path.is_dir)
    check_paths(reporter, human, "Checking required files...", REQUIRED_FILES,
                "STRUCTURE_MISSING_FILE", "file", Path.is_file)

    if human:
        print("Checking framework root excludes grimoire layers...")
    for rel in FORBIDDEN_GRIMOIRE_LAYER_PATHS:
        if (FRAMEWORK_ROOT / rel).exists():
            reporter.error(
                "STRUCTURE_FORBIDDEN_GRIMOIRE_LAYER",
                "grimoire layer belongs in formulae/grimoire/",
                path=rel,
            )
            if human:
                print(f"  FORBIDDEN root path: {rel} (grimoire layer belongs in formulae/grimoire/)")
        elif human:
            print(f"  OK       no {rel}")
    if human:
        print()

    hubs = [f"{d}/{d.rsplit('/', 1)[-1]}.md" for d in HUB_DIRS]
    check_paths(reporter, human, "Checking router hub files (folder-name convention)...", hubs,
                "STRUCTURE_MISSING_HUB", "hub file", Path.is_file)

    if human:
        print("Checking documentation index coverage...")
    doc_violations = doc_index_violations(FRAMEWORK_ROOT)
    for code, path, message in doc_violations:
        reporter.error(code, message, path=path, docs_reference="docs/governance.md")
        if human:
            print(f"  MISSING  {message}")
    if human and not doc_violations:
        print("  OK       every docs/ page is routed from grimoire.md and linked from README.md")
    if human:
        print()

    counts = {}
    for heading, validate_contract, entries, tag, noun, key in CONTRACTS:
        if human:
            print(heading)
        contract, errors = validate_contract(FRAMEWORK_ROOT)
        for error in errors:
            reporter.error(
                error["code"],
                error["message"],
                path=error.get("path"),
                hint=error.get("hint"),
            )
            if human:
                print(f"  {tag:<8} {error.get('path', '-')}: {error['message']}")
        counts[key] = len(entries(contract)) if contract is not None else 0
        if human and not errors:
            print(f"  OK       {counts[key]} {noun}")
        if human:
            print()

    if not human:
        reporter.emit(
            args.format,
            checked={
                "required_directories": len(directories),
                "required_files": len(REQUIRED_FILES),
                "hub_directories": len(HUB_DIRS),
                **counts,
            },
        )
        return reporter.exit_code()

    print("==================================")
    if reporter.error_count() == 0:
        print("Structure validation passed")
        return 0
    print(f"Structure validation failed with {reporter.error_count()} errors")
    return 1


if __name__ == "__main__":
    sys.exit(main())
