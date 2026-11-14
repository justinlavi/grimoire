---
type: reference
title: "Validate Skill References"
aliases: ["validate-skill-refs", "skill-reference-validation"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-13
---

# Validate Framework Skill References

## Purpose

Mechanically validate that every framework-shipped slash-command reference in
framework markdown resolves to a source `SKILL.md`, and that every public
framework-shipped command is represented in the command-surface contract.

This catches drift such as renamed skills, deleted skills, typoed command
references, docs that announce a skill before its source folder exists, and
public commands missing from `rites/data/command_surface.json`.

## Invocation

```
/grm-dev-validate skill-refs
```

Mechanical equivalent:

```bash
FRAMEWORK_HOME/bin/grimoire validate_skill_refs
```

## Workflow

1. Run after renaming, deleting, or adding any `/grm-dev-*` or `/grm-*` skill.
2. Run after editing docs that mention concrete framework-shipped slash commands.
3. Ignore wildcard and placeholder prose such as `/grm-dev-example-*`,
   `/grm-example-*`, and `/grm-dev-example-<name>`; the rite skips these.
4. For each dangling reference, choose one fix:
   - Update the doc reference to an existing skill.
   - Create the missing `skills/<family>/<slug>/SKILL.md`.
   - Remove references to an intentionally retired skill.
5. For each command-surface error, update the skill, invocation, guard, rite,
   or `rites/data/command_surface.json` entry until the contract is complete.
6. After adding or removing a skill, run `FRAMEWORK_HOME/bin/grimoire sync_docs --apply`.

## Related

- Validators hub: [[invocations/dev/validators/validators|validators]]
- Skill schema: [[docs/skill_schema|skill schema]]
- Public command surface: [[docs/command_surface|command surface]]
- Skill catalog generator: [`../../../rites/sync_docs.py`](../../../rites/sync_docs.py)
