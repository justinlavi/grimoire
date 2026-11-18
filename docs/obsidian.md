---
type: reference
title: "Obsidian Setup"
aliases: ["obsidian", "obsidian-setup", "graph-view"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# Obsidian Setup

How to open a grimoire in Obsidian and read its graph. Every grimoire comes with the two Obsidian
settings files it needs, so there is nothing to configure.

## Open the grimoire

1. In Obsidian, choose *Open another vault*, then *Open folder as vault*, and pick the folder of
   the grimoire, for example `~/grimoires/cooking-grimoire`.
2. Open the page named after the folder, for example `cooking-grimoire.md`. It is the root hub,
   the contents page where every route starts.
3. Open the graph view: the graph icon in the left sidebar, or `Ctrl+G` (`Cmd+G` on a Mac).

The graph shows the root hub in hot pink, chapter hubs in cyan and deeper hubs in purple. When it
shows no colors, the settings files are missing; see the next section.

## The settings files

A grimoire carries `.obsidian/app.json` and `.obsidian/graph.json`. `/grm-update` restores
`app.json` to the copy that comes with the framework, so a change made to it in a grimoire does not
last. `graph.json` is the grimoire's own once it exists: `/grm-update` copies it in only when it is
missing, so the graph colors and filters you change in Obsidian stay.

When either file is missing, ask your assistant to run `/grm-update`. To restore them by hand,
copy both from `~/.grimoire/formulae/grimoire/.obsidian/` into the `.obsidian` folder of the
grimoire, then reopen the vault.

`app.json` holds two settings that a grimoire depends on:

| Setting | Value | What goes wrong without it |
|---|---|---|
| `newLinkFormat` | `"absolute"` | Obsidian reads a link such as `[[chapters/foo/bar]]` as relative to the open page. When that path does not exist, a Ctrl-click creates it without asking, as a nested copy of the folder tree. |
| `useMarkdownLinks` | `false` | Obsidian rewrites `[[...]]` links as `[label](path)` when it saves. The validators and the link repair expect `[[...]]` links. |

**A stray nested folder** such as `chapters/build_system/ci/chapters/build_system/ci/` means that
someone Ctrl-clicked a link while `newLinkFormat` was not set. Delete the nested folder, restore
the settings files as above, and reopen the vault.

`app.json` configures Obsidian only. VS Code needs its own setup; see [VS Code setup](vscode.md).

## What the colors mean

| Color | Hex | Group query | Marks |
|---|---|---|---|
| Hot pink | `#FF71CE` | `tag:#hub/root` | The root hub. There is one, and it is the entry point. |
| Cyan | `#01CDFE` | `tag:#hub/chapter` | The hub of a chapter directly under `chapters/`: a main branch of the grimoire. |
| Purple | `#B967FF` | `tag:#hub/sub` | Any deeper hub. It routes onward and holds no knowledge itself. |
| Lavender | `#C996FF` | `["type":"source"]` | A source wrapper in a `sources/` folder: the record of something a page cites. |
| Electric blue | `#4D4DFF` | `["type":"playbook"]` | A procedure: something to do. |
| Pale pink | `#FFB3DE` | `["type":"reference"]` | A definition or schema page: something to look up. |
| Obsidian's default | - | Everything else | Concept and entity pages. |

The [page schema](page_schema.md#tag-conventions) owns the tags and types the groups read.

To look at part of a grimoire, type a query into the graph's search filter, in the same syntax as
the groups: `path:chapters/build_system/` shows one chapter, and
`tag:#hub/chapter -path:chapters/projects/` shows the chapter hubs outside one folder.

The palette a new grimoire starts with is set in the framework, in
`formulae/grimoire/.obsidian/graph.json`. When you change it there, add a group only for a
structural distinction worth seeing in the graph, and keep the palette to about eight groups;
beyond that the colors stop being distinguishable. A grimoire that already has a `graph.json`
keeps its own.

## Useful Obsidian features

| Feature | What it gives you |
|---|---|
| Backlinks pane | Every page that links to the open page. |
| Local graph (`Ctrl+P` or `Cmd+P`, then *Open local graph*) | The graph around the open page. |
| Graph filters | *Hide attachments* shows pages only. *Hide orphans* hides pages that nothing links to. |
| Dataview, a community plugin | Queries over the fields at the top of each page: `type`, `tags`, `last_verified`, `authority`. |
| Folder Notes, a community plugin | A click on a folder opens its hub. |

Both plugins are optional, and a grimoire depends on neither. A Dataview list does not replace
the links written in a hub: your assistant routes by the links in the text of the page, and so do
the validators.

## What stays on your computer

- Your layout: open panes, recent files and the plugins you enabled. Obsidian keeps them in
  `.obsidian/workspace.json` and its neighbours, and a grimoire does not share those files.
- The position of nodes in the graph. Obsidian computes it each time.

## Related

- How links are written in a grimoire: [operating model](operating_model.md#links)
- The tags and types behind the colors: [page schema](page_schema.md)
- Setup for VS Code: [VS Code setup](vscode.md)
