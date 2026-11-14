---
name: {{SKILL_PREFIX}}-dev-improve
description: Improve the framework itself - maintainer only
when_to_use: A framework maintainer or fork owner wants to audit, normalize, and upgrade the framework itself - its docs, invocations, formulae, rites, and skills; before cutting a release; after bulk changes. Maintainer-only; for a grimoire use /grm-update and /grm-check.
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Write Edit
---

# Improve the Framework

You are the framework maintainer performing a comprehensive improvement. Follow the invocation guide below exactly.

**Important**: This should be run from the framework directory: `{{FRAMEWORK_PATH}}`

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Rites**: `{{FRAMEWORK_PATH}}/rites/`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/dev/improve_framework.md`
