---
name: {{SKILL_PREFIX}}-dev-validate
description: Run the framework's mechanical validators and report what fails - all of them, or only the ones a selector names
when_to_use: Before committing a change to the framework; after editing the framework's docs, playbooks, rites, skills or command metadata; the user asks whether the framework validates, or whether its links, frontmatter, format or security checks pass.
argument-hint: "[all|smart|auto|summary|parallel|links|frontmatter|format|...]"
arguments: selector
user-invocable: true
allowed-tools: Bash Read
---

# Validate the Framework

Run the validators against the framework and report what they found. The arguments, if given, are: **$selector**. Follow the invocation below exactly.

## Context

- **Framework root**: `{{FRAMEWORK_PATH}}`
- **Validator orchestrator**: `{{FRAMEWORK_PATH}}/bin/grimoire validate $selector`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/validators/validate.md`
