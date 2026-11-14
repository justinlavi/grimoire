---
type: hub
title: "Framework Validators"
aliases: ["validators", "framework-validators"]
tags: [framework/invocations, type/hub, scope/validators, hub/sub]
---

# Framework Validators

Mechanical, deterministic checks against the framework repository. The public
entry point is `/grm-dev-validate`; pass a selector to run one validator or omit the
selector to run the full suite.

For the public command workflow, see [[invocations/dev/validators/validate|validate]].

## Available

| Validator | Skill | What it checks |
|---|---|---|
| [[invocations/dev/validators/validate_structure|validate structure]] | `/grm-dev-validate structure` | Required directories and files exist; layout matches conventions |
| [[invocations/dev/validators/validate_encoding|validate encoding]] | `/grm-dev-validate encoding` | UTF-8, LF line endings, BOMs, and mojibake markers |
| [[invocations/dev/validators/validate_portability|validate portability]] | `/grm-dev-validate portability` | No Windows-reserved characters or basenames in any path |
| [[invocations/dev/validators/validate_naming|validate naming]] | `/grm-dev-validate naming` | snake_case for paths; kebab-case for skills |
| [[invocations/dev/validators/validate_format|validate format]] | `/grm-dev-validate format` | Invocation/formula schema compliance |
| [[invocations/dev/validators/validate_frontmatter|validate frontmatter]] | `/grm-dev-validate frontmatter` | Every page declares its `type` and the schema's required fields |
| [[invocations/dev/validators/validate_semantics|validate semantics]] | `/grm-dev-validate semantics` | Hyphenated path examples in markdown prose |
| [[invocations/dev/validators/validate_links|validate links]] | `/grm-dev-validate links` | Internal references resolve and hub routes use wikilinks |
| [[invocations/dev/validators/validate_orphans|validate orphans]] | `/grm-dev-validate orphans` | Every page is reachable from at least one other page |
| [[invocations/dev/validators/validate_provenance|validate provenance]] | `/grm-dev-validate provenance` | Every external/hybrid page cites real chapter-local sources |
| [[invocations/dev/validators/validate_security|validate security]] | `/grm-dev-validate security` | Credential patterns and unsafe Python constructs in rites |
| [[invocations/dev/validators/validate_skill_refs|validate skill refs]] | `/grm-dev-validate skill-refs` | Slash-command references and command-surface entries resolve |
| [[invocations/dev/validators/validate_doc_trees|validate doc trees]] | `/grm-dev-validate doc-trees` | ASCII directory diagrams match the filesystem |

## Run them all

```bash
python3 ../../../rites/validate.py
python3 ../../../rites/validate.py --parallel
python3 ../../../rites/validate.py --smart
python3 ../../../rites/validate.py --auto
python3 ../../../rites/validate.py --format json
```

Or invoke `/grm-dev-validate`, whose workflow home is [[invocations/dev/validators/validate|validate]].

## Related

- Orchestrator invocation -> [[invocations/dev/improve_framework|improve framework]]
- Rite scripts: `rites/`
- Canonical terminology -> [[docs/reference|reference]]
