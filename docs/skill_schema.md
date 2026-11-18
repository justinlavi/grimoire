---
type: reference
title: "Skill Naming Schema"
aliases: ["skill-schema", "skill-naming"]
tags: [framework/docs, type/reference]
authority: grimoire
last_verified: 2026-11-14
---

# Skill Naming Schema

How the framework's commands are grouped and named, and how a `SKILL.md` source is built, for a
framework command or for a grimoire's own. The [command surface](command_surface.md) owns the
contract of each shipped command; [agent configuration](agent_configuration.md) owns how skills
reach each agent.

## Command Families

A command's name shows what it acts on. The framework ships two families, declared in
[`framework.json`](reference.md#framework-manifest).

| Family | Commands | Acts on | Verbs | Source folder | Claude Code plugin |
|---|---|---|---|---|---|
| `grm` | `/grm-<verb>` | A grimoire and the install | `setup`, `create`, `add`, `save`, `update`, `check`, `publish`, `move`, `remove`, `help` | `skills/grm/` | `grimoire` |
| `dev` | `/grm-dev-<verb>` | The framework itself | `validate`, `improve` | `skills/dev/` | `grimoire-dev` |

Both families share the `grm` skill prefix. The `dev` family adds the slug prefix `dev`, which
puts `dev-` between the prefix and the verb.

A grimoire declares one `skill_prefix` in its
[`grimoire.json`](reference.md#grimoire-manifest), such as `cook` or `dnd`. Its commands are
`/<skill_prefix>-<slug>`, one for each `skills/<slug>/SKILL.md` in the grimoire.

### One command, one target

A command acts on one target: the framework or the active grimoire. A rite may serve both through
a flag such as `--grimoire`; each target still gets its own command, and both commands call the
same rite.

| Target | Command | Rite call |
|---|---|---|
| The framework | `/grm-dev-validate frontmatter` | `FRAMEWORK_HOME/bin/grimoire validate frontmatter` |
| The active grimoire | `/grm-check frontmatter` | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT frontmatter` |

The exception is a `grm` command whose job needs the framework as well. `/grm-update` is one: it
brings the framework, the library, the agent files and the active grimoire current together.
Keep such commands rare, and name what else the command acts on in its description.

A `grm` command that works on an existing grimoire resolves it through the
[grimoire directory guard](../invocations/meta/grimoire_directory_guard.md), which reads
`~/grimoires/library.json`. The command does not require the terminal's working directory to be
inside the grimoire when the guard can select one without guessing.

### How a command is typed

| Install | Name | Example |
|---|---|---|
| Flat registration (Codex, and Claude Code without the plugins) | `/grm-<verb>`, `/grm-dev-<verb>` | `/grm-add`, `/grm-dev-validate` |
| Claude Code plugins | `/grimoire:<verb>`, `/grimoire-dev:<verb>` | `/grimoire:add`, `/grimoire-dev:validate` |

Every source writes the flat name: skills, invocations and documentation. `rites/build_plugins.py`
renders the plugin name when it builds `plugins/`.

## Source Names

A skill source declares its name with a placeholder for the skill prefix.

| Family | `name:` line | Example source | Registers as |
|---|---|---|---|
| `grm` | `{{SKILL_PREFIX}}-<folder name>` | `skills/grm/check/SKILL.md` | `/grm-check` |
| `dev` | `{{SKILL_PREFIX}}-dev-<folder name>` | `skills/dev/validate/SKILL.md` | `/grm-dev-validate` |
| A grimoire | `{{SKILL_PREFIX}}-<folder name>` | `<grimoire>/skills/recipe-add/SKILL.md` | `/cook-recipe-add` |

The registration rite, `rites/sync_skills.py`, replaces these placeholders in every skill file it
writes:

| Placeholder | Replaced with |
|---|---|
| `{{SKILL_PREFIX}}` | The skill prefix of the family, or of the grimoire. Only the skill's own files change: the text of an inlined invocation keeps the token, so a playbook can show it |
| `{{FRAMEWORK_PATH}}` | The absolute path of the framework checkout |
| `{{GRIMOIRE_PATH}}` | The absolute path of the grimoire that owns the skill; grimoire skills only |

The rite also replaces the text `FRAMEWORK_HOME/` with the framework path, so a path an inlined
invocation writes with that [path key](reference.md#path-keys) works in the generated skill. Both
path placeholders and `FRAMEWORK_HOME/` are resolved inside inlined invocation text as well.

## Source Layout

A framework skill lives at `skills/<family>/<verb>/SKILL.md`. Registration flattens the two
levels into one command name.

```text
skills/grm/check/SKILL.md       -> /grm-check
skills/grm/add/SKILL.md         -> /grm-add
skills/dev/validate/SKILL.md    -> /grm-dev-validate
skills/dev/improve/SKILL.md     -> /grm-dev-improve
```

`validate_naming` (`/grm-dev-validate naming`) rejects a `name:` line that disagrees with its
folder, a family folder that `framework.json` does not declare, a family folder that holds a
`SKILL.md` directly, and a `SKILL.md` outside every declared family.

Every shipped command also has one entry in the [command surface](command_surface.md).
`/grm-dev-validate skill-refs` rejects a skill with no entry and an entry with no skill.

## SKILL.md Structure

A skill source is a `SKILL.md` with YAML frontmatter and a Markdown body. It is a pointer: the
body runs a rite or names an invocation, and holds no logic of its own.

| Frontmatter field | Required | Purpose |
|---|---|---|
| `name` | Yes | The command name, written as in [Source Names](#source-names). |
| `description` | Yes | One sentence that says what the command does for the user, in the user's words. The agent shows it in the command picker. |
| `when_to_use` | No | What the user says or wants that should lead here. It lets an agent offer the skill for a matching request. |
| `argument-hint` | No | The arguments, as shown while the user types the command, such as `"[quick \| <validator> \| naming \| boundaries \| fix]"`. |
| `arguments` | No | Names for the arguments. The body reads each one as `$<name>`. |
| `user-invocable` | No | `true` lets the user type the command. |
| `disable-model-invocation` | No | `true` stops an agent from running the skill on its own; only a typed command runs it. Set it on a skill that is destructive or that changes the framework. |
| `allowed-tools` | No | The tools the skill may use, separated by spaces, such as `Bash Read`. |
| `paths` | No | Glob patterns, relative to the session's working directory, such as `chapters/travel/trips/**`. Claude Code loads the skill by itself when the user works on a matching file. Keep the pattern narrow: a match loads the whole skill into context. A grimoire skill declares it in its own `SKILL.md`, and registration copies it through. |

[Agent configuration](agent_configuration.md) owns which agent honours which field and the policy
for automatic invocation. The [writing standard](writing_standard.md#what-the-user-sees) owns how
`description` and `when_to_use` are worded.

### Body

The body takes one of two forms. [Script vs AI](script_vs_ai.md#applying-this-to-skills) owns the
choice between them.

| Form | The body | Example |
|---|---|---|
| Rite-backed | Runs `{{FRAMEWORK_PATH}}/bin/grimoire <rite>` and reports the result. | `skills/dev/validate/SKILL.md` |
| Invocation-backed | Names its invocation with a `cat` directive. | `skills/grm/check/SKILL.md` |

The directive is one line:

```text
!`cat {{FRAMEWORK_PATH}}/invocations/<area>/<name>.md`
```

The directive is an instruction to the registration rite. Nothing runs it when the skill loads.
The rite:

1. Replaces the line with the body of the file it names, without that file's frontmatter.
2. Wraps the inlined text in `BEGIN INLINED` and `END INLINED` comments that name the file.
3. Applies the placeholder replacements to the inlined text.
4. Repeats the expansion for directives inside the inlined text, to three levels. A file that is
   already inlined in the skill is not inlined twice.

A directive whose file cannot be read stays in place, and the rite prints a warning.

A generated skill is therefore complete in itself. It works from any working directory and under
an agent policy that disables shell execution in skills. The rite inlines because an agent
honours a `cat` directive only for a file inside the session's working directories, and the
framework is rarely one of them.

Keep each generated skill under 500 lines. `tests/test_sync_skills_inline.py` enforces the limit
for every shipped command.

## Invocation Layout

Invocations are grouped by what they act on, as the commands are.

| Folder | Holds | Used by |
|---|---|---|
| `invocations/grm/` | One playbook for each grimoire verb | `/grm-<verb>` |
| `invocations/dev/` | The playbooks for maintaining the framework, and the quality reviews under `quality/` | `/grm-dev-<verb>` |
| `invocations/validators/` | One page for each validator, shared by both families | `/grm-check <selector>` on a grimoire, `/grm-dev-validate <selector>` on the framework |
| `invocations/meta/` | Fragments that other invocations and skills include | No command of its own |

## Related

- The contract of each shipped command: [command surface](command_surface.md)
- The generated catalog: [skills](skills.md)
- Registration and the agents: [agent configuration](agent_configuration.md)
