"""Generative negative coverage: every validator must fail-on-dirty.

For each validator, `tests/fixtures/negative_specs.json` carries a minimal
violating tree (file contents base64-encoded so the spec is inert to the
validators that scan `tests/`) plus the diagnostic codes that tree must trigger.
This module materializes each tree in a temp dir, runs the validator in
`--format json`, and asserts every promised code fires - so a refactor that
silently stops detecting a violation is caught.

Two gates keep the specs complete:

- `test_every_validator_has_a_negative_spec` requires a spec for every validator in
  rites/data/validators.json, except those named in `NO_NEGATIVE_SPEC`.
- `test_declared_codes_are_covered` statically enumerates every diagnostic code each
  validator can emit and asserts each is either triggered by a fixture or listed in
  that validator's documented allowlist (I/O-only or mutually-exclusive codes).
  Adding a new code without coverage fails the gate.
"""

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS = json.loads((REPO_ROOT / "tests" / "fixtures" / "negative_specs.json").read_text(encoding="utf-8"))
VALIDATORS = json.loads((REPO_ROOT / "rites" / "data" / "validators.json").read_text(encoding="utf-8"))

# Validators in validators.json that have no spec yet, with the reason. Keep this
# empty when every validator has one.
NO_NEGATIVE_SPEC = {
    "validate_portability": "its spec belongs to the content-validator lane and is not added yet",
}

# Validators whose codes reach `reporter.error` through a variable, so the literal
# `reporter.error("CODE", ...)` scan cannot see them: every quoted string in the source
# that starts with one of these prefixes counts as a declared code.
VARIABLE_CODE_PREFIXES = {
    "validate_naming": ("NAMING_", "SKILL_SCHEMA_"),
    "validate_portability": ("PORTABILITY_",),
    "validate_structure": ("STRUCTURE_",),
}


def _materialize(root: Path, files: dict) -> None:
    for rel, b64 in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(base64.b64decode(b64))


def _run(validator: str, run_mode: str, root: Path) -> tuple[int, set]:
    cmd = [sys.executable, str(REPO_ROOT / "rites" / f"{validator}.py")]
    env = dict(os.environ)
    if run_mode == "grimoire":
        cmd += ["--grimoire", str(root)]
    else:  # framework_home: point the framework-only validator at the fixture tree
        env["FRAMEWORK_HOME"] = str(root)
    cmd += ["--format", "json"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=60, cwd=str(REPO_ROOT)
    )
    codes = set()
    try:
        report = json.loads(result.stdout)
        for diag in report.get("diagnostics", []):
            codes.add(diag.get("code"))
    except json.JSONDecodeError:
        pass
    return result.returncode, codes


def _declared_codes(validator: str) -> set:
    txt = (REPO_ROOT / "rites" / f"{validator}.py").read_text(encoding="utf-8")
    pat = re.compile(r'reporter\.(?:error|warning)\(\s*["\']([A-Z][A-Z0-9_]+)["\']', re.S)
    codes = set(pat.findall(txt))
    for prefix in VARIABLE_CODE_PREFIXES.get(validator, ()):
        codes |= set(re.findall(r'["\'](' + re.escape(prefix) + r'[A-Z0-9_]+)["\']', txt))
    return codes


@pytest.mark.parametrize("validator", sorted(SPECS))
def test_validator_fails_on_dirty(validator, tmp_path):
    spec = SPECS[validator]
    _materialize(tmp_path, spec["files"])
    returncode, emitted = _run(validator, spec["run_mode"], tmp_path)

    assert returncode != 0, (
        f"{validator} should exit non-zero on its negative fixture"
    )
    missing = sorted(set(spec["expected_codes"]) - emitted)
    assert not missing, (
        f"{validator} no longer emits expected codes {missing}; "
        f"emitted {sorted(emitted)}"
    )


@pytest.mark.parametrize("validator", sorted(SPECS))
def test_expected_and_allowlist_are_disjoint(validator):
    spec = SPECS[validator]
    overlap = set(spec["expected_codes"]) & set(spec.get("allowlist", {}))
    assert not overlap, f"{validator}: codes both expected and allowlisted: {overlap}"


def test_every_validator_has_a_negative_spec():
    """Every validator the orchestrator runs has a spec, or a named reason it has none."""
    listed = {Path(name).stem for name in VALIDATORS["framework"] + VALIDATORS["grimoire"]}
    missing = sorted(listed - set(SPECS) - set(NO_NEGATIVE_SPEC))
    assert not missing, f"validators with no negative spec and no NO_NEGATIVE_SPEC entry: {missing}"
    unknown = sorted(set(NO_NEGATIVE_SPEC) - listed)
    assert not unknown, f"NO_NEGATIVE_SPEC names validators that are not listed: {unknown}"


def test_declared_codes_are_covered():
    """Every diagnostic code a validator declares is triggered by a fixture or
    documented in that validator's allowlist. Forces new codes into coverage."""
    uncovered = {}
    for validator, spec in SPECS.items():
        declared = _declared_codes(validator)
        covered = set(spec["expected_codes"]) | set(spec.get("allowlist", {}))
        gap = sorted(declared - covered)
        if gap:
            uncovered[validator] = gap
    assert not uncovered, (
        "Declared diagnostic codes with no fixture and no allowlist entry "
        f"(add a fixture or an allowlist reason): {uncovered}"
    )


def test_variable_code_prefixes_find_codes():
    """The prefix scan finds codes the literal scan misses, so it cannot silently go blind."""
    for validator in VARIABLE_CODE_PREFIXES:
        literal = set(re.findall(
            r'reporter\.(?:error|warning)\(\s*["\']([A-Z][A-Z0-9_]+)["\']',
            (REPO_ROOT / "rites" / f"{validator}.py").read_text(encoding="utf-8"),
            re.S,
        ))
        assert _declared_codes(validator) - literal, f"{validator}: prefix scan adds no code"
