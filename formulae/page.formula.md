---
type: concept
title: "[Title]"
aliases: []
tags: [type/concept]
sources: []
authority: grimoire
last_verified: 1970-01-01
---

<!--
`FRAMEWORK_HOME/bin/grimoire new_page` stamps this formula: it fills the frontmatter and removes this comment.
The rules below apply to a copy made by hand. `FRAMEWORK_HOME/docs/page_schema.md` owns them.
- `type:` is one of concept, entity, playbook, reference. A `type: source` wrapper is made from source.formula.md under `chapters/<chapter>/sources/`.
- `authority:` is one of external, grimoire, hybrid.
- `sources:` is required when authority is external or hybrid: paths under chapters/**/sources/, or URLs.
- `aliases:` are optional alternate names for search. A wikilink never resolves through an alias.
- `tags:` use `/`-separated namespaces, for example [chapter/build_system, type/concept, domain/cmake].
- `last_verified:` is the date the page was last checked, as YYYY-MM-DD. 1970-01-01 marks an unstamped page and fails validation.
-->


# [Title]

## Purpose

[One or two sentences: what this page covers and what a reader can do with it.]

## When to Use

[The questions and situations that route a reader to this page. Name the neighbouring page for a case that looks similar and belongs there.]

## Primary Sources

[Required when authority is external or hybrid; remove the section otherwise. One line per source this page draws on: a file under the chapter's `sources/` folder, a URL, or the external system that owns the facts.]

- [path/url/system]

## [Content Sections]

[The knowledge itself, under headings named after what each section holds, for example Invariants, Rules, Workflow or Comparison. Lead each section with its rule, then the reason, then the exceptions.]

## Gotchas

[The mistakes and edge cases a reader is likely to hit, each with what to do instead. Remove the section when there are none.]

## Related

[One line per page a reader is likely to need next, as a full-path wikilink.]

- [[chapters/path/to/related_page_1|related page 1]]
- [[chapters/path/to/related_page_2|related page 2]]
