---
name: {{SKILL_PREFIX}}-dev-validate
description: Run the framework's mechanical validators, optionally narrowed by selector
when_to_use: Before committing framework changes; after editing framework docs, invocations, rites, skills, or command metadata; user asks whether the framework validates, whether links/frontmatter/format/security are clean, or wants a targeted mechanical check.
argument-hint: "[all|smart|auto|summary|parallel|links|frontmatter|format|...]"
arguments: selector
user-invocable: true
allowed-tools: Bash Read
---

# Validate the Framework

You are running deterministic, script-backed validation against the framework itself.
Validation is mechanical: it should run a rite and report pass/fail diagnostics
with file:line citations when available. Judgment-based review belongs to audit
workflows, not this skill.

## Selectors

- No selector or `all`: run the full framework validator suite.
- `smart`: show validators relevant to the current git changes.
- `auto`: run the smart-selected validators.
- `summary`: run the full suite with summary-only output.
- `parallel`: run the full suite in parallel.
- Validator selectors such as `structure`, `encoding`, `portability`, `naming`,
  `semantics`, `format`, `frontmatter`, `links`, `orphans`, `provenance`,
  `skill-refs`, `security`, and `doc-trees` run only those validators.
- Multiple validators may be space-separated or comma-separated.

## Run

```bash
{{FRAMEWORK_PATH}}/bin/grimoire validate $selector
```

Examples:

```bash
{{FRAMEWORK_PATH}}/bin/grimoire validate
{{FRAMEWORK_PATH}}/bin/grimoire validate links frontmatter
{{FRAMEWORK_PATH}}/bin/grimoire validate smart
{{FRAMEWORK_PATH}}/bin/grimoire validate parallel
```

## Procedural Detail

!`cat {{FRAMEWORK_PATH}}/invocations/dev/validators/validate.md`
