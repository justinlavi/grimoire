---
type: reference
title: "Validate Links"
aliases: ["validate-links"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Links

The `links` validator ([rites/validate_links.py](../../rites/validate_links.py)) checks that
internal links resolve, match the casing of the file on disk and use the link style of the layer
they sit in. This page is the reference for its rules, commands and diagnostic codes. It runs on a
grimoire and on the framework.

## What it checks

The validator sorts every Markdown file into one of two layers:

| Layer | Files | Link style for an internal page |
|---|---|---|
| Public documents | Any file named `README.md`, `UPDATE.md`, `CONTRIBUTING.md` or `CHANGELOG.md`, and every file under `docs/` at the root | Relative Markdown link, so the page stays clickable on a git host |
| Vault and AI-routing surfaces | Every other Markdown file: hubs, chapter pages, invocations, formulae, skills | Full-path wikilink, so routing does not depend on where the linking page sits |

[[docs/operating_model|operating model]] owns the layer rule and [[docs/obsidian|obsidian]] owns the
wikilink form. In every layer, a Markdown link is the form for an external URL, a same-page anchor
and a local file that is not a Markdown page.

| # | Rule | Code |
|---|---|---|
| 1 | The target of every Markdown link exists. | `LINK_MARKDOWN_BROKEN` |
| 2 | A Markdown link spells its target as the file is spelled on disk, including case. | `LINK_MARKDOWN_CASE_MISMATCH` |
| 3 | On a vault or AI-routing surface, a link to an internal page is a wikilink. | `LINK_MARKDOWN_INTERNAL` |
| 4 | A public document holds no wikilink. | `LINK_WIKILINK_PUBLIC_DOC` |
| 5 | A wikilink's target is a path from the root to a Markdown file. The `.md` suffix is optional. An alias or a bare filename fails unless it is also such a path. In a table cell the pipe is escaped (`\|`) and the backslash is not part of the path. | `LINK_WIKILINK_BROKEN` |
| 6 | A wikilink spells its target as the file is spelled on disk, including case. | `LINK_CASE_MISMATCH` |
| 7 | A wikilink's label, when it has one, is the target's filename with `_` and `-` read as spaces. Case is ignored. | `LINK_LABEL_VERBOSE` (warning) |
| 8 | Every page is valid UTF-8. A page that is not is skipped, so its links are not checked. | `LINK_READ_ERROR` |

Rule 3 treats a Markdown link as a link to an internal page when its target lies under the root and
ends in `.md`, resolves to a Markdown file, resolves to a folder that holds `README.md`, or has no
suffix while `<target>.md` exists.

A Markdown link target is read as the path it names: an optional title (`[hub](hub.md "The hub")`),
angle brackets, the `#anchor` and the `?query` are removed, and percent-encoding is decoded
(`my%20file.md` names `my file.md`).

Examples:

```markdown
<!-- On a vault or AI-routing surface -->
Travel -> [[chapters/travel/travel|travel]]            passes
Travel -> [travel](../travel/travel.md)                LINK_MARKDOWN_INTERNAL
Travel -> [[travel]]                                   LINK_WIKILINK_BROKEN
Travel -> [[chapters/travel/travel|our travel hub]]    LINK_LABEL_VERBOSE

<!-- In a public document -->
[Installation](docs/installation.md)                   passes
[[docs/installation|installation]]                     LINK_WIKILINK_PUBLIC_DOC

<!-- In either layer -->
[the rite](../../rites/validate_links.py)              passes
[this section](#what-it-checks)                        passes
```

## What it scans

The validator reads every Markdown file under the root.

- It skips the top-level folders `inbox/` and `tests/`, the top-level `publish/` folder,
  chapter-local `sources/` folders, and `.git/`, `node_modules/` and `.obsidian/` at any depth. A
  `publish/` folder deeper in the tree, such as the framework's `formulae/publish/`, is ordinary
  content and is checked.
- It ignores links inside fenced code blocks, indented or not and with backticks or tildes, and
  inside inline code.
- It does not check an external URL (`https://` or any other scheme), a `mailto:` link, a link that
  is only `#anchor`, or the `#anchor` part of any link.
- It does not check a link whose target holds `{` or `<`. On a page under `formulae/` it also skips
  a target that holds one of these template words: `FRAMEWORK_HOME`, `FRAMEWORK_PATH`,
  `GRIMOIRE_PATH`, `invocation_name`, `chapter_name`, `file_name`, `filename`, `related_page`,
  `related_chapter`, `sub_topic`, `Sub-topic`, `Chapter Name`, `Title`, `Source title`,
  `path/to/related` or `path/url/system`. On any other page those words are ordinary text, and a
  target that holds one is checked and reported when it does not resolve.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check links` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT links` |
| The framework | `/grm-dev-validate links` | `FRAMEWORK_HOME/bin/grimoire validate links` |

## Diagnostics

Every code is an error except `LINK_LABEL_VERBOSE`, which is a warning. Every code names the file
and gives the line, except `LINK_READ_ERROR`, which names the file only.

| Code | Meaning | Fix |
|---|---|---|
| `LINK_MARKDOWN_BROKEN` | A Markdown link's target does not exist. When the path differs from a real one only by case, the hint names the on-disk spelling. | Correct the path, or remove the link. |
| `LINK_MARKDOWN_CASE_MISMATCH` | A Markdown link resolves only because this filesystem ignores case. It breaks on Linux and in site builds. | Respell the link as the hint shows. |
| `LINK_MARKDOWN_INTERNAL` | A vault or AI-routing surface links to an internal page with a Markdown link. | Replace it with a full-path wikilink: `[[path/to/page\|page]]`. |
| `LINK_WIKILINK_PUBLIC_DOC` | A public document holds a wikilink. | Replace it with a relative Markdown link. |
| `LINK_WIKILINK_BROKEN` | A wikilink's target is not a path from the root to a Markdown file. When it differs from a real path only by case, the hint names the on-disk spelling. | Write the full path from the root. On a grimoire, `/grm-check fix` promotes filename-only wikilinks to full paths. |
| `LINK_CASE_MISMATCH` | A wikilink resolves only because this filesystem ignores case. It breaks on Linux and in site builds. | Respell the link as the hint shows. On a grimoire, `/grm-check fix` respells it. |
| `LINK_LABEL_VERBOSE` | Warning. A wikilink's label differs from the target's filename. The message gives the expected label. | Shorten the label to the filename; the path already carries the context. |
| `LINK_READ_ERROR` | A page is not valid UTF-8, or could not be read. The validator skipped it. | Save the file as UTF-8; [[invocations/validators/validate_encoding|validate encoding]] reports the same file. |

The two casing codes appear only on a filesystem that ignores case, such as Windows and macOS. On
Linux the same link is reported as broken.

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. `LINK_LABEL_VERBOSE` warnings alone leave the exit code at 0. |
| 1 | At least one error. |
| 2 | `--grimoire` is not a directory, or the dispatcher rejected the arguments; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire, and repair wikilinks with `/grm-check fix` -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Layer rule for links -> [[docs/operating_model|operating model]]
- Full-path wikilinks -> [[docs/obsidian|obsidian]]
- Pages that nothing links to -> [[invocations/validators/validate_orphans|validate orphans]]
