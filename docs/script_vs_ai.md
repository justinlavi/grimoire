---
type: reference
title: "Script vs AI"
aliases: ["script-vs-ai", "rites-vs-invocations"]
tags: [type/reference, framework/docs, principle]
authority: grimoire
last_verified: 2026-11-14
---

# Script vs AI

Where a piece of work belongs: in a rite, which is a script, or in a playbook, which an assistant
follows with judgment. Apply it whenever you add a check, an operation or a skill.

## The rule

A rite does mechanical work. A playbook does work that needs judgment.

Ask one question of the work: does it need an understanding of context or meaning?

| Answer | The work goes to | Examples |
|---|---|---|
| No | A rite | Does this file exist? How many files match this pattern? Does this name follow `snake_case`? Are the required sections present? Does this link resolve? |
| Yes | A playbook | Is this term used correctly? Is this explanation clear enough? Should these two pages be merged? Which structure would serve the reader better? |

When a person would have to think about it, the assistant does it. When a computer can check it
mechanically, a rite does it.

Two limits apply:

- **A rite must earn its place.** Work goes to a rite only when it is mechanical and a script does
  it more cheaply or more reproducibly than an assistant. Mechanical work that fails that test
  stays in a playbook step.
- **The rule decides where work lives, not how much compute it gets.** A judgment task spread
  across many subagents, such as a review of each page or an audit of each chapter, is still
  playbook work. "Is this judgment?" decides between rite and playbook. "Can this judgment run in
  parallel?" decides between one assistant and many.

## What each side does

| | Rite | Playbook |
|---|---|---|
| Work | Find, count, check, extract, and write by a fixed rule | Analyze, judge, recommend, improve |
| Context | Needs none | Depends on it |
| Result | Facts: pass or fail, counts, lists, diagnostics | Findings with their reasons, recommendations, edits |
| Same input twice | The same result | The same decisions; the wording may differ |

A rite:

- Does one clear task.
- Reports facts, and the fix for a mechanical failure. It makes no judgment about quality.
- Declares a mutation profile in [rite profiles](rite_profiles.md) when it writes.
- Meets the [rite quality review](../invocations/dev/quality/validate_rites.md), which owns the
  checks on exit codes, error handling, portability and size.

A playbook:

- Runs rites first, to gather the facts.
- Judges from those facts and gives the reason for each recommendation.
- Never counts or searches by hand what a rite already reports.
- Handles the edge cases that a fixed rule cannot.

The [writing standard](writing_standard.md#deterministic-procedures) owns the shape of a playbook.

## How the two work together

A rite supplies facts and a playbook interprets them.

1. The rite checks and reports. `rites/validate_structure.py` finds the required directories and
   files, prints what is missing and exits with code 0 or 1.
2. The playbook runs the rite and reads its report.
   [`invocations/dev/improve_framework.md`](../invocations/dev/improve_framework.md) runs the
   validators.
3. The assistant decides which findings are real, chooses the fix for each and applies it.

## Signs that work is on the wrong side

| Sign | Fix |
|---|---|
| A rite holds a list of meanings, such as terms to avoid, and tries to judge how each is used. It cannot tell an example of what not to write from a real use, and it cannot choose the replacement. | Keep the mechanical part in the rite: extract the terms that occur. Move the judgment to a playbook that reads the rite's output beside the [reference](reference.md). |
| An assistant reads every file to count them or to check that one exists. | Run the rite or the shell command that counts. |
| The body of a rite-backed skill tells the assistant to decide something. | The skill does judgment work. Make it invocation-backed. |
| An invocation only runs a script and reports its output. | Remove the invocation and have the skill run the rite. |

To move work to the right side, split it: the rite keeps the finding, counting and checking; the
playbook takes the analysis, the judgment and the recommendation; and the rite's output becomes
the playbook's input.

## Applying this to skills

Every framework skill is a pointer to a rite, to an invocation, or to both. The same rule picks
the backing. The [skill schema](skill_schema.md#skillmd-structure) owns how each form is written.

| The command's work | Backing | What the assistant does | Shipped example |
|---|---|---|---|
| Mechanical, with no judgment | Rite-backed: the skill body runs `{{FRAMEWORK_PATH}}/bin/grimoire <rite>` | Runs the rite and reports its output | `/grm-dev-validate` |
| Judgment, conversation or several steps | Invocation-backed: the skill body names an invocation, which registration inlines | Follows the playbook | `/grm-create`, `/grm-check`, `/grm-dev-improve`, `/grm-help` |

A skill may use both, in that order: its body runs the rite, then an invocation says how to read
the rite's output. A mechanical step inside a playbook runs a rite in the same way; the `skills`
scope of `/grm-update` runs `sync_skills`.

When a skill needs more logic, put the logic in a rite or an invocation, and keep the `SKILL.md`
a pointer. The skill then stays portable across agents.
