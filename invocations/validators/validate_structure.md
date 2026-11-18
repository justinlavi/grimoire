---
type: reference
title: "Validate Structure"
aliases: ["validate-framework-structure"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Structure

The `structure` validator of the `framework` profile
([rites/validate_structure.py](../../rites/validate_structure.py)) checks that the framework has its
required directories, files and hubs, that every documentation page is indexed, and that three JSON
contracts are valid. This page is the reference for its rules, commands and diagnostic codes. It
runs on the framework only; on a grimoire the `structure` selector runs
[[invocations/validators/validate_grimoire_structure|validate grimoire structure]].

## What it checks

1. **Required directories exist:** `docs`, `formulae`, `formulae/grimoire`, `rites`, `resources`,
   `skills`, the router folders of rule 4 (`invocations/grm`, `invocations/validators`,
   `invocations/dev`, `invocations/dev/quality`, `invocations/meta`), and the folder of each skill
   family that `framework.json` declares (`skills/grm` and `skills/dev`).
2. **Required files exist:** `grimoire.md`, `README.md`, `UPDATE.md`, `CHANGELOG.md`, `VERSION`,
   `framework.json`, `rites/summon.sh`, `rites/sync_skills.py`, and in `docs/` the pages
   `installation.md`, `agent_targets.md`, `summoning_contract.md`, `agent_configuration.md`,
   `operating_model.md`, `governance.md`, `reference.md`, `page_schema.md`.
3. **No grimoire layer sits at the framework root:** `chapters`, `inbox` and `grimoire.json` do
   not exist there. The grimoire scaffold lives in `formulae/grimoire/`.
4. **Router hubs exist:** `invocations/grm/grm.md`, `invocations/validators/validators.md`,
   `invocations/dev/dev.md`, `invocations/dev/quality/quality.md`, `invocations/meta/meta.md`.
5. **Every documentation page is indexed twice.** `grimoire.md` contains `docs/<stem>` and
   `README.md` contains `docs/<name>.md` for each page directly under `docs/`. The name must stand
   alone: a link to `docs/agent_targets` does not index `docs/agent`. Both files contain
   `CONTRIBUTING` when `CONTRIBUTING.md` exists. A page missing from either index is unreachable
   from that entry point.
6. **The rite-profile contract is valid:** `rites/data/rite_profiles.json`, described in
   [[docs/rite_profiles|rite profiles]].
7. **The summoning contract is valid:** `rites/data/summon_contract.json`, described in
   [[docs/summoning_contract|summoning contract]].
8. **The agent-target registry is valid:** `rites/data/agent_targets.json`, described in
   [[docs/agent_targets|agent targets]].

## What it scans

The validator tests fixed paths under `FRAMEWORK_HOME`, reads `framework.json` for the skill
families, reads the text of `grimoire.md` and `README.md`, and loads the three contracts. Rule 5 covers `docs/*.md` only, not subfolders of
`docs/`. Nothing is skipped by pattern.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate structure` | `FRAMEWORK_HOME/bin/grimoire validate structure` |

## Diagnostics

Every code is an error. A contract diagnostic carries a `hint` that names the edit.

| Code | Meaning | Fix |
|---|---|---|
| `STRUCTURE_MISSING_DIR` | A required directory is missing. | Restore the directory. If the layout changed on purpose, change `OTHER_REQUIRED_DIRS` or `HUB_DIRS` in the rite, or the family's `path` in `framework.json`, in the same commit. |
| `STRUCTURE_MISSING_FILE` | A required file is missing. | Restore the file, or correct its name or location. |
| `STRUCTURE_FORBIDDEN_GRIMOIRE_LAYER` | A grimoire layer exists at the framework root. | Move it under `formulae/grimoire/`, or delete it. |
| `STRUCTURE_MISSING_HUB` | A router folder has no `<folder>/<folder>.md`. | Create the hub with one route per page in the folder. |
| `STRUCTURE_DOC_NOT_IN_HUB` | `grimoire.md` does not name a `docs/` page or `CONTRIBUTING.md`. | Add a route to the page in `grimoire.md`. |
| `STRUCTURE_DOC_NOT_IN_README` | `README.md` does not name a `docs/` page or `CONTRIBUTING.md`. | Add a link to the page in the documentation index of `README.md`. |

Rite-profile contract, `rites/data/rite_profiles.json`:

| Code | Meaning |
|---|---|
| `RITE_PROFILE_READ` | The file is missing, is not UTF-8 or is not valid JSON. |
| `RITE_PROFILE_SCHEMA` | `schema_version` is not 1, or the file is not a JSON object. |
| `RITE_PROFILE_PROFILES` | There is no top-level `profiles` list. |
| `RITE_PROFILE_ENTRY` | An entry is not an object. |
| `RITE_PROFILE_FIELD` | An entry lacks a required field, or `plan_command` is neither null nor a non-empty string. |
| `RITE_PROFILE_KIND` | `profile` is not `plan_apply` or `apply_only`. |
| `RITE_PROFILE_PATH` | An entry's `path` does not exist. |
| `RITE_PROFILE_PLAN` | A `plan_apply` entry has no `plan_command`. |
| `RITE_PROFILE_TEST` | A path in an entry's `tests` list is not a file. |
| `RITE_PROFILE_DUPLICATE` | A rite has more than one entry. |
| `RITE_PROFILE_MISSING` | A rite contains write operations and has no entry. |
| `RITE_PROFILE_EXTRA` | An entry names a rite in which no write operation was detected. |

Summoning contract, `rites/data/summon_contract.json`:

| Code | Meaning |
|---|---|
| `SUMMON_CONTRACT_READ` | The file is missing or is not valid JSON. |
| `SUMMON_CONTRACT_SCHEMA` | `schema_version` is not 1. |
| `SUMMON_CONTRACT_MODES` | There is no top-level `modes` list. |
| `SUMMON_CONTRACT_ENTRY` | An entry under `modes`, `required_pipeline`, `bootstrap_environment` or `release_assets` is not an object. |
| `SUMMON_CONTRACT_FIELD` | An entry lacks a required field. |
| `SUMMON_CONTRACT_PATH` | A mode's `surface` does not exist. |
| `SUMMON_CONTRACT_SYMBOLS` | A mode's `code_symbols` is not a list of strings. |
| `SUMMON_CONTRACT_SYMBOL` | A named code symbol or pipeline owner does not exist in `rites/`. |
| `SUMMON_CONTRACT_DUPLICATE_MODE` | A mode id appears more than once. |
| `SUMMON_CONTRACT_MODE_REF` | A pipeline step names a mode that `modes` does not declare. |

Agent-target registry, `rites/data/agent_targets.json`:

| Code | Meaning |
|---|---|
| `AGENT_TARGETS_READ` | The file is missing or is not valid JSON. |
| `AGENT_TARGETS_SCHEMA` | `schema_version` is not 1. |
| `AGENT_TARGETS_LIST` | There is no top-level `targets` list. |
| `AGENT_TARGETS_EMPTY` | The registry declares no target. |
| `AGENT_TARGETS_ENTRY` | An entry is not an object. |
| `AGENT_TARGETS_ID` | A target id does not match `^[a-z][a-z0-9-]*$`. |
| `AGENT_TARGETS_FIELD` | A target lacks a required field, or a field has the wrong type. |
| `AGENT_TARGETS_INSTRUCTION_MODE` | `instruction_mode` is not `auto` or `manual`. |
| `AGENT_TARGETS_SKILL_MODE` | `skill_mode` is not `full`, `pointer` or `none`. |
| `AGENT_TARGETS_SKILL_TARGET` | `skill_target` is missing while `skill_mode` is `full` or `pointer`, or set while `skill_mode` is `none`. |
| `AGENT_TARGETS_AUTO_CONFIG` | A target is `auto_configured` and its `instruction_mode` is not `auto`. |
| `AGENT_TARGETS_INSTRUCTION_TARGET` | An automatic instruction target is not a `~/...` path. |
| `AGENT_TARGETS_DUPLICATE` | A target id appears more than once. |
| `AGENT_TARGETS_NO_AUTO` | No target has an automatic instruction file. |
| `AGENT_TARGETS_NO_SKILLS` | No target registers skills. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. This validator emits no warnings. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other framework validators -> [[invocations/validators/validate|validate]]
- Hub convention -> [[docs/operating_model|operating model]]
- What belongs in the framework -> [[docs/governance|governance]]
