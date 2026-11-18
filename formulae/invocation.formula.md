---
type: reference
title: "Invocation Formula"
aliases: ["invocation-template"]
tags: [type/reference, framework/formula]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: [Name]

[One or two sentences: what this playbook does and for whom. Each bracketed prompt below says what
its section must answer; the finished invocation replaces every prompt with facts. The shape is the
deterministic procedure in the writing standard (`docs/writing_standard.md`).]

## Trigger

[When this runs: the command as the user types it, with its arguments, and the requests in the
user's own words that lead here. Then the requests that look similar and go elsewhere, each with the
command that owns it.]

```
/[command] [arguments]
```

## Inputs

[What the playbook reads before it acts, by exact path or command: the active grimoire, a rite's
JSON envelope, a contract file, an argument. State what makes an input missing or invalid.]

## Never

[The boundaries this playbook holds. One line each: the action that is off limits, and the reason
breaking it costs more than the task saves.]

## Steps

### 1. [Action]

[The exact command or edit.]

- Done when: [the observable result that ends the step].
- Stop when: [the condition that sends a question to the user instead of a guess].

### 2. [Action]

[Continue in order. A mechanical step runs a rite; a judgment step states what to weigh.]

## Evidence and checks

[What each claim in the reply must cite: a rite's own JSON envelope, a file and line, a validator
result. Which validators must pass before the playbook reports success, as exact commands.]

## Outputs

[The exact files and records the playbook leaves, and the reply: the outcome first, then the single
next action, then what did not run.]

## Related

- [Owner of a rule this playbook applies]: `[path]`
