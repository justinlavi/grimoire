---
type: reference
title: "Validate Provenance"
aliases: ["validate-provenance"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Provenance

The `provenance` validator ([rites/validate_provenance.py](../../rites/validate_provenance.py))
checks that a page which claims an outside source cites one that exists. This page is the reference
for its rules, commands and diagnostic codes. It runs on a grimoire and on the framework.

## What it checks

For every page that declares `authority: external` or `authority: hybrid`:

| # | Rule | Code |
|---|---|---|
| 1 | `sources` is a YAML list. | `PROVENANCE_SOURCES_LIST_REQUIRED` |
| 2 | `sources` has at least one entry. | `PROVENANCE_MISSING_SOURCES` |
| 3 | No entry starts with `inbox/`. The inbox is emptied when its content is filed, so a citation into it breaks. | `PROVENANCE_INBOX_SOURCE` |
| 4 | Each entry that is a chapter-local path (`chapters/<chapter>/.../sources/...`) exists on disk. | `PROVENANCE_SOURCE_MISSING` |
| 5 | No entry points under `publish/`, which holds disposable build output and is not a content layer. | `PROVENANCE_PUBLISH_SOURCE` (warning) |
| 6 | Each other entry is a URL or names a file or folder that exists under the root. A path with a typo, such as `chapters/recipes/source/typo.pdf`, names nothing. | `PROVENANCE_SOURCE_UNRESOLVED` (warning) |

For every source wrapper, a Markdown file under a chapter-local `sources/` folder that declares
`type: source`:

| # | Rule | Code |
|---|---|---|
| 7 | `authority` is `external`. A wrapper captures outside material; authored synthesis belongs on a chapter page. | `PROVENANCE_SOURCE_WRAPPER_AUTHORITY` |
| 8 | `sources` is a YAML list. | `PROVENANCE_SOURCES_LIST_REQUIRED` |
| 9 | `sources` has at least one entry: the original URL, the capture origin or a sibling raw artifact. | `PROVENANCE_SOURCE_WRAPPER_MISSING_SOURCES` |
| 10 | No entry is the wrapper's own path. | `PROVENANCE_SOURCE_WRAPPER_SELF_REFERENCE` |
| 11 | Rules 3, 4 and 5 hold for each entry. Rule 6 does not: a wrapper may name its capture origin in words. | `PROVENANCE_INBOX_SOURCE`, `PROVENANCE_SOURCE_MISSING`, `PROVENANCE_PUBLISH_SOURCE` |

A URL is accepted without a check; the validator makes no network request. A page that is not valid
UTF-8 is skipped and reported as `PROVENANCE_READ_ERROR`.
[[docs/operating_model|operating model]] owns the storage layers and source wrappers, and
[[docs/page_schema|page schema]] owns the `authority` and `sources` fields.

## What it scans

The validator reads every Markdown file under `chapters/`, `docs/` and `invocations/`, and every
Markdown file directly at the root.

- It skips files named `README.md` and `CHANGELOG.md`, and any path with a `formulae` or
  `.git` segment.
- It reads a file under a chapter-local `sources/` folder as a source wrapper, and only when the
  file declares `type: source`. A `README.md` there is skipped.
- A page with `authority: grimoire` is not checked.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check provenance` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT provenance` |
| The framework | `/grm-dev-validate provenance` | `FRAMEWORK_HOME/bin/grimoire validate provenance` |

## Diagnostics

Every code is an error except `PROVENANCE_PUBLISH_SOURCE` and `PROVENANCE_SOURCE_UNRESOLVED`, which
are warnings. A diagnostic names the page; it gives no line.

| Code | Meaning | Fix |
|---|---|---|
| `PROVENANCE_SOURCES_LIST_REQUIRED` | `sources` is a single value, not a list. | Write it as a list: `sources: ["chapters/<chapter>/sources/<file>"]`. |
| `PROVENANCE_MISSING_SOURCES` | An `external` or `hybrid` page lists no source. | Add the source. If the page itself is the source of truth, set `authority: grimoire`. |
| `PROVENANCE_INBOX_SOURCE` | A `sources` entry points into `inbox/`. | File the item with `/grm-add`, then cite its path under the chapter's `sources/` folder. |
| `PROVENANCE_SOURCE_MISSING` | A chapter-local source path does not exist. | Correct the path. If the artifact was renamed or moved, cite its present path or move it back. |
| `PROVENANCE_SOURCE_WRAPPER_AUTHORITY` | A source wrapper declares an `authority` other than `external`. | Set `authority: external`. If the file is authored synthesis, move it out of `sources/` and give it a page type. |
| `PROVENANCE_SOURCE_WRAPPER_MISSING_SOURCES` | A source wrapper lists no source. | Add the original URL, the capture origin or the sibling raw artifact. |
| `PROVENANCE_SOURCE_WRAPPER_SELF_REFERENCE` | A source wrapper cites its own path. | Cite the original URL, the capture origin or the sibling raw artifact instead. |
| `PROVENANCE_PUBLISH_SOURCE` | Warning. A `sources` entry points under `publish/`. | Cite the chapter-local source the published file was built from. |
| `PROVENANCE_SOURCE_UNRESOLVED` | Warning. A `sources` entry on a page is not a URL and names no file or folder under the root. | Correct the path, or cite the source's URL. A repository outside the grimoire is cited by URL. |
| `PROVENANCE_READ_ERROR` | A page is not valid UTF-8, or could not be read. The validator skipped it. | Save the file as UTF-8. |

An empty `sources` on an `external` or `hybrid` page is also reported by
[[invocations/validators/validate_frontmatter|validate frontmatter]], as
`FRONTMATTER_MISSING_SOURCES`. One fix clears both validators. Whether a cited source exists is
checked here only.

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. Warnings alone leave the exit code at 0. |
| 1 | At least one error. |
| 2 | `--grimoire` is not a directory, or the dispatcher rejected the arguments; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Storage layers and source wrappers -> [[docs/operating_model|operating model]]
- `authority` and `sources` fields -> [[docs/page_schema|page schema]]
- File a source -> [[invocations/grm/add|add]]
