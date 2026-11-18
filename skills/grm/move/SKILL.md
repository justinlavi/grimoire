---
name: {{SKILL_PREFIX}}-move
description: Rename or move a page or a chapter and fix every link that pointed to it
when_to_use: The user wants to rename a page or a chapter, move a page into another chapter, or reorganize where content lives, and says "rename this page", "move X under Y" or "reorganize this chapter". To delete content the command is /grm-remove.
argument-hint: "[from-path] [to-path]"
arguments: source, destination
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Move or Rename Grimoire Content

Rename or move a page or a chapter in the active grimoire. Follow the playbook below exactly. The source and destination the user named, if any: **$source -> $destination**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/move.md`
