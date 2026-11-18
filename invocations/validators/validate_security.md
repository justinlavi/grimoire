---
type: reference
title: "Validate Security"
aliases: ["validate-security"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Security

The `security` validator ([rites/validate_security.py](../../rites/validate_security.py)) scans the
framework for text shaped like a hardcoded credential and scans the rites for `eval(` and `exec(`.
This page is the reference for its rules, commands and diagnostic codes. It runs on the framework
only.

## What it checks

1. **No Markdown or Python file holds a credential-shaped assignment.** Each pattern below is a
   name, then `=`, then a non-empty value in single or double quotes. The first four ignore case
   and match inside a longer name, so `client_secret = "..."` matches.

   | Pattern | Example that matches |
   |---|---|
   | `password` | `password = "example"` |
   | `api_key`, `api-key` or `apikey` | `API_KEY = "example"` |
   | `secret` | `secret = 'example'` |
   | `token` | `token = "example"` |
   | `BEGIN`, then `PRIVATE KEY` on the same line | The header line of a PEM private key |

2. **No rite contains `eval(`.** Evaluating text as code lets input run as code.
3. **No rite contains `exec(`.**

Rules 2 and 3 match the name `eval` or `exec` followed by `(`, as a whole word. They match text,
not syntax, so a comment or a string that holds the call also matches, and so does `builtins.eval(`.
A longer name that ends in the same letters, such as `ast.literal_eval(`, does not match.

The validator finds patterns. It cannot find a logic flaw, and it does not replace review of a rite;
[[invocations/dev/quality/validate_rites|validate rites]] is that review.

## What it scans

- Rule 1 reads every `.md` and `.py` file under `FRAMEWORK_HOME`, except under `.git/`,
  `node_modules/` and `.obsidian/`. It skips `rites/`, `invocations/validators/` and
  `invocations/dev/quality/`, which hold the patterns themselves or examples of them.
- Rules 2 and 3 read every `.py` file directly in `rites/`, except `validate_security.py`.
- A file that is not valid UTF-8 is reported with `SECURITY_READ_ERROR` and skipped; `encoding`
  reports it as an error.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate security` | `FRAMEWORK_HOME/bin/grimoire validate security` |

The `grimoire` profile has no `security` validator.

## Diagnostics

Every code is an error except `SECURITY_READ_ERROR`, which is a warning. The validator has no
allowlist and no per-line suppression.

| Code | Meaning | Fix |
|---|---|---|
| `SECURITY_CREDENTIAL_PATTERN` | A file holds a credential-shaped assignment. The message names the kind and the hint quotes the first 80 characters of the match. | If the value is real: remove it, rotate the credential, and read it from the environment or a file outside the repository. If it is an example: reword it so that no quoted value follows the `=`. |
| `SECURITY_EVAL` | A rite contains `eval(`. | Parse the input explicitly, or dispatch on it. |
| `SECURITY_EXEC` | A rite contains `exec(`. | Call an explicit API in its place. |
| `SECURITY_READ_ERROR` | Warning: a file is not valid UTF-8, so it was not scanned. | Run `encoding` and convert the file to UTF-8. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. A `SECURITY_READ_ERROR` warning alone leaves the exit code at 0. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments; the validator did not run. With `--grimoire`, `security` is an unknown selector and exits 2. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other framework validators -> [[invocations/validators/validate|validate]]
- Review of rite quality -> [[invocations/dev/quality/validate_rites|validate rites]]
- Security policy -> [[docs/governance|governance]]
