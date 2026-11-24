---
type: reference
title: "Grimoire Reference Guide"
aliases: ["terminology", "glossary", "reference"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-24
---

# Grimoire Reference Guide

The vocabulary of Grimoire and the files that give things their names: the grimoire manifest, the
framework manifest, the library, the path keys and the formula placeholders. Everyday use of a
grimoire takes only the first table.

| Section | Answers |
|---|---|
| [In plain language](#in-plain-language) | The six words that everyday use of a grimoire takes |
| [Vocabulary](#vocabulary) | Every system term, its one meaning and where it is used |
| [The Magical Boundary](#the-magical-boundary) | Where system terms are used and where a grimoire's own words are |
| [Grimoire Manifest](#grimoire-manifest) | The fields of `grimoire.json` |
| [Framework Manifest](#framework-manifest) | The fields of `framework.json` |
| [Local Library](#local-library) | The fields of `~/grimoires/library.json` and what writes it |
| [Path Keys](#path-keys) | The names that stand for the framework and for a grimoire in a path |
| [Placeholders in Formulae](#placeholders-in-formulae) | Each double-brace token a formula carries |
| [Text File Standard](#text-file-standard) | Encoding and line endings |

## In plain language

Using a grimoire takes six words, and you never have to say them back.

| Word | Plain meaning |
|---|---|
| A grimoire | A knowledge base on one subject, for one person or for many, kept as a folder of pages. |
| Grimoire | The product that builds and maintains grimoires. You install it once. |
| Assistant | The AI you talk to. It reads and writes the grimoire with you. |
| Page | One document in a grimoire. |
| Hub | The contents page of a folder. Your assistant keeps it current. |
| Command | Something you type to your assistant, such as `/grm-add`. |

## Vocabulary

Each term has one meaning. The last column of each table says where the term is used.

- A term marked **All text** is used everywhere, including everyday text: command descriptions,
  what a rite prints, what an assistant replies and the README of a grimoire.
- A term marked **System text** is used only in text that describes or runs the framework:
  playbooks, skills, the contract pages and source comments. Everyday text states the outcome in
  the plain words above instead.

The [writing standard](writing_standard.md#readers) owns that rule.

### Product and places

| Term | Meaning | Where it is | Used in |
|---|---|---|---|
| Grimoire | The product. | - | All text |
| The framework | The software inside the product: the rites, invocations, formulae, skills and documentation that every grimoire shares. | `~/.grimoire/`, written `FRAMEWORK_HOME` | System text |
| A grimoire | A knowledge base on one subject. It is a git repository with a `grimoire.json` at its root. | `~/grimoires/<name>/` | All text |
| Active grimoire | The grimoire a command acts on. The [grimoire directory guard](../invocations/meta/grimoire_directory_guard.md) resolves it. | Written `GRIMOIRE_ROOT` | System text |
| Manifest | The JSON file that declares an identity: `grimoire.json` for a [grimoire](#grimoire-manifest), `framework.json` for the [framework](#framework-manifest). | Repository root | System text |
| Library | The registry of installed grimoires and their paths. | [`~/grimoires/library.json`](#local-library) | System text |

### Inside a grimoire

| Term | Meaning | Where it is | Used in |
|---|---|---|---|
| Page | An authored Markdown file with [frontmatter](page_schema.md). | `chapters/**/*.md`, the root hub | All text |
| Frontmatter | The YAML block that opens a page, between two `---` lines. | The top of a page | System text |
| Chapter | A folder directly under `chapters/` that holds one area of knowledge. | `chapters/<chapter>/` | System text |
| Sub-chapter | A folder nested inside a chapter, at any depth. | `chapters/<chapter>/<sub>/` | System text |
| Hub | The page that routes a folder. It holds pointers and no knowledge. | `<folder>/<folder>.md` | All text |
| Root hub | The hub of the whole grimoire, where routing starts. | `<grimoire>/<grimoire>.md` | System text |
| Leaf | A page that is not a hub. It holds the knowledge. | Any other page under `chapters/` | System text |
| Source | Evidence a page cites: a raw artifact or a source wrapper. | `chapters/**/sources/` | System text |
| Source wrapper | A Markdown capture record for one source, with `type: source`. | `chapters/<chapter>/sources/<slug>.md` | System text |
| Inbox | The drop zone for content waiting to be classified. | `inbox/` | System text |
| Authority | Where a page's truth lives: `external`, `grimoire` or `hybrid`. | The `authority` field | System text |

The [operating model](operating_model.md) owns the layers and the hub rules. The
[page schema](page_schema.md) owns the fields, the page types and the authority models.

### Inside the framework

| Term | Meaning | Where it is | Used in |
|---|---|---|---|
| Rite | A script that does mechanical work: it validates, registers, installs or repairs. It runs as `FRAMEWORK_HOME/bin/grimoire <rite> [arguments]`. | `rites/*.py` | System text |
| Validator | A rite that checks one rule set and reports diagnostics. It writes nothing to the tree it checks. | `rites/validate_*.py` | System text |
| Selector | The word that names one validator in a command, such as `links` in `/grm-check links`. | [`invocations/validators/`](../invocations/validators/validators.md) | System text |
| Summoning rite | The installer. | `rites/summon.sh`, `rites/summon.py` | System text |
| Mutation profile | The declared way a rite writes: `plan_apply` or `apply_only`. | [Rite profiles](rite_profiles.md) | System text |
| Envelope | The JSON object a rite prints with `--format json`. It is the evidence an assistant reports from. | Standard output of a rite | System text |
| Invocation | A page an assistant follows or consults to carry out a framework operation. | `invocations/**/*.md` | System text |
| Playbook | A page with `type: playbook`: a procedure followed step by step. A framework playbook is an invocation with the six sections of the [invocation formula](../formulae/invocation.formula.md). | `invocations/`, or a grimoire's chapters | System text |
| Formula | A template that an assistant or a rite copies and fills in. | `formulae/` | System text |
| Skill | A `SKILL.md` file that gives an agent one command. | `skills/<family>/<slug>/SKILL.md`; in a grimoire, `skills/<slug>/SKILL.md` | System text |
| Command | What a user types to run a skill, such as `/grm-add`. | - | All text |
| Command family | A group of framework commands that act on the same thing: `grm` on grimoires, `dev` on the framework. | [Skill schema](skill_schema.md#command-families) | System text |
| Skill prefix | The first part of a command name: `grm` for the framework, and the manifest's `skill_prefix` for a grimoire. | `framework.json`, `grimoire.json` | System text |
| Plugin | A Claude Code package that carries one command family: `grimoire` or `grimoire-dev`. | `plugins/` | System text |
| Agent | The program that hosts the assistant, such as Claude Code or Codex. | [Agent targets](agent_targets.md) | System text |
| Assistant | The AI that reads a grimoire and follows playbooks. | - | All text |
| Agent instruction file | The file an agent reads at the start of every session, such as `~/.claude/CLAUDE.md`. | [Agent targets](agent_targets.md) | System text |
| Routing block | The marked section of an agent instruction file that tells the assistant how to find and route through grimoires. | Source: `rites/templates/grimoire_block.md` | System text |
| Registration | Writing skills into an agent's skill directory, done by the `sync_skills` rite. | [Agent configuration](agent_configuration.md) | System text |

## The Magical Boundary

System terms name parts of the framework. A grimoire's content uses the practical words of its
subject.

| Layer | Words | Examples |
|---|---|---|
| The framework | System terms: invocation, formula, rite, summoning | `invocations/`, `formulae/`, `rites/` |
| A grimoire's content | The subject's own words | `recipes/`, `techniques/`, `equipment/`, `policies/`, `guides/`, `checklists/`, `runbooks/`, `templates/`, `scripts/`, `snippets/`, `configs/` |

- Never create an `invocations/`, `formulae/` or `rites/` folder in a grimoire. Those folders
  exist only in the framework.
- Never use a system term in chapter prose. Naming a framework command is fine.
- Everyday text uses the [plain words](#in-plain-language) in every layer.

A reader looks for content in the words of the subject. A cook searches for "sourdough recipe",
not "bread formula". `/grm-check boundaries` reviews a grimoire against these rules.

## Grimoire Manifest

Every grimoire declares its identity in `grimoire.json` at its root.

```json
{
  "name": "cooking-grimoire",
  "skill_prefix": "cook",
  "description": "Personal cooking knowledge: recipes, techniques, equipment",
  "naming": "snake_case"
}
```

| Field | Required | Rule |
|---|---|---|
| `name` | Yes | The name of the grimoire. It matches the folder name and the library key. |
| `skill_prefix` | Yes | The prefix of the grimoire's own commands, `/<skill_prefix>-<slug>`. It matches `^[a-z][a-z0-9]*$`, and no two installed grimoires share one. |
| `description` | No | One line. |
| `naming` | No | The naming convention assistants apply to files and folders they create: `snake_case` when the field is absent, `preserve` to keep the casing of imported material, or another named style such as `kebab-case`. A non-empty string of at most 40 characters. The [operating model](operating_model.md#naming-and-depth-conventions) owns the convention. |

`validate_grimoire_structure` rejects a grimoire whose manifest is missing, unreadable or breaks a
rule above. `/grm-create` asks for the skill prefix and writes the manifest when it scaffolds a
grimoire.

A grimoire holds its own identity so that a clone knows its skill prefix without a library entry,
and so that the library and the grimoire cannot disagree about it.

## Framework Manifest

The framework is not a grimoire. It declares itself in `framework.json` at its root.

```json
{
  "name": "grimoire",
  "kind": "framework",
  "skill_prefix": "grm",
  "skill_families": {
    "grm": {
      "skill_prefix": "grm",
      "path": "skills/grm",
      "slug_prefix": "",
      "plugin": "grimoire"
    },
    "dev": {
      "skill_prefix": "grm",
      "path": "skills/dev",
      "slug_prefix": "dev",
      "plugin": "grimoire-dev"
    }
  },
  "description": "Framework for creating and maintaining grimoires"
}
```

| Field | Rule |
|---|---|
| `name` | `grimoire`. |
| `kind` | `framework`. Registration skips a manifest without it. A folder that holds a `framework.json` is never registered as a grimoire. |
| `skill_prefix` | The prefix for a family that declares none. |
| `skill_families` | One entry per command family. The [skill schema](skill_schema.md#command-families) owns the families. |
| `skill_families.<family>.skill_prefix` | The prefix of the family's commands. |
| `skill_families.<family>.path` | The folder that holds the family's skill sources. |
| `skill_families.<family>.slug_prefix` | A word placed between the prefix and the verb, or an empty string. |
| `skill_families.<family>.plugin` | The Claude Code plugin that carries the family; the family name when the field is absent. |
| `description` | One line. |

## Local Library

`~/grimoires/library.json` records where each installed grimoire lives, and nothing else. The
identity of a grimoire is in its [manifest](#grimoire-manifest).

```json
{
  "grimoires": {
    "cooking-grimoire": {
      "local_path": "$HOME/grimoires/cooking-grimoire",
      "online_path": "https://git.example.com/you/cooking-grimoire.git"
    },
    "dnd-grimoire": {
      "local_path": "$HOME/grimoires/dnd-grimoire",
      "online_path": "https://git.example.com/you/dnd-grimoire.git"
    }
  }
}
```

| Field | Rule |
|---|---|
| Key | The folder name of the grimoire. It is also the [path key](#path-keys) for that grimoire. |
| `local_path` | The absolute path to the root of the grimoire. `$HOME` stands for the user's home directory. |
| `online_path` | The address the copy on this computer fetches from, or `null` when it has none. It never holds a credential: when a link carries one (`https://<token>@host/...`), git keeps it in the copy's own configuration and this field holds the address without it. `/grm-setup` with another address for a grimoire that is already here changes nothing until the user agrees to switch, or names an access after the link; then the copy and this field change together. |
| `access` | `read` or `edit`; `edit` when the field is absent. A grimoire joined from a link starts as `read`: it is pulled and never changed on this computer. `/grm-setup <link> read` and `/grm-setup <link> edit` set the field outright, also for a grimoire that is already here; without the word, `/grm-setup` sets it when the user says how they will use the grimoire. The commands that change a grimoire ask before they switch it to `edit`; the [grimoire directory guard](../invocations/meta/grimoire_directory_guard.md#before-a-command-changes-the-grimoire) holds the rule, and `grimoire_access` reads and sets the field. |

The installer, `/grm-setup` and `/grm-create` add entries. `/grm-update library` reconciles the
file with the folders under `~/grimoires/`: it reports a grimoire that has no entry, an entry
whose folder is gone, an entry whose path is wrong and a folder that has no `grimoire.json`, and
it writes the corrections when the user confirms. A missing or unreadable library reads as empty.

## Path Keys

A path in a playbook, a page or the routing block starts with a key instead of a location on one
machine.

| Key | Stands for | Example |
|---|---|---|
| `FRAMEWORK_HOME` | The framework checkout: `~/.grimoire/`, or the value of the `FRAMEWORK_HOME` environment variable when it is set | `FRAMEWORK_HOME/docs/installation.md` |
| `GRIMOIRE_ROOT` | The root of the active grimoire | `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT` |
| A library key, such as `cooking-grimoire` | The `local_path` of that grimoire in the library | `cooking-grimoire/chapters/breads/sourdough.md` |

A library key is the name of the grimoire's folder, so `cooking-grimoire` resolves to
`~/grimoires/cooking-grimoire/`. The routing block gives an assistant the first and third keys.
Skill sources write the framework and the grimoire as placeholders that registration replaces
with real paths; the [skill schema](skill_schema.md#source-names) owns those.

## Placeholders in Formulae

A formula marks each value to substitute with a token in double braces. `/grm-create` fills the
grimoire tokens when it scaffolds a grimoire, and `/grm-add` fills the chapter tokens when it
creates a chapter hub. No token remains in a finished file.

| Placeholder | Meaning | Written to | Example value |
|---|---|---|---|
| `{{GRIMOIRE_NAME}}` | Display name | Title and H1 of the root hub; H1 of `README.md` | `Cooking`, `D&D`, `Project Alpha` |
| `{{GRIMOIRE_NAME_LOWER}}` | Display name in lowercase | An alias of the root hub | `cooking`, `dnd`, `project alpha` |
| `{{GRIMOIRE_DOMAIN}}` | Subject area | The read model of the root hub | `cooking`, `tabletop gaming` |
| `{{GRIMOIRE_PURPOSE}}` | Tagline of two to five words | `description` in the manifest; the italic subtitle under the root hub's H1 | `personal cooking knowledge`, `a D&D campaign's lore` |
| `{{GRIMOIRE_PURPOSE_DETAILED}}` | Long description | `README.md` only | `recipes, techniques, equipment and ingredient inventories: the full personal cooking reference` |
| `{{GRIMOIRE_DIRECTORY}}` | Folder name of the grimoire | `name` in the manifest; the filename and an alias of the root hub; `README.md` | `cooking-grimoire`, `dnd-grimoire` |
| `{{GRIMOIRE_REPO_URL}}` | Git URL the grimoire is installed from | The install section of `README.md` | `https://git.example.com/you/cooking-grimoire.git` |
| `{{SKILL_PREFIX}}` | Skill prefix of the grimoire | `skill_prefix` in the manifest; the `grimoire/<prefix>` tag of the root hub; `README.md` | `cook`, `dnd` |
| `{{NAMING}}` | Naming convention | `naming` in the manifest | `snake_case`, `preserve`, `kebab-case` |
| `{{CHAPTER_ROUTES}}` | One route per starter chapter, as full-path wikilinks | The root hub | - |
| `{{CHAPTER_TREE}}` | Directory tree of the starter chapters | `README.md` | - |
| `{{CHAPTER_TITLE}}` | Display title of a chapter | Title and H1 of the chapter hub | `Recipes`, `Onboarding` |
| `{{CHAPTER_NAME}}` | Folder name of a chapter | The alias, the `chapter/<name>` tag and the route paths of the chapter hub | `recipes`, `onboarding` |

A skill source uses `{{SKILL_PREFIX}}` in its `name:` line for the same purpose; the
[skill schema](skill_schema.md#source-names) owns that use.

Each description has one home. The tagline lives in the manifest and under the root hub's H1,
where skill pickers and listings show it. The long description lives in `README.md` only. A page
that needs the long description links to `README.md`, so the same text cannot drift across files.

## Text File Standard

The framework and every grimoire store text the same way.

- UTF-8 without a byte-order mark.
- LF line endings.
- Unicode is allowed where it helps reading: emoji, dashes, arrows, box-drawing characters.
- Mojibake and repair artifacts are not allowed.

`.gitattributes` and `.editorconfig` set the standard, and the encoding validator checks it: run
`/grm-check encoding` on a grimoire and `/grm-dev-validate encoding` on the framework.
