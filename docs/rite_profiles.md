---
type: reference
title: "Mutating Rite Profiles"
aliases: ["rite-profiles", "mutation-profiles", "plan-apply-profile"]
tags: [type/reference, framework/docs, scope/rites]
authority: grimoire
last_verified: 2026-11-14
---

# Mutating Rite Profiles

The contract for every rite that writes lives in
[`rites/data/rite_profiles.json`](../rites/data/rite_profiles.json). This page states the
profiles, the fields of an entry, what checks the contract and how to change it. The file holds
the commands, the write scopes and the tests of each rite.

## Profiles

A profile states how a rite writes. A rite that writes declares exactly one. A rite that writes
nothing has no entry.

| Profile | Meaning | Rule |
|---|---|---|
| `plan_apply` | Has a plan command and an apply command. | The entry names both. The plan is specific enough for an assistant to summarize before anything is written. When the default mode writes, the rite also has a preview flag such as `--dry-run`. |
| `apply_only` | Writes through one explicit operation, where a separate plan would add nothing. | It refuses an unsafe overwrite, or its entry states exactly what it replaces. |

## Fields

The file has a `schema_version` of `1` and a `profiles` list. Every entry carries these fields.

| Field | Value | Meaning |
|---|---|---|
| `path` | Path, such as `rites/sync_library.py` | The rite. |
| `profile` | One of the two profiles | How the rite writes. |
| `default_mode` | `plan` or `apply` | What the rite does when it runs with no mode flag. |
| `plan_command` | String or `null` | The command that previews the writes. Required for `plan_apply`. |
| `apply_command` | String | The command that writes. |
| `writes` | List of strings | Every place the rite writes. |
| `idempotency` | String | What a second run does. |
| `validation_profile` | String | The commands that prove the rite's work. |
| `tests` | List of paths | The test files that cover the rite's writes. Each path exists. |

## Profiled rites

| Rite | Profile | Default mode |
|---|---|---|
| `rites/adopt_grimoire.py` | `apply_only` | `apply` |
| `rites/build_plugins.py` | `plan_apply` | `plan` |
| `rites/grimoire_access.py` | `plan_apply` | `plan` |
| `rites/install_grimoire.py` | `apply_only` | `apply` |
| `rites/new_page.py` | `plan_apply` | `plan` |
| `rites/plugin_auto_update.py` | `plan_apply` | `plan` |
| `rites/repair_links.py` | `plan_apply` | `plan` |
| `rites/restructure_grimoire.py` | `plan_apply` | `plan` |
| `rites/save_grimoire.py` | `plan_apply` | `plan` |
| `rites/stage_publish.py` | `plan_apply` | `plan` |
| `rites/summon.sh` | `apply_only` | `apply` |
| `rites/summon_core.py` | `apply_only` | `apply` |
| `rites/summon_state.py` | `plan_apply` | `plan` |
| `rites/sync_docs.py` | `plan_apply` | `plan` |
| `rites/sync_library.py` | `plan_apply` | `plan` |
| `rites/sync_skills.py` | `plan_apply` | `apply` |
| `rites/update_grimoires.py` | `plan_apply` | `plan` |

The contract treats a rite that is not listed as one that writes nothing.
`tests/test_rite_profiles.py` fails when a rite in the file is missing from this table.

## Rules

- **Every rite that writes has an entry.** That covers files, directories, build artifacts, agent
  files, install state and git history.
- **Every invocation that runs a writing rite states how it applies.** It says whether the
  assistant may run the apply command directly or must show the plan and ask the user first.
- **Every writing rite has a test of its write scope.** The test runs in a temporary directory or
  a temporary home, and covers the scope of the writes or their idempotency. It exists before the
  rite's behavior is widened.
- **Managed-prefix membership decides what `rites/sync_skills.py` cleans and overwrites.** Inside
  the `grm-` prefix and the `skill_prefix` of each grimoire, the rite removes or replaces any skill
  directory that is not in the current catalog. It never touches a directory outside those
  prefixes. The `FRAMEWORK_SKILL_OWNERSHIP` marker it stamps into each generated `SKILL.md`
  records where the skill came from; the rite never reads it to decide a write.

## Validation

`/grm-dev-validate structure` checks the contract. From a checkout, run
`python rites/validate_structure.py`. It reports an error when:

- The file is unreadable, `schema_version` is not `1`, or `profiles` is not a list.
- A required field is missing or empty, or `profile` is not one of the two profiles.
- `path` names a file that does not exist, or a rite appears twice.
- A `plan_apply` entry has no `plan_command`.
- A path in `tests` names a file that does not exist.
- A file directly under `rites/` writes and has no entry. The check reads each `.py` and `.sh`
  file for file-system writes (including the `write_utf8` and `write_json` helpers of `rites/_lib.py`)
  and for git commands that change a repository (including `run_git` calls).
- An entry names a rite in which the check finds no write.

`/grm-dev-validate skill-refs` checks that each command owned by a rite carries that rite's
profile; the [command surface](command_surface.md#validation) owns that check.

## Changing a rite's profile

When you add a rite that writes, or change how one writes, from the root of a checkout:

1. Add or edit the rite's entry in `rites/data/rite_profiles.json`, with every field.
2. State the profile in the rite's module docstring.
3. Add or edit the rite's row in [Profiled rites](#profiled-rites).
4. Run `python rites/validate_structure.py`. It exits with code 0 when the contract holds.
5. Run `python -m pytest -q tests/test_rite_profiles.py`. It passes when the entries match the
   rites that write and this page names each one.

## Related

- When a rite does the work: [script vs AI](script_vs_ai.md)
- The rite quality review: [validate rites](../invocations/dev/quality/validate_rites.md)
- The helper that loads and checks the contract: [`rites/rite_profiles.py`](../rites/rite_profiles.py)
