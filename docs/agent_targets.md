---
type: reference
title: "Agent Target Registry"
aliases: ["agent-targets", "agent-registry", "agent-support-matrix"]
tags: [type/reference, framework/docs, scope/agents]
authority: grimoire
last_verified: 2026-11-14
---

# Agent Target Registry

This page describes [`rites/data/agent_targets.json`](../rites/data/agent_targets.json), the
registry of the AI agents the framework supports and of where the framework writes for each one.
The file is the authority: the rites read it, and when this page and the file differ, the file is
right.

## Targets

| Agent | `id` | Instruction target (mode) | Skill target (mode) |
|---|---|---|---|
| Claude Code | `claude` | `~/.claude/CLAUDE.md` (`auto`) | `~/.claude/skills` (`full`) |
| Codex / ChatGPT CLI | `codex` | `~/.codex/AGENTS.md` (`auto`) | `~/.agents/skills` (`pointer`) |
| ChatGPT (hosted) | `chatgpt-hosted` | Custom Instructions (`manual`) | None (`none`) |
| GitHub Copilot | `github-copilot` | `.github/copilot_instructions.md` (`manual`) | None (`none`) |
| Cursor | `cursor` | Project or user rules (`manual`) | None (`none`) |

The `id` is the value that `--agent` takes in `sync_skills` and `inject_agent_file`.

## Modes

| Field | Value | Meaning |
|---|---|---|
| `instruction_mode` | `auto` | The installer, `/grm-update` and `inject_agent_file` write the routing block into the instruction target |
| | `manual` | A person pastes the routing block, after the user approves |
| `skill_mode` | `full` | Registration copies every file of a skill's source folder |
| | `pointer` | Registration writes `SKILL.md` alone |
| | `none` | The agent has no skill folder the framework can write |

[Agent configuration](agent_configuration.md) owns how the routing block and the skills are
written.

## Which agents count

An agent that is not installed is not configured. The installer, `summon --check`, `--reconcile`
and `--update`, and `sync_skills` without `--agent` work on the agents whose home folder exists.
The home folder is the parent of the instruction target: `~/.claude` for Claude Code and `~/.codex`
for Codex. When no agent's home exists, every agent counts, so a machine with no assistant yet is
still set up. `sync_skills --agent <id>` and `inject_agent_file --agent <id>` write for the agent
you name whether or not its home exists.

## Conditions per agent

Each entry's `summary` and `limitations` fields hold these conditions in the file.

| Agent | Condition |
|---|---|
| Claude Code | The only agent that starts a command by itself (`supports_model_invocation`). The entry names the `grimoire` marketplace in `plugin_marketplace`: when plugins of that marketplace are installed (`<plugin>@grimoire` in `~/.claude/plugins/installed_plugins.json`) they serve the framework's commands, and `~/.claude/skills` holds only the grimoires' own skills. A plugin of the same name from another marketplace does not count. [Plugin mode](agent_configuration.md#plugin-mode) owns the detail |
| Codex / ChatGPT CLI | Codex also reads `~/.codex/skills`, which the entry lists in `deprecated_skill_targets`, so registration removes managed skills from that folder |
| ChatGPT (hosted) | The framework can reach no local skill folder |
| GitHub Copilot | The instruction file belongs to a project, so ask the user before you edit it. A length limit may force you to trim the block to its routing sections |
| Cursor | The framework does not manage Cursor rule files |

## Change the registry

Edit the JSON file, then this page. Two checks hold them together:

| Check | Enforces |
|---|---|
| `python rites/validate.py structure` | Every entry has the required fields and a valid `id`, `instruction_mode` and `skill_mode` |
| `python -m pytest tests/test_agent_targets.py` | This page names the label, the instruction target and the skill target of every entry; `sync_skills` takes its targets from the registry; `rites/summon.sh` downloads the registry and its loader |
