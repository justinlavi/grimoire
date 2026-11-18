---
name: {{SKILL_PREFIX}}-help
description: List the Grimoire commands and this grimoire's own commands, or with all, the commands of every grimoire you have
when_to_use: The user asks what commands exist, what they can do here or what Grimoire can do, or says "help", "list the commands" or "what can I do".
argument-hint: "[all]"
arguments: scope
user-invocable: true
allowed-tools: Bash Read
---

# Grimoire Help

Show the commands the user can run. Follow the playbook below exactly. The scope, if given: **$scope**

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/help.md`
