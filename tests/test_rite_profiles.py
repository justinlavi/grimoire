"""Contract tests for the framework's mutating-rite profiles."""

import ast
from pathlib import Path

from rite_profiles import (
    _WriteVisitor,
    discover_write_capable_rites,
    profile_entries,
    validate_rite_profiles,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _detects_write(src: str) -> bool:
    visitor = _WriteVisitor()
    visitor.visit(ast.parse(src))
    return visitor.mutates


def test_write_detector_flags_atomic_and_move_idioms():
    assert _detects_write("tmp.replace(dest)")      # Path.replace(target) - atomic rename
    assert _detects_write("p.rename(dest)")         # Path.rename(target)
    assert _detects_write("os.replace(a, b)")
    assert _detects_write("os.rename(a, b)")
    assert _detects_write("os.write(fd, blob)")
    assert _detects_write("shutil.move(a, b)")
    assert _detects_write("path.write_text('x')")


def test_write_detector_ignores_string_and_container_ops():
    assert not _detects_write("s.replace('a', 'b')")                 # str.replace (2 args)
    assert not _detects_write("s.replace('a', 'b').replace('c','d')")
    assert not _detects_write("d.copy()")                           # dict/list copy
    assert not _detects_write("f.write('x')")                       # file write, not os.write
    assert not _detects_write("x = 1 + 2")


def test_write_detector_flags_path_and_descriptor_writes():
    assert _detects_write("p.open('w')")                       # Path.open takes the mode first
    assert _detects_write("p.open(mode='a')")
    assert _detects_write("p.open('r+')")
    assert _detects_write("os.fdopen(fd, 'wb')")
    assert _detects_write("p.touch()")
    assert _detects_write("p.rmdir()")
    assert _detects_write("p.symlink_to(target)")
    assert _detects_write("open(p, 'w')")


def test_write_detector_ignores_reads():
    assert not _detects_write("p.open()")
    assert not _detects_write("p.open('r')")
    assert not _detects_write("p.open('rb')")
    assert not _detects_write("open(p)")
    assert not _detects_write("os.fdopen(fd, 'rb')")


def test_write_detector_flags_lib_write_helpers():
    assert _detects_write("write_utf8(path, text)")
    assert _detects_write("_lib.write_utf8(path, text)")
    assert _detects_write("write_json(path, data)")
    assert _detects_write("_lib.write_json(path, data, indent=4)")


def test_write_detector_applies_the_git_rule_to_run_git():
    assert _detects_write("run_git(root, 'commit', '-m', 'x')")
    assert _detects_write("_lib.run_git(root, 'push')")
    assert _detects_write("run_git(root, 'checkout', 'main')")
    assert not _detects_write("run_git(root, 'status', '--porcelain')")
    assert not _detects_write("_lib.run_git(root, 'diff', '--name-status', 'HEAD')")
    assert not _detects_write("run_git(root, 'ls-files', '-z')")


def test_rite_profile_contract_covers_write_capable_rites():
    contract, errors = validate_rite_profiles(REPO_ROOT)

    assert not errors
    assert contract is not None
    profiled = {entry["path"] for entry in profile_entries(contract)}
    assert profiled == discover_write_capable_rites(REPO_ROOT)


def test_rite_profile_docs_list_every_profiled_rite():
    contract, errors = validate_rite_profiles(REPO_ROOT)
    assert not errors

    docs = (REPO_ROOT / "docs" / "rite_profiles.md").read_text(encoding="utf-8")
    for entry in profile_entries(contract):
        assert f"| `{entry['path']}` | `{entry['profile']}` |" in docs
