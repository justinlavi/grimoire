#!/usr/bin/env python3
"""Launcher body: resolve the framework and run one rite.

`bin/grimoire` (POSIX sh) and `bin/grimoire.cmd` (Windows) find a Python 3.10+ and
hand off here. The framework is the checkout this file sits in (`<framework>/bin/`)
or, for a copy of the launcher kept elsewhere, `$FRAMEWORK_HOME`, default
`~/.grimoire`.

    grimoire <rite> [arguments...]
    grimoire --list

A rite runs in Python's UTF-8 mode, so its file reads and writes default to UTF-8 on every
platform.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
USAGE = (
    "usage: grimoire <rite> [arguments...]\n"
    "       grimoire --list\n"
    "Runs rites/<rite>.py from the framework with this Python."
)


def framework_root() -> Path:
    beside = HERE.parent
    if (beside / "rites").is_dir():
        return beside
    return Path(os.environ.get("FRAMEWORK_HOME") or Path.home() / ".grimoire").expanduser()


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    rites = framework_root() / "rites"
    if argv[0] == "--list":
        if not rites.is_dir():
            print(f"grimoire: framework not found at {rites.parent}", file=sys.stderr)
            return 2
        for path in sorted(rites.glob("*.py")):
            if not path.name.startswith("_"):
                print(path.stem)
        return 0
    rite, args = argv[0], argv[1:]
    script = rites / f"{rite}.py"
    if not script.is_file():
        print(f"grimoire: no rite named '{rite}' (expected {script})", file=sys.stderr)
        return 2
    if sys.version_info < (3, 10):
        print("grimoire: Python 3.10 or newer is required", file=sys.stderr)
        return 127
    command = [sys.executable, "-X", "utf8", str(script), *args]
    if os.name == "posix":
        os.execv(sys.executable, command)
    return subprocess.run(command).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
