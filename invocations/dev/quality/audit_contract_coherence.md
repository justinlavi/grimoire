---
type: playbook
title: "Audit Contract Coherence"
aliases: ["audit-contract-coherence", "contract-coherence"]
tags: [framework/invocations, type/playbook, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Audit Contract Coherence

Checks that each free-text field in the framework's two machine contracts is true of the code and, where a rite can run on a disposable target, of what the rite does. The validators prove that each field exists and has the right type; none of them reads what a sentence says.

## Trigger

Runs as step 5 of `/grm-dev-improve` ([[invocations/dev/improve_framework|improve framework]]), after the rite quality review. It has no command of its own. It also fits:

- After a change to a rite that has an entry in either contract.
- After a change to the prose in either contract.
- Before a framework release.

Requests that go elsewhere:

| Request | Owner |
|---|---|
| Does each field exist, with the right type, an allowed value, a path that resolves and no duplicate? Is the set of commands complete? | `/grm-dev-validate structure skill-refs`. `rites/command_surface.py` and `rites/rite_profiles.py` hold these checks and treat the prose as opaque |
| Does the `mutation_profile` of a command equal the `profile` of the rite that owns it? | `/grm-dev-validate skill-refs`, which reports `COMMAND_SURFACE_MUTATION_PROFILE_DRIFT` |
| Is a rite script well written: docstring, error handling, exit codes, portability, size? | [[invocations/dev/quality/validate_rites|validate rites]]. Both reviews look at reruns: that one as script quality, this one as a claim in a contract |
| Does each command have exactly one playbook? | [[invocations/dev/quality/review_architecture|review architecture]]. This audit goes one level deeper: is each field true of what that playbook does? |

## Inputs

Run every command from the framework directory, `FRAMEWORK_HOME`.

| Input | Read it with |
|---|---|
| The command contract | `rites/data/command_surface.json`, described by [[docs/command_surface|command surface]] |
| The rite contract | `rites/data/rite_profiles.json`, described by [[docs/rite_profiles|rite profiles]] |
| A tree that passes the validators | Step 2 of [[invocations/dev/improve_framework|improve framework]] is done. The validators have proven existence, type, allowed values, path resolution, uniqueness and completeness; do not check those again |
| The lane protocol | [[invocations/meta/subagent_lanes|subagent lanes]] |
| Python and a writable temporary directory | Needed for every probe. Without them every claim is a `code_read` |

The audit covers these fields:

| Contract | Field | The claim | How it is checked |
|---|---|---|---|
| `command_surface` | `mutation_behavior` | What the command changes on disk, or that it reads only, or that judgment gates its writes | Trace it to the owner: read the rite in `rite_owner`, or the playbook when the owner is `judgment` or `hybrid`. Probe it when the owning rite has a recipe in step 4 |
| `command_surface` | `mutation_profile`, read as a claim | The declared profile is true of what the command does | Compare the declared profile with the `mode` of the envelope, for a command whose rite has a recipe in step 4 |
| `command_surface` | `log_behavior` | Which record the command writes to, if any | Read the owner. A grimoire has no activity log; its history is its git history. A sentence that claims a log entry in a grimoire is `FALSE` |
| `command_surface` | `validation_profile` | The listed validators exist, accept the named flags, and fit what the command does | The helper in step 5, then judgment on fit |
| `rite_profiles` | `writes` | The declared paths are exactly what the rite touches, no more and no less | A probe with a disk comparison before and after, for a rite with a recipe in step 4. Otherwise read every write call |
| `rite_profiles` | `idempotency` | The rerun behaviour holds | The rerun in the rite's recipe in step 4. Otherwise read the control flow |
| `rite_profiles` | `plan_command`, `apply_command`, `default_mode` | The commands run, their flags are real, and each selects the mode it claims | Run the declared commands with `--format json`, for a rite with a recipe in step 4. Otherwise check the flags against the rite's argument parser and read the code |
| `rite_profiles` | `validation_profile` | The follow-up validators exist, accept their flags, and fit the rite | The helper in step 5, then judgment on fit |

A rite that reports through `ResultReporter` in `rites/diagnostics.py` is enveloped: with `--format json` it prints the result envelope, an object with `rite`, `status`, `mode`, `root`, `summary`, `mutations` and `messages`. A validator also accepts `--format`, but it prints a findings report, which says nothing about writes. `--format` alone does not make a rite probeable.

## Never

- Never run a probe against a real grimoire, `~/grimoires/`, `~/grimoires/library.json` or an agent directory. Every probe runs on a fresh `mktemp -d` target; a probe on real state turns an audit into damage.
- Never run `summon.py`, `summon.sh`, `sync_skills.py` or `sync_docs.py` as a probe. They write to the install, to agent directories under the user's home or to a tracked file. Read their code instead.
- Never call a reading a proof. Each verdict records how it was reached, so that a `TRUE` from a probe is never confused with a `TRUE` from a reading.
- Never record `TRUE` for a claim you could not check. Record `UNVERIFIABLE` and state why.
- Never invent a probe result. When Python or a temporary directory is missing, tag the claim `code_read` and say so.
- Never edit contract JSON to match code that is wrong. That writes a bug into the contract as documented behaviour.
- Never edit a rite in this audit. A change to behaviour belongs to [[invocations/dev/quality/validate_rites|validate rites]] or to the user.
- Never add a check to a validator, or weaken one, from this audit. The mechanical checks stay deterministic.
- Never let a lane edit a framework file. Lanes report; the main context edits.

## Steps

### 1. Inventory the contracts and derive the enveloped rites

```bash
grep '"command":' rites/data/command_surface.json       # the commands
grep '"rite_owner":' rites/data/command_surface.json    # the rite that owns each command, or null
grep '"path":' rites/data/rite_profiles.json            # the profiled rites
grep -l "ResultReporter" rites/*.py | grep -v diagnostics.py   # the enveloped rites
```

Derive the enveloped rites from the last command on every run. Never copy the list from an earlier pass.

- Done when: you hold the four lists.

### 2. Reduce each field to a claim and tag its evidence tier

For every command and every rite, list the claims to audit, one for each field in the table in Inputs. Tag each claim with its tier before you check it, so that confidence is never raised afterwards.

| Tier | Applies to |
|---|---|
| `behavioral_probe` | A claim about an enveloped rite, or about a command that rite owns, when step 4 holds a recipe for the rite or you can build an isolated temporary target for it |
| `code_read` | Every other claim: a rite that is not enveloped, an enveloped rite that cannot be isolated, such as `sync_skills`, and every claim whose owner is a playbook |

`behavioral_probe` outranks `code_read`. A claim with no isolated probe is a `code_read`, not a guess.

- Done when: every claim has a tier.

### 3. Run the lanes

Follow the lane protocol in [[invocations/meta/subagent_lanes|subagent lanes]], as [[invocations/dev/quality/review_architecture|review architecture]] does. When subagents are available, dispatch one lane per row. A lane reads, and may run probes on its own temporary target.

| Lane | Scope | Primary question |
|---|---|---|
| `cs-judgment` | Commands in `command_surface` whose `owner_type` is `judgment` or `hybrid` | Do `mutation_behavior` and `log_behavior` match the owning playbook? |
| `cs-rite-join` | Commands in `command_surface` that a rite owns | Does the declared `mutation_profile` match the `mode` of the envelope? The static comparison with `profile` belongs to `/grm-dev-validate skill-refs`; do not repeat it |
| `rp-envelope` | The enveloped rites from step 1 that can be isolated | The probe lane: `writes`, `idempotency`, and the plan, apply and default modes, with `--format json` |
| `rp-codeonly` | The profiled rites that the probe lane does not cover, such as `sync_skills`, `sync_docs`, `summon_core` and `validate` | Do `writes`, `idempotency` and the commands match the code? |
| `vp-crosscut` | `validation_profile` in both contracts | Do the named validators exist, accept the named flags, and fit the effect? |

Dispatch each lane with this text:

```text
Audit contract coherence for this lane only.
Repo root: FRAMEWORK_HOME. Lane: <name>. Scope: <commands/rites/fields>.
For any behavioral probe, create your OWN disposable target with mktemp -d
(a throwaway grimoire scaffold, or a throwaway HOME via --home <tmp> for
sync_library / adopt_grimoire); never touch a real grimoire, ~/grimoires, or
~/grimoires/library.json. If a probe cannot be isolated, downgrade the claim to
code_read and say so. Do not edit any file - surface findings only.
Return one verdict object per claim using the schema in
audit_contract_coherence.md.
```

Each probe lane has its own temporary directory, so the lanes can run at the same time. Without subagents, run the same five lanes one after another: each creates and removes its own temporary target, and you keep each lane's verdicts apart until step 6. The probe lane runs in both modes.

A lane that cannot isolate a probe tags the claim `code_read` and says so. It never runs the probe on real state.

- Done when: every lane has returned one verdict object for each claim in its scope.

### 4. Run the probes on disposable targets

Each probe runs on a fresh `mktemp -d` target that holds the smallest condition the rite can act on. Assert only on `status`, `mode`, and the `path` and `action` of each mutation. Ignore summary counts and message text.

The envelope derives `status`: `error` when a message has the severity `error`, `ok` when the run made a mutation, `noop` otherwise. A second apply that returns `noop` is therefore the signal for idempotency.

| Rite | Temporary target | Run | Expect |
|---|---|---|---|
| `repair_links` | A grimoire with one wikilink that names a file without its path | `--grimoire <tmp> --format json` | `mode` `plan`, no mutations. The run exits 1 because it found a repair to make; that is not a failed probe |
| | | `--grimoire <tmp> --apply --format json` | `mode` `apply`, `status` `ok`, `repair` mutations on `.md` paths |
| | | The apply again | `status` `noop`, no mutations |
| `sync_library` | A home that holds a grimoire the library does not list | `--home <tmp> --format json` | `mode` `plan`, no mutations |
| | | `--home <tmp> --apply --format json` | `mode` `apply`, a `write` mutation on `library.json` |
| | | The apply again | `status` `noop` |
| `adopt_grimoire` | A home that holds a folder with no `grimoire.json` | `<dir> --home <tmp> --skill-prefix <prefix> --format json` | `mode` `apply`, `status` `ok`, a `write` mutation on `grimoire.json` |
| | | The same command again | `status` `error`, exit code 1, `grimoire.json` unchanged. This proves the refusal to overwrite |
| `save_grimoire` | A grimoire that passes validation, is a git repository, and has a bare repository as `origin` | `--grimoire <tmp> --format json` | `mode` `plan`, no mutations |
| | | `--grimoire <tmp> --apply --message x --format json` | `mode` `apply`, a `commit` mutation, then a `push` mutation |
| | | The apply again | `status` `noop` |

For `writes`, compare the temporary tree before and after the run, and fail the probe when a path outside the declared `writes` changed. The envelope is the rite's own report; the disk comparison catches a write the rite did not declare.

For an enveloped rite with no row, build an isolated target the same way when its flags allow it (`--grimoire <tmp>` or `--home <tmp>`). When they do not, the claim is a `code_read`.

When a flag in a recipe is absent, or a temporary target cannot be built, record `UNVERIFIABLE`. A failed setup is not a false contract.

- Done when: every claim tagged `behavioral_probe` has a result from a run or the verdict `UNVERIFIABLE`.

### 5. Read the code for the rest and run the validation-profile helper

For each `code_read` claim, trace the claim to source. Read the rite, or the playbook when judgment owns the command, and confirm that `mutation_behavior`, `log_behavior`, `writes` and `idempotency` match the calls that write.

- `tests/test_sync_skills.py` supports the claims about `sync_skills`. Cite it, and keep the tier `code_read`.
- The profile of `rites/summon_core.py` names `python rites/summon.py` as its `apply_command`. That is intended: `summon.py` is the dispatcher that imports `summon_core`. Record it as a note, not as a failure.

For `validation_profile` in both contracts, check each `python rites/<name>.py ...` token with these two commands, replacing `<name>` and the flag:

```bash
test -f rites/<name>.py || echo "MISSING rite: rites/<name>.py"
grep -q -- '--grimoire' rites/<name>.py || echo "FLAG not in argparse: --grimoire"
```

A missing file or a missing flag is a fact: the verdict is `FALSE` or `UNDERSPECIFIED`. Whether the named validators are the right checks after the write is judgment.

- Done when: every `code_read` claim has a verdict with a `file:line`, and every `validation_profile` token is checked.

### 6. Merge the verdicts and decide fix or defer

Join the verdicts of all lanes and group them by `verdict`, `fix_target` and `evidence_type`, so that a finding proven by a probe is never merged with one from a reading. For each verdict that is not `TRUE`, decide which side is right before you act.

| Case | Meaning | Action |
|---|---|---|
| Prose wrong | The code is right and the sentence misdescribes it | Edit the contract JSON so that the sentence matches the code. Then run `FRAMEWORK_HOME/bin/grimoire validate` and the probe that found it, to confirm that the suite passes and the sentence matches the behaviour. This is the only edit the audit makes, and it edits data, never code |
| Code wrong | The sentence states the intent and the code breaks it | Do not edit the rite. Report it with `fix_target` `code`, a `file:line` or the failing part of the envelope, and a first step. Add it to the [[docs/architecture_backlog|architecture backlog]] when it must outlive this conversation |
| Unverifiable | The rite is not enveloped, a playbook owns the claim, or the probe could not be isolated | Record it with its evidence type |

- Done when: every verdict that is not `TRUE` has one of the three actions, and the suite exits 0 after the last contract edit.
- Stop when: you cannot tell whether the sentence or the code is right. Ask the user which one states the intent.

## Evidence and checks

- A probed claim cites the command that ran and the part of the envelope that decides it.
- A read claim cites a `file:line`.
- Every verdict states its evidence type. State plainly which `TRUE` verdicts rest on a probe and which on a reading.
- After any contract edit, `FRAMEWORK_HOME/bin/grimoire validate` exits 0.

## Outputs

Files: edits to `rites/data/command_surface.json` and `rites/data/rite_profiles.json` where the prose was wrong, and backlog items for code findings that must outlive the conversation.

Each lane returns one object per claim:

| Field | Holds |
|---|---|
| `claim_id`, `contract`, `subject`, `field` | Which claim |
| `prose_claim` | The contract sentence under audit |
| `evidence_type` | `behavioral_probe` or `code_read` |
| `probe_invocation`, `envelope_excerpt` | For a probed claim: the command and the part of the envelope |
| `code_evidence` | For a read claim: `file:line` |
| `verdict` | `TRUE`, `FALSE`, `UNDERSPECIFIED`, `EXCEEDS_SCOPE` or `UNVERIFIABLE` |
| `drift_kind`, `fix_target`, `proposed_fix`, `blast_radius` | What drifted, which side to fix (`prose`, `code` or none), the fix, and the files it affects |

This audit's part of the `/grm-dev-improve` reply:

1. Claims audited, split by evidence tier.
2. The verdict tally, with the `TRUE` verdicts split into probed and read.
3. The lanes run, skipped or run in series, each with its reason.
4. Contract edits applied, with the result of the validators after them.
5. Code findings deferred, each with its `file:line` or envelope excerpt and its backlog ID.
6. Any rite that is enveloped in this pass and was not in the last, or the reverse.

## Related

- Orchestrator: [[invocations/dev/improve_framework|improve framework]]
- Command contract: [[docs/command_surface|command surface]]
- Rite contract: [[docs/rite_profiles|rite profiles]]
- When a rite acts and when judgment does: [[docs/script_vs_ai|script vs ai]]
- Deferred work: [[docs/architecture_backlog|architecture backlog]]
