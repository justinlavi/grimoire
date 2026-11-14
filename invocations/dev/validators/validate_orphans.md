---
type: reference
title: "Validate Orphans"
aliases: ["validate-orphans"]
tags: [framework/invocations, type/reference, scope/quality]
authority: grimoire
last_verified: 2026-05-12
---

# Validate Framework Orphans

## Purpose

Detect pages no other page reaches through valid layer-specific links. Orphans are pages the routing surface can't reach; they're either dead content or a missing hub pointer.

## Invocation

```
/grm-dev-validate orphans
```

Or directly:

```bash
FRAMEWORK_HOME/bin/grimoire validate_orphans
```

For an active grimoire, use `/grm-check orphans`.

## Exempt

- The framework root hub (`grimoire.md`).
- `README.md`, `CHANGELOG.md`, `log.md`, `VERSION`.
- Source wrappers under chapter-local `sources/` folders.

Folder hubs are checked: an unreachable folder hub means the parent hub is missing a pointer.

## When to run

- As a phase of `/grm-dev-improve`.
- After bulk renames.
- After removing a framework hub or page.

## Resolutions

For each orphan, three options:

1. **Wire it** - add a link using the appropriate layer style: Markdown in public docs, wikilinks in vault/AI surfaces.
2. **Promote it** - turn it into a hub itself if it represents a folder concept.
3. **Delete it** - the content is dead.

Don't auto-wire orphans during validation. Surface them for judgment.

## Related

- Schema: [[docs/page_schema|page schema]]
- Validator suite: [[invocations/dev/validators/validators|validators]]
