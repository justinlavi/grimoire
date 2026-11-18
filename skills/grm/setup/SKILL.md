---
name: {{SKILL_PREFIX}}-setup
description: Set up a grimoire to use, from a link you were given, from a folder of notes you have, or from scratch
when_to_use: The user just installed Grimoire or was told to use a grimoire, and says "set me up", "get started", "I have a link to a grimoire", "make this folder a grimoire" or "register this directory", or asks what to do first. Also when no grimoire is set up yet, or when an update reports a folder that is not a grimoire.
argument-hint: "[git url | folder]"
arguments: target
user-invocable: true
allowed-tools: Bash Read
---

# Setup

Set up a grimoire with the user, one question at a time. Follow the playbook below exactly. The repository link or folder the user passed, if any: **$target**

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/setup.md`
