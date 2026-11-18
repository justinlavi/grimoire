---
type: hub
title: "Framework Validators"
aliases: ["validators", "framework-validators"]
tags: [framework/invocations, type/hub, scope/validators, hub/sub]
---

# Validators

The validators are rites that check a grimoire or the framework and exit with a pass or a fail. This
hub owns the selector table. Each validator's page owns its rules, its commands and its diagnostic
codes.

## Selectors

`rites/data/validators.json` lists the validators of each profile in run order. `/grm-check` runs the
`grimoire` profile on a grimoire; `/grm-dev-validate` runs the `framework` profile on the framework.

| Selector | Rite | Profile | Checks | Page |
|---|---|---|---|---|
| `structure` | `validate_grimoire_structure.py` | grimoire | Manifest, root hub, required files and folders, folder-named hubs, managed scaffold files, Obsidian settings | [[invocations/validators/validate_grimoire_structure|validate grimoire structure]] |
| `structure` | `validate_structure.py` | framework | Required directories, files and hubs; documentation index coverage; the rite-profile, summoning and agent-target contracts | [[invocations/validators/validate_structure|validate structure]] |
| `encoding` | `validate_encoding.py` | both | UTF-8 without BOM, LF line endings, no mojibake or repair artifacts | [[invocations/validators/validate_encoding|validate encoding]] |
| `portability` | `validate_portability.py` | both | Path names that Windows accepts; no two files that differ only by case | [[invocations/validators/validate_portability|validate portability]] |
| `naming` | `validate_naming.py` | framework | snake_case `.md` and `.py` filenames; skill folders that match their command family | [[invocations/validators/validate_naming|validate naming]] |
| `semantics` | `validate_semantics.py` | framework | No hyphenated `chapters/` path examples in Markdown | [[invocations/validators/validate_semantics|validate semantics]] |
| `format` | `validate_format.py` | both | Table delimiter rows, closed code fences, tree branch markers; on the framework also playbook sections, hub length and formula titles | [[invocations/validators/validate_format|validate format]] |
| `frontmatter` | `validate_frontmatter.py` | both | Page frontmatter follows the page schema | [[invocations/validators/validate_frontmatter|validate frontmatter]] |
| `links` | `validate_links.py` | both | Links resolve, match on-disk casing and use the link style of their layer | [[invocations/validators/validate_links|validate links]] |
| `orphans` | `validate_orphans.py` | both | Every page has an inbound link | [[invocations/validators/validate_orphans|validate orphans]] |
| `provenance` | `validate_provenance.py` | both | `external` and `hybrid` pages and source wrappers cite sources that exist | [[invocations/validators/validate_provenance|validate provenance]] |
| `skill-refs` | `validate_skill_refs.py` | framework | Slash-command references resolve to a skill; the command-surface contract is complete | [[invocations/validators/validate_skill_refs|validate skill refs]] |
| `security` | `validate_security.py` | framework | No credential patterns in Markdown or Python; no `eval(` or `exec(` in rites | [[invocations/validators/validate_security|validate security]] |
| `doc-trees` | `validate_doc_trees.py` | both | Directory-tree diagrams match the filesystem | [[invocations/validators/validate_doc_trees|validate doc trees]] |

A selector is accepted in lower or upper case, with `_` in place of `-` (`skill_refs`), and as the
rite's name without `.py` (`validate_links`). A selector that is not in the profile being run exits
with code 2 and lists the profile's selectors.

## Run them

- On a grimoire (`/grm-check quick`, `/grm-check <selector>`) -> [[invocations/grm/check|check]]
- On the framework (`/grm-dev-validate [selector]`), with the modes `all`, `smart`, `auto`, `summary` and `parallel`, the report format and the exit codes -> [[invocations/validators/validate|validate]]

## Related

- Resolve `GRIMOIRE_ROOT`, the active grimoire -> [[invocations/meta/grimoire_directory_guard|grimoire directory guard]]
- Judgment reviews of the framework, which no validator performs -> [[invocations/dev/improve_framework|improve framework]]
- Dispatcher that maps selectors to rites: [rites/validate.py](../../rites/validate.py)
- Vocabulary -> [[docs/reference|reference]]
