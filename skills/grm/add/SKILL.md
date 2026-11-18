---
name: {{SKILL_PREFIX}}-add
description: Put knowledge into your grimoire by writing up a topic, keeping an answer from this chat, or filing a document, a folder or the inbox
when_to_use: The user says "add this to the grimoire", "add a chapter for X", "document Y", "save this answer", "import this PDF", "file this article", "process the inbox" or "sort this folder", or has dropped files into the grimoire's inbox. For a whole new grimoire the command is /grm-create.
argument-hint: "[topic | \"this answer\" | file | folder | inbox]"
arguments: material
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Add

Put knowledge into the active grimoire. Follow the playbook below exactly. The material or path the user gave, if any: **$material**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/add.md`
