---
type: reference
title: "Subagent Review Lanes"
aliases: ["subagent-lanes", "review-lanes"]
tags: [framework/invocations, type/reference, scope/meta]
authority: grimoire
last_verified: 2026-11-14
---

# Subagent Review Lanes

The protocol for running the read-only analysis phases of a review playbook as parallel lanes: when
lanes apply, what a lane may do, what it returns, and how the reports are merged. The host playbook
supplies its own lane table and is complete without lanes.

## When lanes apply

Use lanes only when both conditions hold:

1. The assistant can spawn subagents or parallel reviewers.
2. The host playbook marks its analysis phases as lanes.

Otherwise run the host playbook's phases in their written order, keep each phase's notes separate
until synthesis, and report that the pass ran serially. A serial pass reaches the same findings; it
only takes longer. [[docs/script_vs_ai|script vs ai]] owns when parallel work earns its cost.

Lanes change how the analysis is computed. They never change what is decided or applied.

## What a lane may do

A lane reads and proposes. The orchestrator keeps three things and never delegates them:

- mechanical validation (the host playbook's validator phase);
- applying or confirming edits (`/grm-check` confirms before it applies; `/grm-dev-improve` defers a
  change that touches more than ten files);
- synthesis of the lane reports.

When workers are permitted to edit, give each one a write scope that overlaps no other. Otherwise
dispatch read-only lanes and let the orchestrator apply one integrated change.

## Lane output contract

Every lane returns the same fields, so that the reports merge.

| Field | Holds |
|---|---|
| `lane` | One of the host playbook's named lanes |
| `scope_reviewed` | The files, globs or pages inspected |
| `checks_run` | The read-only validators or commands run, or `none` |
| `findings` | Findings ordered by impact and risk; each carries the fields in the next table |
| `deferred_opportunities` | Changes too broad for the current pass |
| `workflow_updates` | Heuristics worth adding to the host playbook |

Each finding carries:

| Field | Holds |
|---|---|
| `id` | A stable identifier that synthesis can cite |
| `priority` | `P0` to `P3` |
| `evidence` | `file:line` references |
| `invariant_or_claim` | The rule or claim at stake. Framework lane: a source-of-truth, contract or read-path rule. Grimoire lane: a routing, orphan, freshness, boundary or cross-reference rule. |
| `recommendation` | The proposed change |
| `action` | `apply_now`, `defer`, `codify` or `retain`. A surface-only pass (contradictions, stale claims) surfaces the finding; a lane never applies. |
| `blast_radius` | The files or surfaces affected; compare it with the host playbook's defer threshold |
| `read_path_delta` | The effect on the shortest useful path (the agent read path for the framework, hub-to-leaf depth for a grimoire), or `n/a` |

A finding about a grimoire uses that grimoire's own subject words;
[[docs/reference|reference]] owns the boundary between system and content vocabulary.

## Dispatch template

Dispatch one lane per scope as a read-only explorer:

```text
Review <WORKFLOW_TARGET> in this lane only.
Lane:
Scope:
Read only. Do not edit or confirm unless explicitly assigned a write scope.
Find the issues this lane is responsible for, with file:line evidence.
Return the lane output contract from subagent_lanes.md.
```

## Synthesis

Merge the lane reports in the main context before any edit. The host playbook defines its own
synthesis matrix and grading. Look for:

| Pattern | Usual cause |
|---|---|
| The same finding from two lanes | A missing canonical home: a source-of-truth gap in the framework, a page that does not exist yet or a missing cross-reference in a grimoire |
| Conflicting recommendations | Unclear ownership or audience boundaries |
| Repeated `defer` items | Work that belongs in a backlog, roadmap or TODO |

## Related

- Host playbooks: [[invocations/grm/check|check]], [[invocations/dev/improve_framework|improve framework]], [[invocations/dev/quality/review_architecture|review architecture]]
- When parallel work earns its cost: [[docs/script_vs_ai|script vs ai]]
- Page fields a finding cites: [[docs/page_schema|page schema]]
