---
type: reference
title: "Validate Encoding"
aliases: ["validate-encoding", "validate-newlines", "validate-mojibake"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Encoding

The `encoding` validator ([rites/validate_encoding.py](../../rites/validate_encoding.py)) checks
that text files are UTF-8 without a byte order mark, use LF line endings and hold no mojibake. This
page is the reference for its rules, commands and diagnostic codes. It runs on a grimoire and on
the framework.

## What it checks

Unicode is allowed: emoji, dashes, arrows and box-drawing characters all pass. The validator rejects
what breaks when a file moves between Windows, Linux, macOS, git and an assistant's rewrite. The
text file standard itself is owned by [[docs/reference|reference]].

1. **The file decodes as UTF-8.**
2. **The file does not start with a UTF-8 byte order mark** (the bytes `EF BB BF`).
3. **The file holds no carriage return.** CRLF and bare CR line endings both fail; without this
   rule git rewrites every touched file between LF and CRLF.
4. **The file holds no mojibake sequence:** the replacement character `U+FFFD`, or `U+00C3`,
   `U+00C2` or `U+00E2` followed by the character that completes a UTF-8 pair read in cp1252 or
   Latin-1: for `U+00C3` and `U+00C2`, a character from `U+00A0` to `U+00BF`; for `U+00C3` and
   `U+00E2`, also a C1 control or a character cp1252 maps to the bytes `0x80` to `0x9F`. These
   sequences appear when UTF-8 punctuation, accents or emoji are decoded in another encoding and
   saved again. The three letters alone are valid text: French and Portuguese words that use them
   pass.
5. **The file holds no repair artifact:** one of three fixed ASCII sequences that a failed dash or
   arrow repair leaves behind, or a `?` directly between two numbers, which is a range whose dash
   was lost. A `?` between two numbers inside a URL or a path (a token that holds `/` or `=`) is a
   query string and passes. `ASCII_ARTIFACTS` and `NUMERIC_RANGE_RE` in the rite hold the exact
   sequences; this page does not spell them, because it is itself checked.

Rules 4 and 5 each report the first match in a file, with its line.

## What it scans

The validator reads every file under the root that has a text suffix or a text name.

- Suffixes: `.cfg`, `.css`, `.csv`, `.html`, `.ini`, `.js`, `.json`, `.md`, `.py`, `.sh`, `.toml`,
  `.ts`, `.txt`, `.yaml`, `.yml`.
- Names: `.editorconfig`, `.gitattributes`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`,
  `VERSION`.
- Skipped folders: `.git`, `node_modules` and `.obsidian` at any depth, `publish` at the root, and
  `__pycache__`, `.mypy_cache` and `.pytest_cache` at any depth. A `publish/` folder
  deeper in the tree, such as the framework's `formulae/publish/`, is ordinary content and is
  checked.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check encoding` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT encoding` |
| The framework | `/grm-dev-validate encoding` | `FRAMEWORK_HOME/bin/grimoire validate encoding` |

## Diagnostics

Every code is an error.

| Code | Meaning | Fix |
|---|---|---|
| `ENCODING_UTF8` | The file is not valid UTF-8. The message holds the byte offset. | Save the file again as UTF-8 from its original encoding. |
| `ENCODING_BOM` | The file starts with a byte order mark. | Save the file as UTF-8 without BOM. |
| `ENCODING_CRLF` | The file holds a carriage return. | Convert the line endings to LF. The repository's `.gitattributes` and `.editorconfig` keep them that way. |
| `ENCODING_MOJIBAKE` | The file holds a mojibake sequence. The message quotes it and the diagnostic gives the line. | Restore the intended character from git history or from the source text. |
| `ENCODING_REPAIR_ARTIFACT` | The file holds a repair artifact. The message quotes it and the diagnostic gives the line. | Restore the intended dash, arrow or range. |
| `ENCODING_READ_ERROR` | The file could not be read. The message holds the cause. | Correct the file's permissions or remove the broken file. |

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
- Text file standard -> [[docs/reference|reference]]
- Path names that Windows accepts -> [[invocations/validators/validate_portability|validate portability]]
