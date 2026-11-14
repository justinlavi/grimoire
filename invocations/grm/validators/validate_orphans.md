---
type: reference
title: "Validate Grimoire Orphans"
aliases: ["validate-grimoire-orphans"]
tags: [framework/invocations, type/reference, scope/grimoire]
authority: grimoire
last_verified: 2026-05-25
---

# Invocation: Validate Grimoire Orphans

## Purpose

Detect authored grimoire pages that no other page links to.

## Invocation

```
/grm-check orphans
```

## Workflow

Run against the resolved active grimoire:

```bash
FRAMEWORK_HOME/bin/grimoire validate_orphans --grimoire GRIMOIRE_ROOT
```

Orphans are candidates to wire into a hub, merge, or delete after review.
