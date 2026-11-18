---
type: hub
title: "{{GRIMOIRE_NAME}}"
aliases: ["{{GRIMOIRE_DIRECTORY}}", "{{GRIMOIRE_NAME_LOWER}}"]
tags: [grimoire/{{SKILL_PREFIX}}, type/hub, hub/root]
---

# {{GRIMOIRE_NAME}}

*{{GRIMOIRE_PURPOSE}}.* This page is the root hub: start here for any {{GRIMOIRE_DOMAIN}} request. [[README|README]] holds the full description. The framework's own hub is `FRAMEWORK_HOME/grimoire.md`.

## How to Route

- Follow one pointer below to its hub, then hub to hub, depth-first, until a leaf page answers the request.
- Follow only the pointers a hub lists.
- Link pages inside this grimoire with full-path wikilinks (`[[chapters/path/to/page|label]]`). Refer to the framework or another grimoire with a path placeholder (`FRAMEWORK_HOME/...`).

## Route By Chapter

{{CHAPTER_ROUTES}}

## Fallback

When no route matches, propose one leaf page and the hub pointer that reaches it. Do not answer inline.
