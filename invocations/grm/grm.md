---
type: hub
title: "Grimoire Invocations"
aliases: ["grimoire-invocations", "grimoire-ops"]
tags: [framework/invocations, type/hub, scope/grimoire, hub/chapter]
---

# Grimoire Invocations

The playbooks behind the ten `/grm-*` commands. Maintainer commands route through
[[invocations/dev/dev|dev]].

## Available

| Playbook | Command | Route here to |
|---|---|---|
| [[invocations/grm/setup|setup]] | `/grm-setup` | Set up a grimoire from a link or from a folder, or hand off to create |
| [[invocations/grm/create_grimoire|create grimoire]] | `/grm-create` | Start a grimoire from scratch |
| [[invocations/grm/add|add]] | `/grm-add` | Write up a topic or a chat answer, or file a document, a folder or the inbox as cited sources |
| [[invocations/grm/save|save]] | `/grm-save` | Share your changes |
| [[invocations/grm/update|update]] | `/grm-update` | Bring everything current, or reconcile one surface: `skills`, `library`, `agentfile` |
| [[invocations/grm/check|check]] | `/grm-check` | Run the full health pass, or one scope: `quick`, a validator, `naming`, `boundaries`, `fix` |
| [[invocations/grm/publish|publish]] | `/grm-publish` | Turn the grimoire into a website: `init <target>`, `build`, `check` |
| [[invocations/grm/move|move]] | `/grm-move` | Rename or move a page or chapter |
| [[invocations/grm/remove|remove]] | `/grm-remove` | Delete a page or chapter |
| [[invocations/grm/help|help]] | `/grm-help` | List the grimoire commands and the active grimoire's own skills |

## Related

- What each validator checks -> [[invocations/validators/validators|validators]]
- Shared fragments -> [[invocations/meta/meta|meta]]
- Maintainer commands -> [[invocations/dev/dev|dev]]
- Skill catalog -> [[docs/skills|skills]]
- Everyday use of the commands -> [[docs/getting_started|getting started]]
- Storage layers and hub routing -> [[docs/operating_model|operating model]]
