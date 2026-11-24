---
type: reference
title: "Installation"
aliases: ["install", "summon", "setup"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-21
---

# Installing Grimoire

This page holds every way to install the framework, the test that an install works, and what to
do when it does not. [Getting started](getting_started.md) holds the shortest path: install, set
up a grimoire, and the everyday commands.

| Section | Answers |
|---|---|
| [Requirements](#requirements) | What must be on the machine, and what an install writes |
| [Choose a route](#choose-a-route) | Which of the four routes fits |
| [Claude Code plugin](#claude-code-plugin) | The two-line install for Claude Code |
| [The installer](#the-installer) | The one-line install for Codex and any other assistant |
| [Clone grimoires during the install](#clone-grimoires-during-the-install) | How the installer finds and clones grimoires you already have |
| [Install without a terminal](#install-without-a-terminal) | A git client and the assistant do the work |
| [Manual install](#manual-install) | Each step by hand |
| [Run a rite](#run-a-rite) | The `grimoire` launcher |
| [Smoke test](#smoke-test) | How to confirm the install works |
| [Troubleshooting](#troubleshooting) | Symptom, cause, fix |

## Requirements

- **An AI assistant, installed and signed in.** Grimoire sets up
  [Claude Code](https://docs.claude.com/en/docs/claude-code) and
  [Codex](https://developers.openai.com/codex/cli) by itself. Every other assistant needs a manual
  step; [agent targets](agent_targets.md) lists them. You type the `/grm-*` commands into the
  assistant, not into a terminal.
- **`git`.**
- **Python 3.10 or newer**, reachable as `python3`, `python` or the Windows `py` launcher.
- **For the installer only:** a POSIX shell with `curl` or `wget`. On Windows that is Git Bash.

An install writes to these places:

| Place | Holds |
|---|---|
| `~/.grimoire/` | The framework |
| `~/grimoires/` | Your grimoires and `library.json`, the list of them |
| The instruction file and the skill folder of each assistant Grimoire sets up | The routing block and the commands; [agent targets](agent_targets.md) names the paths |
| `~/.cache/grimoire/summon-last.json` | A record of the last install or check |

## Choose a route

| Route | Use it when |
|---|---|
| [Claude Code plugin](#claude-code-plugin) | You use Claude Code |
| [The installer](#the-installer) | You use Codex or another assistant, or you want existing grimoires cloned in the same run |
| [Install without a terminal](#install-without-a-terminal) | You have a git client with a window and no shell |
| [Manual install](#manual-install) | You want to run each step yourself |

Every route ends the same way: start a new session in the assistant and type `/grm-setup`. It
joins an existing grimoire from its repository link, turns a folder into a grimoire, or starts a
new one.

## Claude Code plugin

Type these two lines in a Claude Code session:

```text
/plugin marketplace add justinlavi/grimoire
/plugin install grimoire@grimoire
```

The first line names the public repository. To install from a mirror, a copy of this repository
kept somewhere else, give the mirror's address there:
`/plugin marketplace add https://gitlab.example.com/tools/grimoire.git`. The plugin clones the
framework from the address the marketplace was added with, and both take their updates from it.
Access to a private mirror uses the credential git stores for that host.

In the VS Code extension, type `/plugins`: enter the address on the **Marketplaces** tab, then
install `grimoire` on the **Plugins** tab. From a terminal where the `claude` command is
installed, the same two steps are:

```text
claude plugin marketplace add justinlavi/grimoire
claude plugin install grimoire@grimoire
```

Then start a new session. At the start of that session the plugin clones the framework into
`~/.grimoire`, and says so when `git` or Python 3.10 is missing. A plugin install spells the
commands `/grimoire:<verb>`: type `/grimoire:setup`.

| You want | Do |
|---|---|
| The commands for maintaining the framework (`/grimoire-dev:validate`, `/grimoire-dev:improve`) | `/plugin install grimoire-dev@grimoire` |
| The plugins to update by themselves | Turn on auto-update for the `grimoire` marketplace; see [plugin mode](agent_configuration.md#plugin-mode) |
| To install for every machine in an organization | An administrator sets `extraKnownMarketplaces` and `enabledPlugins` in the managed settings of Claude Code |

## The installer

Run this in a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash
```

This line installs from the public repository. The table below has the form that installs from a
mirror or a fork: it sets `FRAMEWORK_URL` to that address, and the install takes its updates from
there.

The installer is also called the summoning rite. It asks one question: install the framework
only, or install the framework and clone grimoires you already have. It then installs the
framework at `~/.grimoire/` (or pulls it when it is already there), clones the grimoires you
choose, and sets up each assistant it supports. The
[summoning contract](summoning_contract.md) owns the order of those steps, the environment
variables, and the `--check`, `--reconcile` and `--update` commands that inspect and repair an
install.

It installs no dependency without asking. When Python 3.10 is missing, it offers to install Python
with the package manager of the machine (`apt`, `dnf` or `pacman` through `sudo`, or `brew`), and
stops when you decline. Run through `curl | bash`, it reads your answers from the terminal, not
from the pipe.

| You want | Run |
|---|---|
| To install from a fork or a private mirror | `curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh \| FRAMEWORK_URL=https://github.com/your-org/grimoire.git bash` |
| To install a branch or tag other than `main` | `curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/<ref>/rites/summon.sh \| FRAMEWORK_REF=<ref> bash`. Name the ref in both places |
| To clone grimoires without the question | `curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh \| bash -s -- --scope https://github.com/my-org` |
| To install where `raw.githubusercontent.com` is unreachable | Clone the framework into `~/.grimoire`, then `bash ~/.grimoire/rites/summon.sh`. The installer uses the files of that checkout and pulls it from its own remote |

With `FRAMEWORK_URL` set to a host other than github.com, the one-line form still downloads the
installer's own files from the public repository and clones the framework from the mirror. When
the machine cannot reach the public repository, use the last row.

## Clone grimoires during the install

The installer finds grimoires by asking the API of a git host. The framework ships no list of
grimoires. The framework and your grimoires can live on different hosts.

**Tell it where to look.** Pass a URL as `--scope`, set `GRIMOIRE_SCOPE`, or answer the prompt.
An empty answer installs the framework only.

| URL | The installer |
|---|---|
| One repository, such as `https://github.com/you/cooking-grimoire` | Offers that repository, whatever its name |
| A group, organization or user, such as `https://github.com/you` or `https://gitlab.company.com/my-group` | Offers each repository whose name ends in `-grimoire`, whose topics include `grimoire`, or whose description contains "grimoire" |

It lists what it found and you choose which to clone.

**Sign in to a private host.** The installer reads a token from the environment and, when there
is none, from the credential git stores for the host.

| Host | Variable |
|---|---|
| GitLab (gitlab.com or self-hosted) | `GITLAB_TOKEN` |
| GitHub (github.com or GitHub Enterprise) | `GITHUB_TOKEN` |

```bash
read -rs -p "GitLab token: " GITLAB_TOKEN
export GITLAB_TOKEN
curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash -s -- --scope https://gitlab.company.com/my-group
```

**When it finds nothing.** The installer reports the failure, installs the framework and clones
no grimoire. Join a grimoire afterwards with `/grm-setup <url>` in the assistant; add `read` or `edit` after the link to say how you will use it.

**When a grimoire is found before the framework.** The README of every grimoire carries the
installer line with that grimoire's own URL as `--scope`, so one command installs both.
`/grm-create` writes that section from `formulae/grimoire/README.md`.

## Install without a terminal

A git client with a window and an AI assistant are enough. The assistant runs the rites.

1. Clone `https://github.com/justinlavi/grimoire`, or the mirror you were given, into
   `~/.grimoire` with the git client. The folder must be `~/.grimoire`.
2. Start a new session in the assistant.
3. Tell the assistant:

   ```text
   Read ~/.grimoire/UPDATE.md and follow its AI Update Playbook exactly.
   This is a fresh install, so set up the library, agent files, and skills from scratch.
   ```

4. Start one more new session, because assistants read the command list when a session starts.
   Then type `/grm-setup`.

[UPDATE.md](../UPDATE.md) owns the procedure the assistant follows.

## Manual install

1. Clone the framework into `~/.grimoire/`.
2. Clone each grimoire into `~/grimoires/<grimoire-name>/`. The other rites find the framework
   and the grimoires at these two places.
3. Write the library: `~/.grimoire/bin/grimoire sync_library --apply`. The
   [reference](reference.md) describes the file.
4. Write the routing block: `~/.grimoire/bin/grimoire inject_agent_file --apply`. For an
   assistant Grimoire does not set up, paste the block by hand as
   [agent configuration](agent_configuration.md#the-routing-block) describes.
5. Register the commands: `~/.grimoire/bin/grimoire sync_skills`.

## Run a rite

Run every rite as `~/.grimoire/bin/grimoire <rite> [arguments]`. The launcher finds a Python 3.10
or newer interpreter and runs `rites/<rite>.py` with it, so no instruction depends on what the
interpreter is called on a machine. The rite runs in Python's UTF-8 mode, so its file reads and
writes default to UTF-8 on every platform, and the launcher exits with the rite's exit code.

| You want | Run |
|---|---|
| A rite | `~/.grimoire/bin/grimoire validate --summary` |
| The list of rites | `~/.grimoire/bin/grimoire --list` |
| A rite from the Windows command prompt | `%USERPROFILE%\.grimoire\bin\grimoire.cmd validate --summary` |

## Smoke test

Run the four checks in order. Each names what a pass looks like.

1. **The install agrees with the disk.** Run `~/.grimoire/bin/grimoire summon --check`. A pass
   exits 0 and prints "In sync". A failure exits 1, prints "Drift detected" and names the part
   that drifted: the library, a routing block or the commands. `/grm-update` repairs each of them.
2. **The assistant has the commands.** Start a new session and type `/grm-setup`. A pass: the
   assistant asks whether you want to join a grimoire, start one or convert a folder.
3. **The assistant reads a grimoire.** Ask: "Read the root hub of `<grimoire-name>` and tell me
   which chapters it routes to." A pass: the assistant opens `<grimoire>/<grimoire>.md` at the
   path `~/grimoires/library.json` gives and lists exactly the chapters in that file. An
   assistant that invents chapters or cannot find the file is missing the routing block; see
   [Troubleshooting](#troubleshooting).
4. **The assistant follows a route.** Ask: "Which page is the owner of `<topic>` in
   `<grimoire-name>`?" A pass: the assistant goes from the root hub through each hub to one page
   and names the path of every file it read.

Checks 3 and 4 need a grimoire. Skip them until `/grm-setup` has given you one.

## Troubleshooting

When in doubt, start a new session and type `/grm-update`. It brings the framework, the library,
the routing block, the commands and every grimoire current.

| Symptom | Cause | Fix |
|---|---|---|
| A command is missing from the picker | The assistant read the command list before the command was registered | Start a new session. Still missing: `/grm-update skills`, or `~/.grimoire/bin/grimoire sync_skills` when no command works |
| The commands are stale or wrongly named, and `/grm-update` is missing or fails | The registered commands are too old to repair themselves | Pull `~/.grimoire`, then tell the assistant to follow [UPDATE.md](../UPDATE.md) |
| A grimoire's own commands are missing, and the framework's are present | The grimoire has no `grimoire.json`, or the file has no `skill_prefix`, so registration skips the grimoire | Add it as the [reference](reference.md) describes, then `/grm-update skills` |
| The assistant cannot find a grimoire | The grimoire is not in `~/grimoires/library.json`, or its `local_path` is wrong after the folder was moved or renamed | `/grm-update library`, or `~/.grimoire/bin/grimoire sync_library --apply` |
| The assistant guesses instead of reading pages | The routing block is missing or stale in the assistant's instruction file, for example after `~/.claude/` or `~/.codex/` was deleted, or on another machine | `/grm-update agentfile`, or `~/.grimoire/bin/grimoire inject_agent_file --apply` |
| The installer cannot clone | No network path to the git host, or no credential for it | Connect the VPN if the host needs one, then test with `git ls-remote <url>` |
| The installer reports "No grimoires found" | The scope URL is wrong, the host is unreachable, or a private host got no token | Check the URL, then set `GITLAB_TOKEN` or `GITHUB_TOKEN` and run it again |
| A message that Python 3.10 or newer is required | No interpreter of that version answers to `python3`, `python` or `py` | Install Python from python.org (on Windows, tick "Add to PATH") or with the package manager, then run the command again |
