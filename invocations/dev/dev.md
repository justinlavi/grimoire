---
type: hub
title: "Framework Invocations"
aliases: ["framework-invocations", "maintainer-ops"]
tags: [framework/invocations, type/hub, scope/framework, hub/chapter]
---

# Framework Invocations

Routes to the playbooks behind the two commands that maintain the framework itself. Commands that act on a grimoire route through [[invocations/grm/grm|grm]].

## Available

| Command | Playbook | Use it to |
|---|---|---|
| `/grm-dev-validate [selector]` | [[invocations/validators/validate|validate]] | Run the framework's mechanical validators, all of them or the ones a selector names |
| `/grm-dev-improve` | [[invocations/dev/improve_framework|improve framework]] | Run the validators and the judgment reviews, apply low-risk fixes, and report what is deferred |

- The judgment reviews that `/grm-dev-improve` runs -> [[invocations/dev/quality/quality|quality]]
- One page per validator, with its selector -> [[invocations/validators/validators|validators]]

## Related

- Grimoire commands -> [[invocations/grm/grm|grm]]
- Shared fragments -> [[invocations/meta/meta|meta]]
- Command catalog -> [[docs/skills|skills]]
