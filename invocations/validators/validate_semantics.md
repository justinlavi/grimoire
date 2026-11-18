---
type: reference
title: "Validate Semantics"
aliases: ["validate-semantics"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Semantics

The `semantics` validator ([rites/validate_semantics.py](../../rites/validate_semantics.py)) finds
example paths under `chapters/` that the framework's Markdown writes with a hyphen. The framework's
examples use snake_case, the default convention for a grimoire. This page is the reference for the
validator's rule, commands and diagnostic code. It runs on the framework only.

## What it checks

No line of a Markdown file holds a hyphenated `chapters/` path. Two shapes match:

| Shape | Pattern | Fails | Passes |
|---|---|---|---|
| A folder directly under `chapters/` named as two runs of lowercase letters joined by a hyphen | `chapters/[a-z]+-[a-z]+/` | `chapters/knife-skills/` | `chapters/knife_skills/` |
| A `.md` filename under `chapters/` that ends in lowercase letters, a hyphen and lowercase letters | `chapters/[^ ]*[a-z]+-[a-z]+\.md` | `chapters/breads/sourdough-starter.md` | `chapters/breads/sourdough_starter.md` |

- A path outside these two shapes passes. `chapters/2026-plan/` passes, and so does a hyphenated
  name outside `chapters/`, such as `file-name.md` alone.
- A line that starts with `#` is exempt: a heading, or a comment line inside a code block.
- Every other line is checked, inside fenced code blocks too.

The validator reads text only. Whether a name is clear or easy to find is a judgment, which
`/grm-check naming` makes for a grimoire and `/grm-dev-improve` makes for the framework.

## What it scans

The validator reads every Markdown file under `FRAMEWORK_HOME`, except under `.git/`,
`node_modules/` and `.obsidian/`. It skips:

- files named `validate_semantics.md`, `validate_naming.md` and `script_vs_ai.md`, which show the
  pattern on purpose;
- the folder `invocations/dev/quality/`.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate semantics` | `FRAMEWORK_HOME/bin/grimoire validate semantics` |

The `grimoire` profile has no `semantics` validator: a grimoire chooses its own naming convention.

## Diagnostics

| Code | Meaning | Fix |
|---|---|---|
| `SEMANTICS_HYPHENATED_EXAMPLE` | Error. A line holds a hyphenated `chapters/` path. The validator reports the first such line in each file, so a file can hold more. | Rewrite every hyphenated example path in the file in snake_case, then run the validator again. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. This validator emits no warnings. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments; the validator did not run. With `--grimoire`, `semantics` is an unknown selector and exits 2. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other framework validators -> [[invocations/validators/validate|validate]]
- Names of the framework's own files -> [[invocations/validators/validate_naming|validate naming]]
- Naming convention -> [[docs/operating_model|operating model]]
- Judgment review of a grimoire's names -> [[invocations/grm/check|check]]
