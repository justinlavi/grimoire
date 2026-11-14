---
type: playbook
title: "Validate the Framework"
aliases: ["framework-validate", "mechanical-validation"]
tags: [framework/invocations, type/playbook, scope/validators]
authority: grimoire
last_verified: 2026-11-13
---

# Invocation: Validate the Framework

## Purpose

Run deterministic, script-backed validators against the framework. This workflow is
mechanical: validators return pass/fail diagnostics and exit codes. Judgment
work belongs to audit or improve workflows.

## Invocation

```bash
/grm-dev-validate
/grm-dev-validate all
/grm-dev-validate smart
/grm-dev-validate auto
/grm-dev-validate summary
/grm-dev-validate parallel
/grm-dev-validate links frontmatter
/grm-dev-validate links,frontmatter
```

The skill maps directly to:

```bash
python3 rites/validate.py
python3 rites/validate.py links frontmatter
python3 rites/validate.py smart
python3 rites/validate.py parallel
```

## Validator Selectors

| Selector | Rite |
|---|---|
| `structure` | `validate_structure.py` |
| `encoding` | `validate_encoding.py` |
| `portability` | `validate_portability.py` |
| `naming` | `validate_naming.py` |
| `semantics` | `validate_semantics.py` |
| `format` | `validate_format.py` |
| `frontmatter` | `validate_frontmatter.py` |
| `links` | `validate_links.py` |
| `orphans` | `validate_orphans.py` |
| `provenance` | `validate_provenance.py` |
| `skill-refs` | `validate_skill_refs.py` |
| `security` | `validate_security.py` |
| `doc-trees` | `validate_doc_trees.py` |

## Report

Report any failed validators with diagnostics grouped by file and line when
available. Exit code 0 means the selected validators passed; exit code 1 means
one or more selected validators failed; exit code 2 means the selector or mode
was invalid.

## Related

- Validator hub -> [[invocations/dev/validators/validators|validators]]
- Framework improvement -> [[invocations/dev/improve_framework|improve framework]]
- Grimoire mechanical validation -> [[invocations/grm/check|check]]
