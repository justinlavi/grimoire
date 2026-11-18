---
type: reference
title: "Public Command Surface"
aliases: ["command-surface", "command-matrix", "skill-command-contract"]
tags: [type/reference, framework/docs, scope/skills]
authority: grimoire
last_verified: 2026-11-14
---

# Public Command Surface

The contract for every command the framework ships lives in
[`rites/data/command_surface.json`](../rites/data/command_surface.json). This page states what an
entry holds, what checks it and how to change it when a command is added, removed or renamed.
The file holds the rows. The "Command contract" section of [skills](skills.md) renders them as a
table.

Each entry ties one command to the parts that carry it out:

```text
command -> skill source -> invocation -> rite or judgment owner ->
guard and preconditions -> mutation and log behavior -> validation profile
```

## Fields

The file has a `schema_version` of `1` and a `commands` list. Every entry carries all twelve
fields.

| Field | Value | Meaning |
|---|---|---|
| `command` | String, such as `/grm-add` | The command in its flat form, `/<prefix>-<slug>`. |
| `family` | `grm` or `dev` | The [command family](skill_schema.md#command-families) whose folder holds the skill. |
| `skill_source` | Path | The `SKILL.md` that registers the command. |
| `invocation` | Path | The invocation the command follows. |
| `guard` | Path or `null` | The shared guard the command runs first, or `null` when it has none. |
| `owner_type` | `rite`, `judgment` or `hybrid` | What does the work: a rite alone, the assistant's judgment alone, or both. |
| `rite_owner` | Path or `null` | The rite that does the mechanical work, or `null` when no single rite does. |
| `preconditions` | List of strings | What must be true before the command acts. |
| `mutation_profile` | `read_only`, `plan_apply`, `apply_only` or `judgment_gated` | How the command writes. `plan_apply` and `apply_only` are the [rite profiles](rite_profiles.md#profiles); `read_only` marks a command that writes nothing. `judgment_gated` marks a command whose playbook decides each write by judgment, so no single rite profile describes it. |
| `mutation_behavior` | String | What the command writes, in plain words. |
| `log_behavior` | String | What record the command leaves of its run. Every command but one states that it writes no log; a grimoire's history is its git history. `/grm-dev-improve` states that it updates `CHANGELOG.md` for changes a user can see. |
| `validation_profile` | String | The commands that prove the work, separated by semicolons. |

## Validation

`/grm-dev-validate skill-refs` checks the contract. From a checkout, run
`python rites/validate_skill_refs.py`; it exits with code 0 when the contract holds and 1 when it
does not. It reports an error when:

- The file is unreadable, `schema_version` is not `1`, or `commands` is not a list.
- A string field is empty, or `preconditions` is not a list of non-empty strings.
- `command` is not a valid command name.
- `owner_type` or `mutation_profile` is outside its allowed values.
- `skill_source` or `invocation` names a path that does not exist, or `guard` or `rite_owner` is
  neither `null` nor an existing path.
- `family` or `skill_source` disagrees with the skill found under `skills/`.
- A command appears twice, a shipped skill has no entry, or an entry has no skill.
- A command with `owner_type` of `rite` has a `mutation_profile` that differs from its rite's
  profile in [`rite_profiles.json`](../rites/data/rite_profiles.json). When that rite has no
  profile there, it does not write, and the command must be `read_only`.

## Changing a command

When you add, remove or rename a command, from the root of a checkout:

1. Create, delete or rename `skills/<family>/<verb>/SKILL.md`. The
   [skill schema](skill_schema.md) owns its structure.
2. Create, delete or rename the invocation the skill names.
3. Edit the command's entry in `rites/data/command_surface.json`.
4. Run `python rites/validate_skill_refs.py`. It exits with code 0 when every command reference
   and every entry resolves.
5. Run `python rites/sync_docs.py --apply` to regenerate [skills](skills.md).
6. Run `python rites/build_plugins.py --apply` to render the command into `plugins/`.
7. Run `python -m pytest -q`. The suite fails when `docs/skills.md` or `plugins/` is out of step
   with the sources.

## Related

- Command families and `SKILL.md` structure: [skill schema](skill_schema.md)
- The generated catalog: [skills](skills.md)
- The validator: [validate skill refs](../invocations/validators/validate_skill_refs.md)
- Rite mutation profiles: [rite profiles](rite_profiles.md)
