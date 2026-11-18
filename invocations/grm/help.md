---
type: playbook
title: "Grimoire Help"
aliases: ["grimoire-help", "grm-skill-catalog"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Help

Show the commands the user can run: the `/grm-*` commands and the active grimoire's own
commands. With `all`, also show the commands of every registered grimoire.

## Trigger

```
/grm-help
/grm-help all
```

The user asks what commands exist, what they can do here, or what Grimoire can do.

| A request that looks similar | Goes to |
|---|---|
| A command is missing from the picker | `/grm-update skills` |
| How one command works | That command's playbook, through [[invocations/grm/grm|grm]] |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above.
- The scope: none, or `all`.
- `FRAMEWORK_HOME/docs/skills.md`, the generated catalog of framework commands
  ([[docs/skills|skills]]).
- `GRIMOIRE_ROOT/grimoire.json`, for the grimoire's `name` and `skill_prefix`.
- `GRIMOIRE_ROOT/skills/*/SKILL.md`, for the `description` of each of the grimoire's own commands.
- With `all`: `~/grimoires/library.json`, and the `grimoire.json` and `skills/*/SKILL.md` of every
  grimoire it lists.

## Never

- Never list a command from memory. A command that is not in the catalog or in a `skills/` folder
  does not exist, and a user who types it gets nothing.
- Never list the `/grm-dev-*` rows or the "Command contract" section of the catalog. They serve
  maintaining the framework, not using a grimoire.
- Never change a file. This playbook only reads.

## Steps

### 1. Read the framework commands

Read `FRAMEWORK_HOME/docs/skills.md` and take the rows of its "Grimoire operations" table: each
`/grm-*` command and what it does. Leave out every `/grm-dev-*` row.

- Done when: you hold one row per command in that table.
- Stop when: `docs/skills.md` is missing. Read the `description` of each
  `FRAMEWORK_HOME/skills/grm/*/SKILL.md` in its place, and tell the user that the catalog is missing
  and that `FRAMEWORK_HOME/bin/grimoire sync_docs --apply` regenerates it.

### 2. Read the active grimoire's own commands

1. Read `name` and `skill_prefix` from `GRIMOIRE_ROOT/grimoire.json`.
2. List `GRIMOIRE_ROOT/skills/*/SKILL.md`. Each folder is one command, named
   `/<skill_prefix>-<folder name>`; its `description` is in the file's frontmatter.

- Done when: you hold one row per folder, or you know that `skills/` is absent or empty.

### 3. Read every other registered grimoire (scope `all` only)

For each grimoire in `~/grimoires/library.json` other than the active one, expand `$HOME` in its
`local_path` and repeat step 2 on that folder.

- Done when: every grimoire in the library has its rows, or is marked as shipping no commands.
- Stop when: a `local_path` does not exist. List that grimoire as not found and suggest
  `/grm-update library`.

### 4. Present the catalog

Render one table per group, the command on the left and its description on the right. Use no ASCII
boxes and no decorative separators. When a grimoire ships no commands of its own, say so in one line
in place of its table.

```
Grimoire commands (/grm-*) - N commands
| Command | What it does |
|---|---|
| /grm-... | ... |

<Grimoire name> commands (/<prefix>-*) - N commands
| Command | What it does |
|---|---|
| /<prefix>-... | ... |
```

With `all`, add one table of the same shape for each other registered grimoire. Without it, end
with one line: `For the commands of every registered grimoire, run /grm-help all.`

- Done when: the user has the tables.

## Evidence and checks

- Every row comes from a file: `docs/skills.md` for a framework command, a `SKILL.md` for a
  grimoire command. Copy the description; do not paraphrase a command into doing more than its
  description says.
- Each `N` is the number of rows in its table.

## Outputs

- No file changes.
- A reply that holds the tables and the closing line, and nothing else.

## Related

- Skill catalog: [[docs/skills|skills]]
- Register missing commands: [[invocations/grm/update|update]]
- Command families and naming: [[docs/skill_schema|skill schema]]
