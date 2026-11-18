---
name: {{SKILL_PREFIX}}-update
description: Bring Grimoire, your commands and every grimoire on this computer up to date, or repair one of them by name
when_to_use: The user wants everything up to date or wants everyone else's changes, says something may be stale, a command is missing or old, a grimoire folder was moved or renamed and the assistant cannot find it, or the assistant stopped reading the grimoire's pages. The user says "update", "update everything", "my command disappeared" or "the assistant can't find my grimoire".
argument-hint: "[skills | library | agentfile]"
arguments: scope
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Update

Bring the user's setup up to date. Follow the playbook below exactly, and run only the section of the scope. The scope, if given: **$scope**

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/update.md`
