#!/usr/bin/env python3
"""Grimoire Summoning Rite - installs the framework and optionally clones grimoires.

This file is the dispatcher. The install logic lives in `summon_core.py` (git,
discovery, library, agent files, skills; standard library only) and the
agent-legible state surface lives in `summon_state.py`. A run with no state flag
installs; `--check`, `--reconcile` and `--update` report on an install and
repair it.

Mutation profile: apply_only for the install (it writes the framework checkout,
the chosen grimoire clones, the library, the routing block and the skill
folders); plan_apply for `--reconcile` and `--update`, which write only with
`--apply`, and `--check`, which writes only its transcript. `summon_state.py`
describes the state commands.

Usage:
    python rites/summon.py [--framework-url URL] [--scope URL]
    python rites/summon.py --check | --reconcile | --update  [--apply] [--prune]
                      [--home PATH] [--framework-root PATH] [--transcript-path PATH]
                      [--format human|json|jsonl]

One-liner entry point:
    curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash

Options:
    --framework-url URL     URL of the framework git repository to install
    --scope URL             URL of the group/org containing your grimoires
    --check (--plan)        Report drift in the library, routing blocks and skills
    --reconcile             Repair the library and skills offline
    --update                Pull every library grimoire, reconcile, and heal
    --apply                 With --reconcile or --update, write the changes
    --prune                 With --apply, remove library entries whose folder is gone
    --home PATH             Grimoire home (default: ~/grimoires)
    --framework-root PATH   Framework checkout (default: the one this file is in)
    --transcript-path PATH  Where the transcript goes (default: ~/.cache/grimoire/summon-last.json)
    --format FORMAT         human (default), json or jsonl
    -h, --help              Show this help message

The framework URL is the first of: `--framework-url`, the FRAMEWORK_URL
environment variable, the origin of the git checkout this file runs from, the
public repository.

Environment variables:
    FRAMEWORK_URL     Same as --framework-url (the flag takes precedence)
    FRAMEWORK_REF     Branch or tag to clone
    GRIMOIRE_SCOPE    Same as --scope (the flag takes precedence)
    GITLAB_TOKEN      GitLab personal access token for private instances
    GITHUB_TOKEN      GitHub token for private orgs

Exit codes: 0 = installed, or the state command succeeded (in sync, or the
applied run converged); 1 = the install failed, drift was found, or the applied
run ended blocked, in error, with work left, or with a grimoire to pull by hand;
2 = argparse invalid arguments.
"""

import argparse
import sys

from summon_core import run_cli


def build_parser():
    """Build the dispatcher's argument parser (install flags plus the state surface)."""
    parser = argparse.ArgumentParser(
        description="Grimoire Summoning Rite - install the framework and optionally clone grimoires"
    )
    parser.add_argument(
        "--framework-url",
        help=(
            "URL of the framework git repository to install (default: FRAMEWORK_URL, then the origin "
            "of the checkout this file runs from, then the public GitHub repository)"
        ),
    )
    parser.add_argument(
        "--scope",
        help="URL of the group/org containing your grimoires (e.g., https://github.com/my-org)",
    )
    return parser


def main():
    parser = build_parser()

    # --check, --reconcile and --update route to summon_state. The piped
    # bootstrap ships the install-only subset, so a missing summon_state runs the
    # installer.
    try:
        from summon_state import add_state_args, is_state_invocation, run_state_command
        state_surface = True
    except ImportError:
        state_surface = False

    if state_surface:
        add_state_args(parser)
    args = parser.parse_args()

    if state_surface and is_state_invocation(args):
        sys.exit(run_state_command(args))

    run_cli(args)


if __name__ == "__main__":
    main()
