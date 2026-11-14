---
type: reference
title: "Validate Grimoire Format"
aliases: ["validate-grimoire-format"]
tags: [framework/invocations, type/reference, scope/grimoire]
authority: grimoire
last_verified: 2026-05-25
---

# Invocation: Validate Grimoire Format

## Purpose

Validate portable Markdown formatting in the active grimoire: table delimiters, fenced code blocks, and directory tree examples.

## Invocation

```
/grm-check format
```

## Workflow

Run against the resolved active grimoire:

```bash
FRAMEWORK_HOME/bin/grimoire validate_format --grimoire GRIMOIRE_ROOT
```

The grimoire mode uses the shared format rite but only applies checks that make sense for grimoire content. Framework-specific invocation and formula checks remain under `/grm-dev-validate format`.
