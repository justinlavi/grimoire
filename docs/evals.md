---
type: reference
title: "Invocation Eval Tier"
aliases: ["evals", "invocation-evals"]
tags: [type/reference, framework/docs, scope/testing]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation Eval Tier

The eval tier tests playbooks. It runs an assistant against a small seeded grimoire and checks
that the playbook led it to the right decision. This page covers how to run the evals and how
to add one.

Validators and rite tests cover the mechanical half of the framework. A playbook asks for
judgment: which storage layer a file belongs in, whether two pages contradict each other, where a
page goes. No deterministic test covers that, so the eval tier calls a model.
[Script vs AI](script_vs_ai.md) owns the split between the two halves.

## Running the evals

Run both commands from the root of a checkout.

| Command | Runs | Calls a model |
|---|---|---|
| `python -m pytest -q` | The fast gate: every deterministic test, including the eval scaffolding | No |
| `FRAMEWORK_EVAL_MODEL=1 python -m pytest -m eval` | The eval tier: one test for each spec, in `tests/test_eval_live.py` | Yes |

Two environment variables control the eval tier.

| Variable | When set | When unset |
|---|---|---|
| `FRAMEWORK_EVAL_MODEL` | Any non-empty value opts in. The tests in `tests/test_eval_live.py` run, and the model seam calls the Claude Code command line. | Every test in `tests/test_eval_live.py` is skipped, and the model seam raises an error instead of calling a model. |
| `FRAMEWORK_EVAL_CLAUDE` | The model seam runs the executable at this path. Set it when `claude` is not on `PATH`; the Claude Code extension for VS Code keeps its executable under `resources/native-binary/`. | The model seam runs `claude` from `PATH`. When there is none, the seam raises an error, and the eval is scored `error`, like every other seam failure. |

`FRAMEWORK_EVAL_MODEL` alone does not select the tier. `pyproject.toml` deselects tests marked
`eval` by default (`-m "not eval"`), so the command also needs `-m eval`.

A passing run prints one passed test for each spec. A failing test prints the eval's result: the
parsed decision, each assertion with its detail, and each judge verdict.

## How the fast gate stays free of a model

The fast gate is `python -m pytest -q` and `python rites/validate.py`. CI runs both and never runs
the eval tier, because a required check that depends on a model would fail for reasons the change
did not cause.

- **The harness is not a rite.** It lives in `tests/eval_harness.py`. `rites/validate.py` never
  runs it, and `rites/data/validators.json` does not list it.
- **One function reaches the model.** The harness takes a model seam, `model_fn(prompt, cwd)`,
  as an argument. The scaffolding tests pass a fake seam that returns fixed text. The default
  seam, `claude_cli_seam`, refuses to run unless `FRAMEWORK_EVAL_MODEL` is set.
- **The model tests are marked.** They carry the `eval` marker, which `pyproject.toml` deselects.

## What an eval does

1. The harness decodes the spec's files into a fixture grimoire in a temporary directory.
2. It builds the prompt: the user request, the full text of the playbook under test, and the
   spec's decision directive.
3. The seam runs `claude -p` in the fixture with the prompt on standard input. The assistant may
   read and edit files there and run Python, so it can run rites. `FRAMEWORK_HOME` points at the
   checkout unless the environment already sets it. A run times out after 600 seconds.
4. The harness reads the last fenced `json` block in the output as the decision.
5. It judges the decision and the files on disk.

An eval passes when the output holds a decision, every assertion passes and every judge criterion
passes. It fails otherwise. It reports an error when the seam raises.

The harness judges in two ways:

- **Assertions come first.** An assertion is a deterministic check on the decision or on the
  fixture. Use one wherever the expected outcome is a closed set: which layer, which `authority`,
  which pages.
- **A judge criterion is the fallback.** Each criterion is one yes-or-no question, put to the
  model in a call of its own. It passes only when the verdict is `pass` and the model quotes the
  evidence from the output word for word. Use one for an outcome that no assertion can express,
  such as whether the findings name the seeded contradiction.

| Assertion `type` | Other keys | Passes when |
|---|---|---|
| `list_any` | `list`, `where` | Some item of that list in the decision matches every key in `where`. A key that ends in `__contains` matches a substring. A key that ends in `__contains_all` matches when each given string occurs in some element of a list. |
| `field_equals` | `field`, `value` | The field of the decision equals the value. A dotted `field` reaches a nested key. |
| `field_in` | `field`, `values` | The field of the decision is one of the values. |
| `file_exists` | `path` | The path exists in the fixture. |
| `file_absent` | `path` | The path does not exist in the fixture. |
| `glob_min` | `pattern`, `min` | At least `min` paths in the fixture match the pattern. |
| `file_from_decision_exists` | `field` | The path the decision gives in that field exists in the fixture. |

## Eval spec format

The specs live in
[`tests/fixtures/invocation_eval_specs.json`](../tests/fixtures/invocation_eval_specs.json), in a
list named `evals`.

| Field | Required | Meaning |
|---|---|---|
| `eval_id` | Yes | A unique id. |
| `invocation` | Yes | The playbook under test, as a path under `invocations/`. |
| `grimoire_name` | Yes | The folder name of the fixture grimoire. |
| `user_request` | Yes | The command the assistant receives, as a user would type it. |
| `scenario_files` | Yes | The fixture grimoire: each relative path mapped to the file's content in base64. |
| `decision_directive` | Yes | The instruction, appended to the prompt, that asks for the `json` decision block. |
| `assertions` | Yes | The deterministic checks. |
| `judge_criteria` | No | The judge criteria. Each has `id`, `question`, `pass_if` and `fail_if`. |

A spec carries at least one assertion or one judge criterion. Every fixture passes `validate.py` as it stands.

File contents are base64 because the content validators, such as `validate_security` and
`validate_encoding`, scan `tests/`. A fixture with a deliberate defect, stored as plain text, would
fail the gate it exists to test. The
[negative-coverage tests](../tests/test_negative_coverage.py) follow the same rule.

| File | Holds |
|---|---|
| [`tests/eval_harness.py`](../tests/eval_harness.py) | The harness: spec loading, the fixture, the prompt, assertions, the judge and the seams |
| [`tests/test_eval_scaffolding.py`](../tests/test_eval_scaffolding.py) | The deterministic tests: specs are valid, playbooks exist, fixtures are validate-clean, the prompt and the checks work |
| [`tests/test_eval_live.py`](../tests/test_eval_live.py) | The model run |

The shipped specs cover `/grm-add` sorting an inbox into layers, `/grm-check` finding a seeded
contradiction, and `/grm-add` placing a page written from a chat answer.

## Adding an eval

1. Build a clean fixture grimoire, modeled on `tests/fixtures/good_grimoire/`. Seed exactly one
   defect that takes judgment to find.
2. Encode every file in base64 and add a spec to `invocation_eval_specs.json`.
3. Write a `decision_directive` that forces a structured decision. Use `assertions` wherever the
   outcome is a closed set, and `judge_criteria` only for the rest.
4. Run `python -m pytest tests/test_eval_scaffolding.py`. It passes when the spec is well formed,
   the playbook exists and the fixture is in its declared state.
5. Run `FRAMEWORK_EVAL_MODEL=1 python -m pytest -m eval`. The eval you added passes when the
   playbook leads a real model to the expected decision.

## Related

- The boundary between rites and playbooks: [script vs AI](script_vs_ai.md)
- The autonomy tiers that maintenance work follows: [governance](governance.md#autonomous-maintainer)
