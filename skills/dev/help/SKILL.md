---
name: {{SKILL_PREFIX}}-dev-help
description: Display the framework skill catalog and installed grimoire skill guide
when_to_use: Maintainer or power user wants the complete platform catalog - every /grm-dev-* and /grm-* command plus every installed grimoire's own skills. Use when the user explicitly asks for the full platform catalog or all installed grimoires. For everyday grimoire-user help, use /grm-help.
user-invocable: true
allowed-tools: Bash Read
---

# Framework Help

You are displaying the framework skill catalog plus any skills installed by registered grimoires.

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Canonical framework skill catalog**: `{{FRAMEWORK_PATH}}/docs/skills.md` (auto-generated from `skills/<family>/<slug>/SKILL.md`)
- **Grimoire library**: `~/grimoires/library.json`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/dev/help.md`
