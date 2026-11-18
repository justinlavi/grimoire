---
type: reference
title: "Grimoire Directory Guard"
aliases: ["domain-guard", "grimoire-cwd-guard", "active-grimoire-guard"]
tags: [framework/invocations, type/reference, scope/meta]
authority: grimoire
last_verified: 2026-11-14
---

# Grimoire Directory Guard

How a command finds the grimoire it acts on, and how it learns whether it may change that
grimoire. Resolve `GRIMOIRE_ROOT` before you read or change any grimoire content.

1. Read `~/grimoires/library.json` and expand `$HOME` in each grimoire's `local_path`.
2. Apply the first row that matches the current working directory:

| Current working directory | Action |
|---|---|
| Equal to, or inside, a registered grimoire | Set `GRIMOIRE_ROOT` to that grimoire's root. |
| The framework root | Refuse, unless the user names a grimoire. |
| Elsewhere, and one grimoire is registered | Set `GRIMOIRE_ROOT` to it and tell the user which grimoire you selected. |
| Elsewhere, and several are registered | List them, ask which one to use, and continue after the user chooses. |
| Elsewhere, and none is registered | Stop. Tell the user to run `/grm-setup` to set one up. |

3. Stop when the active grimoire cannot be resolved without guessing.

The terminal does not have to `cd` into the grimoire. Use explicit paths:

- Rites: pass `--grimoire GRIMOIRE_ROOT`.
- File reads and writes: use paths under `GRIMOIRE_ROOT`.
- A command that needs a working directory: set it to `GRIMOIRE_ROOT`.

## Before a command changes the grimoire

A grimoire joined from a link is registered for reading on this computer (`"access": "read"` in
its library entry): updates keep it current, and no command changes its files. `/grm-add`,
`/grm-save`, `/grm-move`, `/grm-remove`, `/grm-check fix` and `/grm-publish init` change files, so
each of them first runs `FRAMEWORK_HOME/bin/grimoire grimoire_access --grimoire GRIMOIRE_ROOT --format json`:

- `summary.access` is `edit`: continue.
- `summary.access` is `read`: say that this copy is set up for reading, and ask once whether to
  switch it to editing. On yes, run the same command with `--set edit --apply`, confirm that
  `summary.access` is `edit`, and continue. On no, stop; nothing changed.

The switch changes one field of the library entry. The host of the grimoire decides whether the
user may share changes; `/grm-save` reports a refused push. A rite that reports `status: blocked`
with `summary.access` `read` met this rule: apply it.
