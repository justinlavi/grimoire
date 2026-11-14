---
type: reference
title: "Grimoire Reference Guide"
aliases: ["terminology", "glossary", "reference"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-05-12
---

# Grimoire Reference Guide

**Terminology, symbols, and conventions for Grimoire**

---

## In plain language

New here? These are the only terms you need, and you never have to say them back to use the system.

| Term | Plain meaning | Do you touch it? |
|---|---|---|
| Grimoire | A focused knowledge base (a wiki) on one subject. | Yes — it is your content. |
| The framework | Grimoire the program: the shared software that powers every grimoire. | Rarely — it just runs. |
| Hub | The index / table-of-contents page for a folder. | The AI keeps it current. |
| Page | One knowledge document (a Markdown file). | Yes — you read and write these. |
| Frontmatter | The labeled `---` block at the top of a page. | The AI maintains it. |
| Rite | A Python automation script the framework runs for you. | No — you never edit it. |
| Invocation | A checklist the AI follows to carry out an operation. | No. |
| Summoning rite | The one-line installer. | Once, to install. |
| Skill | A slash command you type into your AI agent, like `/grm-add`. | Yes — you run these. |

The rest of this page documents the playful "magical" names the framework uses for these concepts. You can keep using the plain words above.

---

## ⚡ The Magical Boundary ⚡

**IMPORTANT**: the framework and grimoires have two vocabulary layers with different jobs:

### 🔮 The System (Context) = Magical
When **using** the framework or talking about the framework layer:
- Use playful, magical language
- "Perform an invocation", "consult your grimoire", "summon the framework"
- AI agents may use the magical vocabulary when operating framework-managed workflows

### 📝 The Content = Practical
When **creating knowledge** inside chapters:
- Use natural, subject-specific terminology
- Personal / hobby: `recipes/`, `techniques/`, `equipment/`, `notes/`
- Operations: `policies/`, `guides/`, `checklists/`, `runbooks/`
- Engineering: `templates/`, `scripts/`, `snippets/`, `configs/`
- **Never** create `invocations/`, `formulae/`, or `rites/` in grimoires

**Why?** Discoverability and clarity. A cook searches for "sourdough recipe" not "bread formula".

### AI Agents
- **Magical language** for framework-managed operations: "performing invocation", "consulting grimoire", "routing to chapter"
- **Practical language** for content creation: standard domain terminology, real folder names (`templates/`, `scripts/`), no magical terms in chapter content
- The magic is in the **system**, not the **content**

---

## Core Concepts

| Concept | Magical Term | Directory/File |
|--------|-------------|---------------|
| Universal foundation | **The framework** | Standalone at `~/.grimoire/`, referenced via `FRAMEWORK_HOME` |
| Knowledge base instance | **Grimoire** | grimoire repository root |
| Grimoire identity | **Manifest** | `grimoire.json` at grimoire root (declares name, skill prefix, description) |
| Knowledge category | **Chapter** | `chapters/` |
| Sub-category | **Sub-chapter** | `chapters/{name}/{sub}/` |
| Knowledge document | **Page** | `*.md` files |
| Executable workflow | **Invocation** | `invocations/grm/*.md` and `invocations/dev/*.md` |
| Template/blueprint | **Formula** | `formulae/*.md` (the framework only) |
| Automation script | **Rite** | `rites/*.py` (the framework only) |

**Note**: Invocations, Formulae, and Rites exist **only in the framework**. Grimoires use practical terminology.

---

## Authority Models

Every page declares one of `external`, `grimoire`, or `hybrid` to indicate where truth lives. Full table, required-fields matrix, and rules of thumb in [page schema](page_schema.md#authority-models).

Page template: `FRAMEWORK_HOME/formulae/page.formula.md`

---

## Skills

The current framework skill catalog lives in **[skills](skills.md)** (auto-generated from each framework `skills/<family>/<slug>/SKILL.md`). To enumerate every skill installed for an agent — the framework plus every grimoire — invoke `/grm-dev-help`.

Skill names follow command families: the framework ships `grm-*` for universal grimoire operations and `grm-dev-*` for maintaining the framework itself. Each grimoire ships `{skill prefix}-*` from its own manifest. The canonical schema is [skill schema](skill_schema.md).

Source `SKILL.md` files use `name: {{SKILL_PREFIX}}-<registered-slug>` and the registration rite substitutes the command-family or grimoire skill prefix at install time. Skill targets and copy modes are defined in [agent targets](agent_targets.md).

---

## Local Library

The framework uses one local library: `~/grimoires/library.json`. It is a **pure registry**: it records *where* installed grimoires live, nothing else. Each grimoire's identity (name, skill prefix, description) lives in its own [manifest](#grimoire-manifest).

`~/grimoires/library.json`, created by the summoning rite or `/grm-dev-update library`. Lists grimoires the user has cloned and where they live on disk.

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

Fields:
- `local_path` — absolute filesystem path to the grimoire root (supports `$HOME`).
- `online_path` — git clone URL; set to `null` if not applicable.

To add a grimoire, run `/grm-dev-update library` after cloning into `~/grimoires/`. To detect drift (stale entries, missing grimoires, unmanaged directories), run the same skill in dry-run mode.

---

## Grimoire Manifest

Every grimoire declares its identity in a `grimoire.json` file at its repository root:

```json
{
  "name": "cooking-grimoire",
  "skill_prefix": "cook",
  "description": "Personal cooking knowledge: recipes, techniques, equipment",
  "naming": "snake_case"
}
```

Fields:
- `name` — canonical grimoire name; should match the library key.
- `skill_prefix` — short lowercase slug (`^[a-z][a-z0-9]*$`) used as the skill prefix. Required if the grimoire has a `skills/` directory.
- `description` — one-line description.
- `naming` — optional; the file and folder naming convention agents apply to new material (`snake_case` when absent, `preserve` to keep imported material's own casing, or another named style such as `kebab-case`). Any casing is valid; see [operating model](operating_model.md#naming-and-depth-conventions).

The framework is not a grimoire and uses `framework.json` instead:

```json
{
  "name": "grimoire",
  "kind": "framework",
  "skill_prefix": "grm",
  "skill_families": {
    "grm": {"skill_prefix": "grm", "path": "skills/grm", "slug_prefix": "", "plugin": "grimoire"},
    "dev": {"skill_prefix": "grm", "path": "skills/dev", "slug_prefix": "dev", "plugin": "grimoire-dev"}
  },
  "description": "Framework for creating and maintaining grimoires"
}
```

`skill_prefix` is the default prefix for a family that declares none. `skill_families` defines the command families the framework ships: each names its source folder, an optional `slug_prefix` placed between the prefix and the verb, and the Claude Code `plugin` that carries it.

**Why not in the library?** The grimoire owns its own identity. A cloned grimoire knows its skill prefix without needing a library entry, the registration rite reads skill prefix directly from the grimoire, and there is no way for library and grimoire to drift out of sync.

When creating a new grimoire, `/grm-create` prompts for the skill prefix and writes `grimoire.json` as part of scaffolding.

---

## Path Reference Convention

**IMPORTANT**: When referencing Grimoire paths, use named keys defined in the agent instruction file:

| Key | Purpose | Example |
|----|--------|--------|
| `FRAMEWORK_HOME` | Reference the framework from anywhere | `FRAMEWORK_HOME/docs/installation.md` |
| `{domain}-grimoire` | Reference a specific grimoire | `cooking-grimoire/chapters/breads/sourdough.md` |

**Why?** Library keys match the actual folder slug. `cooking-grimoire` resolves to `~/grimoires/cooking-grimoire/`. `FRAMEWORK_HOME` is the exception — it names the framework, not a grimoire.

**In automatic agent instruction files**, the library maps keys to actual filesystem paths:
```markdown
**Library**: `~/grimoires/library.json`

**Framework key**: `FRAMEWORK_HOME` = path to the framework installation (`~/.grimoire/` by default)
```

---

## Placeholders in Formulae

When creating new grimoires, use these placeholders in formula templates:

| Placeholder | Description | Example value |
|------------|------------|--------------|
| `{{GRIMOIRE_NAME}}` | Display name; brand only - used in the root-hub H1 | `Cooking`, `D&D`, `Project Alpha` |
| `{{GRIMOIRE_NAME_LOWER}}` | Lowercase display name for aliases and prose | `cooking`, `dnd`, `project alpha` |
| `{{GRIMOIRE_DOMAIN}}` | Subject area / category | `cooking`, `tabletop gaming` |
| `{{GRIMOIRE_PURPOSE}}` | Short tagline, 2–5 words; used in the manifest `description` and as an italic subtitle in the root hub | `personal cooking knowledge`, `a D&D campaign's lore`, `Project Alpha knowledge` |
| `{{GRIMOIRE_PURPOSE_DETAILED}}` | Long-form description; lives **only** in `README.md`; never duplicated to manifest or hub | `recipes, techniques, equipment, and ingredient inventories — the full personal cooking reference` |
| `{{GRIMOIRE_DIRECTORY}}` | Filesystem name | `cooking-grimoire`, `dnd-grimoire` |
| `{{GRIMOIRE_REPO_URL}}` | Canonical git URL for installing this grimoire | `https://git.example.com/you/cooking-grimoire.git` |
| `{{SKILL_PREFIX}}` | Short slug for skill prefix | `cook`, `dnd` |
| `{{NAMING}}` | File and folder naming convention recorded in the manifest | `snake_case` (default), `preserve`, `kebab-case` |
| `{{CHAPTER_ROUTES}}` | Generated routing pointers (filled by create_grimoire) | - |
| `{{CHAPTER_LIST}}` | List of chapters with descriptions | - |
| `{{CHAPTER_TREE}}` | Directory tree of chapters | - |
| `{{CHAPTER_TITLE}}` | Chapter hub display title (H1 and frontmatter title) | `Recipes`, `Onboarding` |
| `{{CHAPTER_NAME}}` | Chapter folder slug used in tags and routing paths | `recipes`, `onboarding` |
| `{{EXAMPLE_CHAPTER}}` | One example chapter name | `recipes`, `onboarding` |

**Description-duplication policy.** Three description-shaped placeholders, each with a single canonical home:

- `GRIMOIRE_NAME` — brand only, used in the root-hub H1 and as the manifest `name` field.
- `GRIMOIRE_PURPOSE` — short tagline, 2–5 words. Lives in the manifest `description` and as an italic subtitle under the root hub's H1. Surfaces in skill pickers, library listings, and at-a-glance scans.
- `GRIMOIRE_PURPOSE_DETAILED` — long-form paragraph. Lives in `README.md` only; never duplicated to the manifest, the root hub, the log, or any skill file. If another page needs the description, link to README.

This prevents the same description from drifting across three files while still letting the manifest and hub carry a one-line tagline that's useful at a glance.

---

## Text File Standard

The framework and every grimoire use the same repository text standard:

- UTF-8 without BOM.
- LF line endings.
- Unicode is allowed when useful for readability, including emoji, em dashes, arrows, and box-drawing characters.
- Mojibake and repair artifacts are not allowed.

This is enforced by `.gitattributes`, `.editorconfig`, `/grm-dev-validate encoding`, and `/grm-check encoding`.

---
