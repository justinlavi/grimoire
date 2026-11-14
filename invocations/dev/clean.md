---
type: playbook
title: "Clean Workspace Artifacts"
aliases: ["workspace-clean", "clean-artifacts"]
tags: [framework/invocations, type/playbook, scope/framework]
authority: grimoire
last_verified: 2026-05-25
---

# Invocation: Clean Workspace Artifacts

## Purpose

Remove the temporary artifacts the validator orchestrator writes under the framework's `rites/.artifacts`.

## Invocation

```
/grm-dev-clean
```

## Workflow

Mutation profile: `plan_apply` via `rites/clean_artifacts.py`. This
invocation may apply directly because it removes only managed transient
artifact directories; use `--dry-run` when the user asks to preview removals.

### 1. Run the cleanup rite

```bash
FRAMEWORK_HOME/bin/grimoire clean_artifacts
```

### 2. Report the result

Show what was cleaned.

### 3. Preview mode

If the user wants to preview without deleting:

```bash
FRAMEWORK_HOME/bin/grimoire clean_artifacts --dry-run
```

## Related

- Framework maintenance: [[invocations/dev/dev|dev]]
