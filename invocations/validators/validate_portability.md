---
type: reference
title: "Validate Portability"
aliases: ["validate-portability", "validate-windows-paths"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Portability

The `portability` validator ([rites/validate_portability.py](../../rites/validate_portability.py))
checks that every path can be checked out on Windows, Linux and macOS. This page is the reference
for its rules, commands and diagnostic codes. It runs on a grimoire and on the framework.

## What it checks

One path that Windows rejects makes `git checkout` abort there with `invalid path`, and the clone
is left with a partial working tree. The validator checks every segment of every file's path:

| # | Rule | Code |
|---|---|---|
| 1 | A segment holds none of the characters `<` `>` `:` `"` `\|` `?` `*`. Windows rejects them in names. | `PORTABILITY_RESERVED_CHAR` |
| 2 | A segment's name before its first `.` is not a Windows device name: `CON`, `PRN`, `AUX`, `NUL`, `COM1` to `COM9`, `LPT1` to `LPT9`, in any case. `aux.md` fails. | `PORTABILITY_RESERVED_BASENAME` |
| 3 | A segment does not end in `.` or a space. Windows strips them, so the name on disk differs from the name in git. | `PORTABILITY_TRAILING_DOT_SPACE` |
| 4 | No two entries in one folder, files or folders, differ only by case, such as `Notes.md` beside `notes.md` or `Notes/` beside `notes/`. On Windows and macOS one overwrites the other. | `PORTABILITY_CASE_COLLISION` |

The validator checks each path segment once, however many files lie beneath it: a reserved folder
name is one finding, and a pair of folders that differ only by case is one finding.

## What it scans

The validator reads the path of every file under the root, so it sees a folder through the files
inside it; a folder with no file is not seen. It skips `.git/`, `node_modules/` and `.obsidian/` at
any depth and `publish/` at the root.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check portability` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT portability` |
| The framework | `/grm-dev-validate portability` | `FRAMEWORK_HOME/bin/grimoire validate portability` |

Fix every finding before the grimoire or the framework is shared with another machine.

## Diagnostics

Every code is an error. The message names the segment and the reason.

| Code | Meaning | Fix |
|---|---|---|
| `PORTABILITY_RESERVED_CHAR` | A path segment holds a character Windows reserves. The diagnostic names the file or folder. | Rename it. For a placeholder, use curly braces: `{target_app}` in place of `<target_app>`. For an optional placeholder, use an `_opt` suffix: `{variant_opt}` in place of `<variant?>`. |
| `PORTABILITY_RESERVED_BASENAME` | A path segment is a Windows device name. | Rename the file or folder. |
| `PORTABILITY_TRAILING_DOT_SPACE` | A path segment ends in `.` or a space. | Remove the trailing character. |
| `PORTABILITY_CASE_COLLISION` | Two files, or two folders, in one folder differ only by case. The diagnostic names the folder (`.` for the root) and the entries. | Rename or merge one of them, then update the links to it. |

When the file itself was unintended, delete it instead of renaming it. In a grimoire, ask before
renaming imported material.

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
- Link casing, the other case rule -> [[invocations/validators/validate_links|validate links]]
- Text encoding and line endings -> [[invocations/validators/validate_encoding|validate encoding]]
