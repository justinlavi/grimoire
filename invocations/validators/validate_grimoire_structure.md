---
type: reference
title: "Validate Grimoire Structure"
aliases: ["validate-structure-domain"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Validate Grimoire Structure

The `structure` validator of the `grimoire` profile
([rites/validate_grimoire_structure.py](../../rites/validate_grimoire_structure.py)) checks that a
grimoire has the manifest, files, folders and hubs the framework's scaffold requires. This page is
the reference for its rules, commands and diagnostic codes. It runs on a grimoire only; on the
framework the `structure` selector runs
[[invocations/validators/validate_structure|validate structure]].

## What it checks

The scaffold contract, `FRAMEWORK_HOME/formulae/grimoire/scaffold_contract.json`, names the required
directories, the managed files and the required JSON settings. The validator applies these rules:

1. **Manifest.** `grimoire.json` exists at the root, parses as JSON, and declares `name` and a
   `skill_prefix` that matches `^[a-z][a-z0-9]*$`. When `naming` is present it is a non-empty string
   of at most 40 characters. [[docs/reference|reference]] owns the manifest's fields.
2. **Root README.** `README.md` exists at the root.
3. **Root hub.** `<name>.md` exists at the root and declares `type: hub`. `<name>` is the manifest's
   `name`. When no `<name>.md` exists, a hub named after the root folder is accepted, so a checkout in
   a folder of any name validates the same way as the original. `orphans` finds the root hub the same
   way.
4. **Required directories.** `chapters/`, `inbox/`, `publish/` and `.obsidian/` exist.
5. **Chapter hubs.** Every folder under `chapters/` that holds Markdown at any depth has the hub
   `<folder>/<folder>.md`, and that hub declares `type: hub`.
6. **Hub placement.** A page under `chapters/` that declares `type: hub` is named after its folder.
   Rules 5 and 6 together let a reader tell a hub from a leaf by its path;
   [[docs/operating_model|operating model]] owns the hub convention.
7. **Managed scaffold files.** `.editorconfig`, `.gitattributes`, `.obsidian/app.json`,
   `inbox/README.md` and `publish/README.md` exist and are byte-identical to their copies in
   `FRAMEWORK_HOME/formulae/grimoire/`. They are support files that every grimoire shares, so a
   local variant makes grimoires behave differently across machines and assistants.
8. **Seeded files.** `.gitignore` and `.obsidian/graph.json` exist. The framework copies each in
   when it is absent and never overwrites it, so its content belongs to the grimoire and is not
   compared. Obsidian rewrites `graph.json` whenever a person changes the graph settings.
9. **Obsidian link settings.** `.obsidian/app.json` sets `"newLinkFormat": "absolute"` and
   `"useMarkdownLinks": false`. With other values, following an unresolved full-path wikilink in
   Obsidian creates a nested copy of the folder tree.
10. **Scaffold contract.** The contract loads and agrees with `FRAMEWORK_HOME/formulae/grimoire/`.

## What it scans

The validator reads the grimoire root, every folder and Markdown page under `chapters/`, and the
framework's `formulae/grimoire/` folder.

- Rules 5 and 6 skip asset folders (`templates`, `snippets`, `scripts`, `configs`, `assets`, `media`,
  matched without regard to case at any depth), chapter-local `sources/` folders, and folders whose
  name contains `<` or `>`. A folder under `chapters/` named `publish` is an ordinary chapter folder.
- `README.md`, the root hub and `grimoire.json` are customized per grimoire. The validator requires
  them and does not compare their content.
- `skills/` is optional.

## How to run it

| Target | Command | Rite call |
|---|---|---|
| A grimoire | `/grm-check structure` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT structure` |

`GRIMOIRE_ROOT` is the active grimoire, resolved by the
[[invocations/meta/grimoire_directory_guard|grimoire directory guard]]. The framework is not a
grimoire: `/grm-dev-validate structure` runs a different rite.

## Diagnostics

Every code is an error except `GRIMOIRE_STRUCTURE_MISSING_SEEDED`, which is a warning.

| Code | Meaning | Fix |
|---|---|---|
| `GRIMOIRE_STRUCTURE_MISSING_MANIFEST` | No `grimoire.json` at the root. | Create it with `name` and `skill_prefix`. |
| `GRIMOIRE_STRUCTURE_INVALID_MANIFEST` | `grimoire.json` does not parse, lacks `name` or `skill_prefix`, or holds an invalid `skill_prefix` or `naming`. The message names the fault. | Correct the field the message names. |
| `GRIMOIRE_STRUCTURE_MISSING_FILE` | `README.md` is missing. | Create `README.md`; `FRAMEWORK_HOME/formulae/grimoire/README.md` is its template. |
| `GRIMOIRE_STRUCTURE_MISSING_ROOT_HUB` | `<name>.md` is missing at the root. | Create the root hub, or rename the existing hub to match the manifest's `name`. |
| `GRIMOIRE_STRUCTURE_HUB_NOT_DECLARED` | A folder-named page (the root hub or a `<folder>/<folder>.md`) does not declare `type: hub`. | Set `type: hub`. If the page is a leaf, rename it so its name differs from its folder's. |
| `GRIMOIRE_STRUCTURE_MISSING_DIR` | A required directory is missing. | Create the directory. |
| `GRIMOIRE_STRUCTURE_MISSING_CHAPTER_HUB` | A folder under `chapters/` holds Markdown and has no `<folder>/<folder>.md`. | Create the hub and route to the folder's pages from it. |
| `GRIMOIRE_STRUCTURE_HUB_MISPLACED` | A page declares `type: hub` and is not named after its folder. | If it is the folder's hub, rename it to `<folder>.md` with `/grm-move` so links follow. Otherwise change its `type` to the page type it is. |
| `GRIMOIRE_STRUCTURE_MISSING_MANAGED` | A managed scaffold file is missing. | Run `/grm-update`, or copy the file from `FRAMEWORK_HOME/formulae/grimoire/`. |
| `GRIMOIRE_STRUCTURE_STALE_MANAGED` | A managed scaffold file differs from the framework's copy. | Run `/grm-update`, or copy the file from `FRAMEWORK_HOME/formulae/grimoire/`. Keep a local variant only when the user asks for one; the validator keeps failing while it differs. |
| `GRIMOIRE_STRUCTURE_MISSING_SEEDED` | Warning: `.gitignore` or `.obsidian/graph.json` is missing. | Run `/grm-update`, or copy `FRAMEWORK_HOME/formulae/grimoire/gitignore` to `.gitignore` or `FRAMEWORK_HOME/formulae/grimoire/.obsidian/graph.json` to `.obsidian/graph.json`. |
| `GRIMOIRE_STRUCTURE_JSON_MISSING` | `.obsidian/app.json` is missing. | Same as a missing managed file. |
| `GRIMOIRE_STRUCTURE_JSON_UNREADABLE` | `.obsidian/app.json` is not valid UTF-8 JSON, or is not a JSON object. | Replace it with the framework's copy. |
| `GRIMOIRE_STRUCTURE_JSON_VALUE` | `.obsidian/app.json` holds a different value for a required setting. The message names the key, the required value and the value found. | Set the key to the required value, or replace the file with the framework's copy. |

Four codes report a fault in the framework, not in the grimoire. The fix for each is to bring the
framework current ([[UPDATE|UPDATE]]) and run the validator again.

| Code | Meaning |
|---|---|
| `GRIMOIRE_STRUCTURE_CONTRACT_READ` | The scaffold contract is missing or is not valid JSON. The validator stops after this diagnostic. |
| `GRIMOIRE_STRUCTURE_CONTRACT` | The scaffold contract disagrees with `formulae/grimoire/`. The message names the entry. |
| `GRIMOIRE_STRUCTURE_FORMULA_MISSING_MANAGED` | `formulae/grimoire/` lacks a managed file that the contract names. |
| `GRIMOIRE_STRUCTURE_FORMULA_ROOT_MISSING` | `FRAMEWORK_HOME/formulae/grimoire/` does not exist. |

## Exit codes

| Exit code | Meaning |
|---|---|
| 0 | No error. A `GRIMOIRE_STRUCTURE_MISSING_SEEDED` warning alone leaves the exit code at 0. |
| 1 | At least one error. |
| 2 | The dispatcher rejected the arguments, or the `--grimoire` path is not a directory; the validator did not run. |

## Related

- Selector table -> [[invocations/validators/validators|validators]]
- Run it with the other grimoire validators -> [[invocations/grm/check|check]]
- Hub convention and storage layers -> [[docs/operating_model|operating model]]
- Bring the managed scaffold current -> [[invocations/grm/update|update]]
