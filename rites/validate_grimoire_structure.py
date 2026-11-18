#!/usr/bin/env python3
"""Validates a grimoire's structure against framework conventions.

Required at the grimoire root:
    <name>.md             (root hub; `name` from grimoire.json, else the folder's name)
    README.md
    grimoire.json
    chapters/             (LLM-authored knowledge)

For each chapter folder F, the hub file F/F.md must exist (folder-name
convention). Sub-chapters follow the same rule recursively.

The folder-name convention is enforced as an if-and-only-if under chapters/: a
folder-named page (the root hub and each F/F.md) must declare `type: hub`, and a
page that declares `type: hub` must be folder-named. This lets an agent tell hubs
from leaves by path alone. Demonstrative asset folders are exempt.

Managed scaffold files (.editorconfig, .gitattributes, .obsidian/app.json and the layer
READMEs) must match the framework's formulae byte for byte. Seeded files (.gitignore,
.obsidian/graph.json) are the grimoire's own once present: a missing one is a warning, and
their content is not compared.

Usage:
    python rites/validate_grimoire_structure.py [--grimoire <path>]

Mutation profile: read-only.
Exit codes: 0 = compliant (warnings do not change it), 1 = violations
"""

import argparse
import filecmp
import json
import sys
from pathlib import Path

from _lib import (
    default_framework_root,
    is_hub,
    is_inside_colocated_source_dir,
    load_manifest,
    page_type,
    read_utf8,
    resolve_grimoire_arg,
    root_hub_path,
    walk_files,
)
from diagnostics import DiagnosticReporter, add_output_format_arg
from scaffold_contract import (
    ScaffoldContractError,
    json_requirements,
    load_scaffold_contract,
    managed_scaffold_files,
    required_customized_files,
    seeded_scaffold_files,
    required_directories,
    validate_contract_against_formula,
)
from stage_publish import ASSET_FOLDERS


# Folders of demonstrative or supporting files: not routers, so they need no hub.


def declared_type(path):
    """Return a page's declared frontmatter `type`, or "" when unreadable or absent."""
    try:
        return page_type(read_utf8(path))
    except (OSError, UnicodeDecodeError):
        return ""


def is_asset_folder(folder, root):
    """True for a folder under an asset folder, a chapter-local sources/ folder, or a
    `<placeholder>` folder."""
    rel = folder.relative_to(root)
    if is_inside_colocated_source_dir(rel):
        return True
    return any(
        part.casefold() in ASSET_FOLDERS or "<" in part or ">" in part
        for part in rel.parts
    )


def chapter_folders_with_markdown(chapters, markdown_files):
    """Return, sorted, every folder under `chapters` that holds Markdown at any depth."""
    folders = set()
    for page in markdown_files:
        folder = page.parent
        while folder != chapters:
            folders.add(folder)
            folder = folder.parent
    return sorted(folders)


def main():
    parser = argparse.ArgumentParser(description="Validate grimoire structure")
    parser.add_argument("--grimoire", type=Path, default=Path.cwd(),
                        help="Grimoire root (default: cwd)")
    add_output_format_arg(parser)
    args = parser.parse_args()
    root = resolve_grimoire_arg(args.grimoire)
    framework_root = default_framework_root()
    formula_root = framework_root / "formulae" / "grimoire"
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_grimoire_structure", root)

    if human:
        print()
        print("Validating Grimoire Structure")
        print("==================================")
        print(f"Grimoire root: {root}")
        print()

    try:
        scaffold_contract = load_scaffold_contract(framework_root)
    except ScaffoldContractError as exc:
        reporter.error("GRIMOIRE_STRUCTURE_CONTRACT_READ", str(exc))
        if not human:
            reporter.emit(args.format)
            return reporter.exit_code()
        print(f"  WARN     {exc}")
        print()
        print("==================================")
        print("Grimoire structure validation failed with 1 issue(s)")
        return 1

    for contract_error in validate_contract_against_formula(scaffold_contract, formula_root):
        reporter.error("GRIMOIRE_STRUCTURE_CONTRACT", contract_error)
        if human:
            print(f"  WARN     scaffold contract error: {contract_error}")

    # 1. Manifest must exist, parse, and declare both 'name' and a valid skill_prefix.
    manifest = None
    if not (root / "grimoire.json").is_file():
        reporter.error("GRIMOIRE_STRUCTURE_MISSING_MANIFEST", "missing grimoire.json", path="grimoire.json")
        if human:
            print("  MISSING  grimoire.json")
    else:
        manifest, manifest_errors = load_manifest(root)
        if manifest is None:
            # load_manifest reports the cause in errors[0].
            reporter.error("GRIMOIRE_STRUCTURE_INVALID_MANIFEST", manifest_errors[0], path="grimoire.json")
            if human:
                print(f"  WARN     {manifest_errors[0]}")
        else:
            for err_msg in manifest_errors:
                reporter.error("GRIMOIRE_STRUCTURE_INVALID_MANIFEST", err_msg, path="grimoire.json")
                if human:
                    print(f"  WARN     {err_msg}")
            if human:
                print(f"  OK       grimoire.json (name={manifest.get('name', root.name)})")

    # 2. Required root files (other than the dynamic hub name).
    for f in required_customized_files(scaffold_contract):
        if not (root / f).is_file():
            reporter.error("GRIMOIRE_STRUCTURE_MISSING_FILE", f"missing file: {f}", path=f)
            if human:
                print(f"  MISSING  file: {f}")
        elif human:
            print(f"  OK       {f}")

    # 3. Root hub.
    root_hub = root_hub_path(root, manifest)
    if not root_hub.is_file():
        name = manifest.get("name") if isinstance(manifest, dict) else None
        expected = f"{name if isinstance(name, str) and name else root.name}.md"
        reporter.error(
            "GRIMOIRE_STRUCTURE_MISSING_ROOT_HUB",
            f"missing root hub: {expected}",
            path=expected,
        )
        if human:
            print(f"  MISSING  root hub: {expected}")
    else:
        root_hub_type = declared_type(root_hub)
        if root_hub_type != "hub":
            reporter.error(
                "GRIMOIRE_STRUCTURE_HUB_NOT_DECLARED",
                f"root hub {root_hub.name} must declare type: hub (found type: {root_hub_type or 'none'})",
                path=root_hub.name,
                docs_reference="docs/operating_model.md",
            )
            if human:
                print(f"  WARN     root hub {root_hub.name} must declare type: hub (found {root_hub_type or 'none'})")
        elif human:
            print(f"  OK       {root_hub.name}")

    # 4. Required scaffold directories.
    for d in required_directories(scaffold_contract):
        if not (root / d).is_dir():
            reporter.error("GRIMOIRE_STRUCTURE_MISSING_DIR", f"missing directory: {d}", path=d)
            if human:
                print(f"  MISSING  directory: {d}")
        else:
            if human:
                print(f"  OK       {d}/")

    # 5. Hub files inside chapters/ (folder-name convention, recursive). Asset folders,
    # chapter-local sources/ folders and `<placeholder>` folders are not routers and need
    # no hub. `publish` is a chapter name here, not the build layer.
    chapters = root / "chapters"
    chapter_pages = walk_files(chapters, "*.md", root_prune=()) if chapters.is_dir() else []
    if chapter_pages:
        if human:
            print()
            print("Checking chapter hubs (folder-name convention)...")
        for folder in chapter_folders_with_markdown(chapters, chapter_pages):
            if is_asset_folder(folder, root):
                continue
            hub = folder / f"{folder.name}.md"
            hub_rel = hub.relative_to(root).as_posix()
            if not hub.is_file():
                reporter.error(
                    "GRIMOIRE_STRUCTURE_MISSING_CHAPTER_HUB",
                    f"missing hub: {hub_rel}",
                    path=hub_rel,
                )
                if human:
                    print(f"  MISSING  hub: {hub_rel}")
            else:
                hub_type = declared_type(hub)
                if hub_type != "hub":
                    reporter.error(
                        "GRIMOIRE_STRUCTURE_HUB_NOT_DECLARED",
                        f"hub {hub_rel} must declare type: hub (found type: {hub_type or 'none'})",
                        path=hub_rel,
                        docs_reference="docs/operating_model.md",
                    )
                    if human:
                        print(f"  WARN     hub {hub_rel} must declare type: hub (found {hub_type or 'none'})")
                elif human:
                    print(f"  OK       {hub_rel}")

    # 5b. Declared hubs must sit in a folder-named position (the reverse of the rule
    # above), so that under chapters/ a page is a hub exactly when its filename stem equals
    # its folder name, and an agent can tell hubs from leaves by path alone.
    for page in chapter_pages:
        if is_hub(page) or is_asset_folder(page.parent, root):
            continue
        if declared_type(page) == "hub":
            rel = page.relative_to(root).as_posix()
            reporter.error(
                "GRIMOIRE_STRUCTURE_HUB_MISPLACED",
                f"{rel} declares type: hub but is not a folder-named hub "
                f"(a hub here must be named {page.parent.name}.md)",
                path=rel,
                docs_reference="docs/operating_model.md",
            )
            if human:
                print(f"  WARN     {rel} declares type: hub but is not a folder-named hub")

    # 6. Managed scaffold files match the current framework formulae. They are
    # operational support files, not grimoire-specific content; the root README, root
    # hub and grimoire.json are customised per grimoire and are not compared.
    if formula_root.is_dir():
        if human:
            print()
            print("Checking managed scaffold files against current framework formulae...")
        for rel in managed_scaffold_files(scaffold_contract):
            expected = formula_root / rel
            actual = root / rel
            if not expected.is_file():
                reporter.error(
                    "GRIMOIRE_STRUCTURE_FORMULA_MISSING_MANAGED",
                    f"Framework formula missing managed scaffold: {rel}",
                    path=rel,
                )
                if human:
                    print(f"  WARN     framework formula missing managed scaffold: {rel}")
            elif not actual.is_file():
                reporter.error("GRIMOIRE_STRUCTURE_MISSING_MANAGED", f"missing managed scaffold: {rel}", path=rel)
                if human:
                    print(f"  MISSING  managed scaffold: {rel}")
            elif not filecmp.cmp(expected, actual, shallow=False):
                reporter.error(
                    "GRIMOIRE_STRUCTURE_STALE_MANAGED",
                    f"managed scaffold differs from framework formula: {rel}",
                    path=rel,
                    hint=f"Copy from FRAMEWORK_HOME/formulae/grimoire/{rel}.",
                )
                if human:
                    print(f"  STALE    managed scaffold differs from framework formula: {rel}")
            else:
                if human:
                    print(f"  OK       {rel}")
    else:
        reporter.error("GRIMOIRE_STRUCTURE_FORMULA_ROOT_MISSING", f"Framework formula root missing: {formula_root}")
        if human:
            print(f"  WARN     framework formula root missing: {formula_root}")

    # 6b. Seeded scaffold files: copied in when absent and owned by the grimoire after
    # that, so absence is a warning the next update fixes and content is never compared.
    for rel in seeded_scaffold_files(scaffold_contract):
        if not (root / rel).is_file():
            reporter.warning(
                "GRIMOIRE_STRUCTURE_MISSING_SEEDED",
                f"missing seeded scaffold: {rel}",
                path=rel,
                hint="Run /grm-update to seed it, or copy FRAMEWORK_HOME/formulae/grimoire/ yourself.",
            )
            if human:
                print(f"  WARN     missing seeded scaffold: {rel} (heal seeds it)")
        elif human:
            print(f"  OK       {rel} (seeded, grimoire-owned)")

    # 7. JSON requirements from the scaffold contract.
    for requirement in json_requirements(scaffold_contract):
        rel = requirement["path"]
        actual = root / rel
        if not actual.is_file():
            reporter.error("GRIMOIRE_STRUCTURE_JSON_MISSING", f"{rel} missing", path=rel)
            if human:
                print(f"  WARN     {rel} missing")
            continue
        try:
            cfg = json.loads(read_utf8(actual))
            if not isinstance(cfg, dict):
                raise ValueError("expected a JSON object")
        except (ValueError, OSError) as exc:
            reporter.error("GRIMOIRE_STRUCTURE_JSON_UNREADABLE", f"{rel} unreadable: {exc}", path=rel)
            if human:
                print(f"  WARN     {rel} unreadable: {exc}")
            continue

        for key, expected_value in requirement["required_values"].items():
            actual_value = cfg.get(key)
            if actual_value != expected_value:
                reporter.error(
                    "GRIMOIRE_STRUCTURE_JSON_VALUE",
                    f"{rel} must set {key!r} to {expected_value!r} (got {actual_value!r})",
                    path=rel,
                )
                if human:
                    print(
                        f"  WARN     {rel} must set {key!r} to {expected_value!r} "
                        f"(got {actual_value!r})"
                    )
            else:
                if human:
                    print(f"  OK       {rel} ({key}={expected_value!r})")

    if not human:
        reporter.emit(args.format)
        return reporter.exit_code()

    print()
    print("==================================")
    if reporter.error_count() == 0:
        print("Grimoire structure validation passed")
        return 0
    print(f"Grimoire structure validation failed with {reporter.error_count()} issue(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
