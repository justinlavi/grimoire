---
name: {{SKILL_PREFIX}}-dev-improve
description: Check and improve the framework itself - run the validators and the quality reviews, apply the low-risk fixes, and report what is deferred
when_to_use: Before a framework release or a version bump; after changing the framework's docs, playbooks, formulae, rites or skills in bulk; when the framework reads as stale, repetitive or hard to navigate. To check a grimoire, use /grm-check.
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Write Edit
---

# Improve the Framework

Run the quality pass over the framework. Follow the invocation below exactly, from the framework directory: `{{FRAMEWORK_PATH}}`

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Rites**: `{{FRAMEWORK_PATH}}/rites/`, each run as `{{FRAMEWORK_PATH}}/bin/grimoire <rite>`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/dev/improve_framework.md`
