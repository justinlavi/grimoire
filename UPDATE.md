# Grimoire Update

This procedure brings the framework and every grimoire in the library current. Use it when the
installed `/grm-*` commands are missing, stale or wrongly named: it runs from the framework
source and uses no installed command. `/grm-update` runs the same procedure when it works.

It needs the framework checkout, `git`, and Python 3.10 or newer. The `bin/grimoire` launcher
finds the interpreter (`python3`, `python`, or the Windows `py` launcher).

## Start an update

1. Pull the framework with any Git tool you trust: SmartGit, GitHub Desktop, Git Bash, or a
   terminal. The framework is the folder `~/.grimoire`.
2. Open a new session in your AI assistant.
3. Tell the assistant:

```text
Read ~/.grimoire/UPDATE.md and follow its AI Update Playbook exactly.
Do not rely on installed slash commands until the update re-registers skills.
```

If the framework lives somewhere else, give the assistant the real path to this file.

## AI Update Playbook

The assistant runs these steps in order. These rules hold in every step:

- **Trust the source tree.** The pulled framework source is the source of truth. The skill files
  registered in the agent may be stale, so run no installed slash command until step 6 passes.
- **Run every command exactly as written.**
- **Report each rite's own machine output** (`--format json`), never a number you counted
  yourself. Claim that a grimoire is current only from its pull classification plus a clean
  validation. Claim that skills are registered only from the fields step 4 names.
- **Never force.** Do not pull over local changes, and do not discard or overwrite a commit to
  make a pull succeed.

### 1. Resolve the framework

The framework is the checkout that holds this file. Pin its root. When this file is not under
`~/.grimoire`, write its directory in place of `~/.grimoire`:

```bash
FRAMEWORK="$(git -C ~/.grimoire rev-parse --show-toplevel)"
```

- Done when: `$FRAMEWORK` is the root of a git checkout that contains this file.
- Stop when: neither the directory of this file nor `~/.grimoire` is a framework checkout. Ask the
  user for the path of the framework checkout.

### 2. Pull the framework

Pull `$FRAMEWORK` from the remote it tracks, whether that is the upstream project or a fork.

```bash
git -C "$FRAMEWORK" status --short          # if dirty: STOP, report, do not pull or force
GIT_TERMINAL_PROMPT=0 git -C "$FRAMEWORK" pull --ff-only
git -C "$FRAMEWORK" rev-parse HEAD && cat "$FRAMEWORK/VERSION"
```

- Done when: the first command prints nothing, the pull exits 0, and the third command prints the
  commit and the version. Run every later step from this source.
- Stop when: the first command prints any line (a dirty tree), the pull refuses because the
  checkout has local commits (not a fast-forward), or the pull fails (for example a private fork
  that the current credentials cannot reach). Report what git printed and let the user resolve it.

### 3. Validate the framework source

```bash
"$FRAMEWORK/bin/grimoire" validate --summary --format json
```

- Done when: the command exits 0 and the envelope's `status` is `pass`.
- Stop when: the command exits non-zero. Report each entry of `reports` whose `status` is `fail`.
  Run no step that changes skills or grimoires on a framework that fails validation.

### 4. Update everything

```bash
"$FRAMEWORK/bin/grimoire" summon --update --apply --format json
```

In one pass the command reconciles `~/grimoires/library.json` against disk, pulls every grimoire
in the library, registers the framework and grimoire skills with `--reset-managed`, writes the
routing block into each agent instruction file, and heals the grimoires it confirmed current. A
grimoire kept on this computer only (a plain folder, or a git repository with no remote) has
nothing to pull: its status is `local_only`, and the command heals it like a current one. A copy
registered for reading (`access` is `read` in its entry) is pulled and never healed: its managed
files come from the shared copy, so the command leaves every file in it as the pull left it. A
failure on one grimoire never aborts the run. The
[summoning contract](docs/summoning_contract.md#state-commands) owns the detail.

To see the classification of each grimoire before anything is written, run the same command
without `--apply` first.

Report, quoting the envelope:

1. The `summary.grimoire_summary` counts and the `status` of each entry in `summary.grimoires`.
2. Skill registration: `summary.skill_sync`, which holds the `registered`, `cleaned`, `reset` and
   `blocked` counts that `sync_skills` reported, the `messages` that begin `skills:` (its warnings
   and errors, such as a skill skipped for a wrong name or a collision), and
   `summary.skills_registered`, the count of framework-managed skills on disk after the run. When a
   `messages` entry says the skill report could not be read or lacks a count, say so and report
   only the counts that are present.
3. Each grimoire in `summary.needs_manual_pull`, on its own line, in these words:

   > NOT updated — pull it yourself with your tokens, then re-run: `git -C <path> pull --ff-only`

   The command did not touch such a grimoire: its host needs a sign-in, the network is down, or
   its branch has diverged. Healing a grimoire that is behind its upstream would repeat work that
   exists upstream and make the two diverge.
4. For the user, one plain line per grimoire, taken from those fields. For example: "Cooking: up
   to date; D&D: pulled new changes; Journal: kept on this computer only; Project Alpha: NOT
   updated, needs your login". For a grimoire whose status is neither current nor in
   `summary.needs_manual_pull`, quote its `reason`. For a grimoire whose `heal.status` is
   `needs_check`, say that its managed files are current and that its own pages do not pass
   validation, and offer to run `/grm-check` in it. A grimoire whose `access` is `read` is a copy
   for reading; say "up to date" or "pulled new changes" for it and nothing about healing.

- Done when: the command has printed its envelope and you have reported the four items. Exit
  code 0 means everything converged. Exit code 1 with `status` `ok` or `noop` means a grimoire
  is not current (`summary.needs_manual_pull`, or a `status` with a `reason` in
  `summary.grimoires`), a grimoire's content fails validation (`heal.status` is `needs_check`), or
  the command left something it does not fix (`summary.residual`); report each `residual` entry's
  `reason` and continue to step 5.
- Stop when: the envelope's `status` is `blocked` or `error`. Report its `messages` and ask the
  user how to proceed.

### 5. Confirm the agent routing block

The routing block is the region of an agent instruction file between
`<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->` and `<!-- END GRIMOIRE KNOWLEDGE BASE -->`. The markers
are the whole contract. Step 4 writes the block wherever the markers leave no doubt: it creates a
missing file, inserts the block into a file that has none, and refreshes one clean marked region.

Read the step 4 envelope:

- A `mutations` entry whose `detail` reads `create`, `insert` or `refresh` `routing block <target>`
  names a file the command wrote.
- A warning in `messages` that begins `agent_blocks: <target>` names a file the command left
  alone. That file has duplicate or malformed markers, or a `## Grimoire Knowledge Base` heading
  with no markers.

For each file the command left alone:

1. Read `$FRAMEWORK/rites/templates/grimoire_block.md`. It is the canonical block.
2. Replace the existing routing block, in whatever form it has, with the canonical block. When
   you cannot find one, insert the canonical block after the first heading.
3. Keep every line outside the markers unchanged.

`/grm-update agentfile` runs this same step.

- Done when: each file the command left alone holds exactly one marked region equal to the
  canonical block, or the envelope held no `agent_blocks:` warning.
- Stop when: you cannot tell which lines of a file belong to the routing block. Ask the user.

### 6. Run the final gate

```bash
"$FRAMEWORK/bin/grimoire" summon --check --format json
```

The check is offline. It covers the framework tree, the library, the routing blocks and skill
registration of every installed assistant. It fetches no grimoire, so a grimoire that step 4 reported as NOT updated does not fail it.

- Done when: the command exits 0. Report the exit code. Then ask the user to open a new session
  in the assistant, because assistants cache the command list.
- Stop when: the command exits 1. Report the `reason` and `command` of each entry in
  `summary.next_actions`, and do not report the update as complete.

## Related

- [README](README.md)
- [Installation](docs/installation.md)
- [Agent configuration](docs/agent_configuration.md)
- [Summoning contract](docs/summoning_contract.md)
- [The `/grm-update` playbook](invocations/grm/update.md)
