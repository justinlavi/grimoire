---
type: playbook
title: "Remove Grimoire Content"
aliases: ["remove", "delete", "remove-content"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Remove

Delete a page or a chapter from the active grimoire and leave nothing pointing at it. The rite
`rites/restructure_grimoire.py` deletes the files and reports every inbound wikilink that breaks;
this playbook does what the rite leaves to judgment: the confirmation, the parent hub and the
broken links.

## Trigger

```
/grm-remove [path]
```

The user says "delete this page", "remove the X chapter" or "get rid of Y".

| A request that looks similar | Goes to |
|---|---|
| Rename or move content, or keep it somewhere else | `/grm-move` |
| Repair filename-only or wrongly cased wikilinks | `/grm-check fix` |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above.
- `$target`: a path relative to the grimoire root, under `chapters/`: one page or a whole chapter
  folder.
- The plan that step 1 prints.

## Never

- Never apply before the user explicitly confirms the deletion. The rite cannot undo a removal.
- Never remove a chapter hub on its own; remove the whole chapter folder. A folder without its hub
  cannot be routed to.
- Never leave a wikilink that targets deleted content. A dead link sends the next reader, and the
  next assistant, nowhere.
- Never work around a refusal by deleting files by hand. A hand deletion reports no inbound links.

## Steps

### 1. Resolve the target and plan

```bash
FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire GRIMOIRE_ROOT --remove PATH
```

The plan writes nothing. It lists every page and every other file that would be deleted (a chapter
folder is deleted with everything in it) and every inbound wikilink that would break. The rite
refuses a path that does not exist, a path that does not resolve inside `chapters/` or that passes
through a symbolic link, and a chapter hub on its own.

- Done when: the rite exits 0 and prints `Would remove <path> (<n> page(s))` with the inbound
  wikilinks, or with the line that none exist.
- Stop when: the rite exits 1. When its message says the grimoire is set up for reading, apply the
  guard's rule for a command that changes the grimoire, and run this step again after a switch
  to editing. Otherwise report its reason and ask for a different target.

### 2. Confirm

Show the user what will be deleted, the pages and the other files (source artifacts, images) the
plan lists, and which inbound links will break. When important pages link to the target, suggest `/grm-move`
to relocate the content in place of deleting it.

- Done when: the user explicitly confirms the deletion.
- Stop when: the user does not confirm. Delete nothing.

### 3. Apply

```bash
FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire GRIMOIRE_ROOT --remove PATH --apply
```

- Done when: the rite exits 0 and prints `Removed <path> (<n> page(s))`.
- Stop when: the rite exits 1. Report its reason; nothing was deleted.

### 4. Repair the references

Work through every inbound link the rite reported:

| Link | Edit |
|---|---|
| The pointer in the parent chapter hub | Remove it. |
| Any other inbound link | Point it at a sensible replacement page, or remove the reference. |

- Done when: no page links to the deleted content.
- Stop when: a link has more than one plausible replacement. Ask the user which page it should
  point at.

### 5. Validate

```bash
FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT links orphans structure
```

Fix what the removal caused and run the command again.

- Done when: the command exits 0.
- Stop when: a diagnostic remains that the removal did not cause, or that needs a decision about
  content. Report it with its file and line.

## Evidence and checks

- Cite the rite's own lines for what was deleted and which links broke. With `--format json` the
  figures are `summary.removed_pages`, `summary.removed_other_files` (with the names in
  `summary.pages` and `summary.other_files`) and `summary.inbound_breaks`, and each broken link is a
  `warning` message.
- The removal is complete only when
  `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT links orphans structure` exits 0.

## Outputs

- The page or chapter folder deleted from `chapters/`.
- The parent hub and every page that linked to the deleted content edited as step 4 lists.
- A reply that says what was deleted, which links were repointed or removed and whether validation
  passed, followed by the one next action: `/grm-save` to share the change.

## Related

- Rename or move content: [[invocations/grm/move|move]]
- Repair wikilinks: [[invocations/grm/check|check]]
