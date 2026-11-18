---
type: playbook
title: "Save"
aliases: ["save", "grm-save", "share-changes", "commit-and-push"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Save

Share the user's changes to a grimoire: check the grimoire, record the changes under a one-line
description, bring in everyone else's changes, and send the result to the shared copy. The rite
`rites/save_grimoire.py` does the mechanical work and refuses anything unsafe; this playbook holds
the conversation. A grimoire that one person uses is saved the same way; there is nothing to bring
in.

## Trigger

```
/grm-save
/grm-save "<what you changed>"
```

The user says "save", "share this" or "send my changes", or asks how other people get their
changes.

| A request that looks similar | Goes to |
|---|---|
| Pick up everyone else's changes without sharing your own | `/grm-update` |
| Find or repair what validation reports | `/grm-check` |
| Put the grimoire on a website | `/grm-publish` |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above.
- `$message`: the user's own description of the change, when they gave one.
- The envelope `save_grimoire --format json` prints: `status`, `mode`, `summary` (`changes`,
  `change_count`, `branch`, `upstream`, `ahead`, `behind`, `commit`, `pushed`), `mutations` and
  `messages`.

The grimoire must be a git repository. The plan in step 1 reports when it is not.

## Never

- Never force-push, rewrite history or discard the user's work. The rite enforces this; do not work
  around it with raw git. The user may have no way to recover a lost commit.
- Never save a grimoire that fails validation. Everyone else who uses the grimoire would receive
  the broken pages on their next update.
- Never apply before the user says yes to the description line. The line becomes the permanent
  record of the change.

## Steps

### 1. Plan

```bash
FRAMEWORK_HOME/bin/grimoire save_grimoire --grimoire GRIMOIRE_ROOT --format json
```

The plan writes nothing. It lists every change (`added`, `changed`, `removed`, `new`, `conflicted`),
the branch, and how far the branch is ahead of or behind the shared copy, and it runs the grimoire
validators. Act on the first row that matches the envelope:

| Envelope | Action |
|---|---|
| `status: blocked`, `summary.access` is `read` | This copy is set up for reading. Apply the guard's rule for a command that changes the grimoire; after a switch to editing, run this step again. |
| `status: blocked`, message "not a git repository" | Say that there is no shared copy to save to yet. Offer to set one up with the user's git host. End. |
| `status: noop`, `summary.change_count` is 0 and `summary.ahead` is 0 | Say that there is nothing to save. End. |
| `status: blocked`, message "touch the same lines as yours" | An earlier save stopped on a conflict and a page still holds markers. Take the step 3 action for that message. |
| `status: blocked`, message "validation failed" | Name the failing validators in plain words. Offer to fix them with `/grm-check quick` or the specific repair. End; do not save around a failure. |
| `status: noop` with changes or `summary.ahead` above 0 | Summarise the changes in one or two sentences ("you added two pages under travel and changed the food hub"). Continue. |

A `warning` message that the remote could not be reached means the plan could not look for
everyone else's changes. Say so; step 3 may fail at the same point.

- Done when: the envelope matched a row, and the user has seen either the reason the save ended or
  the summary of changes.
- Stop when: `status` is `blocked` for a reason the table does not list. Quote the message and ask
  the user how to proceed.

### 2. Compose the description

Write one line from the plan that names what changed, not how, in the form "Add Kyoto day plan and
route it from the travel hub". Use `$message` when the user passed one. Keep the line under 72
characters when you can. Show the line and ask for a yes before saving.

When `summary.change_count` is 0 and `summary.ahead` is above 0, the changes are already recorded
and only need sharing. Skip the line, say so, and run step 3 without `--message`.
When an earlier save stopped on a conflict and the plan reports no conflict marker, the commit is
already recorded. Skip the line; step 3 finishes the save and ignores any `--message`.

- Done when: the user approves the line or supplies their own, or nothing is left to record.
- Stop when: the user does not approve. Do not run step 3.

### 3. Apply

```bash
FRAMEWORK_HOME/bin/grimoire save_grimoire --grimoire GRIMOIRE_ROOT --apply --message "<line>" --format json
```

The rite validates again, records every change as one commit, brings in everyone else's changes
with a rebase, and pushes without force. Act on the first row that matches the envelope:

| Envelope | What happened | Action |
|---|---|---|
| `summary.pushed` is true; `mutations` holds `push`, and `commit` when there were changes to record | The changes are recorded and shared. | Go to step 4. |
| `status: blocked`, message "touch the same lines as yours" | The rite stopped before sending anything. The user's work is recorded on this computer, and the pages the message names hold conflict markers (lines that start with `<<<<<<<`, `=======` and `>>>>>>>`) around the two versions. | Name the pages. Explain that both versions need a human decision. Walk through each page: show both versions, ask which to keep or how to merge, then remove the marker lines and write the result. Run this step again; the rite continues from where it stopped, and a page that still holds a marker is named again. If the user would rather stop, run the rite with `--abandon`: the pages return to the recorded version, nothing is sent, and the next save meets the same conflict. |
| `status: blocked`, message "git does not know who you are yet" | Git has no name and email for the user. | Give the two `git config --global` lines from the message. Run them with the user's values once they confirm, then run this step again. |
| `status: blocked`, message "push failed" | The changes are recorded but not shared; the usual cause is VPN or credentials. | Say so. The user can run `/grm-save` again later, and only the sharing happens. |
| `mutations` holds `commit` only, with the message "no remote configured" | The changes are recorded on this computer; the grimoire has no shared copy. | Say so, and offer to set one up with the user's git host. |

- Done when: `summary.pushed` is true.
- Stop when: any other row matched. Take that row's action and wait for the user. For a `blocked`
  status the table does not list, quote the message; when `summary.commit` holds a hash, add that
  the changes are recorded on this computer.

### 4. Close

Tell the user in one line what was shared, and that everyone else who uses the grimoire receives
it on their next `/grm-update`.

- Done when: the user has that line.

## Evidence and checks

- Take every claim from the rite's envelope, never from your own reading of the repository.
  "Recorded" cites the `commit` mutation and the short hash in `summary.commit`. "Shared" cites the
  `push` mutation and `summary.pushed: true`. Conflicting files come from the blocked message.
- The rite runs `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT --summary` before it
  plans and before it applies. A grimoire is valid for saving only when the envelope carries the
  message "validation passed".
- Never report "shared" while `summary.pushed` is false.
- Exit codes: 0 = plan rendered, saved, or nothing to save; 1 = blocked or a git error; 2 = invalid
  arguments.

## Outputs

- One commit in the grimoire's repository that holds every change, with the approved line as its
  message, pushed to the branch's shared copy.
- A reply that leads with the outcome and gives one next action. Use plain words: "record" and
  "share", not "stage", "commit" and "push", unless the user speaks git.

## Related

- Save rite: `FRAMEWORK_HOME/rites/save_grimoire.py`
- Pick up everyone else's changes: [[invocations/grm/update|update]]
- Repair what validation reports: [[invocations/grm/check|check]]
- Set up a grimoire: [[invocations/grm/setup|setup]]
