---
type: reference
title: "Validate Format"
aliases: ["validate-format"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Format

The `format` validator ([rites/validate_format.py](../../rites/validate_format.py)) checks Markdown
that breaks rendering (table delimiter rows, code fences, tree examples) and the shape of the
framework's invocations, hubs and formulae. This page is the reference for its rules, commands and
diagnostic codes. It runs on a grimoire and on the framework.

## What it checks

| # | Rule | Applies to | Code |
|---|---|---|---|
| 1 | An invocation page has a title line that starts with `# `. | Every page under `invocations/` that is not a hub | `FORMAT_MISSING_INVOCATION_SECTION` |
| 2 | A playbook (`type: playbook`) has the six sections `## Trigger`, `## Inputs`, `## Never`, `## Steps`, `## Evidence and checks` and `## Outputs`, each spelled exactly. | The same pages | `FORMAT_MISSING_INVOCATION_SECTION` |
| 3 | A hub has at most 200 lines. | Every hub under `invocations/` | `FORMAT_HUB_TOO_LONG` |
| 4 | A formula has a title line that starts with `# `. | Every Markdown file under `formulae/` | `FORMAT_FORMULA_MISSING_TITLE` |
| 5 | A table delimiter row has three or more hyphens in a cell. | Every Markdown file, outside code fences | `FORMAT_SHORT_TABLE_DELIMITER` |
| 6 | Every fenced code block is closed. | Every Markdown file | `FORMAT_UNCLOSED_CODE_FENCE` |
| 7 | A tree example does not use the backtick branch marker. | Every Markdown file, inside code fences too | `FORMAT_TREE_BACKTICK_MARKER` |

Rules 1 to 4 read the folders `invocations/` and `formulae/` at the root. A grimoire has neither
folder, so rules 5 to 7 are the ones that apply to it.

Details the rules depend on:

- **Hub.** A file named after its folder, `<folder>/<folder>.md`. A hub routes, so a long hub is
  holding content that belongs on the pages it routes to.
- **Playbook sections.** [[formulae/invocation.formula|invocation.formula]] is the template, and
  [[docs/writing_standard|writing standard]] states what each section holds.
- **Table delimiter row.** Rule 5 reports a row of two or more cells in which every cell has one or
  two hyphens, such as `|--|--|`.
- **Code fences.** A fence opens with three backticks or three tildes and closes with the same
  character. Rule 6 reports the opening line of the block that never closes, once per file.
- **Backtick branch marker.** Rule 7 reports a tree line whose branch starts with a backtick
  followed by `--`. The marker `|--` is the accepted form.

## What it scans

- Rules 1 to 3 read every Markdown file under `invocations/`. Rules 1 and 2 skip the shared
  fragments `grimoire_directory_guard.md` and `subagent_lanes.md`.
- Rule 4 reads every Markdown file under `formulae/`.
- Rules 5 to 7 read every Markdown file under the root. They skip chapter-local `sources/`
  folders.
- Every rule skips the root `publish/` folder, and `.git/`, `node_modules/` and `.obsidian/` at any
  depth. A `publish/` folder deeper in the tree, such as `formulae/publish/`, is read.
- Each file is read once, as UTF-8. A file that is not valid UTF-8 is reported with
  `FORMAT_READ_ERROR` and skipped; `encoding` reports it as an error.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check format` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT format` |
| The framework | `/grm-dev-validate format` | `FRAMEWORK_HOME/bin/grimoire validate format` |

## Diagnostics

Every code is an error except `FORMAT_READ_ERROR`, which is a warning.

| Code | Meaning | Fix |
|---|---|---|
| `FORMAT_MISSING_INVOCATION_SECTION` | An invocation page lacks its title line, or a playbook lacks one of the six sections. The message names the missing part; one diagnostic per part. | Add the section with the exact heading and real content, following the invocation formula. |
| `FORMAT_HUB_TOO_LONG` | A hub under `invocations/` has more than 200 lines. | Cut each route to one line and move the detail to the page the route points at. |
| `FORMAT_FORMULA_MISSING_TITLE` | A file under `formulae/` has no line that starts with `# `. | Add the title heading. |
| `FORMAT_SHORT_TABLE_DELIMITER` | A table delimiter row has cells of one or two hyphens. The diagnostic gives the line. | Write three or more hyphens in each cell: `\|---\|---\|`. |
| `FORMAT_UNCLOSED_CODE_FENCE` | A fenced code block never closes. The diagnostic gives the line where it opens. | Add the closing fence with the same character. To show a fenced block inside a fenced block, open the outer one with tildes and the inner one with backticks. |
| `FORMAT_TREE_BACKTICK_MARKER` | A tree line uses the backtick branch marker. The diagnostic gives the line. | Replace the marker with `\|--` and keep the indentation aligned. |
| `FORMAT_READ_ERROR` | Warning: a Markdown file is not valid UTF-8, so its format was not checked. | Run `encoding` and convert the file to UTF-8. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. A `FORMAT_READ_ERROR` warning alone leaves the exit code at 0. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments, or the `--grimoire` path is not a directory; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Playbook template -> [[formulae/invocation.formula|invocation.formula]]
- Whether a tree example matches the filesystem -> [[invocations/validators/validate_doc_trees|validate doc trees]]
