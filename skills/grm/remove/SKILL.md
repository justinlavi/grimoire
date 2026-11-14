---
name: {{SKILL_PREFIX}}-remove
description: Delete a page or chapter and flag every link that pointed to it so nothing breaks silently - for renaming or moving use /grm-move
when_to_use: User wants to delete a page or remove a whole chapter from a grimoire - "delete this page", "remove the X chapter", "get rid of Y". Reports inbound links that would break and drops the hub pointer. For renaming or moving content use /grm-move.
argument-hint: "[path]"
arguments: target
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Write Edit
---

# Remove Grimoire Content

You are deleting a page or chapter from the active grimoire and making sure nothing is left pointing at it. Resolve the active grimoire, then follow the invocation.

If the user named a target, use it: **$target**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Invocation**: `{{FRAMEWORK_PATH}}/invocations/grm/remove.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/remove.md`
