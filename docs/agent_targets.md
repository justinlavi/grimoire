---
type: reference
title: "Agent Target Registry"
aliases: ["agent-targets", "agent-registry", "agent-support-matrix"]
tags: [type/reference, framework/docs, scope/agents]
authority: grimoire
last_verified: 2026-05-25
---

# Agent Target Registry

## Purpose

The framework supports multiple AI agents, but not every agent exposes the same local
surfaces. The machine-readable source is
[`rites/data/agent_targets.json`](../rites/data/agent_targets.json). This page
is the human read path for instruction files, skill directories, automatic
configuration, and known limits.

## Targets

| Agent | Instruction target | Instruction mode | Skill target | Skill mode | Auto-configured | Auto-invocation |
|---|---|---|---|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` (plugin hook supplies the block when the `grimoire` plugin is installed) | auto | plugins `grimoire` and `grimoire-dev` from the `grimoire` marketplace; grimoire skills in `~/.claude/skills` | full | yes | yes |
| Codex / ChatGPT CLI | `~/.codex/AGENTS.md` | auto | `~/.agents/skills` (former `~/.codex/skills` cleaned of managed skills) | pointer | yes | no |
| ChatGPT (hosted) | Custom Instructions | manual | none | none | no | no |
| GitHub Copilot | `.github/copilot_instructions.md` | manual | none | none | no | no |
| Cursor | Project or user rules | manual | none | none | no | no |

## Skill Modes

- `full`: register every file from each skill source directory.
- `pointer`: register only `SKILL.md`; the skill points back to the framework or the
  grimoire source.
- `none`: the framework has no local skill directory to write for that agent.

## Instruction Modes

- `auto`: the Summoning Rite and `/grm-dev-update agentfile` can write the canonical
  Grimoire routing block to the target instruction file.
- `manual`: copy the canonical block from
  [grimoire block](../rites/templates/grimoire_block.md)
  after explicit user approval.

## Related

- [agent configuration](agent_configuration.md)
- [installation](installation.md)
- [`rites/sync_skills.py`](../rites/sync_skills.py)
- [`rites/agent_targets.py`](../rites/agent_targets.py)
