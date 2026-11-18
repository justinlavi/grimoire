---
type: reference
title: "Validate Naming"
aliases: ["validate-naming"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Naming

The `naming` validator ([rites/validate_naming.py](../../rites/validate_naming.py)) checks that the
framework's Markdown and Python files are named in snake_case and that its skill folders match the
command families `framework.json` declares. This page is the reference for its rules, commands and
diagnostic codes. It runs on the framework only.

## What it checks

File names:

1. **No hyphen.** A `.md` or `.py` filename that starts with a lowercase letter holds no `-`:
   `quick_start.md` passes, `quick-start.md` fails.
2. **No camel case.** A `.md` or `.py` filename holds no lowercase letter directly followed by an
   uppercase letter: `quickStart.md` and `validateStructure.py` fail.
3. **Snake case.** The rest of the name, without its extension, is lowercase letters and digits
   joined by single underscores, with up to two leading or trailing underscores (`_lib.py`). Any
   other name, such as `Title_Case.md`, `FOO.md`, `My-File.md` or `my file.md`, is a warning.
   `NAMING_HYPHENATED` and `NAMING_CAMELCASE` take precedence for a name they already report.

[[docs/operating_model|operating model]] owns the convention and its reasons.

Skill layout, as [[docs/skill_schema|skill schema]] defines it:

4. `framework.json` is readable and declares `skill_families`, each an object whose `path` is
   `skills/<folder>`.
5. `skills/` exists, and every folder directly under it is the folder of a declared family.
6. Every declared family folder exists.
7. Every folder inside a family folder holds a `SKILL.md`.
8. Each `SKILL.md` declares the `name` its location implies: `{{SKILL_PREFIX}}-<folder>`, or
   `{{SKILL_PREFIX}}-<slug_prefix>-<folder>` when the family declares a `slug_prefix`.
   `skills/dev/validate/SKILL.md` therefore declares `name: {{SKILL_PREFIX}}-dev-validate`.
9. No `SKILL.md` sits directly in a family folder, and none sits under `skills/` outside the
   declared families.

## What it scans

- Rules 1 to 3 read the name of every `.md` and `.py` file under `FRAMEWORK_HOME`, except under
  `.git/`, `node_modules/` and `.obsidian/` at any depth and `tests/` at the root. They exempt the
  names `README.md`, `UPDATE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`,
  `LICENSE.md` and `SKILL.md`, and a formula's `<name>.formula.md` (rule 3 reads `<name>`).
- Rules 1 to 3 check file names only. They do not check folder names or files of other types.
  Skill folders are kebab-case by design.
- Rules 4 to 9 read `framework.json` and the tree under `skills/`.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate naming` | `FRAMEWORK_HOME/bin/grimoire validate naming` |

The `grimoire` profile has no `naming` validator: a grimoire records its own convention in
`grimoire.json`, and any casing is valid there. `/grm-check naming` is a different thing, the
judgment review of names in [[invocations/grm/check|check]].

## Diagnostics

Every code is an error except `NAMING_NOT_SNAKE_CASE`, which is a warning.

| Code | Meaning | Fix |
|---|---|---|
| `NAMING_HYPHENATED` | A `.md` or `.py` filename holds a hyphen. | Rename the file to snake_case with `git mv`, update every link to it, then run `/grm-dev-validate links`. |
| `NAMING_CAMELCASE` | A `.md` or `.py` filename holds a lowercase letter followed by an uppercase letter. | The same. |
| `NAMING_NOT_SNAKE_CASE` | Warning: a `.md` or `.py` filename is not lowercase snake_case and is not exempt. | Rename the file to snake_case, or add its name to the exemptions in the rite if a tool fixes it. |
| `SKILL_SCHEMA_MANIFEST_READ` | `framework.json` is missing, is not valid UTF-8 JSON, or is not an object. | Repair `framework.json`. |
| `SKILL_SCHEMA_MISSING_FAMILIES` | `framework.json` has no `skill_families`, or it is empty. | Declare the families; [[docs/reference|reference]] shows the shape. |
| `SKILL_SCHEMA_FAMILY_INVALID` | A family is not an object, or has a missing or invalid `path` (it must be `skills/<folder>`), `skill_prefix`, `slug_prefix` or `plugin`. The message names the field. | Correct the field the message names, such as a `path` of `skills/grm`. |
| `SKILL_SCHEMA_NO_FAMILIES` | No valid family remains after the checks above. | Fix the diagnostics reported before this one. |
| `SKILL_SCHEMA_MISSING_DIR` | `skills/` does not exist. | Restore the folder. |
| `SKILL_SCHEMA_UNEXPECTED_FAMILY_DIR` | A folder directly under `skills/` belongs to no declared family. | Move its skills into a family folder, or declare the family in `framework.json`. |
| `SKILL_SCHEMA_MISSING_FAMILY_DIR` | A declared family's folder does not exist. | Create the folder, or remove the family from `framework.json`. |
| `SKILL_SCHEMA_MISSING_SKILL_FILE` | A skill folder holds no `SKILL.md`. | Add the `SKILL.md`, or remove the empty folder. |
| `SKILL_SCHEMA_NAME_MISMATCH` | A `SKILL.md` declares a `name` other than the one its folder implies. The message gives both. | Correct the `name` line, or rename the folder. |
| `SKILL_SCHEMA_DIRECT_SKILL_FILE` | A `SKILL.md` sits directly in a family folder. | Move it into its own skill folder. |
| `SKILL_SCHEMA_FILE_OUTSIDE_FAMILIES` | A `SKILL.md` sits under `skills/` outside every declared family. | Move it into a family folder. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. A `NAMING_NOT_SNAKE_CASE` warning alone leaves the exit code at 0. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments; the validator did not run. With `--grimoire`, `naming` is an unknown selector and exits 2. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other framework validators -> [[invocations/validators/validate|validate]]
- Naming convention -> [[docs/operating_model|operating model]]
- Command families and `SKILL.md` structure -> [[docs/skill_schema|skill schema]]
- Hyphenated path examples in prose -> [[invocations/validators/validate_semantics|validate semantics]]
