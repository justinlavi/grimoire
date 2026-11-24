#!/usr/bin/env python3
"""Join an existing grimoire: clone it into the grimoire home and register it.

The deterministic half of `/grm-setup`. Given a git URL, the rite derives the
grimoire's directory name from the repository name, clones (or fast-forwards)
it under `~/grimoires/`, checks that it carries a `grimoire.json` manifest,
records it in `~/grimoires/library.json`, and registers its skills. Credentials
are whatever git already holds for the host: the rite never asks for a token;
if the clone needs one, git's own credential helper prompts the way it does for
any repository.

Mutation profile: apply_only. The rite writes the clone, a library entry
(`library.json`, under compare-and-swap) and the agent skill folders.

Usage:
    python rites/install_grimoire.py <git-url> [--name <directory>] [--home <path>]
        [--access read|edit] [--switch-url] [--no-skills] [--format human|json|jsonl]

`--access` is the access recorded for the grimoire. Without it, a grimoire with
no library entry yet is registered for reading (a copy made to read never
collects local changes) and an existing entry keeps its own access. The envelope
summary carries `access`, the value recorded for the key.

The library records the address the checkout fetches from. When the grimoire is
already on disk and came from another address, the rite stops and changes
nothing; the summary carries that address as `origin`. With `--switch-url` the
rite fetches the new address, checks that it shares history with the checkout,
and points the checkout at it. A repository with no shared history is another
grimoire and is refused.

A link may carry a credential (`https://<token>@host/...`). Git keeps it in the
checkout's own configuration, where it needs it. The library, the envelope and
every message hold the address without it. Two links that differ only by their
credential are one address: when the link carries a credential the checkout does
not have, the rite fetches with it and, on success, gives it to the checkout; the
summary then carries `credential: "refreshed"`. A credential that cannot fetch
changes nothing.

A grimoire that ends registered for reading while its checkout holds unsaved
changes or commits its upstream does not have gets a warning, and the summary
carries their counts as `unshared`.

The envelope records `clone` when the rite cloned and `pull` only when the
fast-forward pull of an existing checkout succeeded. A folder that is not a git
checkout is an error, and a library or skill registration that fails is an error.

Exit codes: 0 = installed and registered (or already current), 1 = blocked or
failed (clone failed, folder in the way, no manifest, library or skill
registration failed), 2 = argparse invalid arguments.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
from pathlib import Path

import summon_core
import sync_library
from _lib import address_credentials, load_manifest, read_library, scrub_credentials, strip_credentials
from diagnostics import ResultReporter, add_output_format_arg

FRAMEWORK_PATH = Path(__file__).resolve().parent.parent
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def derive_key(url: str) -> str:
    """Directory name for a grimoire, from the last path segment of its URL.

    Local paths (a bare repository on a shared drive, a Windows path with
    backslashes) are taken as paths; everything else goes through the same
    URL parser the installer uses for scopes.
    """
    raw = url.strip()
    looks_local = (
        "\\" in raw
        or re.match(r"^[A-Za-z]:[\\/]", raw) is not None
        or raw.startswith(("/", "./", "../", "~"))
        or Path(raw).exists()
    )
    if looks_local and "://" not in raw and not raw.startswith("git@"):
        name = Path(raw.replace("\\", "/").rstrip("/")).name
    else:
        _host, scope = summon_core.parse_scope_url(raw)
        name = summon_core._library_key_from_repo_path(scope)
    return re.sub(r"\.git$", "", name)


def same_address(first: str, second: str) -> bool:
    """True when two addresses name one repository.

    A trailing slash, `.git`, letter case and the credentials an address carries
    are ignored.
    """
    def bare(value: str) -> str:
        text = strip_credentials(value).replace("\\", "/").rstrip("/")
        return re.sub(r"\.git$", "", text, flags=re.IGNORECASE).rstrip("/").lower()

    return bare(first) == bare(second)


def recorded_access(library_path: Path, key: str) -> str | None:
    """The access the library records for `key`, or None when it has no entry."""
    library, _reason = read_library(library_path)
    entry = (library or {}).get("grimoires", {}).get(key)
    if not isinstance(entry, dict):
        return None
    return "read" if entry.get("access") == "read" else "edit"


def switch_address(target: Path, origin: str, url: str, credential_only: bool = False) -> tuple[str, str]:
    """Point the checkout at `url` when `url` holds the same grimoire.

    Returns `("ok", "")`, or `("error", text)` when the address cannot be fetched,
    or `("blocked", text)` when it shares no history with the checkout. The
    checkout's remote changes only on `ok`. `credential_only` words the texts for
    a link that differs from the checkout's only by its credential. No text
    carries a credential.
    """
    folder = str(target)
    shown, came_from = strip_credentials(url), strip_credentials(origin)
    code, _out, err = summon_core.git_capture("-C", folder, "fetch", "--quiet", url)
    if code != 0:
        reason = (err or "fetch failed").strip().splitlines()[-1][:200]
        if credential_only:
            return "error", (
                f"could not fetch {shown} with the credential in the link ({reason}), so {target} keeps the "
                "sign-in it had: check that the link is current and complete, and your VPN"
            )
        return "error", (
            f"could not fetch {shown} ({reason}), so {target} still comes from {came_from}: check the URL, "
            "your VPN, and that git can sign in to this host"
        )
    code, _out, _err = summon_core.git_capture("-C", folder, "merge-base", "HEAD", "FETCH_HEAD")
    if code != 0:
        return "blocked", (
            f"the repository at {shown} shares no history with {target}, which comes from {came_from}, so it is "
            "another grimoire and nothing was changed: pass --name for another directory"
        )
    code, _out, err = summon_core.git_capture("-C", folder, "remote", "set-url", "origin", url)
    if code != 0:
        return "error", f"could not point {target} at {shown}: {(err or 'git remote set-url failed').strip()[:200]}"
    return "ok", ""


def unshared_work(target: Path) -> tuple[int, int]:
    """Unsaved changes and commits the upstream does not have, as two counts; zero where git cannot tell."""
    folder = str(target)
    code, out, _err = summon_core.git_capture("-C", folder, "status", "--porcelain")
    changes = len([line for line in out.splitlines() if line.strip()]) if code == 0 else 0
    code, out, _err = summon_core.git_capture("-C", folder, "rev-list", "--count", "@{upstream}..HEAD")
    commits = int(out.strip()) if code == 0 and out.strip().isdigit() else 0
    return changes, commits


def _run_sync_skills() -> tuple[bool, str]:
    """Register the skills; returns `(ok, detail)` with the detail a reader needs."""
    returncode, output = summon_core.run_sync_skills(FRAMEWORK_PATH / "rites" / "sync_skills.py")
    report = summon_core.read_skill_sync_report(output)
    if report["problems"]:
        return False, "; ".join(report["problems"]) + (f" ({output.strip()[-200:]})" if output.strip() else "")
    errors = [m["message"] for m in report["messages"] if m["severity"] == "error"]
    detail = f"registered {report['counts'].get('registered', 0)} skill(s)"
    if returncode != 0:
        detail = f"sync_skills exited {returncode}" + (": " + "; ".join(errors) if errors else "")
    return returncode == 0, detail


def _register(key, entry, target, library_path, log, home, access, reporter) -> bool:
    """Write the library entry: the address the checkout fetches from, and `access` when one was given."""
    entry["online_path"] = strip_credentials(sync_library.detect_origin_url(target) or entry["online_path"])
    before = recorded_access(library_path, key)
    registered = summon_core.update_local_library(
        [key], {"grimoires": {key: entry}}, log, home=home,
        access=access or "read", replace_access=access is not None,
    )
    if registered and before is not None and access is not None and before != access:
        reporter.mutation("write", path=library_path, detail=f"{key}.access = {access}")
    return registered


class _Parser(argparse.ArgumentParser):
    """An argument parser whose error text never carries the credential of a link."""

    def error(self, message: str):
        super().error(scrub_credentials(message))


def main() -> int:
    parser = _Parser(description="Clone and register an existing grimoire")
    parser.add_argument("url", help="Git URL of the grimoire (https://..., git@host:path.git, or a local path); "
                                    "a credential in it is used and never recorded or printed")
    parser.add_argument("--name", default="", help="Directory name under the grimoire home (default: repository name)")
    parser.add_argument("--home", type=Path, default=summon_core.GRIMOIRES_HOME, help="Grimoire home (default: ~/grimoires)")
    parser.add_argument("--access", choices=("read", "edit"), default=None,
                        help="Access to record for the grimoire (default: read for a grimoire with no "
                             "library entry yet; an existing entry keeps its own)")
    parser.add_argument("--switch-url", action="store_true",
                        help="When the grimoire is already on disk from another address, point it at this one")
    parser.add_argument("--no-skills", action="store_true", help="Skip skill registration after the clone")
    add_output_format_arg(parser)
    args = parser.parse_args()
    human = args.format == "human"

    home = args.home.expanduser().resolve()
    reporter = ResultReporter("install_grimoire", root=home, mode="apply")

    address = strip_credentials(args.url)
    key = args.name.strip() or derive_key(args.url)
    if not key or not SAFE_KEY_RE.fullmatch(key):
        reporter.message("error", f"cannot derive a safe directory name from {address!r}; pass --name")
        if human:
            print(f"  [ERROR] Cannot derive a directory name from {address!r}; pass --name <directory>")
        else:
            reporter.emit(args.format)
        return 1

    target = home / key
    library_path = home / "library.json"
    summary = {"key": key, "path": str(target), "url": address, "manifest": "unknown", "skills": "skipped"}

    sink = contextlib.nullcontext() if human else contextlib.redirect_stdout(io.StringIO())
    with sink:
        log = summon_core.Logger()
        if human:
            print()
            print("  Join a grimoire")
            print("  ---------------")
            print()
        outcome = None
        stopped = False
        if not summon_core.check_git(log):
            reporter.message("error", "git is required but not found on PATH")
        else:
            home.mkdir(parents=True, exist_ok=True)
            entry = {"name": key, "online_path": args.url}
            origin = sync_library.detect_origin_url(target) if (target / ".git").is_dir() else ""
            switched, text = "", ""
            if origin and not same_address(origin, args.url):
                came_from = strip_credentials(origin)
                summary["origin"] = came_from
                if args.switch_url:
                    switched, text = switch_address(target, origin, args.url)
                else:
                    switched, text = "blocked", (
                        f"{key} is already at {target} and comes from {came_from}, not from {address}; nothing "
                        "was changed. Run again with --switch-url to make this copy come from the new "
                        "address, or pass --name for another directory when this is another grimoire"
                    )
                if switched == "ok":
                    reporter.mutation("remote", path=target, detail=f"{came_from} -> {address}")
            elif origin and address_credentials(args.url) not in ("", address_credentials(origin)):
                # One address, and the link carries a credential the checkout does not have.
                switched, text = switch_address(target, origin, args.url, credential_only=True)
                if switched == "ok":
                    summary["credential"] = "refreshed"
                    reporter.mutation("remote", path=target, detail=f"credential refreshed for {address}")
            if switched not in ("", "ok"):
                stopped = True
                reporter.message("error", text, path=target)
                if switched == "blocked":
                    reporter.set_status("blocked")
            if not stopped:
                outcome = summon_core.install_grimoire(key, entry, log, home=home)

        if stopped:
            pass
        elif outcome is None:
            reporter.message(
                "error",
                f"could not clone {address} into {target}: check the URL, your VPN, and "
                + ("the sign-in: the credential in the link may be out of date or cut short, or git may hold "
                   "none for this host" if address_credentials(args.url) else
                   "that git already holds a credential for this host (git prompts once, the way it does for "
                   "any repository)"),
                path=target,
            )
        elif outcome == summon_core.SKIPPED:
            reporter.message(
                "error",
                f"{target} exists and is not a git checkout, so nothing was cloned: "
                "move it away, or pass --name for another directory",
                path=target,
            )
        else:
            if outcome == summon_core.KEPT:
                reporter.message(
                    "warning",
                    f"{target} is already a checkout and its fast-forward pull failed (local changes?); it stays as it was",
                    path=target,
                )
            else:
                reporter.mutation("clone" if outcome == summon_core.CLONED else "pull", path=target, detail=address)
            manifest, errors = load_manifest(target)
            if manifest is None or errors:
                summary["manifest"] = "missing" if manifest is None else "invalid"
                reporter.message(
                    "error",
                    f"{key} is on disk but is not a registered grimoire yet: "
                    + ("; ".join(errors) if errors else "no grimoire.json")
                    + ". Run /grm-setup <directory> to write its manifest and register it.",
                    path=target,
                )
                reporter.set_status("blocked")
            elif not _register(key, entry, target, library_path, log, home, args.access, reporter):
                summary["manifest"] = "ok"
                reporter.message(
                    "error",
                    f"{library_path} could not be updated, so {key} is not registered: see the messages above; "
                    "fix that file and run the rite again",
                    path=library_path,
                )
            else:
                summary["manifest"] = "ok"
                recorded, _reason = read_library(library_path)
                recorded_entry = (recorded or {}).get("grimoires", {}).get(key)
                summary["access"] = "read" if isinstance(recorded_entry, dict) and recorded_entry.get("access") == "read" else "edit"
                reporter.mutation("register", path=library_path, detail=key)
                changes, commits = unshared_work(target) if summary["access"] == "read" else (0, 0)
                if changes or commits:
                    summary["unshared"] = {"changes": changes, "commits": commits}
                    text = (
                        f"{key} is set up for reading and its copy holds work that was never shared "
                        f"({changes} unsaved change(s), {commits} commit(s)). A copy for reading takes in no "
                        "updates while it holds that work: switch the copy to editing and save, or discard the work"
                    )
                    reporter.message("warning", text, path=target)
                    log.warn(text)
                if not args.no_skills:
                    ok, detail = _run_sync_skills()
                    summary["skills"] = "synced" if ok else "failed"
                    if ok:
                        reporter.message("info", f"skill registration: {detail}")
                        log.ok(f"Skills registered ({detail})")
                    else:
                        reporter.message("error", f"skill registration failed: {detail}")
                        log.warn(f"Skill registration failed: {detail}")

    if human:
        print()
        if reporter.status() in ("ok", "noop"):
            print(f"  [OK]    {key} is installed at {target} and registered in the library.")
            print("  Open a fresh agent session so it sees the grimoire's skills.")
        else:
            for message in reporter.messages:
                if message["severity"] == "error":
                    print(f"  [ERROR] {message['message']}")
        return reporter.exit_code()

    reporter.emit(args.format, summary=summary)
    return reporter.exit_code()


if __name__ == "__main__":
    sys.exit(main())
