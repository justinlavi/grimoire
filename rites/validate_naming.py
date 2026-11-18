#!/usr/bin/env python3
"""Validates the framework's file names and skill layout.

File names: every Markdown and Python file in the framework is named in snake_case. A
hyphen and a lowercase letter followed by an uppercase letter are errors; any other
departure (an uppercase letter at the start, a space) is a warning. Files with a name the
tools fix are exempt: README.md, UPDATE.md, CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md,
AGENTS.md, LICENSE.md and SKILL.md, and a formula's `<name>.formula.md`. Folder names are
not checked: skill folders are kebab-case by design.

Skill layout: framework.json declares skill families, and the folders under skills/ must
match them, each skill folder holding a SKILL.md whose `name` its location implies.

Runs on the framework only.

Usage: python rites/validate_naming.py
Mutation profile: read-only.
Exit codes: 0 = no errors (warnings do not change it), 1 = violations found
"""

import re
import sys

from _lib import (
    default_framework_root,
    is_skipped,
    load_skill_families_checked,
    ok,
    read_frontmatter_name,
    walk_files,
    warn,
)
from diagnostics import DiagnosticReporter, add_output_format_arg

FRAMEWORK_ROOT = default_framework_root()

# Names the tools or hosts fix, so they cannot be snake_case.
FIXED_NAMES = {
    "README.md", "UPDATE.md", "CHANGELOG.md", "CONTRIBUTING.md",
    "CLAUDE.md", "AGENTS.md", "LICENSE.md", "SKILL.md",
}
FORMULA_SUFFIX = ".formula"
SNAKE_CASE_RE = re.compile(r"_{0,2}[a-z0-9]+(?:_[a-z0-9]+)*_{0,2}")

SKIP_DIRS = {"tests"}


def snake_case_stem(name, ext):
    """Return a file name's stem without its extension and a `.formula` marker."""
    stem = name[: -len(ext) - 1]
    if ext == "md" and stem.endswith(FORMULA_SUFFIX):
        stem = stem[: -len(FORMULA_SUFFIX)]
    return stem


def check_naming(ext, label, reporter, human):
    violations = 0

    if human:
        print(f"Checking {label} naming...")
    for path in walk_files(FRAMEWORK_ROOT, f"*.{ext}"):
        name = path.name
        rel = path.relative_to(FRAMEWORK_ROOT)
        if is_skipped(rel, SKIP_DIRS) or name in FIXED_NAMES:
            continue

        flagged = False
        if name[0].islower() and "-" in name:
            reporter.error(
                "NAMING_HYPHENATED",
                "hyphenated name should use snake_case",
                path=path,
            )
            if human:
                warn(f"Hyphenated (should use snake_case): {rel}")
            violations += 1
            flagged = True

        if re.search(r"[a-z][A-Z]", name):
            reporter.error(
                "NAMING_CAMELCASE",
                "CamelCase name should use snake_case",
                path=path,
            )
            if human:
                warn(f"CamelCase (should use snake_case): {rel}")
            violations += 1
            flagged = True

        if not flagged and not SNAKE_CASE_RE.fullmatch(snake_case_stem(name, ext)):
            reporter.warning(
                "NAMING_NOT_SNAKE_CASE",
                "name should use lowercase snake_case",
                path=path,
            )
            if human:
                warn(f"Not snake_case: {rel}")
            violations += 1

    if human and violations == 0:
        ok(f"All {label} use proper naming")
    if human:
        print()
    return violations


def load_skill_families(reporter, human):
    """Return the framework's skill families, reporting each problem with them."""
    families, problems = load_skill_families_checked(FRAMEWORK_ROOT)
    valid = []
    for family in families:
        parts = family["path"].relative_to(FRAMEWORK_ROOT).parts
        if len(parts) == 2 and parts[0] == "skills":
            valid.append(family)
            continue
        problems.append(f"skill_families.{family['name']} path must be skills/<folder>")

    for problem in problems:
        if problem.startswith("could not read") or "must hold a JSON object" in problem:
            code = "SKILL_SCHEMA_MANIFEST_READ"
        elif problem.startswith("framework.json"):
            code = "SKILL_SCHEMA_MISSING_FAMILIES"
        else:
            code = "SKILL_SCHEMA_FAMILY_INVALID"
        reporter.error(code, problem, path="framework.json")
        if human:
            warn(problem)
    return valid


def check_skill_schema(reporter, human):
    violations = 0
    skills_dir = FRAMEWORK_ROOT / "skills"

    if human:
        print("Checking skill naming schema...")
    if not skills_dir.is_dir():
        reporter.error("SKILL_SCHEMA_MISSING_DIR", "missing skills/ directory", path="skills")
        if human:
            warn("Missing skills/ directory")
        return 1

    families = load_skill_families(reporter, human)
    if not families:
        reporter.error("SKILL_SCHEMA_NO_FAMILIES", "no valid skill families declared", path="framework.json")
        if human:
            warn("No valid skill families declared")
        return 1

    expected_top_dirs = {family["path"].name for family in families}
    for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if folder.name not in expected_top_dirs:
            reporter.error(
                "SKILL_SCHEMA_UNEXPECTED_FAMILY_DIR",
                "unexpected skill family directory",
                path=folder,
            )
            if human:
                warn(f"Unexpected skill family directory: {folder.relative_to(FRAMEWORK_ROOT)}")
            violations += 1

    for family in families:
        family_dir = family["path"]
        if not family_dir.is_dir():
            reporter.error(
                "SKILL_SCHEMA_MISSING_FAMILY_DIR",
                "missing skill family directory",
                path=family_dir,
            )
            if human:
                warn(f"Missing skill family directory: {family_dir.relative_to(FRAMEWORK_ROOT)}")
            violations += 1
            continue

        for folder in sorted(p for p in family_dir.iterdir() if p.is_dir()):
            skill_file = folder / "SKILL.md"
            if not skill_file.is_file():
                reporter.error("SKILL_SCHEMA_MISSING_SKILL_FILE", "missing SKILL.md", path=folder)
                if human:
                    warn(f"Missing SKILL.md: {folder.relative_to(FRAMEWORK_ROOT)}")
                violations += 1
                continue

            command_slug = (
                f"{family['slug_prefix']}-{folder.name}"
                if family["slug_prefix"]
                else folder.name
            )
            expected_name = f"{{{{SKILL_PREFIX}}}}-{command_slug}"
            actual_name = read_frontmatter_name(skill_file)
            if actual_name != expected_name:
                reporter.error(
                    "SKILL_SCHEMA_NAME_MISMATCH",
                    f"skill name mismatch (expected `{expected_name}`, got `{actual_name}`)",
                    path=skill_file,
                )
                if human:
                    warn(
                        f"Skill name mismatch: {skill_file.relative_to(FRAMEWORK_ROOT)} "
                        f"(expected `{expected_name}`, got `{actual_name}`)"
                    )
                violations += 1

        direct_skill = family_dir / "SKILL.md"
        if direct_skill.exists():
            reporter.error(
                "SKILL_SCHEMA_DIRECT_SKILL_FILE",
                "skill family has direct SKILL.md; expected nested skill folders",
                path=direct_skill,
            )
            if human:
                warn(f"Skill family has direct SKILL.md; expected nested skill folders: {direct_skill.relative_to(FRAMEWORK_ROOT)}")
            violations += 1

    for skill_file in walk_files(skills_dir, "SKILL.md"):
        if any(skill_file.is_relative_to(family["path"]) for family in families):
            continue
        reporter.error(
            "SKILL_SCHEMA_FILE_OUTSIDE_FAMILIES",
            "SKILL.md is outside declared skill families",
            path=skill_file,
        )
        if human:
            warn(f"SKILL.md is outside declared skill families: {skill_file.relative_to(FRAMEWORK_ROOT)}")
        violations += 1

    if human and violations == 0:
        ok("All skills follow the command-family naming schema")
    if human:
        print()
    return violations


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate naming conventions")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"
    reporter = DiagnosticReporter("validate_naming", FRAMEWORK_ROOT)

    if human:
        print()
        print("Validating Naming Conventions")
        print("==================================")
        print(f"Framework root: {FRAMEWORK_ROOT}")
        print()

    markdown_violations = check_naming("md", "markdown file", reporter, human)
    python_violations = check_naming("py", "Python script", reporter, human)
    skill_violations = check_skill_schema(reporter, human)

    if not human:
        reporter.emit(
            args.format,
            checked={
                "markdown_violations": markdown_violations,
                "python_violations": python_violations,
                "skill_violations": skill_violations,
            },
        )
        return reporter.exit_code()

    print("==================================")
    if reporter.error_count() == 0:
        print("Naming validation passed")
        return 0
    print(f"Naming validation found {reporter.error_count()} issues")
    return 1


if __name__ == "__main__":
    sys.exit(main())
