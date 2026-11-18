---
type: reference
title: "Summoning Rite Contract"
aliases: ["summon-contract", "summoning-contract", "installer-contract"]
tags: [type/reference, framework/docs, scope/install]
authority: grimoire
last_verified: 2026-11-14
---

# Summoning Rite Contract

This page describes [`rites/data/summon_contract.json`](../rites/data/summon_contract.json), the
contract of the installer (the summoning rite): its four surfaces, the order of an install, the
environment variables, and the commands that inspect and repair an install. The file is the
authority; when this page and the file differ, the file is right.
[Installation](installation.md) owns the install routes.

## Surfaces

The installer runs in a terminal, from source, on a stock Python. It has four surfaces, the
`modes` of the contract; each mode lists its required behaviours in the file. `/grm-setup` holds
the conversation that follows an install.

| Surface | Role | Does |
|---|---|---|
| `rites/summon.sh` | Shell bootstrap | Finds Python 3.10 or newer, and installs it only after the user agrees. Run from the one-line command, it downloads the dispatcher and its companion files into a temporary folder; run from a checkout, it uses the files of the checkout |
| `rites/summon.py` | Dispatcher | Runs the installer, or routes `--check`, `--reconcile` and `--update` to the state surface. A download by the one-line command has no state surface, so there it always runs the installer |
| `rites/summon_core.py` | Install core | Runs the [install order](#install-order) |
| `rites/summon_state.py` | State surface | Runs the [state commands](#state-commands) and writes the transcript |

The companion files are `summon.py`, `summon_core.py`, `agent_targets.py`,
`data/agent_targets.json` and `templates/grimoire_block.md`. A download is retried with `curl` or
`wget`, then falls back to a Python download.

## Install order

Every install runs these steps in this order. They are the `required_pipeline` of the contract.

1. Check that `git` is available.
2. Install the framework, or update it when it is already installed.
3. Discover grimoires from a GitHub or GitLab scope URL. This step is optional.
4. Clone the grimoires the user selects. This step is optional.
5. Write the grimoires it cloned into `~/grimoires/library.json`.
6. Write the routing block into each agent instruction file the framework sets up.
7. Register the framework's skills and the grimoires' skills.

The install core also reads `GRIMOIRE_SCOPE`, `GITLAB_TOKEN` and `GITHUB_TOKEN` for steps 3
and 4; [installation](installation.md#clone-grimoires-during-the-install) describes them.

## Bootstrap environment controls

The shell bootstrap reads these variables. They are the `bootstrap_environment` of the contract.

| Variable | Purpose | Default |
|---|---|---|
| `FRAMEWORK_URL` | The repository the framework is cloned from. The dispatcher takes the first of `--framework-url`, this variable, the origin of the git checkout it runs from, and the public repository | `https://github.com/justinlavi/grimoire.git` |
| `FRAMEWORK_REF` | The branch or tag to install. The downloads of the companion files and the clone of the framework both use it | `main` |
| `FRAMEWORK_RAW_BASE` | The base URL the companion files download from | Derived from `FRAMEWORK_URL` and `FRAMEWORK_REF` |
| `GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS` | How many times a companion-file download is tried | 3 |
| `GRIMOIRE_SUMMON_RETRY_DELAY` | Seconds between two attempts | 2 |
| `GRIMOIRE_SUMMON_CONNECT_TIMEOUT` | Seconds before a download connection times out | 20 |

## State commands

Three flags of `summon` report on an install and repair it. They give an assistant a
machine-readable view, and they run from an installed framework:
`FRAMEWORK_HOME/bin/grimoire summon --check`.

| Command | Effect | Exit code |
|---|---|---|
| `--check` (alias `--plan`) | Reports drift in the framework tree (not populated), the library, the agent routing blocks and skill registration. Writes nothing but the transcript | 0 in sync, 1 drift |
| `--reconcile` | Proposes the offline repair. Writes nothing but the transcript | 0 in sync, 1 drift |
| `--reconcile --apply` | Adds missing library entries and corrects wrong ones, registers skills, and writes the routing block into each agent instruction file | 0 converged, 1 error, blocked, or something left |
| `--update` | Fetches every grimoire in the library and reports whether each is current. Changes no grimoire | 0 all current, 1 any grimoire not current (behind, diverged, dirty, detached, no upstream or unreachable) |
| `--update --apply` | Reconciles the library, fast-forwards each clean grimoire that is behind, registers skills with `--reset-managed`, writes the routing blocks, and heals the grimoires it confirmed current | 0 converged, 1 error, something left, a grimoire that is not current, or a grimoire whose content fails validation after the heal (`heal.status` `needs_check`, a warning) |

| Flag | Effect |
|---|---|
| `--prune` | With either `--apply` form, also deletes library entries whose folder is gone |
| `--format json` or `jsonl` | Prints the shared envelope of [`ResultReporter`](../rites/diagnostics.py) |
| `--home <path>` | Uses another folder than `~/grimoires` for the library scan |
| `--framework-root <path>` | Uses another framework checkout than the one detected |
| `--transcript-path <path>` | Writes the transcript somewhere other than `~/.cache/grimoire/summon-last.json` |

**An agent that is not installed is not configured.** Every command works on the agents whose home
folder exists (`~/.claude`, `~/.codex`; the [agent targets](agent_targets.md) page names them).
When no agent's home exists, every agent counts, so a machine with no assistant yet is still set
up.

**A routing block counts as drift when it is absent, stale or not one clean region.** A target the
`grimoire` plugin serves is the exception for an absent block: the plugin's session hook prints
the block, so the instruction file needs none.

**An update reports what the skill registration did.** The envelope's `summary.skill_sync` holds
the `registered`, `cleaned`, `reset` and `blocked` counts that `sync_skills` reported, and the
warnings and errors of that run appear among the `messages`. When the report cannot be read or
lacks a count, a warning says so.

**Every install and every state command writes a transcript.** The transcript is the envelope
plus `operation`, `run_id`, `started_at`, `ended_at`, `steps` and `final_state`, so that a later
session can compare what was intended with what happened.

**`--home` does not sandbox a write.** It scopes the library scan only. `--reconcile --apply`
still registers skills into the agent folders under the real home, and the transcript still goes
to its default path. To inspect a sandbox, combine `--check`, `--home` and `--transcript-path`.

[UPDATE.md](../UPDATE.md) owns the procedure that uses `--update --apply`, and names the fields of
the envelope to report.

## Boundaries

The state surface keeps five boundaries. Each is a required behaviour in the contract.

| Boundary | Behaviour |
|---|---|
| No repair on a broken base | `--apply` runs `validate.py` first. When the framework fails validation the command reports `blocked` and writes nothing |
| No silent deletion | A library entry whose folder is gone stays unless `--prune` is given. Each removal is recorded as a mutation |
| No guess at a routing block | The command finds a block by its BEGIN and END markers alone. It writes only where the markers leave no doubt, and reports every other file for the `/grm-update agentfile` edit. [The routing block](agent_configuration.md#the-routing-block) lists the cases |
| No pull of the framework | Pulling the framework itself is a step a person approves. The pull step of [UPDATE.md](../UPDATE.md) owns it |
| No heal of a grimoire that is behind | `--update` fast-forwards only a clean branch that is behind its upstream, and heals only the grimoires it confirmed current. A grimoire with no shared copy (status `local_only`: a plain folder, or a git repository with no remote) has nothing to pull and counts as current. A copy registered for reading (`access` `read` in the library) is pulled and never healed, so the command leaves no change in it. A grimoire that is unreachable or diverged goes into `needs_manual_pull`; one that is dirty, detached or on a branch with no upstream is reported with its `reason`. Each of these stays untouched. A failure on one grimoire never aborts the run |

## Change the installer

1. Update `rites/data/summon_contract.json` when a surface, an environment variable or a step of
   the install order changes. Then update this page.
2. Keep two rules true:
   - The routing block has one classifier and one writer, `summon_core.classify_routing_block` and
     `summon_core.apply_routing_block`; the installer, `inject_agent_file` and the state commands
     call them. The library has one writer, `sync_library.update_library`, which the state
     commands and the installer call.
   - The shell bootstrap downloads exactly the companion files the dispatcher needs, and those
     files import nothing from the framework at load time. They import other rites inside a
     function, after the framework is on disk.
3. Run the checks:

   ```bash
   python rites/validate.py structure
   python -m pytest tests/test_summon_core.py tests/test_summon_contract.py tests/test_summon_state.py
   ```

   `validate.py structure` validates the contract file. `tests/test_summon_contract.py` fails when
   `rites/summon.sh` assigns a `GRIMOIRE_SUMMON_*` or `FRAMEWORK_*` variable that the contract does
   not list. `tests/test_summon_core_install.py` fails when the download list changes or a
   bootstrap file imports more than the standard library at load time.
