---
type: playbook
title: "Update"
aliases: ["update", "grm-update", "sync", "refresh-setup"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Update

Bring the user's setup current. With no scope, follow the update procedure in [[UPDATE|UPDATE]] for
the framework and every registered grimoire. With a scope, reconcile one local surface without
pulling anything: the commands in the picker, the list of grimoires, or the assistant's routing
block. This playbook is the owner of the three scopes.

## Trigger

```
/grm-update              # everything: pull, validate, re-register, refresh, heal
/grm-update skills       # register the framework's commands and every registered grimoire's commands
/grm-update library      # reconcile ~/grimoires/library.json with the folders on disk
/grm-update agentfile    # create or refresh the Grimoire routing block in the agent instruction files
```

The user says "update", "update everything" or "get everyone else's changes", or describes a symptom:

| Symptom | Scope |
|---|---|
| A command is missing from the picker, or is out of date | `skills` |
| A grimoire folder was moved or renamed and the assistant cannot find it | `library` |
| The assistant stopped following the library: its routing block is stale, or its instruction file was deleted (a fresh machine, a removed `~/.codex/`) | `agentfile` |
| Everyone else's changes, a framework release, or several of the above | none |

| A request that looks similar | Goes to |
|---|---|
| Share your own changes | `/grm-save` |
| Set up a grimoire from a link or from a folder | `/grm-setup` |
| Find out whether a grimoire is in good shape | `/grm-check` |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

No scope of this playbook needs an active grimoire. The update acts on the framework, on every
grimoire under `~/grimoires/` and on the user's agent instruction files. Continue when the guard
resolves no grimoire.

- The positional scope: none, `skills`, `library` or `agentfile`.
- `FRAMEWORK_HOME/UPDATE.md`, for the update without a scope.
- The output of the rite each scope runs. Add `--format json` to any of them for the envelope.

## Never

- Never report a number you counted yourself. An update that looks complete and is not leaves the
  user on stale commands or stale pages.
- Never write the library before the user has seen the drift report. Applying drops entries whose
  folders are gone.
- Never change a line outside the routing-block markers in an agent instruction file. Everything
  outside the markers belongs to the user.
- Never edit a project-level instruction file (a repository's `AGENTS.md`, `CLAUDE.md` or
  `.github/copilot_instructions.md`) without the user's confirmation, and never scan all of `$HOME`
  for instruction files.

## Steps

### 1. Route on the scope

Read the positional scope and run only its section below.

- Done when: one section is selected.
- Stop when: the scope is a word other than `skills`, `library` or `agentfile`. Ask which one the
  user means.

### Scope: none (the full update)

#### 1. Follow UPDATE.md

```bash
cat FRAMEWORK_HOME/UPDATE.md
```

Read [[UPDATE|UPDATE]] and follow its AI Update Playbook exactly. It owns every step: pulling the
framework, validating it, pulling and healing the grimoires, registering commands, refreshing the
routing blocks, the final gate, and what to report.

- Done when: the final gate in UPDATE.md, `FRAMEWORK_HOME/bin/grimoire summon --check --format json`,
  has run and you have its exit code.
- Stop when: a step of UPDATE.md reaches its own stop condition (a dirty framework tree, a pull
  that is not a fast-forward, a failed validation). Report it and let the user resolve it.

#### 2. Report

Give the report that UPDATE.md specifies, quoting the envelope of
`summon --update --apply --format json`: the `summary.grimoire_summary` counts, each grimoire's
`status`, the skill registration (`summary.skill_sync` and the `skills:` messages), and every
grimoire under `summary.needs_manual_pull`, each with the one-line instruction to pull it by hand.
Then ask the user to open a fresh session.

- Done when: the user has one line per grimoire and knows which grimoires were not updated.

### Scope: `skills`

Mutation profile: `plan_apply`, through `rites/sync_skills.py`.

#### 1. Register the commands

```bash
FRAMEWORK_HOME/bin/grimoire sync_skills
```

| Option | Effect |
|---|---|
| `--dry-run` | Print the planned registrations, clean-ups and collisions; write nothing |
| `--reset-managed` | Clear the managed namespaces, then write the current catalog fresh |
| `--agent claude` or `--agent codex` | Register for one assistant; the ids come from `FRAMEWORK_HOME/rites/data/agent_targets.json` |
| `--format json` | Print the envelope: `summary.registered`, `cleaned`, `reset`, `blocked` |

The rite registers the framework's commands and the commands of every registered grimoire. The
`grm-` prefix and each grimoire's prefix are namespaces the framework owns: the rite removes a skill
under one of them that is not in the current catalog, and it never touches a skill outside them.

- Done when: the rite exits 0 and prints `<assistant>: registered <n> skill(s)` for each assistant.
- Stop when: the rite exits 1. A collision blocked the registration; report each collision line and
  ask the user which skill keeps the name.

#### 2. Report

Tell the user, from the rite's lines for each assistant: how many commands were registered, how many
stale ones were cleaned, any collision, and which assistants were written. Give the count for the
assistant the user is in; do not add counts across assistants. Ask the user to open a fresh session,
because assistants cache the command list.

- Done when: the user has the counts and the request to open a fresh session.

### Scope: `library`

Mutation profile: `plan_apply`, through `rites/sync_library.py`.

#### 1. Report the drift

```bash
FRAMEWORK_HOME/bin/grimoire sync_library
```

The run writes nothing. Call out each kind of drift it prints:

| Drift | Meaning | Remedy |
|---|---|---|
| Missing | A grimoire on disk that the library does not list | `--apply` adds it |
| Stale | A library entry whose folder is gone, or whose path is empty or relative | `--apply` drops it |
| Mismatched | A library entry whose path differs from where the grimoire lives | `--apply` corrects it |
| Unmanaged | A folder under `~/grimoires/` with no `grimoire.json` | `/grm-setup <folder>` makes it a grimoire; otherwise move it out of `~/grimoires/` |
| Skill-prefix collision | Two grimoires declare the same prefix | Change one grimoire's `skill_prefix` in its `grimoire.json` |

- Done when: the user has seen every drift line, or the rite printed that the library is in sync.

#### 2. Apply when the user asks

```bash
FRAMEWORK_HOME/bin/grimoire sync_library --apply
```

The rite never registers a folder that holds a framework checkout, keeps unknown fields on existing
entries, and sorts entries by key. `--home <path>` points it at another grimoire home for testing.
Then run the `skills` scope, so that the commands of a grimoire the library gained are registered.

- Done when: the rite exits 0 and the `skills` scope has run.
- Stop when: the rite exits 1. Either another process changed the library during the write (run the
  scope again), or `library.json` cannot be read (the rite leaves it as it is; report the message
  and ask the user to fix or remove the file). Report the message.

### Scope: `agentfile`

Mutation profile: `plan_apply`, through `rites/inject_agent_file.py`, with a judgment edit for the
files the rite cannot decide.

#### 1. Plan

```bash
FRAMEWORK_HOME/bin/grimoire inject_agent_file
```

The routing block is the region between `<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->` and
`<!-- END GRIMOIRE KNOWLEDGE BASE -->`; the markers are the whole contract. The targets are the
`instruction_mode: auto` entries of `FRAMEWORK_HOME/rites/data/agent_targets.json` whose agent is
installed (its home folder, such as `~/.codex`, exists; with no agent installed, all of them). The
rite prints one action per target:

| Action | File state | With `--apply` |
|---|---|---|
| `create` | The file does not exist | Writes the file with a heading and the block |
| `insert` | The file has no routing block in any form | Adds the block |
| `refresh` | One clean marked region that is out of date | Replaces the region |
| `present` | One clean marked region that is current | Writes nothing |
| `review` | Duplicate or malformed markers, a block without markers, or a file that is not UTF-8 | Writes nothing; step 3 handles it |

- Done when: every target shows an action.

#### 2. Apply the mechanical actions

```bash
FRAMEWORK_HOME/bin/grimoire inject_agent_file --apply
```

Add `--agent claude` or `--agent codex` for one target, installed or not.

- Done when: the rite prints its `Done:` line, and each target line reads `created`, `inserted into`,
  `refreshed`, `present` or `needs the agentfile judgment edit`.

#### 3. Resolve the `review` targets

For each `review` target, and for a project-level file the user names, edit only the routing block:

1. Replace any existing routing block, in any form, with the canonical block from
   `FRAMEWORK_HOME/rites/templates/grimoire_block.md`.
2. When the file has no block, insert the canonical block after the first top-level heading, or at
   the end when there is no heading.
3. Keep every line outside the markers exactly as it is.

- Done when: `FRAMEWORK_HOME/bin/grimoire inject_agent_file` shows `present` for every target.
- Stop when: the file's intent is unclear, or the file is a project-level instruction file the user
  has not confirmed. Ask before editing.

## Evidence and checks

- Every count and status in the reply comes from a rite's own output: the `summon --update`
  envelope for the full update, the per-assistant lines of `sync_skills`, the drift lines of
  `sync_library`, the action lines of `inject_agent_file`.
- The full update is complete only when `FRAMEWORK_HOME/bin/grimoire summon --check --format json`
  exits 0. Exit 1 means drift remains; report `summary.next_actions`.
- A grimoire under `needs_manual_pull` was not updated. Say so; never count it as current.

## Outputs

- Full update: what UPDATE.md's procedure leaves (a current framework, current grimoires, a
  reconciled library, registered commands, refreshed routing blocks).
- `skills`: skill folders in each assistant's skill directory.
- `library`: `~/grimoires/library.json`, written only by `--apply`.
- `agentfile`: the routing block in each agent instruction file; no line outside the markers changes.
- A reply that leads with the outcome in the user's words ("your commands are up to date in this
  assistant"), gives the single next action (usually: open a fresh session), and names what was not
  updated.

## Related

- The update procedure: [[UPDATE|UPDATE]]
- Which assistants are supported and where their files live: [[docs/agent_targets|agent targets]]
- How skills and the routing block are registered: [[docs/agent_configuration|agent configuration]]
- The canonical routing block: `FRAMEWORK_HOME/rites/templates/grimoire_block.md`
- Set up a grimoire from a link or from a folder: [[invocations/grm/setup|setup]]
- Share your own changes: [[invocations/grm/save|save]]
