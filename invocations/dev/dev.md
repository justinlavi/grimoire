---
type: hub
title: "Framework Invocations"
aliases: ["framework-invocations", "maintainer-ops"]
tags: [framework/invocations, type/hub, scope/framework, hub/chapter]
---

# Framework Invocations

Maintainer and platform operations: invocations that modify the framework itself, the local grimoire library, user agent files, and agent skill directories. Five `/grm-dev-*` verbs.

For grimoire operations, route to [[invocations/grm/grm|grm]]. For the canonical skill catalog, see [[docs/skills|skills]].

## Available

### Improvement

- Framework improvement -> [[invocations/dev/improve_framework|improve framework]]

Boundary enforcement lives in the grimoire layer: `/grm-check boundaries --framework` runs it against the framework itself ([[invocations/grm/check|check]]).

### Update

- Bring the framework and every grimoire current, or reconcile one surface (`skills`, `library`, `agentfile`) at platform scope -> [[invocations/dev/update|update]]. Mirror of `/grm-update`; the canonical, skill-less procedure is [[UPDATE|UPDATE]].
- Register an unmanaged directory as a grimoire -> `/grm-setup <folder>` ([[invocations/grm/setup|setup]]).
- Clean transient workspace artifacts -> [[invocations/dev/clean|clean]]

### Validators

Mechanical, exit-code validators, run via `/grm-dev-validate [selector]`. Full list and selectors -> [[invocations/dev/validators/validators|validators]]

### Quality

Judgment-based quality audits and their orchestrator -> [[invocations/dev/quality/quality|quality]]

### Help

- Show the framework skill catalog and installed grimoire skills -> [[invocations/dev/help|help]]

## When to run

- Before any framework release
- After bulk doc/rite changes
- Monthly drift audit
- As phases of `/grm-dev-improve`

## Related

- Grimoire operations -> [[invocations/grm/grm|grm]]
- Meta support -> [[invocations/meta/meta|meta]]
