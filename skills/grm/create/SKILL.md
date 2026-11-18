---
name: {{SKILL_PREFIX}}-create
description: Start a new grimoire from scratch, with its folders, its first chapters and its commands set up
when_to_use: The user wants a new knowledge base, says "set up a grimoire for X" or asks how to create a grimoire. Use it in place of creating the folders by hand. To add a page or a chapter to a grimoire that exists, the command is /grm-add.
argument-hint: [grimoire-name]
arguments: name
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Create Grimoire

Create a new grimoire. Follow the playbook below exactly. The name the user gave, if any: **$name**

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/create_grimoire.md`
