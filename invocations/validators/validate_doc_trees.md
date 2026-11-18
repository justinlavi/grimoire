---
type: reference
title: "Validate Framework Doc Trees"
aliases: ["validate-framework-doc-trees", "framework-validate-doc-trees", "validate-tree-diagrams-framework"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Doc Trees

The `doc-trees` validator ([rites/validate_doc_trees.py](../../rites/validate_doc_trees.py)) checks
that directory-tree diagrams in Markdown match the filesystem. It catches a README, hub or guide
that still lists a folder after the folder was renamed, added or removed. This page is the
reference for its rules, commands and diagnostic codes. It runs on a grimoire and on the framework.

## What it checks

A diagram is a root line followed by branch lines, inside a fenced code block:

```
<grimoire>/
├── README.md
└── chapters/
    └── recipes/
```

The validator recognises the branch markers `├──`, `└──` and `|--`. A branch line must follow the
root line within three lines. Text after ` #` on a line is a comment and is ignored.

1. **The diagram is anchored to a real directory.** The validator resolves the root line once, in
   this order, and takes the first directory that exists:
   1. the root being validated, when the root line's last segment equals the root's name: the
      manifest `name` of `grimoire.json`, or of `framework.json` for the framework. The name of
      the checkout folder does not matter, so the framework gives the same result installed at
      `~/.grimoire` or cloned into `grimoire`;
   2. the root line read as a path relative to the root being validated, with a leading `./`
      removed (`.github/workflows/` stays `.github/workflows/`);
   3. for a root line that is a single name, the first directory of that name under the root, in
      sorted order. The search skips what the other validators skip: `.git/`, `node_modules/` and
      `.obsidian/` at any depth and `publish/` at the root. A folder that holds no file is not
      found.
2. **Every listed entry exists under the anchor.** An entry that ends in `/` must be a directory.
   An entry without a trailing `/` that has deeper entries below it is a directory too, which is
   how `tree` prints one. Any other entry without a `/` is satisfied by a file or a directory.
3. **A complete diagram lists every immediate child of the anchor.** This rule applies only when
   the diagram has no `...` or `…` entry and no placeholder entry, and at least one of its top-level
   entries exists on disk. It never reports a name that starts with `.`, or `__pycache__`, `venv` or
   `node_modules`. A finding under this rule is a warning.

## What it scans

The validator reads every fenced code block in every Markdown file under the root, whether the
fence is indented or not and whether it uses backticks or tildes. It skips what is illustrative,
because comparing an illustration with the filesystem reports noise.

| Skipped | Condition |
|---|---|
| A file | It is named `CHANGELOG.md`, or it lies under the top-level `inbox/`, or under a folder the other validators skip (`publish/` at the root, `.git/`, `node_modules/`, `.obsidian/`). |
| Every diagram in a file | A segment of the file's path is `templates`, `snippets`, `scripts`, `examples`, `sources` or `inbox` (in any case), or contains `<`, `{` or `[`. |
| A diagram | Its root line contains a placeholder: `<`, `{`, `[`, `*`, `...` or `…`. |
| A diagram | No directory resolves for its root line, or it has no root line and starts with a branch. |
| An entry | The entry contains a placeholder. The rest of the diagram is still checked. |

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check doc-trees` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT doc-trees` |
| The framework | `/grm-dev-validate doc-trees` | `FRAMEWORK_HOME/bin/grimoire validate doc-trees` |

## Diagnostics

| Code | Meaning | Fix |
|---|---|---|
| `DOC_TREE_MISSING_ENTRY` | Error. The diagram lists a file or directory that does not exist under its anchor. The diagnostic gives the file and the line of the entry. | Correct the diagram when the layout changed. Create or rename the path when the diagram shows the intended layout. |
| `DOC_TREE_UNLISTED_ENTRY` | Warning. The anchor directory has an immediate child that a complete diagram does not list. The diagnostic gives the line of the diagram's root. | Add the entry, or add a `...` entry to mark the diagram as partial. |
| `DOC_TREE_PARSE_FAILED` | Error. A file is not valid UTF-8, or could not be read. The message holds the cause. | Repair the file the message names, then run the validator again. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. `DOC_TREE_UNLISTED_ENTRY` warnings alone leave the exit code at 0. |
| 1 | At least one error. |
| 2 | `--grimoire` is not a directory, or the dispatcher rejected the arguments; the validator did not run. |

When `--grimoire` is not a directory, the rite prints one line on stderr that names the path.

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it on a grimoire -> [[invocations/grm/check|check]]
- Run it on the framework -> [[invocations/validators/validate|validate]]
- Branch-marker style in tree examples -> [[invocations/validators/validate_format|validate format]]
