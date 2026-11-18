---
name: {{SKILL_PREFIX}}-check
description: Find out whether your grimoire is in good shape by looking for broken links, unreachable, stale or contradictory pages and structural problems, or run one part of the check by name
when_to_use: The user asks whether the grimoire is healthy or valid, wants broken links, orphans, stale pages or contradictions found, asks whether names are clear and easy to find, wants system words in the content reviewed, or wants broken wikilinks repaired. Also before a save, after a batch of adds, and from time to time. The user says "check the grimoire", "health check", "validate", "find orphans", "fix wikilinks" or "audit naming".
argument-hint: "[quick | <validator> | naming | boundaries | fix]"
arguments: scope
user-invocable: true
allowed-tools: Bash Read Edit
---

# Check

Check the active grimoire. Follow the playbook below exactly, and run only the section of the scope. The scope, if given: **$scope**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/check.md`
