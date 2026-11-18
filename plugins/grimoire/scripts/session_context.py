#!/usr/bin/env python3
"""Session-start hook for the grimoire plugin: keep the framework current, print routing context.

Runs at the start of every Claude Code session while the plugin is enabled.
Its stdout becomes session context, so it prints only what the agent needs:

1. The framework. It lives at ``~/.grimoire`` for every agent. When the
   checkout is absent the hook clones it from the marketplace repository the
   plugin was installed from; when it is present, clean, and on ``main`` it
   fast-forwards it. A dirty or diverged checkout is left alone and reported.
2. The Grimoire routing block, when the user's ``~/.claude/CLAUDE.md`` does not
   already carry one, so a plugin-only install needs no instruction-file edit.
3. The installed grimoires with their descriptions and paths, read from
   ``~/grimoires/library.json``. Each grimoire that is a clean git checkout
   on a branch with an upstream is fetched and fast-forwarded; the result is
   a note on its line. A grimoire with unsaved changes, or with local and
   remote commits, is left alone and reported. A host that fails once is not
   tried again for the other grimoires. When an update changed a grimoire's
   own commands, the hook registers them through ``sync_skills.py``.
4. One drift line from ``summon.py --check``, so the agent can offer
   ``/grimoire:update`` at the right moment.

The script is self-contained (stdlib only) because it must run before the
framework exists. The whole run shares one time budget that stays under the
hook's 120-second timeout, and every subprocess is capped by what is left of it.
An unreachable network, malformed JSON, or any unexpected exception degrades to
a one-line note and exit code 0.

Environment overrides (tests, forks): ``FRAMEWORK_HOME`` (framework
checkout), ``FRAMEWORK_URL`` (clone source), ``FRAMEWORK_SESSION_HOME``
(grimoire home, default ``~/grimoires``), ``FRAMEWORK_CLAUDE_HOME`` (default
``~/.claude``), ``FRAMEWORK_SESSION_NO_NETWORK=1`` (skip fetch and clone).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
HOME = Path.home()
FRAMEWORK_HOME = Path(os.environ.get("FRAMEWORK_HOME") or HOME / ".grimoire").expanduser()
GRIMOIRE_HOME = Path(os.environ.get("FRAMEWORK_SESSION_HOME") or HOME / "grimoires").expanduser()
CLAUDE_HOME = Path(os.environ.get("FRAMEWORK_CLAUDE_HOME") or HOME / ".claude").expanduser()
NO_NETWORK = os.environ.get("FRAMEWORK_SESSION_NO_NETWORK") == "1"
BEGIN = "<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->"
END = "<!-- END GRIMOIRE KNOWLEDGE BASE -->"
START = time.monotonic()
BUDGET = 100
GIT_TIMEOUT = 10
FETCH_TIMEOUT = 30
CLONE_TIMEOUT = 60
GRIMOIRE_FETCH_TIMEOUT = 15
SKILLS_TIMEOUT = 30
DEFAULT_URL = "https://github.com/justinlavi/grimoire.git"
COMMAND_NOTE = (
    "commands: this install runs Grimoire as a Claude Code plugin, so the user types /grimoire:<verb> "
    "(/grimoire:add, /grimoire:save, /grimoire:update, ...). Wherever a page or the routing block says "
    "/grm-<verb>, say /grimoire:<verb>; /grm-dev-<verb> is /grimoire-dev:<verb> and needs the grimoire-dev plugin."
)
CHECK_TIMEOUT = 30
MIN_STEP_SECONDS = 3


def remaining() -> float:
    """Seconds left in the shared time budget."""
    return BUDGET - (time.monotonic() - START)


def git(*args: str, cwd: Path | None = None, timeout: int = GIT_TIMEOUT) -> tuple[int, str]:
    timeout = min(timeout, remaining())
    if timeout < MIN_STEP_SECONDS:
        return 124, "no time left"
    env = dict(os.environ)
    # A missing credential fails at once: no terminal prompt and no sign-in window.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
        )
    except FileNotFoundError:
        return 127, "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _read_json(path: Path) -> object:
    """The parsed JSON file, or None when it is missing, unreadable or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def framework_url() -> str:
    """The marketplace repository the plugin came from is the framework repository."""
    override = os.environ.get("FRAMEWORK_URL")
    if override:
        return override
    marketplace = ""
    parts = PLUGIN_ROOT.as_posix().split("/")
    if "cache" in parts:
        index = parts.index("cache")
        if index + 1 < len(parts):
            marketplace = parts[index + 1]
    known = CLAUDE_HOME / "plugins" / "known_marketplaces.json"
    known_entry = _as_dict(_read_json(known)).get(marketplace)
    source = _as_dict(_as_dict(known_entry).get("source"))
    if source.get("source") == "github" and isinstance(source.get("repo"), str) and source["repo"]:
        return f"https://github.com/{source['repo']}.git"
    for key in ("url", "path"):
        if isinstance(source.get(key), str) and source[key]:
            return source[key]
    bundled = _as_dict(_read_json(HERE / "framework_source.json")).get("url")
    return bundled if isinstance(bundled, str) and bundled else DEFAULT_URL


def clone_framework() -> str:
    url = framework_url()
    FRAMEWORK_HOME.parent.mkdir(parents=True, exist_ok=True)
    code, out = git("clone", "--quiet", url, str(FRAMEWORK_HOME), timeout=CLONE_TIMEOUT)
    if code != 0:
        shutil.rmtree(FRAMEWORK_HOME, ignore_errors=True)
        return f"framework: clone of {url} failed ({out[-160:]}); run /grimoire:update once the host is reachable"
    return f"framework: installed at {FRAMEWORK_HOME} from {url}"


def recover_unpopulated_checkout() -> str:
    """Finish a clone that stopped before its working tree was written; return a one-line status."""
    code, _ = git("checkout", "--quiet", "HEAD", "--", ".", cwd=FRAMEWORK_HOME)
    if code == 0 and (FRAMEWORK_HOME / "rites").is_dir():
        return f"framework: restored the working tree at {FRAMEWORK_HOME} (an earlier clone was interrupted)"
    if any(entry.name != ".git" for entry in FRAMEWORK_HOME.iterdir()):
        return f"framework: {FRAMEWORK_HOME} has a git folder but no rites folder, and other files; leaving it alone"
    if NO_NETWORK:
        return f"framework: {FRAMEWORK_HOME} holds an interrupted clone (network disabled)"
    shutil.rmtree(FRAMEWORK_HOME, ignore_errors=True)
    return clone_framework()


def ensure_framework() -> str:
    """Clone or fast-forward the framework checkout; return a one-line status."""
    if not (FRAMEWORK_HOME / ".git").is_dir():
        if FRAMEWORK_HOME.exists() and any(FRAMEWORK_HOME.iterdir()):
            return f"framework: {FRAMEWORK_HOME} exists but is not a git checkout; leaving it alone"
        if NO_NETWORK:
            return f"framework: not installed at {FRAMEWORK_HOME} (network disabled)"
        return clone_framework()
    if not (FRAMEWORK_HOME / "rites").is_dir():
        return recover_unpopulated_checkout()
    code, status = git("status", "--porcelain", cwd=FRAMEWORK_HOME)
    if code != 0:
        return f"framework: present at {FRAMEWORK_HOME} (git status failed: {status[-120:]})"
    if status.strip():
        return f"framework: present at {FRAMEWORK_HOME} with local changes; not updated"
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=FRAMEWORK_HOME)[1].strip()
    if branch != "main":
        return f"framework: present at {FRAMEWORK_HOME} on branch {branch}; not updated"
    if NO_NETWORK:
        return f"framework: present at {FRAMEWORK_HOME} (network disabled)"
    code, out = git("fetch", "--quiet", cwd=FRAMEWORK_HOME, timeout=FETCH_TIMEOUT)
    if code != 0:
        return f"framework: present at {FRAMEWORK_HOME}; could not reach its remote"
    code, counts = git("rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=FRAMEWORK_HOME)
    fields = counts.split()
    behind = int(fields[0]) if code == 0 and fields and fields[0].isdigit() else 0
    if behind:
        code, out = git("merge", "--ff-only", "--quiet", "@{upstream}", cwd=FRAMEWORK_HOME)
        if code == 0:
            return f"framework: updated at {FRAMEWORK_HOME} ({behind} new commit{'s' if behind != 1 else ''})"
        return f"framework: present at {FRAMEWORK_HOME}; {behind} commit(s) behind but not fast-forwardable; run /grimoire:update"
    return f"framework: current at {FRAMEWORK_HOME}"


def routing_block() -> str:
    for candidate in (FRAMEWORK_HOME / "rites" / "templates" / "grimoire_block.md", HERE / "grimoire_block.md"):
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            continue
    return ""


def instruction_file_has_block() -> bool:
    try:
        text = (CLAUDE_HOME / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return False
    return BEGIN in text and END in text


def _host_of(url: str) -> str:
    """The host part of a remote URL (https, ssh or scp style), or an empty string."""
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^/@]*@)?([^/:]+)", url) or re.match(r"^(?:[^/@:]+@)?([^/:\\]+):(?![/\\])", url)
    return match.group(1).lower() if match else ""


UNREACHABLE_NOTE = "could not reach its remote; using the copy on disk"
REFUSED_NOTE = (
    "could not update from its remote (sign-in, permission, or the repository moved); "
    "using the copy on disk; run /grimoire:update"
)
# What git prints when a fetch never reached the host. Any other failure came
# from the host itself and says nothing about its other repositories.
_UNREACHABLE_MARKERS = (
    "could not resolve host", "failed to connect", "could not connect", "couldn't connect",
    "connection timed out", "connection refused", "connection reset", "network is unreachable",
    "no route to host", "operation timed out",
)


def _never_reached(code: int, output: str) -> bool:
    """True when a failed fetch timed out or never reached its host."""
    low = output.lower()
    return code == 124 or any(marker in low for marker in _UNREACHABLE_MARKERS)


class _UpdateState:
    """What the grimoire pass has learned so far: unreachable hosts and whether time ran out."""

    def __init__(self) -> None:
        self.dead_hosts: set[str] = set()
        self.out_of_time = False
        self.commands_changed: set[str] = set()


def register_skills() -> bool:
    """Register the grimoires' own commands through the framework; True when it succeeded."""
    rite = FRAMEWORK_HOME / "rites" / "sync_skills.py"
    timeout = min(SKILLS_TIMEOUT, remaining() - CHECK_TIMEOUT)
    if not rite.is_file() or timeout < MIN_STEP_SECONDS:
        return False
    try:
        proc = subprocess.run(
            [sys.executable or "python3", str(rite), "--format", "json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _update_grimoire(key: str, path: Path, state: _UpdateState) -> str:
    """Fetch and fast-forward one grimoire checkout; return its note, or an empty string.

    Only a clean working tree on a branch with an upstream is touched, and only
    by a fast-forward merge. A change under ``skills/`` is recorded in ``state``.
    """
    if state.out_of_time or not (path / ".git").exists() or NO_NETWORK:
        return ""
    if remaining() < CHECK_TIMEOUT + MIN_STEP_SECONDS:
        state.out_of_time = True
        return ""
    code, status = git("status", "--porcelain", cwd=path)
    if code != 0:
        return ""
    if status.strip():
        return "has unsaved changes; not updated"
    if git("symbolic-ref", "--quiet", "HEAD", cwd=path)[0] != 0:
        return ""
    code, upstream = git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=path)
    if code != 0:
        return ""
    code, url = git("remote", "get-url", upstream.split("/", 1)[0], cwd=path)
    host = _host_of(url.strip()) if code == 0 else ""
    if host and host in state.dead_hosts:
        return UNREACHABLE_NOTE
    code, output = git("fetch", "--quiet", cwd=path, timeout=GRIMOIRE_FETCH_TIMEOUT)
    if code != 0:
        if not _never_reached(code, output):
            return REFUSED_NOTE
        if host:
            state.dead_hosts.add(host)
        return UNREACHABLE_NOTE
    code, counts = git("rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=path)
    fields = counts.split()
    if code != 0 or len(fields) != 2 or not all(f.isdigit() for f in fields):
        return ""
    behind, ahead = int(fields[0]), int(fields[1])
    if not behind:
        return ""
    if ahead:
        return "has local commits and remote commits; run /grimoire:update"
    old = git("rev-parse", "HEAD", cwd=path)[1].strip()
    if git("merge", "--ff-only", "--quiet", "@{upstream}", cwd=path)[0] != 0:
        return "could not fast-forward; run /grimoire:update"
    new = git("rev-parse", "HEAD", cwd=path)[1].strip()
    code, changed = git("diff", "--name-only", old, new, "--", "skills", cwd=path)
    if code == 0 and changed.strip():
        state.commands_changed.add(key)
    return f"updated ({behind} new commit{'s' if behind != 1 else ''})"


def installed_grimoires() -> list[str]:
    entries = _as_dict(_as_dict(_read_json(GRIMOIRE_HOME / "library.json")).get("grimoires"))
    rows: list[tuple[str, str, str]] = []
    state = _UpdateState()
    for key, entry in sorted(entries.items()):
        raw = _as_dict(entry).get("local_path")
        if not isinstance(raw, str) or not raw:
            rows.append((key, f"- {key}: (no local path registered)", ""))
            continue
        path = Path(raw.replace("$HOME", str(HOME))).expanduser()
        try:
            note = _update_grimoire(key, path, state)
        except Exception:
            note = ""
        manifest = _read_json(path / "grimoire.json")
        description = _as_dict(manifest).get("description")
        if not isinstance(description, str):
            description = "(grimoire.json missing)" if manifest is None else ""
        line = f"- {key}: {description} ({path.as_posix()})"
        if _as_dict(entry).get("access") == "read":
            line += " [read-only]"
        rows.append((key, line, note))
    commands_note = ""
    if state.commands_changed:
        try:
            registered = register_skills()
        except Exception:
            registered = False
        commands_note = (
            "its commands changed: open a new session to use them" if registered
            else "its commands changed: run /grimoire:update skills, then open a new session"
        )
    lines = []
    for key, line, note in rows:
        if key in state.commands_changed:
            note = f"{note}; {commands_note}"
        lines.append(f"{line} - {note}" if note else line)
    return lines


def drift_line() -> str:
    summon = FRAMEWORK_HOME / "rites" / "summon.py"
    if not summon.is_file():
        return ""
    python = sys.executable or "python3"
    timeout = min(CHECK_TIMEOUT, remaining())
    if timeout < MIN_STEP_SECONDS:
        return ""
    try:
        proc = subprocess.run(
            [python, str(summon), "--check", "--format", "json", "--home", str(GRIMOIRE_HOME),
             "--transcript-path", str(GRIMOIRE_HOME / ".session-check.json")],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        report = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return ""
    if not isinstance(report, dict):
        return ""
    if report.get("status") in ("ok", "noop") and proc.returncode == 0:
        return "setup: in sync"
    messages = [m for m in _as_list(report.get("messages")) if isinstance(m, dict)]
    notes = [str(m.get("message", "")) for m in messages if m.get("severity") in ("warning", "error")]
    if not notes:
        actions = [a for a in _as_list(_as_dict(report.get("summary")).get("next_actions")) if isinstance(a, dict)]
        notes = [str(a["reason"]) for a in actions if a.get("reason")]
    detail = " (" + "; ".join(notes[:3]) + ")" if notes else ""
    return "setup: drift detected; offer /grimoire:update" + detail


def session_text() -> str:
    out: list[str] = []
    out.append(ensure_framework())
    out.append(COMMAND_NOTE)
    if not instruction_file_has_block():
        block = routing_block()
        if block:
            out.append("")
            out.append(block)
    grimoires = installed_grimoires()
    out.append("")
    out.append("## Installed grimoires")
    out.extend(grimoires or ["- none registered yet; /grimoire:setup joins or creates one"])
    drift = drift_line()
    if drift:
        out.append("")
        out.append(drift)
    text = "\n".join(out)
    if len(text) > 9500:
        text = text[:9500] + "\n... (truncated)"
    return text


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
    try:
        text = session_text()
    except Exception as exc:  # the hook never fails a session
        text = f"framework: the session hook stopped early ({type(exc).__name__}: {str(exc)[:120]}); Grimoire context is unavailable this session"
    try:
        print(text)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
