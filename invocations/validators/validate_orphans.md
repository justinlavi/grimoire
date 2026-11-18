---
type: reference
title: "Validate Orphans"
aliases: ["validate-orphans"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Orphans

The `orphans` validator ([rites/validate_orphans.py](../../rites/validate_orphans.py)) finds pages
that no page links to. Such a page cannot be reached by routing from the root hub: it is either
dead content or a hub is missing a pointer to it. This page is the reference for the validator's
rule, commands and diagnostic code. It runs on a grimoire and on the framework.

## What it checks

Every scanned page has at least one inbound link from a scanned page. Two kinds of link count:

- a wikilink, on any page, whose target resolves as a path from the root to a Markdown file;
- a Markdown link, in a public document, that resolves to a Markdown file under the root.

A Markdown link on a vault or AI-routing surface does not count, and neither does a link inside a
fenced code block or inline code. A page's link to itself does not count either. A Markdown link
is read as in [[invocations/validators/validate_links|validate links]], which defines the two
layers: a title, the `#anchor`, the `?query` and percent-encoding do not change the page it names.

Folder hubs are checked like any page: a hub with no inbound link means its parent hub lacks a
pointer.

## What it scans

The validator reads every Markdown file under the root, both as a page that needs a link and as a
source of links.

- It skips the top-level folders `inbox/`, `skills/`, `plugins/` and `tests/`, the top-level
  `publish/` folder, chapter-local `sources/` folders, and `.git/`, `node_modules/` and
  `.obsidian/` at any depth. A link from a skipped file does not count. A page that is not valid
  UTF-8 contributes no links.
- These pages need no inbound link: files named `README.md`, `UPDATE.md`, `CHANGELOG.md`,
  `CONTRIBUTING.md` or `SKILL.md`, and the root hub. The root hub is the file at the root
  named after the manifest `name` in `grimoire.json`, or in `framework.json` for the framework, such
  as `cooking-grimoire/cooking-grimoire.md`. When no such file exists the validator falls back to a
  file named after the root folder. The name of the checkout folder therefore does not matter: the
  framework installed at `~/.grimoire` keeps its hub `grimoire.md`.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check orphans` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT orphans` |
| The framework | `/grm-dev-validate orphans` | `FRAMEWORK_HOME/bin/grimoire validate orphans` |

## Diagnostics

| Code | Meaning | Fix |
|---|---|---|
| `ORPHAN_PAGE` | Error. No scanned page links to this page. The diagnostic names the page. | Choose one with the user; the validator cannot tell which is right. Link the page from the hub that owns its topic, in that layer's link style. Or merge its content into another page and delete it. Or delete it, on a grimoire with `/grm-remove`. |

Never wire an orphan to a hub only to clear the diagnostic. An orphan is a question about where
the page belongs, and a wrong pointer hides it.

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No orphan. This validator emits no warnings. |
| 1 | At least one orphan. |
| 2 | `--grimoire` is not a directory, or the dispatcher rejected the arguments; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Link layers and link style -> [[invocations/validators/validate_links|validate links]]
- Hub routing -> [[docs/operating_model|operating model]]
