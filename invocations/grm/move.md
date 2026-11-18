---
type: playbook
title: "Move or Rename Grimoire Content"
aliases: ["move", "rename", "move-content"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Move

Rename or move a page or a chapter inside the active grimoire and keep every link and hub correct.
The rite `rites/restructure_grimoire.py` moves the files and retargets every full-path wikilink
and every frontmatter `sources:` entry that pointed at them; this playbook does what the rite leaves
to judgment: the hubs and the display labels.

## Trigger

```
/grm-move [from-path] [to-path]
```

The user says "rename this page", "move X under Y" or "reorganize this chapter".

| A request that looks similar | Goes to |
|---|---|
| Delete a page or chapter | `/grm-remove` |
| Repair filename-only or wrongly cased wikilinks | `/grm-check fix` |
| Write a page that does not exist yet | `/grm-add` |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above.
- `$source` and `$destination`: paths relative to the grimoire root, both under `chapters/`, for
  example `chapters/setup/intro.md` and `chapters/onboarding/intro.md`. A rename is a move whose
  destination is another name in the same folder. Moving a whole chapter means moving its folder.
- The plan that step 2 prints.

## Never

- Never apply a move the user described in prose before they confirm the exact paths. A wrong
  guess rewrites links across the grimoire.
- Never move a chapter hub on its own; move the whole chapter folder. A hub is named after its
  folder, and a hub moved alone breaks that convention.
- Never work around a refusal by moving files by hand. The rite's refusals protect existing pages
  and the hub convention, and a hand move leaves every inbound link pointing at the old path.

## Steps

### 1. Resolve the source and the destination

Turn the request into `SRC` and `DST`. When the user described the change in prose, state the two
exact paths and ask for confirmation.

- Done when: `SRC` names one existing page or folder under `chapters/`, `DST` is a path under
  `chapters/` that does not exist, and the user confirmed any path you inferred.
- Stop when: the request fits more than one page or folder. Ask which one.

### 2. Plan the move

```bash
FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire GRIMOIRE_ROOT --move SRC DST
```

The plan writes nothing. Review the file moves, the wikilink rewrites and the source references it lists. Moving a chapter
folder also renames its folder-named hub. The rite refuses a source that does not exist, a
destination that already exists, a path that does not resolve inside `chapters/` or that passes
through a symbolic link, a chapter hub on its own, a destination inside the source, a page
destination that does not end in `.md`, and a move in which two pages would land at the same path.
A page that is not valid UTF-8 is left untouched and listed; fix its links by hand.

- Done when: the rite exits 0 and prints `Would move <n> file(s)` and
  `Would rewrite <n> wikilink(s) across <m> file(s)`.
- Stop when: the rite exits 1. When its message says the grimoire is set up for reading, apply the
  guard's rule for a command that changes the grimoire, and run this step again after a switch
  to editing. Otherwise report its reason and ask for different paths.

### 3. Apply

```bash
FRAMEWORK_HOME/bin/grimoire restructure_grimoire --grimoire GRIMOIRE_ROOT --move SRC DST --apply
```

- Done when: the rite exits 0 and prints `Moved <n> file(s)` and `Rewrote <n> wikilink(s)`.
- Stop when: the rite exits 1. Report its reason; nothing was moved.

### 4. Wire the hubs and the labels

The rite retargets link paths. It edits no hub and no display label. Make these edits:

| Where | Edit |
|---|---|
| Source chapter hub | Remove the pointer to the moved page when the page left that chapter. |
| Destination chapter hub | Add a full-path wikilink to the moved page. When the destination chapter has no hub, create one from `FRAMEWORK_HOME/formulae/chapter_hub.formula.md` and add a pointer to it in the parent hub. |
| Display labels | Correct every label that still names the old location. The rite keeps labels verbatim, so a renamed page can still read with its old label. |

- Done when: the destination hub routes to the moved content, the source hub does not, and no
  label names the old location.

### 5. Validate

```bash
FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT links orphans structure provenance
```

Fix what the move caused and run the command again.

- Done when: the command exits 0.
- Stop when: a diagnostic remains that the move did not cause, or that needs a decision about
  content. Report it with its file and line.

## Evidence and checks

- Cite the rite's own lines for what moved and how many links it rewrote. With `--format json` the
  figures are `summary.moved`, `summary.link_rewrites`, `summary.source_rewrites` and
  `summary.files_relinked`.
- The move is complete only when
  `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT links orphans structure provenance` exits 0.

## Outputs

- The moved page or chapter folder at `DST`, with a moved chapter's hub renamed after its folder.
- Every full-path wikilink to the moved files retargeted, and the source, destination and parent
  hubs edited as step 4 lists.
- A reply that says what moved where, how many links were updated, which hubs changed and whether
  validation passed, followed by the one next action: `/grm-save` to share the change.

## Related

- Delete content: [[invocations/grm/remove|remove]]
- Repair wikilinks: [[invocations/grm/check|check]]
- Add content: [[invocations/grm/add|add]]
- Hub convention: [[docs/operating_model|operating model]]
