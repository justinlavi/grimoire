---
type: reference
title: "Grimoire Operating Model"
aliases: ["operating-model", "routing-model"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# Grimoire Operating Model

How a grimoire is laid out and how an assistant moves through it: the storage layers, the hub
convention, links, naming, depth and the rules that stop authored knowledge from drifting. The
[page schema](page_schema.md) owns frontmatter and the [reference](reference.md) owns the
vocabulary.

| Section | Answers |
|---|---|
| [Storage Layers](#storage-layers) | Where each kind of content lives and who writes it |
| [Source wrappers](#source-wrappers) | How a source is filed so that pages can cite it |
| [Hub Convention](#hub-convention) | Which file routes a folder, and how that is enforced |
| [Links](#links) | Which link form each kind of file uses |
| [Naming And Depth Conventions](#naming-and-depth-conventions) | How files and folders are named, and how deep the tree goes |
| [Routing Principles](#routing-principles) | What every hub and leaf must do for routing to work |
| [How To Route](#how-to-route) | The steps from a request to the page that answers it |
| [Scope Rules](#scope-rules) | Where shared and scope-specific knowledge go |
| [Templates And Snippets](#templates-and-snippets) | Where reusable assets live |
| [Drift Management](#drift-management) | How a page stays true to the system it describes |

## Storage Layers

A grimoire keeps each kind of content in one layer.

| Layer | Path | Written by | Holds |
|---|---|---|---|
| Sources | `chapters/**/sources/` | The assistant, when `/grm-add` files a source; nobody edits it afterwards | Raw artifacts and source wrappers, beside the chapter material they support: articles, transcripts, papers, screenshots, datasets. Pages cite these paths. |
| Inbox | `inbox/` | The user and the assistant | Mixed content waiting to be classified. `/grm-add` with no argument clears it. |
| Wiki | `chapters/` and the root hub | The assistant | Authored pages, each with [frontmatter](page_schema.md). |
| Schema | `grimoire.json` and the routing block in the agent instruction file | The user, with the assistant | How an assistant operates this grimoire. |
| Publish | `publish/` | Build tooling; the assistant authors nothing here | Build and publishing output: a rendered site, an exported bundle, generated artifacts. |

Rules that hold across the layers:

- **A grimoire has no activity log.** Its history is its git history.
  `FRAMEWORK_HOME/bin/grimoire recent_changes --grimoire GRIMOIRE_ROOT` renders the recent content
  commits.
- **`publish/` is not a content layer.** Every grimoire has it, and it stays empty of output until
  the grimoire is published. The validators skip its contents, the knowledge graph excludes it, and
  pages never cite a path under it; `validate_provenance` warns when one does. The build output it holds is disposable; a build regenerates
  it.
- **`sources/` is permanent and `inbox/` is transient.** Pages with `authority: external` cite
  paths under `chapters/**/sources/`. `/grm-add` classifies each inbox item: a source goes beside
  the chapter material it supports, authored content goes to `chapters/`, and an item it cannot
  classify stays in `inbox/` for the user to decide.
- **A page never cites an `inbox/` path in `sources:`.** Inbox content disappears once it is
  processed, so `validate_provenance` rejects the citation.

### Source wrappers

A chapter's `sources/` folder holds raw artifacts, source wrappers, or both.

| Item | What it is | Path |
|---|---|---|
| Raw artifact | A file copied as received, in any format: a PDF, an article export, a transcript, an image, a dataset. It carries no frontmatter and is never rewritten to fit the page schema. | `chapters/<chapter>/sources/<file>` |
| Source wrapper | A Markdown capture record made from `FRAMEWORK_HOME/formulae/source.formula.md`. It declares `type: source` and `authority: external`, and its `sources:` points at the original URL, the capture origin or a sibling raw artifact. | `chapters/<chapter>/sources/<slug>.md` |
| Both | The wrapper, with the bulky or binary original in a folder of the same name. | `chapters/<chapter>/sources/<slug>.md` and `chapters/<chapter>/sources/<slug>/<file>` |

A `sources/` folder sits next to the material it supports, at any depth: a chapter, a sub-chapter,
a project, a trip.

- Use a wrapper when a text source needs a cleaned body, when a binary source needs readable
  capture metadata, or when an external URL needs a local record that pages can cite.
- Authored synthesis belongs in `chapters/`, outside `sources/`. A page that draws on a source
  cites the wrapper or the raw artifact in its `sources:` field; `validate_provenance` follows
  those pointers.
- A page may cite an external URL directly when the URL itself is the stable pointer. Once the
  content is filed locally, cite the local path, so the citation survives link rot.
- A source wrapper keeps no backlinks to the pages derived from it.

## Hub Convention

Every folder F that routes has a hub file at `F/<basename(F)>.md`. The rule is the same at every
depth:

- The root hub of a grimoire is `<grimoire>/<grimoire>.md`.
- The hub of a chapter or sub-chapter is `<folder>/<folder>.md`.

A hub routes to sub-hubs, to leaf pages, or to both. Folder-named hubs give every node in the
Obsidian graph a unique label and make full-path wikilinks readable, for example
`[[chapters/build_system/build_system|build system]]`. Hubs carry a level tag (`hub/root`,
`hub/chapter`, `hub/sub`); the [page schema](page_schema.md#tag-conventions) owns the tags, and
they do not change how routing works.

Under `chapters/`, a page is a hub exactly when its filename equals its folder name, so an
assistant can tell a hub from a leaf by path alone. `validate_grimoire_structure` enforces three
things:

1. Every folder that contains Markdown has a hub.
2. Every folder-named page, the root hub included, declares `type: hub`.
3. No other page declares `type: hub`.

Three kinds of folder are exempt because they do not route: asset folders (`templates/`,
`snippets/`, `scripts/`, `configs/`, `assets/`, `media/`), chapter-local `sources/` folders, and
folders whose name contains a `<placeholder>`.

## Links

The kind of file decides the link form for a pointer to another Markdown page.

| File | Link form | Example |
|---|---|---|
| Public documentation: every `README.md`, `UPDATE.md`, `CONTRIBUTING.md` and `CHANGELOG.md`, and everything under `docs/` | Relative Markdown link, so the page stays clickable on a Git host | `[page schema](page_schema.md)` |
| Vault and routing surfaces: root hubs, chapter pages, invocations, skill sources, formulae | Full-path wikilink | `[[chapters/projects/cf_sw/overview\|overview]]` |

In every file, an external URL, a same-page anchor and a local file that is not Markdown use a
standard Markdown link.

A wikilink follows four rules:

1. **The target is the path from the repository root.** Write
   `[[chapters/projects/cf_sw/overview|overview]]`, not `[[overview]]` or
   `[overview](overview.md)`. The `.md` suffix is optional. A bare filename is valid only for a
   file at the root, such as `[[README]]`.
2. **The target is spelled as the file is on disk,** including case.
3. **The label is the target filename, normalized for reading.** The path already carries the
   chapter and parent folders, so `[[chapters/travel/trips/2026/06_fukuoka/overview|overview]]`
   needs nothing more in its label. A label that repeats parent context draws a warning.
4. **An alias is never a target.** Aliases are page metadata. Linking by path keeps routing
   deterministic, prevents two pages from claiming one alias, and stops an editor from creating an
   empty page named after the alias.

`validate_links` enforces these rules; its [validator page](../invocations/validators/validate_links.md)
lists the diagnostics. [Obsidian setup](obsidian.md) and [VS Code setup](vscode.md) configure each
editor to resolve wikilinks from the repository root.

## Naming And Depth Conventions

### One naming convention per grimoire

Each grimoire names its files and folders in one convention, `snake_case` by default. Any casing
is valid. What matters is consistency inside the grimoire and links that match the spelling on
disk.

- The grimoire records its convention in `grimoire.json` as `naming`; the
  [reference](reference.md#grimoire-manifest) owns the field.
- `/grm-create` asks for the convention with `snake_case` preselected. `/grm-add` applies it to
  the material it writes, recommends it for imported material, and never renames an imported file
  or folder without asking. `/grm-check naming` reports deviations as advisory findings.
- `snake_case` is the default because a name in it greps as one whole word and stays stable in a
  full-path wikilink.
- Two rules are enforced by validators, because breaking them breaks a build: `validate_links`
  rejects a link whose casing differs from the file on disk, and `validate_portability` rejects
  two names in one directory that differ only by case.
- Folder roles (`sources/`, `templates/` and the other asset folders) are recognised in any
  casing.
- The framework's own tree is lowercase `snake_case`, enforced by `validate_naming`, with
  conventional exceptions such as `README.md`. Skill slugs use `kebab-case`.

A filename may carry extra dots before `.md`, and a wikilink to it resolves. Use them
deliberately, to mark a kind of deliverable or a role that is part of the page's identity.

| Pattern | Example file | Example wikilink |
|---|---|---|
| Acronym suffix | `plugin_ICD.md` | `[[chapters/documentation/icd/plugin_ICD\|plugin_ICD]]` |
| Role suffix | `plugin_ICD.template.md` | `[[chapters/documentation/icd/templates/plugin_ICD.template\|plugin_ICD.template]]` |
| Both | `gcs.SDK.example.md` | `[[chapters/sdk/gcs.SDK.example\|gcs.SDK.example]]` |

### Open-ended depth

The hub tree is as deep as the topic needs, and no deeper. No rule sets a maximum or a uniform
depth. A flat topic stays shallow (root, then leaf); a layered topic nests as far as it needs.
Each hop must narrow the search, so remove a hub only when it adds a hop without narrowing: a hub
that routes to a single leaf.

## Routing Principles

- **Minimal read.** Every hop narrows the search, and the path stops at the leaf that answers the
  question. The path is as short as the structure allows: root hub to leaf for a flat topic, root
  to chapter to sub-chapter to leaf for a layered one.
- **Hubs are maps.** A hub holds pointers. Leaf pages hold the invariants, stable patterns and
  source pointers.
- **One canonical leaf per rule.** State a rule in one leaf and link to it from every other place
  that needs it.
- **Two axes.** The hub tree is the primary axis; every page has one home in it. A topical facet
  tag (`domain/<...>`) is an optional second axis for subjects that cut across chapters. The
  [page schema](page_schema.md#tag-conventions) owns it.

## How To Route

1. Start at the root hub: `<grimoire>/<grimoire>.md`.
2. Classify the request. Decide which chapter it falls into, and whether it is shared or belongs
   to one project or use case.
3. Follow one explicit pointer. The target is a leaf, and routing is done, or it is another hub.
4. Repeat step 3 at each hub. Go depth-first. Branch to a sibling only when the current hub
   directs you to it.
5. Read the leaf. Read one related leaf only when the hub or the leaf's `Related` section calls
   for it.
6. For a rule that applies to one scope, follow the sub-hub that the root or chapter hub routes
   through, typically `projects/projects.md`, `clients/` or `teams/`, and then the hub of that
   scope.
7. When you add knowledge, add an explicit full-path wikilink to the hub that should route to it.
   Write the pointer as a route, not as a suggestion to search. When the content needs its own
   grouping, add a sub-folder with its own hub.

## Scope Rules

- A **shared chapter** holds rules that apply across every scope the grimoire covers: the house
  rules of a whole campaign in a D&D grimoire, the techniques of a whole kitchen in a cooking
  grimoire.
- A **scope-specific chapter**, often under `projects/`, `clients/` or `teams/`, holds the
  overrides and values that apply to one scope.
- Never put a scope-specific value in a shared chapter.
- Never copy a shared rule into a scope-specific page. Link to the shared page.

## Templates And Snippets

- Assets that belong to one chapter live in it: `chapters/<chapter>/templates/` and
  `chapters/<chapter>/snippets/`.
- Assets reused across chapters live in `chapters/shared/templates/`.
- A hub points at a concrete file, never at an instruction to search.
- A template is a standard. It sets how content is structured across the grimoire, and pages
  follow it.

## Drift Management

Every page except a hub declares where its truth lives: `external`, `grimoire` or `hybrid`. The
[page schema](page_schema.md#authority-models) owns the three models. Details that a code or
configuration system owns stay external. Procedures, policy and normalized domain knowledge can be
grimoire-authoritative when the page says so.

- **An external or hybrid page is query-first.** It cites the authoritative source by path or URL
  and gives the command that extracts the current value, instead of copying the value. A copied
  value carries the label "as of <date> - verify before use".
- **A grimoire-authoritative page carries change control.** It states that it is the source of
  truth, what is in and out of its scope, and how often it is reviewed. It cites external inputs
  as evidence, not as the authority.
- **Never store an implementation value that cannot be derived again.** A value with no query and
  no source pointer will drift. Replace it with a source pointer, or with a labeled snapshot that
  names its query.
