---
type: reference
title: "S-tier Architecture Backlog"
aliases: ["architecture-backlog", "s-tier-backlog", "deferred-architecture-items"]
tags: [type/reference, framework/docs, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# S-tier Architecture Backlog

The queue of architecture work that needs review, sequencing or explicit approval before anyone
implements it, and the decisions that still bind. Items come from `/grm-dev-improve`, from the
[architecture review](../invocations/dev/quality/review_architecture.md) and from the current
release program.

The backlog lists what is open and nothing else. It is not a release note:
[`CHANGELOG.md`](../CHANGELOG.md) records what each release changed. An item leaves this file in
the change that implements or rejects it.

## How To Use This Backlog

- Add an item only when the change is too broad for the current `/grm-dev-improve` pass, affects
  the behavior of a public command, touches release or install behavior, or needs a contract
  before it can be implemented.
- Write each item so that anyone can refer to it by its ID and an assistant can start from its
  owner, first slice and validation profile.
- Remove an item in the same change that implements or rejects it. The changelog entry and the
  commit carry the history.
- When a later architecture review finds the same concern, merge it into the existing item. Do
  not add a duplicate.

| Priority | Meaning |
|---|---|
| P0 | A correctness or data-safety problem that blocks the release. Implement it before release. |
| P1 | High-leverage work. The architecture is correct, but drift or maintenance cost is likely later. |
| P2 | An important improvement to scalability or clarity. It can wait behind P1 items. |
| P3 | Useful polish, a generated convenience, or a follow-up that needs a larger contract first. |

## Release Program: Grimoire for Everyone

Every item is designed for someone who uses Grimoire through Claude Code or Codex, possibly at a
company whose self-hosted GitLab sits behind a VPN, and who never reads `docs/`. Installing and
operating Grimoire from a terminal keeps working unchanged or becomes simpler.

The decisions and items rest on these facts:

- Claude Code and Codex both have plugin systems with marketplaces. Codex reads a Claude Code
  `.claude-plugin/marketplace.json`, so one git repository serves both. The Codex IDE extension
  does not load plugins; Codex in the IDE reads skills from `~/.agents/skills` and instructions
  from `~/.codex/AGENTS.md`.
- Claude Code copies a plugin from a directory marketplace into a versioned cache keyed by
  commit. A grimoire therefore cannot be a plugin without duplicating its whole content on every
  commit. Grimoire skills register as flat skill directories; only the framework is a plugin.
- Claude Code injects the standard output of a `SessionStart` command hook as session context,
  up to 10,000 characters.
- Claude Code honours a skill's `!cat` directive only for files inside the session's working
  directories, and an administrator can disable shell execution in skills. Registration
  therefore inlines every invocation into the generated skill.
- An administrator of Claude Code can force-install a marketplace and its plugins through managed
  settings. A private git host works through the user's stored git credential.

### Decisions

| ID | Decision | Position |
|---|---|---|
| D1 | Distribution of the framework to agents | Claude Code: the framework installs as the `grimoire` and `grimoire-dev` plugins from its own marketplace, with namespaced skill names (`/grimoire:add`). Codex: flat skill registration, rendered from the same skill sources by the same rite. The framework checkout stays at `~/.grimoire` for every agent; the plugin is a thin carrier. |

### Open Items

| ID | Priority | Item | Primary owner | Why queued |
|---|---|---|---|---|
| _None_ | - | No open deferred architecture items. | - | - |

## Suggested Implementation Sequence

No open implementation items.

## Update Triggers

Update this backlog when:

- `/grm-dev-improve` defers an item with P1 or P2 impact.
- An item is implemented, rejected or split.
- A release changes one of the primary owner surfaces.
- An architecture review finds the same drift risk again.

Leave it alone for a small local cleanup that fits inside the current pass. That cleanup belongs
in the change itself and, when a user can see it, in `CHANGELOG.md`.
