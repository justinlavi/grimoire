---
type: playbook
title: "Validate Rites"
aliases: ["validate-rites", "rite-quality"]
tags: [framework/invocations, type/playbook, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Validate Framework Rites

Reviews each rite script under `rites/` for what no validator can judge: its docstring, its error handling, its exit codes, what a rerun does, its portability, its size and its output.

## Trigger

Runs as step 4 of `/grm-dev-improve` ([[invocations/dev/improve_framework|improve framework]]). It has no command of its own. It also fits after a rite is created or changed, and before a framework release.

Requests that go elsewhere:

| Request | Owner |
|---|---|
| Find credentials and unsafe constructs in rites | `/grm-dev-validate security` ([[invocations/validators/validate_security|validate security]]) |
| Check structure, naming, links or format | The other selectors of `/grm-dev-validate` ([[invocations/validators/validators|validators]]) |
| Check that a contract sentence about a rite is true | [[invocations/dev/quality/audit_contract_coherence|audit contract coherence]] |

## Inputs

Run every command from the framework directory, `FRAMEWORK_HOME`.

| Input | Read it with |
|---|---|
| The rites in scope | `ls rites/*.py`. Every Python file directly under `rites/` is in scope, the validators, the `sync_*` rites and the orchestrators (`validate.py`, `summon.py`, `sync_skills.py`) included. `rites/data/` and `rites/templates/` are out of scope |
| The declared profile of each rite that writes | `rites/data/rite_profiles.json`. Load it before you review a rite that writes. [[docs/rite_profiles|rite profiles]] explains the profiles and their rules |
| The rules for docstrings and for printed output | "Source comments" and "What the user sees" in the [[docs/writing_standard|writing standard]] |
| When a rite does the work and when a playbook does | [[docs/script_vs_ai|script vs ai]] |

## Never

- Never repeat by eye what a validator checks: security, structure, naming, links, format. A validator's verdict is the same on every run; a reading is not.
- Never tune a rite for speed in this review. When a rite is slow, profile it first; otherwise leave its performance alone.

## Steps

### 1. List the rites

```bash
ls rites/*.py
```

- Done when: you hold the list, and the `rites/data/rite_profiles.json` entry of each rite that writes.

### 2. Review each rite

Read each rite from top to bottom and judge it against this table.

| Area | The rite passes when |
|---|---|
| Docstring | The module docstring meets "Source comments" in the [[docs/writing_standard|writing standard]]: what the rite does, its mutation profile, its usage line and its exit codes, with a one-line summary first. It also names what a caller cannot see: environment variables read, paths written, side effects. |
| Error handling | No bare `except:`; each handler names the exceptions it catches. File reads and writes are guarded, and a missing file produces a clear message, not a traceback. Each subprocess call checks the return code, with `subprocess.run(..., check=True)` or an explicit branch. A missing external tool, such as `git`, makes the rite degrade or fail with a line that says how to fix it. |
| Exit codes | `0` means success or a clean result. `1` means violations found or a failure the user can recover from. `2`, where the rite uses it, means misuse or bad arguments. The docstring lists the codes, and the rite calls `sys.exit(...)` explicitly. |
| Reruns | A second run on an unchanged tree gives the same output and the same exit code. A rite that writes follows the rules for its declared profile in [[docs/rite_profiles|rite profiles]]. No side effect accumulates across runs. Tests in a temporary directory or a temporary home cover the writes of a high-risk rite: one that writes agent files, an install, the library or grimoire content. |
| Portability | The rite resolves the framework root from the `FRAMEWORK_HOME` environment variable and falls back to its own location, as `default_framework_root` in `rites/_lib.py` does. It holds no `/home/...` path and no path specific to one user. It builds paths with `pathlib.Path`, not by joining strings. It passes no GNU-only flag to a subprocess (`grep -P`, the `sed -i` forms that differ between platforms) without a fallback. |
| Size | A rite stays under a soft cap of 300 lines. Above it, look for a helper to extract or for data to move into a file under `rites/data/`, as `rites/validate.py` does with `rites/data/validators.json`. A function stays under 50 lines where it can. |
| Output | Human output can be searched with `grep` and looks the same across the suite. A finding in a file prints as `path:line: message`, so that an editor can jump to it. The run ends with a summary line. Paths are relative to the framework root. Machine output is plain ASCII; an emoji appears only in a summary line for people. "What the user sees" in the [[docs/writing_standard|writing standard]] owns what a line says. |

A rite that fails several areas at once, and the same rite repaired:

```python
# Fails: the error is swallowed, the exit code says nothing, the path is absolute
try:
    data = open("/home/me/.grimoire/foo.md").read()
except:
    pass
```

```python
# Passes: explicit, relative, documented
"""Validate foo. Exit 0 clean, 1 on violations."""
path = FRAMEWORK_ROOT / "foo.md"
if not path.exists():
    print(f"{path.relative_to(FRAMEWORK_ROOT)}: missing", file=sys.stderr)
    sys.exit(1)
```

- Done when: every rite on the list has a verdict for every area, and each failure cites `rites/<name>.py:<line>`.

### 3. Fix each finding and prove the fix

For each finding:

1. Edit the rite.
2. Run it on a clean tree and confirm exit code 0.
3. Run it on a fixture that is known to fail, under `tests/fixtures/`, or on a temporary violation, and confirm exit code 1.

Then run the suite:

```bash
FRAMEWORK_HOME/bin/grimoire validate
```

Defer a finding that the deferral rule in [[invocations/dev/improve_framework|improve framework]] covers, such as splitting a large rite across many files.

- Done when: each fixed rite returned both expected exit codes, and the suite exits 0.

## Evidence and checks

- Each finding cites `rites/<name>.py:<line>` and the area of the table it fails.
- Each fix is proven by the two exit codes of step 3, quoted from the runs.
- `FRAMEWORK_HOME/bin/grimoire validate` exits 0 before this review reports success.

## Outputs

Files: the edited rites.

This review's part of the `/grm-dev-improve` reply:

1. The number of rites reviewed, from the list of step 1.
2. Findings by area, each with its file and line.
3. Fixes applied, each with the two exit codes that prove it.
4. Findings deferred, each with its reason.

## Related

- Orchestrator: [[invocations/dev/improve_framework|improve framework]]
- Mutation profiles: [[docs/rite_profiles|rite profiles]]
- Security scan: [[invocations/validators/validate_security|validate security]]
- When a rite acts and when judgment does: [[docs/script_vs_ai|script vs ai]]
