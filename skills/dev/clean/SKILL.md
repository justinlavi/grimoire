---
name: {{SKILL_PREFIX}}-dev-clean
description: Remove temporary rite artifacts under the framework's rites/.artifacts
when_to_use: rites/.artifacts has accumulated transient validator output; before committing framework changes; user asks to clean up workspace artifacts.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash
---

# Clean Artifacts

You are cleaning up the temporary artifacts the validator orchestrator writes under the framework's `rites/.artifacts`.

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Invocation**: `{{FRAMEWORK_PATH}}/invocations/dev/clean.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/dev/clean.md`
