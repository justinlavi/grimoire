---
type: reference
title: "Agent Configuration"
aliases: ["agent-config", "agent-setup"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-05-25
---

# Agent Configuration

Per-agent setup for using the framework and grimoire skills. The agent support matrix
lives in [agent targets](agent_targets.md), backed by
[`rites/data/agent_targets.json`](../rites/data/agent_targets.json). The
summoning rite ([installation](installation.md)) configures automatic local
targets from that registry.

For installation, see [installation](installation.md). For library and manifest schemas, see [reference](reference.md). For the current framework skill catalog, see [skills](skills.md). For command naming rules, see [skill schema](skill_schema.md).

---

## Agent Instruction Files

Each agent reads a "system instructions" file. Grimoire needs a small block in that file so the agent knows how to route through the library.

**Canonical block**: [grimoire block](../rites/templates/grimoire_block.md) — single source of truth for the instructions text. Copy this into manual targets listed in [agent targets](agent_targets.md). Do not duplicate the block in any other file — edit the canonical and the change propagates wherever it's referenced.

The block never changes when grimoires are added or removed — those changes happen in the library, not the agent file. When the framework itself changes the block, use `/grm-dev-update agentfile` to refresh automatic registry targets or explicitly supplied agent instruction files while preserving unrelated user instructions.

---

## Plugin Mode (Claude Code)

Claude Code runs the framework as two plugins, `grimoire` and `grimoire-dev`, served from the
repository's `.claude-plugin/marketplace.json`. Each plugin is a thin carrier
rendered by `rites/build_plugins.py` from the same `skills/<family>/<slug>/SKILL.md`
sources the flat registration uses, so `/grimoire:add` and `/grm-add` are the same
instructions; the committed `plugins/` tree is the render, and
`python3 rites/build_plugins.py` reports drift. The `grimoire` plugin's session-start
hook (`plugins/grimoire/hooks/hooks.json`, `plugins/grimoire/scripts/session_context.py`)
keeps the framework checkout at `~/.grimoire` current (clone when absent,
fast-forward when clean and on `main`, otherwise leave alone and say so),
prints the Grimoire routing block when `~/.claude/CLAUDE.md` does not carry
one, lists the installed grimoires, and adds a one-line drift note from
`summon.py --check`.

The registry marks Claude Code with `plugin_marketplace`. When the plugins are
installed (`~/.claude/plugins/installed_plugins.json` lists `grimoire@...` or
`grimoire-dev@...`), `sync_skills.py` registers only grimoire-owned skills into
`~/.claude/skills` and cleans the flat `grm-*` copies of a plugin-served family, and
`summon.py --check` treats the target as registered. Codex has no plugin
support in its IDE extension and keeps the flat registration and the injected
routing block.

## Skill Registration

Skills are `SKILL.md` files registered into agent-specific skill directories
declared in [agent targets](agent_targets.md). Registry skill modes define
whether a target receives full skill folders or pointer-only `SKILL.md` files.

All registration targets are written by the same rite:

```bash
~/.grimoire/bin/grimoire sync_skills            # all targets
~/.grimoire/bin/grimoire sync_skills --agent claude
~/.grimoire/bin/grimoire sync_skills --agent codex
~/.grimoire/bin/grimoire sync_skills --grimoire . # the framework + active grimoire
~/.grimoire/bin/grimoire sync_skills --reset-managed --dry-run
~/.grimoire/bin/grimoire sync_skills --reset-managed
```

The valid `--agent` values come from
[`rites/data/agent_targets.json`](../rites/data/agent_targets.json).

Invoke `/grm-dev-update skills` for a global refresh of the framework plus every installed grimoire. Invoke `/grm-update` from inside one grimoire to refresh the framework plus that active grimoire only. The summoning rite runs the global registration for you on install.

Use `--reset-managed` after major framework command-family changes or when old
registered skill directories block a refresh. Dry-run first to preview the
directories that would be replaced.

For the normal "bring this machine up to date" workflow, run `/grm-update`. It can run from any directory. It pulls the framework, validates it, refreshes the local library, pulls every grimoire in the library (branch-aware, with a manual-pull fallback for private hosts), updates agent integration when needed, re-registers skills, and heals each grimoire it confirmed current against the structure rules.

For Codex/ChatGPT, the registered directory must contain only `SKILL.md` — never bundle scripts or references. The generated `SKILL.md` carries its invocation inlined by the registration rite (see [skill schema](skill_schema.md#skillmd-structure)); the source skill stays a thin pointer.

The `grm-` namespace and each grimoire's prefix are framework-owned: every
skill in them is generated by the rite from a `SKILL.md` source. Registration
treats prefix membership as ownership, so any directory under a managed prefix
that is not in the current catalog is a stale framework skill and is removed or
overwritten — no ownership marker required. This guarantees a re-register never
leaves a deprecated `/grm-*` or grimoire skill behind, while a
directory outside every managed prefix (a skill you authored) is never touched.
Each generated `SKILL.md` still carries a `FRAMEWORK_SKILL_OWNERSHIP` metadata
comment naming its source for provenance. Registration plans list `create`,
`update`, stale cleanup, and collisions before writing. Prefix collisions between
grimoire skill sources block writes until the manifest prefixes are made unique.

---

## How Skills Work

A skill is a **thin pointer**. It delegates to one of:

- **Invocation-backed**: the source skill names a markdown guide via `` `!cat {{FRAMEWORK_PATH}}/invocations/...` ``; the registration rite inlines that guide into the generated skill, so the AI receives the instructions with the skill and follows them. Nothing is read at load time.
- **Rite-backed**: skill tells the AI to run a rite via `{{FRAMEWORK_PATH}}/bin/grimoire <rite>`. The script does the work.

Skills must never embed implementation logic directly. This separation keeps them portable across agent platforms.

For when to choose rite-backed vs invocation-backed (and the anti-patterns to avoid), see [script vs ai](script_vs_ai.md#applying-this-to-skills).

---

## SKILL.md Frontmatter Reference

Every `SKILL.md` declares its skill in YAML frontmatter. Required fields are minimal; optional fields tune how the agent presents and auto-invokes the skill.

| Field | Required | Used by | Notes |
|---|---|---|---|
| `name` | Yes | Both | Final registered command name. Source files use `{{SKILL_PREFIX}}-<slug>`; the registration rite substitutes `{{SKILL_PREFIX}}` with the grimoire's skill prefix at install time. |
| `description` | Yes | Both | One-line summary. Codex/ChatGPT renders it next to the command in the picker UI. Claude Code loads it into the model's reasoning context (see "Auto-invocation" below). |
| `argument-hint` | No | Both | Bracketed hint shown during `/` autocomplete (e.g. `[topic]`, `[directory-name]`). |
| `arguments` | No | Both | Comma-separated argument names available as `$name` in the SKILL.md body. |
| `allowed-tools` | No | Both | Space-separated list of tools the skill needs (e.g. `Bash Read Write`). |
| `user-invocable` | No | Both | `true` = appears in the `/` picker. Default depends on agent. |
| `when_to_use` | No | **Claude Code** | Helps Claude auto-invoke the skill without the user typing `/`. Phrase as natural-language scenarios ("User asks X", "User mentions Y"). Codex/ChatGPT ignores this field. |
| `disable-model-invocation` | No | **Claude Code** | `true` prevents Claude from ever auto-invoking the skill — only user-typed slash commands trigger it. Use for destructive ops (deletions, irreversible changes). Codex/ChatGPT ignores this field. |
| `paths` | No | **Claude Code** | Glob patterns relative to the working directory; Claude loads the skill on its own when the user works on matching files. Scope narrowly (`chapters/travel/trips/**`), because a match loads the whole skill. Codex/ChatGPT ignores this field. |

Cross-agent safety: any field Codex/ChatGPT doesn't recognize is silently ignored. The same source `SKILL.md` works for both targets — no per-agent compilation needed.

### Auto-invocation policy

Adding `when_to_use` makes a skill discoverable by intent in Claude Code (the user describes a problem; Claude routes to the right skill). The current framework settings:

- **Most user-facing operations** (`/grm-*` and `/grm-dev-*`, such as `/grm-dev-update`, `/grm-setup`, `/grm-dev-help`, `/grm-dev-validate`) declare `when_to_use` so Claude can auto-suggest them.
- **One destructive skill** (`/grm-dev-clean`) declares `disable-model-invocation: true` because it deletes artifacts; users must invoke it explicitly.
- **Evaluation** lives behind `/grm-dev-validate` and `/grm-check` with their scope arguments. Both stay model-invocable; the judgment reviews (`/grm-check naming`, `/grm-check boundaries`) report in chat and write nothing, so auto-invocation is safe.

When adding a new skill, decide: does the user describe a *problem* that maps to this skill? If yes, give it a `when_to_use`. If the skill is destructive or maintainer-only, set `disable-model-invocation: true`.

The framework declares command families in `framework.json`:
- `grm` (`grm-*`) for universal grimoire operations that act on the active grimoire and the install.
- `dev` (`grm-dev-*`) for maintaining the framework itself (update, validate, improve, clean, help).

Normal grimoires declare one skill prefix in their own `grimoire.json`, such as `cook-*` or `dnd-*`.

Source `SKILL.md` files use `name: {{SKILL_PREFIX}}-<registered-slug>` in their frontmatter. The registration rite substitutes `{{SKILL_PREFIX}}` with the declaring command family's prefix for the framework, or with the grimoire's `skill_prefix` for grimoire-owned skills. See [skill schema](skill_schema.md) and [reference](reference.md#grimoire-manifest) for manifest details.

---

## Grimoire Skills

Grimoires contribute skills via their own `skills/` directory. Place each skill at `<grimoire>/skills/<area>-<verb>-<object>/SKILL.md`. The folder name is the subcommand after the skill prefix. Use `{{FRAMEWORK_PATH}}` and `{{GRIMOIRE_PATH}}` as path placeholders — the registration rite resolves both to absolute paths at install time.

To register new or updated skills in the active grimoire, run `/grm-update`. To refresh all installed grimoires, run `/grm-dev-update skills`.

---

## Troubleshooting

**Agent doesn't see new skills**
- Run `/grm-update skills` from the active grimoire. Then open a new agent session (Claude Code / Codex caches skill listings). (Maintainers can refresh every installed grimoire at once with `/grm-dev-update skills`.)

**Agent skills are badly stale or have old prefixes**
- Pull the framework, then read [`~/.grimoire/UPDATE.md`](../UPDATE.md) from that checkout and follow its instructions exactly. It is the stable path for cases where the installed slash-command layer cannot repair itself.

**The framework may be stale**
- Run `/grm-update`. It updates the framework and every grimoire in `~/grimoires/library.json`; the current directory does not need to be a grimoire.

**Agent has stale or missing Grimoire routing instructions**
- Ask your agent to run `/grm-update agentfile`. It creates a missing instruction file and refreshes a stale Grimoire routing block, preserving your other content. (Maintainer equivalent: `/grm-dev-update agentfile`.)

**Agent can't find a grimoire**
- Verify the grimoire is in `~/grimoires/library.json` and the `local_path` resolves. Ask your agent to run `/grm-update library` to reconcile the library against disk (the fix after moving or renaming a grimoire folder). (Maintainer equivalent: `/grm-dev-update library`.)

**Skill names look wrong (`{{SKILL_PREFIX}}-...`)**
- The grimoire is missing a `grimoire.json` or its `skill_prefix` field. See [reference](reference.md#grimoire-manifest).
