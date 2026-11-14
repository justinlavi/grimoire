---
type: reference
title: "Validate Framework Doc Trees"
aliases: ["validate-framework-doc-trees", "framework-validate-doc-trees", "validate-tree-diagrams-framework"]
tags: [framework/invocations, type/reference, scope/validators]
authority: grimoire
last_verified: 2026-11-13
---

# Invocation: Validate Framework Doc Trees

## Purpose

Detect drift between ASCII directory-tree diagrams (in fenced code blocks)
and the actual filesystem of the framework repository.

## Invocation

```
/grm-dev-validate doc-trees
```

## Workflow

Run against the framework repository root:

```bash
FRAMEWORK_HOME/bin/grimoire validate_doc_trees
```

Exit code 0 means every diagram with a resolvable filesystem anchor matches
reality. Most framework diagrams use placeholder roots like `{grimoire-name}/`
or `~/grimoires/` and are treated as illustrative.

## What it checks

See the grimoire-side
[[invocations/grm/validators/validate_doc_trees|validate doc trees]] for the
full algorithm. The framework-side invocation runs the same script with no
`--grimoire` flag (defaults to the framework root).

## Related

- Validators hub: [[invocations/dev/validators/validators|validators]]
- Improvement playbook: [[invocations/dev/improve_framework|improve framework]]
- Grimoire counterpart: [[invocations/grm/validators/validate_doc_trees|validate doc trees]]
