---
type: reference
title: "Validate Skill References"
aliases: ["validate-skill-refs", "skill-reference-validation"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Skill References

The `skill-refs` validator ([rites/validate_skill_refs.py](../../rites/validate_skill_refs.py))
checks that every slash command the framework's Markdown names has a source `SKILL.md`, and that
the command-surface contract covers every command the framework ships. It catches a reference to a
command that was renamed, deleted, misspelled or announced before its skill exists. This page is
the reference for its rules, commands and diagnostic codes. It runs on the framework only.

## What it checks

1. **Every slash-command reference resolves to a skill.** A reference is `/`, a family prefix, `-`
   and a slug, such as `/grm-check`, not preceded by a letter, a digit, `_`, `/` or `-`. The family
   prefixes come from `skill_families` in `framework.json`. A command exists when a
   `<family path>/<folder>/SKILL.md` declares its `name`.
2. **The command-surface contract is valid and complete.** `rites/data/command_surface.json` has
   one well-formed entry for every shipped command and no entry without a skill.
   [[docs/command_surface|command surface]] owns the fields.
3. **A command owned by a rite declares that rite's mutation profile.** For an entry with
   `owner_type: rite`, `mutation_profile` equals the profile of its `rite_owner` in
   `rites/data/rite_profiles.json`, or `read_only` when the rite has no entry there.
   [[docs/rite_profiles|rite profiles]] owns the profiles.

## What it scans

Rule 1 reads every line of every Markdown file under `FRAMEWORK_HOME`, code included.

- It skips files named `CHANGELOG.md` and the folder `formulae/` at the root, and `.git/`,
  `node_modules/` and `.obsidian/` at any depth.
- It skips a reference directly followed by `-*`, `-<` or `-{`. These are the wildcard and
  placeholder forms that prose uses for a family of commands.
- It ignores a slash command with any other prefix. A grimoire's own commands are not checked.

Rules 2 and 3 read the two contracts, `framework.json` and the `SKILL.md` files under `skills/`.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate skill-refs` | `FRAMEWORK_HOME/bin/grimoire validate skill-refs` |

The `grimoire` profile has no `skill-refs` validator.

## Diagnostics

Every code is an error. A contract diagnostic carries a `hint` that names the edit.

| Code | Meaning | Fix |
|---|---|---|
| `SKILL_REFS_DANGLING` | A Markdown file names a command that has no source `SKILL.md`. One diagnostic per file per command, with the first line. | Correct the reference to an existing command, remove it, or create `skills/<family>/<folder>/SKILL.md`. |
| `SKILL_REFS_MANIFEST_READ` | `framework.json` is missing, is not valid UTF-8 JSON, or is not an object. | Repair `framework.json`. A family with an invalid field is reported by `naming`, not here. |

Command-surface contract, `rites/data/command_surface.json`:

| Code | Meaning |
|---|---|
| `COMMAND_SURFACE_READ` | The file is missing or is not valid JSON. |
| `COMMAND_SURFACE_SCHEMA` | `schema_version` is not 1. |
| `COMMAND_SURFACE_COMMANDS` | There is no top-level `commands` list. |
| `COMMAND_SURFACE_ENTRY` | An entry is not an object. |
| `COMMAND_SURFACE_FIELD` | An entry lacks a required field, or `guard` or `rite_owner` is neither null nor a path. |
| `COMMAND_SURFACE_COMMAND` | `command` is not a valid slash-command name. |
| `COMMAND_SURFACE_OWNER_TYPE` | `owner_type` is not `rite`, `judgment` or `hybrid`. |
| `COMMAND_SURFACE_MUTATION_PROFILE` | `mutation_profile` is not `read_only`, `plan_apply`, `apply_only` or `judgment_gated`. |
| `COMMAND_SURFACE_PATH` | `skill_source`, `invocation`, `guard` or `rite_owner` names a path that does not exist. |
| `COMMAND_SURFACE_FAMILY` | `family` differs from the family that holds the skill. |
| `COMMAND_SURFACE_SKILL_SOURCE` | `skill_source` differs from the path of the skill's `SKILL.md`. |
| `COMMAND_SURFACE_DUPLICATE` | A command has more than one entry. |
| `COMMAND_SURFACE_MISSING` | A shipped command has no entry. |
| `COMMAND_SURFACE_EXTRA` | An entry names a command that no `SKILL.md` backs. |
| `COMMAND_SURFACE_RITE_PROFILES_READ` | `rites/data/rite_profiles.json` is missing or is not valid JSON, so rule 3 cannot run. |
| `COMMAND_SURFACE_MUTATION_PROFILE_DRIFT` | A rite-owned command's `mutation_profile` differs from its rite's profile. The message gives both. |

After a skill is added, removed or renamed, regenerate the skill catalog with
`FRAMEWORK_HOME/bin/grimoire sync_docs --apply`.

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. This validator emits no warnings. |
| 1 | At least one error: a dangling reference or a command-surface contract error. |
| 2 | The dispatcher rejected the arguments; the validator did not run. With `--grimoire`, `skill-refs` is an unknown selector and exits 2. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other framework validators -> [[invocations/validators/validate|validate]]
- Command-surface contract -> [[docs/command_surface|command surface]]
- Command families and `SKILL.md` structure -> [[docs/skill_schema|skill schema]]
- Mutation profiles -> [[docs/rite_profiles|rite profiles]]
- Skill catalog generator: [rites/sync_docs.py](../../rites/sync_docs.py)
