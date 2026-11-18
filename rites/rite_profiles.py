#!/usr/bin/env python3
"""Load and validate the framework's mutating-rite profile contract.

`rites/data/rite_profiles.json` lists every rite that writes, with its profile
(`plan_apply` or `apply_only`), its commands, its writes and the
tests that cover it. `validate_rite_profiles` checks the file against the rites
folder: a rite whose source performs a write (a file write or removal, a move,
a `_lib` write helper, a mutating git command) needs an entry, an entry needs
such a write, and every listed test file exists.

This module also holds `check_contract`, the checks `command_surface.py` shares:
schema version, entry list, required fields, duplicates, and the entries missing
from or extra to the set the contract must cover.

Mutation profile: none; the module only reads.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from _lib import read_utf8

CONTRACT_PATH = Path("rites/data/rite_profiles.json")
ALLOWED_PROFILES = {"plan_apply", "apply_only"}
REQUIRED_STRING_FIELDS = {
    "path",
    "profile",
    "default_mode",
    "apply_command",
    "idempotency",
    "validation_profile",
}
REQUIRED_LIST_FIELDS = {"writes", "tests"}


@dataclass(frozen=True)
class ContractSpec:
    """What distinguishes one contract file from another in `check_contract`."""

    path: Path
    prefix: str
    title: str
    list_key: str
    key_field: str
    required_strings: frozenset
    required_lists: frozenset
    read_hint: str
    entry_hint: str
    list_item_hint: str
    duplicate_hint: str
    missing_message: str
    missing_hint: str
    extra_message: str
    extra_hint: str


def _error(spec: ContractSpec, kind: str, message: str, path: str, hint: str) -> dict[str, str]:
    return {"code": f"{spec.prefix}_{kind}", "message": message, "path": path, "hint": hint}


def check_contract(
    root: Path,
    spec: ContractSpec,
    expected: set[str],
    check_entry: Callable[[dict[str, Any], str, str, list], None],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return a contract file and its structural errors.

    Checks the schema version, the entry list, each entry's required string and
    list fields, duplicate keys, and the keys in `expected` against the keys the
    contract declares. `check_entry(entry, label, entry_path, errors)` adds the
    checks particular to one contract.
    """
    contract_path = spec.path.as_posix()
    try:
        contract = json.loads(read_utf8(root / spec.path))
    except (OSError, ValueError) as exc:
        return None, [_error(
            spec, "READ", f"could not read {spec.title}: {exc}", contract_path, spec.read_hint,
        )]
    if not isinstance(contract, dict):
        return None, [_error(
            spec, "SCHEMA", f"{spec.title} must hold a JSON object", contract_path,
            "Replace the file content with a JSON object.",
        )]

    errors: list[dict[str, Any]] = []
    if contract.get("schema_version") != 1:
        errors.append(_error(
            spec, "SCHEMA", f"{spec.title} must declare schema_version 1", contract_path,
            "Set schema_version to 1.",
        ))

    entries = contract.get(spec.list_key)
    if not isinstance(entries, list):
        errors.append(_error(
            spec, spec.list_key.upper(), f"{spec.title} must contain a {spec.list_key} list",
            contract_path, f"Add a top-level {spec.list_key} array.",
        ))
        entries = []

    seen: dict[str, int] = {}
    for index, entry in enumerate(entries):
        entry_path = f"{contract_path}#/{spec.list_key}/{index}"
        if not isinstance(entry, dict):
            errors.append(_error(
                spec, "ENTRY", f"{spec.title} entry must be an object", entry_path, spec.entry_hint,
            ))
            continue

        label = entry.get(spec.key_field)
        if isinstance(label, str):
            seen[label] = seen.get(label, 0) + 1
        else:
            label = f"<entry {index}>"

        for field in sorted(spec.required_strings):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(_error(
                    spec, "FIELD", f"{label} must declare non-empty {field}", entry_path,
                    f"Add {field} to the entry.",
                ))
        for field in sorted(spec.required_lists):
            value = entry.get(field)
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                errors.append(_error(
                    spec, "FIELD", f"{label} must declare non-empty string items in {field}",
                    entry_path, f"Set {field} to {spec.list_item_hint}.",
                ))
        check_entry(entry, label, entry_path, errors)

    for key, count in sorted(seen.items()):
        if count > 1:
            errors.append(_error(
                spec, "DUPLICATE", f"{key} appears {count} times in the {spec.title}",
                contract_path, spec.duplicate_hint,
            ))
    for key in sorted(expected - set(seen)):
        errors.append(_error(
            spec, "MISSING", spec.missing_message.format(key=key), contract_path, spec.missing_hint,
        ))
    for key in sorted(set(seen) - expected):
        errors.append(_error(
            spec, "EXTRA", spec.extra_message.format(key=key), contract_path, spec.extra_hint,
        ))
    return contract, errors


_MUTATING_ATTRS = {
    "write_text", "write_bytes", "mkdir", "unlink", "rmtree", "copyfile", "copytree",
    "touch", "rmdir", "symlink_to", "hardlink_to",
}
_OS_MUTATORS = {
    "replace", "rename", "remove", "removedirs", "makedirs", "mkdir", "rmdir",
    "symlink", "link", "write", "truncate",
}
_SHUTIL_MUTATORS = {"move", "copy", "copy2", "copyfile", "copytree", "rmtree"}
_PATH_MOVE_ATTRS = {"replace", "rename"}
# Helpers whose only purpose is to write a file: the `_lib` writers and
# `sync_library.update_library`, the writer of `library.json`.
_WRITE_HELPER_NAMES = {"write_utf8", "write_json", "update_library"}
# A rite that drives git mutates the repository even though it never opens a
# file itself. Calls to a git helper (`git(...)`, `git_fn(...)`, `git_capture(...)`,
# `run_git(...)`) or a subprocess list that spells out `git <verb>` count as
# writes when the verb changes the working tree, the index, history, or the remote.
_GIT_HELPER_NAMES = {"git", "git_fn", "git_capture", "run_git"}
_GIT_MUTATORS = {
    "add", "commit", "push", "pull", "rebase", "merge", "clone", "checkout",
    "reset", "rm", "mv", "tag", "init", "stash", "cherry-pick", "revert", "am",
}
_MODE_RE = re.compile(r"[rwaxbt+]+(?:[:|][\w.]+)?")


def _string_constants(node: ast.Call) -> list[str]:
    """Positional string constants of a call, flattening one level of list literals."""
    values: list[str] = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            values.append(arg.value)
        elif isinstance(arg, (ast.List, ast.Tuple)):
            for item in arg.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    values.append(item.value)
    return values


def _call_name(func: ast.expr) -> str:
    """The called function's own name: `git` for `git(...)` and `_lib.git(...)`."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _git_call_mutates(func: ast.expr, node: ast.Call) -> bool:
    """True for `git("push", ...)`-style helper calls and `subprocess.run(["git", "push", ...])`."""
    constants = _string_constants(node)
    if _call_name(func) in _GIT_HELPER_NAMES:
        return any(value in _GIT_MUTATORS for value in constants)
    if "git" in constants:
        after_git = constants[constants.index("git") + 1:]
        return any(value in _GIT_MUTATORS for value in after_git)
    return False


class _WriteVisitor(ast.NodeVisitor):
    """Detect obvious file-system and git writes in a Python rite."""

    mutates = False

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if _call_name(func) in _WRITE_HELPER_NAMES:
            self.mutates = True
        elif isinstance(func, ast.Attribute):
            attr = func.attr
            if attr in _MUTATING_ATTRS:
                self.mutates = True
            elif attr in ("open", "fdopen") and _mode_arg_writes(node, method=True):
                self.mutates = True
            elif _is_module_call(func, "os") and attr in _OS_MUTATORS:
                self.mutates = True
            elif _is_module_call(func, "shutil") and attr in _SHUTIL_MUTATORS:
                self.mutates = True
            elif attr in _PATH_MOVE_ATTRS and _is_single_positional(node):
                # Path.replace(target) / Path.rename(target); str.replace takes 2 args.
                self.mutates = True
            elif _git_call_mutates(func, node):
                self.mutates = True
        elif isinstance(func, ast.Name):
            if func.id == "open" and _mode_arg_writes(node, method=False):
                self.mutates = True
            elif _git_call_mutates(func, node):
                self.mutates = True
        self.generic_visit(node)


def _mode_arg_writes(node: ast.Call, *, method: bool) -> bool:
    """Return True when an open-like call has a write, append, create or update mode.

    `open(path, mode)` takes the mode second; `Path.open(mode)` takes it first,
    and `os.fdopen(fd, mode)` and `io.open(path, mode)` second. A method call
    therefore accepts the first or the second positional argument as the mode.
    """
    candidates = list(node.args[:2] if method else node.args[1:2])
    mode: str | None = None
    for arg in candidates:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _MODE_RE.fullmatch(arg.value):
            mode = arg.value
    for keyword in node.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            mode = keyword.value.value
    return isinstance(mode, str) and any(flag in mode for flag in ("w", "a", "x", "+"))


def _is_module_call(func: ast.Attribute, module: str) -> bool:
    """True when an attribute call's receiver is the named module (e.g. os.rename)."""
    return isinstance(func.value, ast.Name) and func.value.id == module


def _is_single_positional(node: ast.Call) -> bool:
    """True when a call has exactly one positional arg and no keyword/star args.

    Distinguishes the file-system `Path.replace(target)` / `Path.rename(target)`
    from `str.replace(old, new)`, which takes two arguments.
    """
    return (
        len(node.args) == 1
        and not node.keywords
        and not any(isinstance(arg, ast.Starred) for arg in node.args)
    )


def load_rite_profiles(root: Path) -> dict[str, Any]:
    """Load the rite-profile contract JSON."""
    return json.loads(read_utf8(root / CONTRACT_PATH))


def profile_entries(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return profile entries from the contract, or an empty list."""
    entries = contract.get("profiles", [])
    return entries if isinstance(entries, list) else []


def discover_write_capable_rites(root: Path) -> set[str]:
    """Return top-level rites that contain obvious write operations (none without a rites folder)."""
    discovered: set[str] = set()
    rites = root / "rites"
    for path in sorted(rites.iterdir()) if rites.is_dir() else []:
        if path.name.startswith("_"):
            continue
        if path.suffix == ".py" and _python_rite_writes(path):
            discovered.add(path.relative_to(root).as_posix())
        elif path.suffix == ".sh" and _shell_rite_writes(path):
            discovered.add(path.relative_to(root).as_posix())
    return discovered


def _python_rite_writes(path: Path) -> bool:
    try:
        tree = ast.parse(read_utf8(path))
    except (OSError, SyntaxError, ValueError):
        return False
    visitor = _WriteVisitor()
    visitor.visit(tree)
    return visitor.mutates


def _shell_rite_writes(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    write_markers = (
        "git clone",
        "mkdir ",
        "rm -",
        "> ",
        'open(dest, "wb")',
    )
    return any(marker in text for marker in write_markers)


SPEC = ContractSpec(
    path=CONTRACT_PATH,
    prefix="RITE_PROFILE",
    title="rite-profile contract",
    list_key="profiles",
    key_field="path",
    required_strings=frozenset(REQUIRED_STRING_FIELDS),
    required_lists=frozenset(REQUIRED_LIST_FIELDS),
    read_hint="Create valid UTF-8 JSON at rites/data/rite_profiles.json.",
    entry_hint="Replace this entry with an object keyed by rite metadata.",
    list_item_hint="a list of strings",
    duplicate_hint="Keep exactly one profile entry per rite.",
    missing_message="{key} contains write operations but has no rite profile",
    missing_hint="Add a rite-profile entry or move the write behind an existing profiled rite.",
    extra_message="{key} has a write-capable profile but no write operations were detected",
    extra_hint="Remove the profile entry or update the write-operation detector.",
)


def validate_rite_profiles(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return the loaded contract and structured validation errors."""

    def check_entry(entry: dict[str, Any], label: str, entry_path: str, errors: list) -> None:
        def add(kind: str, message: str, hint: str) -> None:
            errors.append(_error(SPEC, kind, message, entry_path, hint))

        plan_command = entry.get("plan_command")
        if plan_command is not None and (not isinstance(plan_command, str) or not plan_command.strip()):
            add("FIELD", f"{label} plan_command must be null or a non-empty string",
                "Use null when a rite has no plan mode.")

        profile = entry.get("profile")
        if isinstance(profile, str) and profile not in ALLOWED_PROFILES:
            add("KIND", f"{label} uses unsupported profile {profile}",
                f"Use one of: {', '.join(sorted(ALLOWED_PROFILES))}.")

        if isinstance(entry.get("path"), str) and not (root / entry["path"]).exists():
            add("PATH", f"{entry['path']} does not exist",
                "Point the profile at an existing repository-relative path.")

        if profile == "plan_apply" and not isinstance(plan_command, str):
            add("PLAN", f"{label} is plan_apply but has no plan_command",
                "Declare the dry-run or planning command.")

        tests = entry.get("tests")
        for test in tests if isinstance(tests, list) else []:
            if isinstance(test, str) and test.strip() and not (root / test).is_file():
                add("TEST", f"{label} lists a test that does not exist: {test}",
                    "List the test files that cover this rite, as repository-relative paths.")

    return check_contract(root, SPEC, discover_write_capable_rites(root), check_entry)
