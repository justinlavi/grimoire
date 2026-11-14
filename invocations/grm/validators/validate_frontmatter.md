---
type: reference
title: "Validate Grimoire Frontmatter"
aliases: ["validate-grimoire-frontmatter"]
tags: [framework/invocations, type/reference, scope/grimoire]
authority: grimoire
last_verified: 2026-05-25
---

# Invocation: Validate Grimoire Frontmatter

## Purpose

Validate active-grimoire page frontmatter against
`FRAMEWORK_HOME/docs/page_schema.md`, including the rule that `type: source` is
reserved for source wrappers under `chapters/**/sources/`.

## Invocation

```
/grm-check frontmatter
```

## Workflow

Run against the resolved active grimoire:

```bash
FRAMEWORK_HOME/bin/grimoire validate_frontmatter --grimoire GRIMOIRE_ROOT
```

Use this when pages were added, imported, or edited. For the framework itself, use `/grm-dev-validate frontmatter`.
