---
name: {{SKILL_PREFIX}}-save
description: Share your changes to the grimoire, after checking it and bringing in everyone else's changes
when_to_use: The user finished editing pages or filing sources and says "save", "share this", "send my changes", "push this" or "sync my edits", or asks how other people get their changes. To get everyone else's changes without sharing your own, the command is /grm-update.
argument-hint: "[what you changed]"
arguments: message
user-invocable: true
allowed-tools: Bash Read
---

# Save

Share the user's changes to the active grimoire. Follow the playbook below exactly. The user's description of the change, if any: **$message**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/save.md`
