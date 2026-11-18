---
name: {{SKILL_PREFIX}}-remove
description: Delete a page or a chapter after showing you every link that would break, then clean up those links
when_to_use: The user wants to delete a page or remove a whole chapter, and says "delete this page", "remove the X chapter" or "get rid of Y". To rename or move content the command is /grm-move.
argument-hint: "[path]"
arguments: target
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Write Edit
---

# Remove Grimoire Content

Delete a page or a chapter from the active grimoire. Follow the playbook below exactly. The target the user named, if any: **$target**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/remove.md`
