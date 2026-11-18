---
type: reference
title: "Validate Frontmatter"
aliases: ["validate-frontmatter"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Frontmatter

The `frontmatter` validator ([rites/validate_frontmatter.py](../../rites/validate_frontmatter.py))
checks every page's YAML frontmatter against the [[docs/page_schema|page schema]], which owns the
fields and their meaning. This page is the reference for the validator's rules, commands and
diagnostic codes. It runs on a grimoire and on the framework.

## What it checks

| # | Rule | Code |
|---|---|---|
| 1 | The file starts with a frontmatter block: `---` on the first line and a closing `---` line. | `FRONTMATTER_MISSING` |
| 2 | `type` is present. | `FRONTMATTER_MISSING_TYPE` |
| 3 | `type` is one of `hub`, `concept`, `entity`, `source`, `playbook`, `reference`, written as one value. A list is invalid. | `FRONTMATTER_INVALID_TYPE` |
| 4 | `type: source` appears only on a source wrapper, a page at `chapters/<chapter>/.../sources/<file>`. | `FRONTMATTER_SOURCE_OUTSIDE_SOURCES` |
| 5 | Every field the page schema requires for the type is present and not empty: `type`, `title` and `tags` for a hub; those plus `authority` and `last_verified` for every other type. | `FRONTMATTER_MISSING_REQUIRED` |
| 6 | `authority`, when present, is one of `external`, `grimoire`, `hybrid`, written as one value. A list is invalid. | `FRONTMATTER_INVALID_AUTHORITY` |
| 7 | A page with `authority: external` or `authority: hybrid` lists at least one entry in `sources`. | `FRONTMATTER_MISSING_SOURCES` |
| 8 | `last_verified`, when present, has the form `YYYY-MM-DD`. | `FRONTMATTER_INVALID_DATE_FORMAT` |
| 9 | `last_verified` is a real calendar date. | `FRONTMATTER_INVALID_DATE` |
| 10 | `last_verified` is not earlier than `2020-01-01`. An earlier date is a placeholder such as `1970-01-01`, not a verification. | `FRONTMATTER_IMPLAUSIBLE_DATE` |
| 11 | `tags` and `aliases`, when present, are YAML lists. | `FRONTMATTER_LIST_REQUIRED` |

A file that fails rule 1, 2 or 3 gets that one diagnostic and no further checks. A file that is not
valid UTF-8 gets `FRONTMATTER_READ_ERROR` and no further checks. A list may be written inline
(`tags: [a, b]`) or as a block whose items are indented or sit at the start of the line. Whether a
cited source exists is checked by
[[invocations/validators/validate_provenance|validate provenance]], not here.

## What it scans

The validator reads every Markdown file under `docs/`, `invocations/`, `formulae/` and `chapters/`,
and every Markdown file directly at the root.

- It skips files named `SKILL.md`, `README.md`, `UPDATE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  `CLAUDE.md`, `AGENTS.md` and `LICENSE.md`. A `SKILL.md` follows the
  [[docs/skill_schema|skill schema]] instead.
- Files under `formulae/` are templates that carry placeholder values. For them the validator
  applies rules 1 to 3, 6 and 11 only.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check frontmatter` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT frontmatter` |
| The framework | `/grm-dev-validate frontmatter` | `FRAMEWORK_HOME/bin/grimoire validate frontmatter` |

## Diagnostics

Every code is an error. A diagnostic names the file; it gives no line.

| Code | Meaning | Fix |
|---|---|---|
| `FRONTMATTER_MISSING` | The file has no frontmatter block at its start. | Add the block. `FRAMEWORK_HOME/formulae/page.formula.md` is the template. |
| `FRONTMATTER_MISSING_TYPE` | The block has no `type`. | Add `type` with one of the six values. |
| `FRONTMATTER_INVALID_TYPE` | `type` holds another value. | Use one of the six values. |
| `FRONTMATTER_SOURCE_OUTSIDE_SOURCES` | A page outside a chapter-local `sources/` folder declares `type: source`. | Move the wrapper into the `sources/` folder of the chapter it supports. If the page is authored knowledge, give it `concept`, `entity`, `playbook` or `reference` and cite the source in `sources`. |
| `FRONTMATTER_MISSING_REQUIRED` | A required field is missing or empty. The message names the field. | Add the field. Every page needs at least one tag. |
| `FRONTMATTER_INVALID_AUTHORITY` | `authority` holds another value. | Use `external`, `grimoire` or `hybrid`. |
| `FRONTMATTER_MISSING_SOURCES` | An `external` or `hybrid` page has no `sources` entry. | Add the source. If the page itself is the source of truth, set `authority: grimoire`. |
| `FRONTMATTER_INVALID_DATE_FORMAT` | `last_verified` is not `YYYY-MM-DD`. | Write the date as `YYYY-MM-DD`. |
| `FRONTMATTER_INVALID_DATE` | `last_verified` has the right form and names no real date. | Correct the month or day. |
| `FRONTMATTER_IMPLAUSIBLE_DATE` | `last_verified` is earlier than `2020-01-01`. | Set it to the date the page was last verified. |
| `FRONTMATTER_LIST_REQUIRED` | `tags` or `aliases` is a single value. | Write it as a list: `tags: [a, b]`. |
| `FRONTMATTER_READ_ERROR` | The file is not valid UTF-8, or could not be read. The message holds the cause. | Save the file as UTF-8, correct its permissions, or remove the broken file. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. This validator emits no warnings. |
| 1 | At least one error. |
| 2 | `--grimoire` is not a directory, or the dispatcher rejected the arguments; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Fields, types and authority models -> [[docs/page_schema|page schema]]
- Source citations, and whether a cited source exists -> [[invocations/validators/validate_provenance|validate provenance]]
