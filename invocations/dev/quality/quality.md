---
type: hub
title: "Quality Invocations"
aliases: ["quality-invocations", "judgment-passes"]
tags: [framework/invocations, type/hub, scope/quality, hub/sub]
---

# Quality Invocations

Routes to the four judgment reviews of the framework. None has a command of its own: each runs as a step of `/grm-dev-improve`, in the order [[invocations/dev/improve_framework|improve framework]] sets.

## Available

| Review | Playbook | Question it answers |
|---|---|---|
| Architecture | [[invocations/dev/quality/review_architecture|review architecture]] | Are the layout, the names and the owner of each fact still the right design? |
| Rite quality | [[invocations/dev/quality/validate_rites|validate rites]] | Is each rite script safe to run, rerun and read? |
| Contract coherence | [[invocations/dev/quality/audit_contract_coherence|audit contract coherence]] | Is every sentence in the two machine contracts true of the code? |
| Documentation | [[invocations/dev/quality/improve_documentation|improve documentation]] | Does every page meet the writing standard? |

- Work a review defers -> [[docs/architecture_backlog|architecture backlog]]

## Related

- Mechanical validators -> [[invocations/validators/validators|validators]]
- Commands that maintain the framework -> [[invocations/dev/dev|dev]]
