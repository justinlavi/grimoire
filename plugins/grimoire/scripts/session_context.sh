#!/bin/sh
# Session-start hook entry for the grimoire plugin.
# Finds a Python 3.10+ interpreter and runs session_context.py; prints a
# one-line note when none is available so the agent can tell the user. The exit
# code is always 0: a session never fails because of this hook.

here="$(cd "$(dirname "$0")" && pwd)"

for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            "$candidate" "$here/session_context.py"
            exit 0
        fi
    fi
done
if command -v py >/dev/null 2>&1; then
    if py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        py -3 "$here/session_context.py"
        exit 0
    fi
fi

echo "framework: Python 3.10 or newer is not installed, so the Grimoire framework cannot run; install Python from python.org (Windows: tick Add to PATH) and start a new session."
exit 0
