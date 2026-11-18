#!/usr/bin/env python3
"""Load and validate the grimoire scaffold contract.

The contract, formulae/grimoire/scaffold_contract.json, lists the directories and files a
grimoire scaffold creates. A file entry is managed (compared to the formula byte for
byte), seeded (`seed_if_absent`: copied in when absent, never overwritten) or customised
per grimoire. Read-only.
"""

from __future__ import annotations

import json
from pathlib import Path

from _lib import read_utf8

CONTRACT_RELATIVE_PATH = Path("formulae") / "grimoire" / "scaffold_contract.json"


class ScaffoldContractError(RuntimeError):
    """Raised when the scaffold contract cannot be loaded."""


def load_scaffold_contract(framework_root: Path) -> dict:
    """Load the grimoire scaffold contract from a framework root."""
    path = framework_root / CONTRACT_RELATIVE_PATH
    try:
        contract = json.loads(read_utf8(path))
    except FileNotFoundError as exc:
        raise ScaffoldContractError(f"missing scaffold contract: {path}") from exc
    except ValueError as exc:  # invalid JSON or not UTF-8
        raise ScaffoldContractError(f"invalid scaffold contract JSON: {path}: {exc}") from exc
    if not isinstance(contract, dict):
        raise ScaffoldContractError(f"scaffold contract must be a JSON object: {path}")
    return contract


def file_entries(contract: dict, include_root_hub: bool = False) -> list[dict]:
    """Return file entries from the contract in creation order."""
    entries: list[dict] = []
    if include_root_hub:
        root_hub = contract.get("root_hub")
        if isinstance(root_hub, dict):
            entries.append(root_hub)
    entries.extend(entry for entry in contract.get("files", []) if isinstance(entry, dict))
    return entries


def directory_entries(contract: dict) -> list[dict]:
    """Return directory entries from the contract in creation order."""
    return [entry for entry in contract.get("directories", []) if isinstance(entry, dict)]


def required_directories(contract: dict) -> list[str]:
    """Directories that a grimoire audit requires."""
    return [entry["path"] for entry in directory_entries(contract) if entry.get("required")]


def required_customized_files(contract: dict) -> list[str]:
    """Required static files that are customized per grimoire."""
    files: list[str] = []
    for entry in file_entries(contract):
        if not entry.get("required"):
            continue
        if entry.get("managed"):
            continue
        if entry.get("role") in {"manifest"}:
            continue
        target = entry.get("target", "")
        if "{{" in target or "}}" in target:
            continue
        files.append(target)
    return files


def managed_scaffold_files(contract: dict) -> list[str]:
    """Files audited by exact comparison against formulae/grimoire."""
    return [entry["target"] for entry in file_entries(contract) if entry.get("managed")]


def seeded_scaffold_files(contract: dict) -> list[str]:
    """Files the framework copies in when absent and never overwrites (user-owned after that)."""
    return [
        entry["target"]
        for entry in file_entries(contract)
        if entry.get("seed_if_absent") and not entry.get("managed")
    ]


def json_requirements(contract: dict) -> list[dict]:
    """JSON value requirements enforced during grimoire structure audits."""
    return [
        entry
        for entry in contract.get("json_requirements", [])
        if isinstance(entry, dict)
    ]


def validate_contract_against_formula(contract: dict, formula_root: Path) -> list[str]:
    """Return schema and source-file errors for a scaffold contract."""
    errors: list[str] = []
    if contract.get("version") != 1:
        errors.append("scaffold contract version must be 1")

    root_hub = contract.get("root_hub")
    if not isinstance(root_hub, dict):
        errors.append("scaffold contract missing root_hub object")
    else:
        _validate_file_entry(root_hub, formula_root, errors, "root_hub")

    seen_targets: set[str] = set()
    if isinstance(root_hub, dict) and root_hub.get("target"):
        seen_targets.add(root_hub["target"])
    for entry in directory_entries(contract):
        path = entry.get("path")
        if not path:
            errors.append("directory entry missing path")
            continue
        if Path(path).is_absolute():
            errors.append(f"directory path must be relative: {path}")
        source = entry.get("source")
        if source and not (formula_root / source).is_dir():
            errors.append(f"directory source missing from formula: {source}")

    for entry in file_entries(contract):
        _validate_file_entry(entry, formula_root, errors, "file")
        target = entry.get("target")
        if target:
            if target in seen_targets:
                errors.append(f"duplicate scaffold target: {target}")
            seen_targets.add(target)

    for entry in json_requirements(contract):
        path = entry.get("path")
        required_values = entry.get("required_values")
        if not path:
            errors.append("json requirement missing path")
        elif path not in seen_targets:
            errors.append(f"json requirement targets non-scaffold file: {path}")
        if not isinstance(required_values, dict):
            errors.append(f"json requirement for {path} missing required_values object")

    return errors


def _validate_file_entry(entry: dict, formula_root: Path, errors: list[str], label: str) -> None:
    source = entry.get("source")
    target = entry.get("target")
    if not source:
        errors.append(f"{label} entry missing source")
    elif Path(source).is_absolute():
        errors.append(f"{label} source must be relative: {source}")
    elif not (formula_root / source).is_file():
        errors.append(f"{label} source missing from formula: {source}")
    if not target:
        errors.append(f"{label} entry missing target")
    elif Path(target).is_absolute():
        errors.append(f"{label} target must be relative: {target}")
