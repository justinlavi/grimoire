---
type: reference
title: "Page Schema"
aliases: ["frontmatter", "page-frontmatter", "frontmatter-spec"]
tags: [type/reference, framework/schema]
authority: grimoire
last_verified: 2026-11-14
---

# Page Schema

The YAML frontmatter that every authored Markdown page carries, in a grimoire and in the
framework: the fields, which page type requires which, and what the validators check.
Frontmatter lets a rite check provenance, staleness and page type, and lets Obsidian query them.

| Section | Answers |
|---|---|
| [Which files carry frontmatter](#which-files-carry-frontmatter) | Where the schema applies and what is exempt |
| [Frontmatter Fields](#frontmatter-fields) | Each field, its values and who must set it |
| [Page Types](#page-types) | The six values of `type` |
| [Authority Models](#authority-models) | The three values of `authority` and what each must cite |
| [Required-fields matrix](#required-fields-matrix) | Which type requires which field |
| [Tag conventions](#tag-conventions) | The tag namespaces, hub tags and topical facets |
| [Worked Examples](#worked-examples) | Frontmatter for a hub, a concept, a playbook and a source wrapper |
| [Validation](#validation) | What each rite enforces |

## Which files carry frontmatter

Every `.md` file under `chapters/`, `docs/`, `invocations/` and `formulae/`, and every `.md` file
at the root of the repository, carries frontmatter. The block starts with `---` on the first line
and ends with a closing `---`.

| Exempt | Reason |
|---|---|
| `README.md`, `UPDATE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE.md` | Public files read on a Git host |
| `SKILL.md` | Skills follow the [skill schema](skill_schema.md) |
| `CLAUDE.md`, `AGENTS.md` | Agent instruction files |
| A raw artifact under `chapters/**/sources/` | It is copied as received; the [operating model](operating_model.md#source-wrappers) owns the source layer |

A formula under `formulae/` carries placeholder frontmatter. The validator checks its `type` and
skips the other rules, because a placeholder such as `YYYY-MM-DD` would fail them. The schema
applies in full to the page made from the formula.

## Frontmatter Fields

```yaml
---
type: hub | concept | entity | source | playbook | reference
title: "Human-readable title"
aliases: ["alt name", "abbreviation"]
tags: [chapter/<chapter>, type/<type>, custom/<...>]
sources: ["chapters/<chapter>/sources/<artifact>.md", "https://...", "<path/under/the/root>"]
authority: external | grimoire | hybrid
last_verified: 2026-05-12
---
```

| Field | Required for | Rule |
|---|---|---|
| `type` | Every page | One of the six [page types](#page-types). |
| `title` | Every page | Free text. Obsidian shows it as the document title. |
| `tags` | Every page | A YAML list in the [tag namespaces](#tag-conventions). |
| `authority` | Every page except a hub | One of the three [authority models](#authority-models). |
| `last_verified` | Every page except a hub | The date, as `YYYY-MM-DD`, when the page was last verified by hand or by an automated check. A date before `2020-01-01` is rejected as a placeholder such as `1970-01-01`. `/grm-check` reports pages older than the stale window, 90 days by default. |
| `sources` | A page with `authority: external` or `authority: hybrid`, and every `type: source` page | A YAML list of paths or URLs. Every path under `chapters/**/sources/` must exist on disk. Any other path should name a file or folder under the root, and a path under `publish/` is not a source; `validate_provenance` warns about both. URLs are not fetched. |
| `aliases` | Optional | A YAML list of alternate names for search and Dataview. An alias is metadata; a wikilink never resolves through one. |

## Page Types

A page declares its `type` so that an assistant knows how to treat it and a validator knows which
rules apply.

| Type | Purpose | Lives in |
|---|---|---|
| `hub` | Routes a folder. It lists pointers to its children and holds no knowledge. | `<folder>/<folder>.md` |
| `concept` | A standing topic, idea or technique. | `chapters/<chapter>/<topic>.md` |
| `entity` | One person, place, organization, product or project. | `chapters/<chapter>/<entity>.md` |
| `source` | A source wrapper: capture metadata, with the source body or a pointer to one immutable artifact. | `chapters/<chapter>/sources/<slug>.md` |
| `playbook` | A procedure to follow step by step. | `chapters/<chapter>/<procedure>.md`, or a framework invocation |
| `reference` | A definition, glossary or schema page, read for lookup. | `chapters/<chapter>/<term>.md`, `docs/*.md` or a framework invocation |

When a page fits none of them, use `concept` and add a precise tag. Do not invent a type; the
validator rejects it.

`type: source` is reserved for source wrappers under `chapters/**/sources/`. A page that
synthesizes a source lives elsewhere under `chapters/`, takes `concept`, `entity`, `playbook` or
`reference`, and cites the wrapper or the raw artifact in `sources:`.

## Authority Models

Every page except a hub declares where its truth lives.

| Authority | Meaning | `sources` |
|---|---|---|
| `external` | The truth lives elsewhere: a code repository, an article, a paper, a service. The page summarizes and routes. | Required. Paths under `chapters/**/sources/`, other paths that exist under the root, or URLs. |
| `grimoire` | The page is the source of truth. Editing it changes the truth. | Optional. The body carries the change-control notes. |
| `hybrid` | The grimoire owns the synthesis; external systems own the implementation details. | Required. |

The [operating model](operating_model.md#drift-management) owns the rules that keep each model
from drifting.

## Required-fields matrix

| Type | `type` | `title` | `tags` | `authority` | `sources` | `last_verified` |
|---|---|---|---|---|---|---|
| `hub` | required | required | required | - | - | - |
| `concept` | required | required | required | required | required if external or hybrid | required |
| `entity` | required | required | required | required | required if external or hybrid | required |
| `source` | required | required | required | required, always `external` | required | required |
| `playbook` | required | required | required | required | required if external or hybrid | required |
| `reference` | required | required | required | required | required if external or hybrid | required |

`aliases` is optional for every type.

## Tag conventions

A tag is a flat string in a `/`-separated namespace. Write it without spaces; use `_` or `-`
inside a segment.

| Namespace | Marks | Rule |
|---|---|---|
| `chapter/<chapter_name>` | The page's place in the chapter tree | A hub carries the tag of its own chapter. |
| `type/<type>` | The same value as the `type` field | It lets Dataview query across tags. |
| `hub/<level>` | The level of a hub | `hub/root` for the root hub, one per grimoire; `hub/chapter` for a hub directly under `chapters/`; `hub/sub` for any deeper hub. |
| `domain/<...>` | An optional topical facet | See [Topical facets](#topical-facets). |
| `status/<state>` | An optional lifecycle state | `status/draft`, `status/stable`, `status/deprecated`. |

### Hub tags

The formulae write these tags, and the [Obsidian graph groups](obsidian.md) color hubs by them.

| Hub | Path | Tags |
|---|---|---|
| Root | `<grimoire>/<grimoire>.md` | `type/hub`, `hub/root`, `grimoire/<skill prefix>` |
| Chapter | `chapters/<chapter>/<chapter>.md` | `type/hub`, `hub/chapter`, `chapter/<chapter>` |
| Sub-chapter | `chapters/<chapter>/<sub>/<sub>.md`, or deeper | `type/hub`, `hub/sub`, `chapter/<sub>` |

### Topical facets

A topical facet is an optional second way to find a page. The hub tree is the first: every page
has one home, reached from hub to hub. A facet tag such as `domain/cmake` groups pages that span
chapters, so an assistant can find them with a text search for the tag instead of walking every
hub.

- Use a facet when a subject recurs across chapters.
- The owner of the grimoire chooses the namespace (`domain/<...>`, or another such as
  `topic/<...>`) and applies one consistently.
- No validator checks facets. The framework sets no topic vocabulary for a grimoire, so
  `/grm-check naming` reviews facet quality by judgment.

## Worked Examples

A chapter hub:

```yaml
---
type: hub
title: "Build System"
aliases: ["build", "build-system"]
tags: [chapter/build_system, type/hub, hub/chapter]
---
```

An external concept page derived from a source:

```yaml
---
type: concept
title: "Lamination"
aliases: ["laminating dough", "book folds"]
tags: [chapter/techniques, technique/dough, type/concept]
sources: ["chapters/techniques/sources/example_recipe_method.md"]
authority: external
last_verified: 2026-05-12
---
```

A grimoire-authoritative playbook:

```yaml
---
type: playbook
title: "VM Handover Procedure"
aliases: ["vm-handover", "handover-runbook"]
tags: [chapter/operations, type/playbook]
authority: grimoire
last_verified: 2026-05-12
---
```

A source wrapper, stored at `chapters/techniques/sources/example_recipe_method.md` and cited by
the concept page above:

```yaml
---
type: source
title: "Example Recipe Method - Lamination Chapter"
tags: [type/source]
sources: ["https://example.com/recipe-method"]
authority: external
last_verified: 2026-05-12
---
```

## Validation

Two rites enforce the schema. A page that fails either one is a violation, and the rite exits
with code 1.

`validate_frontmatter` checks that:

1. The file has frontmatter, opened by `---` on the first line and closed by `---`.
2. `type` is present and is one of the six values.
3. Every field the [matrix](#required-fields-matrix) requires for that type is present and not
   empty.
4. `authority`, when present, is `external`, `grimoire` or `hybrid`, and a page with `external` or
   `hybrid` lists at least one source.
5. A `type: source` page sits under `chapters/**/sources/`.
6. `last_verified` is a real `YYYY-MM-DD` date on or after `2020-01-01`. The check never compares
   the date with today, so the result is the same on every run.
7. `tags` and `aliases` are YAML lists.

`validate_provenance` checks that:

1. A page with `authority: external` or `authority: hybrid` cites at least one source, and each
   local source path under `chapters/**/sources/` exists.
2. No page cites an `inbox/` path.
3. A source wrapper declares `authority: external`, lists at least one source, and does not cite
   itself.

It also warns when a page cites a path under `publish/`, and when a page cites a path that is not
a URL and names no file or folder under the root.

Run them on a grimoire with `/grm-check frontmatter` and `/grm-check provenance`, and on the
framework with `/grm-dev-validate frontmatter` and `/grm-dev-validate provenance`. The validator
pages own the selectors and diagnostics:
[validate frontmatter](../invocations/validators/validate_frontmatter.md) and
[validate provenance](../invocations/validators/validate_provenance.md).
