---
type: reference
title: "Agent Configuration"
aliases: ["agent-config", "agent-setup"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# Agent Configuration

This page owns how the framework connects to an AI agent: the routing block in the agent's
instruction file, the Claude Code plugins, and skill registration. Other pages own the
neighbouring facts:

| Fact | Owner |
|---|---|
| Which agents are supported, their paths and modes | [Agent targets](agent_targets.md) |
| Install routes and troubleshooting | [Installation](installation.md) |
| Command families, command names, `SKILL.md` fields and body | [Skill schema](skill_schema.md) |
| The command catalog | [Skills](skills.md) |

| Section | Answers |
|---|---|
| [The routing block](#the-routing-block) | What an agent's instruction file must carry, and what writes it |
| [Plugin mode](#plugin-mode) | How Claude Code runs the framework as two plugins |
| [Skill registration](#skill-registration) | How commands reach an agent's skill folder |
| [Auto-invocation](#auto-invocation) | Which commands an agent may start by itself |
| [Grimoire skills](#grimoire-skills) | How a grimoire ships its own commands |

## The routing block

Every agent that uses grimoires carries one routing block in its instruction file. The block
tells the agent to resolve a grimoire through `~/grimoires/library.json` and to follow hubs to
the page that answers. It names no grimoire, so adding or removing a grimoire changes the library
and never the block.

- **One source.** The text is [`rites/templates/grimoire_block.md`](../rites/templates/grimoire_block.md).
  Edit only that file. The `grimoire` plugin carries a copy that `rites/build_plugins.py` renders.
- **The markers are the contract.** The block is the region between
  `<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->` and `<!-- END GRIMOIRE KNOWLEDGE BASE -->`. The
  framework owns every line between the markers. The user owns every line outside them.

For an agent whose instruction mode is `auto`, the installer, `/grm-update` and
`~/.grimoire/bin/grimoire inject_agent_file --apply` write the block. Without `--apply` the rite
prints its plan. It acts on the markers alone:

| The instruction file | The rite |
|---|---|
| Does not exist | Creates it with a heading and the block |
| Has no markers and no `## Grimoire Knowledge Base` heading | Inserts the block |
| Has one marked region that differs from the source | Replaces that region |
| Has one marked region equal to the source | Changes nothing |
| Has duplicate or malformed markers, or the heading with no markers, or is not UTF-8 | Writes nothing and reports the file for review |

The rite and the installer write only for the agents installed on this machine (an agent whose
home folder, such as `~/.codex`, is absent is skipped; [agent targets](agent_targets.md#which-agents-count)
says when). `summon --check` counts an absent, stale or unclean block as drift, except an absent
block for Claude Code while the `grimoire` plugin is installed: its session hook prints the block.

A file reported for review needs judgment. `/grm-update agentfile` runs the rite and then makes
that edit: it replaces the existing block, in whatever form it has, with the source, and keeps
every line outside the markers.

For an agent whose instruction mode is `manual`, paste the block from the source file into the
instruction target that [agent targets](agent_targets.md) names. Ask the user before you edit a
file inside a project.

## Plugin mode

Claude Code runs the framework as two plugins from the marketplace that the repository itself
declares in `.claude-plugin/marketplace.json`.

| Plugin | Carries | Commands |
|---|---|---|
| `grimoire` | The `grm` family and the session-start hook | `/grimoire:<verb>` |
| `grimoire-dev` | The `dev` family | `/grimoire-dev:<verb>` |

**The plugins are a render, not a second source.** `rites/build_plugins.py` renders `plugins/`
from the same `skills/<family>/<slug>/SKILL.md` files that flat registration uses, so
`/grimoire:add` and `/grm-add` carry the same instructions. Each plugin's description comes from its
entry in `.claude-plugin/marketplace.json`, which owns the wording. The repository commits the render.
`python rites/build_plugins.py` exits 1 when `plugins/` differs from the sources, and `--apply`
writes it.

**A release is an update.** Each plugin's `version` is the number in `VERSION`, written by
`build_plugins.py`. Claude Code offers an update when that number differs from the installed one,
and `main` changes only at a release, so the plugin and the framework checkout move together. A
machine receives a release in one of two ways:

| Way | How |
|---|---|
| By itself | Auto-update is on for the `grimoire` marketplace. `~/.grimoire/bin/grimoire plugin_auto_update --apply` turns it on in `~/.claude/settings.json` when that file declares the marketplace; so does the **Marketplaces** tab of `/plugin`, and an administrator can set it in managed settings |
| On request | `/plugin marketplace update grimoire`, then `/plugin update grimoire@grimoire` |

**The session-start hook keeps the framework checkout in step.** The `grimoire` plugin runs
`plugins/grimoire/scripts/session_context.py` at the start of every session
(`plugins/grimoire/hooks/hooks.json` declares it). The hook:

1. Clones the framework into `~/.grimoire` when it is absent. It fast-forwards the checkout when
   it is clean and on `main`. It leaves any other checkout alone and says so. A `.git` folder
   without a `rites/` folder is an interrupted clone: the hook restores the working tree, or
   clones again when the folder holds nothing else.
2. Prints the routing block when `~/.claude/CLAUDE.md` does not carry one.
3. Tells the agent that this install spells the commands `/grimoire:<verb>`.
4. Brings each grimoire in `~/grimoires/library.json` up to date: it fetches, and fast-forwards a
   copy that is clean and behind. It leaves alone a copy with unsaved changes, a copy with local
   commits that the shared copy lacks, and a copy whose remote it cannot reach, and it says which
   of these applies. An unreachable host is tried once per session. When an update changed a
   grimoire's own commands, the hook runs `sync_skills.py` to register them and says that they
   are available from the next session. Git runs with no credential prompt and no sign-in
   window, so a missing credential counts as an unreachable remote.
5. Lists the grimoires, each with its description, its path, `[read-only]` when its `access` is
   `read`, and the result of step 4.
6. Adds one line that says whether `summon.py --check` found drift.

The hook shares one 100-second time budget across its network and check steps, under the
120-second timeout `hooks.json` sets. A network that is unreachable, a malformed
`library.json`, or any other failure degrades to a one-line note, and the hook always exits 0.

**Flat registration steps aside for a plugin.** The registry marks Claude Code with
`plugin_marketplace`. When `~/.claude/plugins/installed_plugins.json` lists `grimoire@grimoire` or
`grimoire-dev@grimoire` (the plugin name, then the marketplace that `plugin_marketplace` names; a
plugin of the same name from another marketplace does not count), `sync_skills` removes the flat `grm-*` folders of the family that plugin
serves from `~/.claude/skills` and registers only the grimoires' own skills there.
`summon.py --check` counts such a target as registered.

Codex uses flat registration and the injected routing block.

## Skill registration

One rite, `sync_skills`, writes every skill folder the framework manages. It reads the
framework's `skills/<family>/<slug>/SKILL.md` files and the `skills/` folder of each grimoire in
the library, and writes to the skill target of each agent in
[agent targets](agent_targets.md).

| You want | Run |
|---|---|
| Every target, the framework and every grimoire | `~/.grimoire/bin/grimoire sync_skills` |
| One agent | `~/.grimoire/bin/grimoire sync_skills --agent claude` (or `codex`) |
| The framework and one grimoire | `~/.grimoire/bin/grimoire sync_skills --grimoire <path>` |
| The plan, with nothing written | Add `--dry-run` |
| Every managed folder removed and written again | Add `--reset-managed`. Use it when a stale folder blocks a refresh, and run it with `--dry-run` first |

In the agent, `/grm-update skills` runs the first row. The installer and `/grm-update` run the
rite as part of their work.

Three rules govern what the rite writes:

- **The skill mode of the target decides the files.** A `full` target receives every file of the
  skill's source folder. A `pointer` target receives `SKILL.md` alone, so a skill for Codex must
  not depend on a script or a reference file beside it. In both modes the generated `SKILL.md`
  carries its invocation inline; the [skill schema](skill_schema.md) describes how.
- **A managed prefix means ownership.** The framework owns the `grm-` prefix and the prefix of every grimoire in the library, including one that no longer ships
  skills. The same set drives the stale scan, `--reset-managed` and the cleanup of a target's
  deprecated skill folders. The rite removes or replaces any folder under a managed prefix that the current
  sources do not produce, so a registration never leaves a stale command behind. It never touches
  a folder outside every managed prefix, such as a skill the user wrote. Each generated
  `SKILL.md` carries a `FRAMEWORK_SKILL_OWNERSHIP` comment that names its source; the rite does
  not read that comment to decide what to write.
- **A collision blocks the write.** The plan lists each `create`, `update`, stale cleanup and
  collision before the rite writes. When two grimoires declare the same prefix or two sources
  produce the same command, the rite exits 1 and writes nothing to that target until the
  manifests are unique.

## Auto-invocation

A command starts by itself only in an agent that supports it, and only when its `SKILL.md`
allows it. The registry records the support in `supports_model_invocation`: Claude Code has it,
Codex does not.

Three `SKILL.md` fields act in Claude Code only. An agent ignores a field it does not know, so one
source file serves every target.

| Field | Effect in Claude Code |
|---|---|
| `when_to_use` | Claude starts the command when the user describes a matching need |
| `disable-model-invocation: true` | Only a typed command starts it |
| `paths` | Claude loads the skill when the user works on a matching file |

The policy for the framework's commands:

- A command that the user reaches by describing a problem declares `when_to_use`.
- A command that deletes, or that changes the framework itself, sets
  `disable-model-invocation: true`. Two commands set it: `/grm-remove` and `/grm-dev-improve`.
- `/grm-check` and `/grm-dev-validate` stay open to auto-invocation.
  `tests/test_skill_invocation_policy.py` enforces it.

## Grimoire skills

A grimoire ships its own commands in its `skills/` folder.

- Place each command at `<grimoire>/skills/<area>-<verb>-<object>/SKILL.md`. The folder name is
  the part of the command after the grimoire's prefix: `skills/recipe-add/` in a grimoire whose
  prefix is `cook` registers as `/cook-recipe-add`.
- The prefix is `skill_prefix` in the grimoire's `grimoire.json`; the [reference](reference.md)
  describes the manifest. Registration skips the commands of a grimoire that has no manifest or
  no prefix, and prints a warning.
- Write paths as `{{FRAMEWORK_PATH}}` and `{{GRIMOIRE_PATH}}`. Registration replaces both with
  absolute paths.
- Register with `/grm-update skills`, then start a new session.
