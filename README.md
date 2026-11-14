![grimoire_icon](./resources/grimoire_icon_512.png)

![Grimoire](./resources/grimoire_header.png)

**Grimoire builds and maintains grimoires** — structured, AI-navigable knowledge bases the LLM keeps current.

---

Give your AI agent a map, not a maze.

Most knowledge lives in scattered files that AI has to search through, interpolate between, and ultimately guess at. **Grimoires** give AI agents an explicit routing map: a layered hub structure that leads from any question to the exact document that answers it — deterministically, every time. And the LLM owns the maintenance: it imports new sources, updates cross-references, flags stale claims, and keeps the wiki compounding.

**Grimoire** is the framework you install once to build and maintain grimoires for any subject.

---

## Start here

Not an engineer, or joining a team that already has a grimoire? Read [Getting Started](docs/getting_started.md): install in two commands, `/grm-setup`, and the handful of verbs you will use. The rest of this page is the engineering view.

---

## What's a Grimoire?

A grimoire is a structured knowledge base built around a single subject — personal recipes, a tabletop campaign's lore, research notes, project runbooks.

### Deterministic routing through hubs

Every folder has a **hub** — a markdown file named after the folder. Each hop narrows the search; the agent stops at the leaf that answers the question.

```
"What's the cure time for sourdough?"            (shallow - 2 hops)
cooking-grimoire.md -> breads.md -> sourdough.md

"What's the windowpane test for laminated dough?"   (deeper - 4 hops)
cooking-grimoire.md -> techniques.md -> lamination.md -> windowpane_test.md
```

Both paths are deterministic. The structure stays only as deep as the topic warrants. Full rules in [operating model](docs/operating_model.md).

### Storage Layers

A grimoire keeps its wiki and evidence together. **`chapters/`** holds the
LLM-authored wiki; chapter-local **`sources/`** folders hold immutable artifacts
and wrappers beside the material they support; **`inbox/`** is a transient drop
zone for things waiting to be classified; the change history is the git history.
A **`publish/`** layer (present in every grimoire) holds build or publishing
output (a rendered site or exported bundle); it is excluded from grimoire
validation and from the knowledge graph, and pages never cite it. See
[operating model](docs/operating_model.md) for ownership rules and the
validator-enforced contracts.

### Skills

Every grimoire ships its own slash-command skills — commands prefixed by that grimoire:

| Grimoire | Skill | What it does |
|---|---|---|
| `cooking-grimoire` | `/cook-recipe-add` | Creates a new recipe from the grimoire's own template |
| `cooking-grimoire` | `/cook-meal-plan` | Builds a plan from your documented ingredient inventory |
| `dnd-grimoire` | `/dnd-session-recap` | Writes up the latest session from your notes |
| `dnd-grimoire` | `/dnd-npc-lookup` | Routes to the right NPC or location entry for a scene |

Knowledge and skills compound: the better your documentation, the smarter your skills.

---

## The LLM does the maintenance

The framework ships universal operations every grimoire inherits:

- **`/grm-setup`** — join a grimoire from its repository link, turn a folder of notes into one, or start your first one.
- **`/grm-add`** — put knowledge in: write up a topic or save a chat answer as a page or chapter, or hand it a file, a folder, or the inbox to file as cited sources and fold into the wiki.
- **`/grm-save`** — share what you changed: validate, record, bring in teammates' changes, send.
- **`/grm-update`** — bring the framework and every grimoire current; `skills`, `library`, or `agentfile` reconcile one surface.
- **`/grm-check`** — the full health pass (orphans, stale claims, ghost references, contradictions, missing cross-references); `quick` or a validator name for the mechanical subset, `naming` and `boundaries` for the judgment reviews, `fix` to repair wikilinks.
- **`/grm-move`**, **`/grm-remove`** — reshape the wiki and fix every link.
- **`/grm-publish`** — turn the grimoire into a website (GitLab Pages, GitHub Pages, or Cloudflare), audited before anything is exposed.
- **`/grm-help`** — list every grimoire command you can run.

The commands come in two families: `/grm-*` acts on your grimoires and your install; `/grm-dev-*` is for people who maintain the framework itself (its validators, improvement passes, and the full platform catalog). Full rules live in [skill schema](docs/skill_schema.md).

The human curates sources and asks questions. The LLM does the bookkeeping.

---

## What's the framework?

The framework is the software behind every grimoire: Grimoire the program, as distinct from a grimoire you write. You install it once; your grimoires reference it forever.

**The framework provides** (shared across every grimoire):
- `/grm-*` universal grimoire skills and `/grm-dev-*` maintainer skills
- The page schema (`type`, `authority`, `sources`, `last_verified` frontmatter) that makes wikis machine-checkable
- Formula templates for scaffolding new grimoires, chapters, and pages
- Validation rites: structure, naming, format, links, frontmatter, orphans, provenance, security, semantics, and skill-refs; audit playbooks for judgment checks such as boundaries
- Library management automation
- Framework documentation and governance

**Your grimoires contribute**:
- Their `chapters/` (LLM-authored content plus colocated immutable sources)
- Their own `/<skill prefix>-*` skills — actionable, domain-specific commands
- Their `grimoire.json` manifest declaring their identity and skill prefix

When you update the framework, all your grimoires benefit — because they reference it rather than copy from it.

---

## Supported Agents

The framework automatically configures the agents it can safely write to. The current
target matrix lives in [agent targets](docs/agent_targets.md):

- **Claude Code** — the `grimoire` plugin, or full skill registration; the framework's `/grm-*` and `/grm-dev-*` commands plus each grimoire's own commands
- **Codex / ChatGPT** — pointer-only registration from the same source files
- **GitHub Copilot, Cursor, hosted ChatGPT, and other agents** — manual instruction-block setup; see [agent configuration](docs/agent_configuration.md) for setup notes

---

## Install

**Before you start.** Grimoire runs *inside* an AI coding agent — its `/grm-*` commands are typed into that agent, not into a plain terminal. So you need three things first:

1. **A terminal with `git`** — to run the one-line installer below. (No terminal? See [Install without a terminal](docs/installation.md#install-without-a-terminal).)
2. **One supported AI agent, installed and signed in** — [Claude Code](https://docs.claude.com/en/docs/claude-code) or [Codex / ChatGPT CLI](https://developers.openai.com/codex/cli). This is the program you will type `/grm-create` into. See [Supported Agents](#supported-agents).
3. **About five minutes.**

```bash
curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash
```

This installs the framework into `~/.grimoire/`, keeps your grimoires under `~/grimoires/`, and configures the AI agents you already have; it asks before installing any optional dependency and does not run as root. (On Arch-based systems, an accepted dependency prompt may use `sudo pacman` to install `python-pip` first.)

The summoning rite installs the framework, configures your AI agents, and registers the `/grm-*` and `/grm-dev-*` skill sets. If you have existing grimoires hosted on GitHub or GitLab, the rite can discover and clone them too. Otherwise, skip straight to building your first grimoire from scratch once the install finishes.

Detailed installer mode rules live in [summoning contract](docs/summoning_contract.md).

Claude Code users can skip the terminal entirely: `/plugin marketplace add justinlavi/grimoire`, then `/plugin install grimoire@grimoire`, then a new session. Either way, open a new session inside your AI agent (not a plain terminal) and run `/grm-setup` (`/grimoire:setup` from the plugin) to join your team's grimoire from its link or start your first one. (Maintainers: `/grm-dev-help` lists the full platform catalog.)

**Out of date, or something seems wrong?** Update brings the framework and every grimoire in the library back to a current, validated, synchronized state. Two ways to start it:

1. **Run the skill:** `/grm-update` (or `/grm-dev-update` when maintaining the framework directly).
2. **Or tell your AI agent:**

   > Pull the latest framework, then read `~/.grimoire/UPDATE.md` from that checkout and follow its instructions exactly.

Both paths use [UPDATE.md](UPDATE.md) as the canonical source of truth.

**If something stops working** — skills vanished, the agent can't find a grimoire, or it's guessing instead of reading files — open a new session in your agent and run `/grm-update`.

-> [installation](docs/installation.md) - [5-minute smoke test](docs/installation.md#verify-your-install-5-minute-smoke-test) - [troubleshooting](docs/installation.md#troubleshooting)

---

## Layout

```
~/.grimoire/                      # The framework - install once, reference forever
|-- grimoire.md                   # Root hub
|-- UPDATE.md                     # Update & skill-less self-update entry point
|-- invocations/                  # AI-guided workflows
|-- formulae/                     # Templates for hubs, chapters, pages, sources
|-- rites/                        # Python automation scripts
|-- skills/                       # Slash-command source files
|-- docs/                         # Framework documentation (page_schema.md is canonical)
|-- resources/                    # Branding assets
```

```
~/grimoires/                      # Your grimoires
|-- cooking-grimoire/             # A personal grimoire
|   |-- cooking-grimoire.md       # Root hub
|   |-- grimoire.json             # skill_prefix: cook -> /cook-* skills
|   |-- inbox/                    # Drop zone for content awaiting classification
|   |-- chapters/                 # recipes/, techniques/, equipment/, ...
|   |   |-- recipes/recipes.md    # Chapter hub (folder-name convention)
|   |   |-- recipes/sourdough.md  # Leaf
|   |   |-- recipes/sources/      # Recipe source artifacts and wrappers
|   |   |-- techniques/
|   |       |-- techniques.md     # Chapter hub
|   |       |-- lamination/       # Sub-chapter (nests as deep as needed)
|   |           |-- lamination.md # Sub-chapter hub (same convention)
|   |           |-- book_folds.md # Leaf
|   |           |-- windowpane_test.md
|   |           |-- sources/       # Lamination-specific source artifacts
|   |-- publish/                  # Build/publishing output (idle until you publish)
|   |-- skills/                   # Grimoire skills
|
|-- dnd-grimoire/                 # A tabletop-campaign grimoire
|   |-- dnd-grimoire.md           # Root hub
|   |-- grimoire.json             # skill_prefix: dnd -> /dnd-* skills
|   |-- inbox/
|   |-- chapters/                 # campaigns/, characters/, lore/, rules/, ...
|   |-- publish/
|   |-- skills/
|
|-- library.json                  # Local registry of installed grimoires and their paths
```

Create as many grimoires as you need. The framework provides the machinery; each grimoire supplies its own knowledge, skills, and source artifacts.

---

## Documentation

**For everyone**

| | |
|---|---|
| [Update](UPDATE.md) | Skill-less entry point to bring the framework and every grimoire current |
| [Installation](docs/installation.md) | Before you start, one-command setup, install without a terminal, manual setup, smoke test, troubleshooting |
| [Agent Configuration](docs/agent_configuration.md) | Per-agent setup: Claude Code, Codex, Copilot, Cursor |
| [Operating Model](docs/operating_model.md) | Storage layers and routing |
| [Page Schema](docs/page_schema.md) | Frontmatter spec for every page |
| [Obsidian](docs/obsidian.md) | Open as a vault; graph-view color groups |
| [VS Code](docs/vscode.md) | VS Code wikilink setup |
| [Skills](docs/skills.md) | Every command with descriptions |
| [Reference](docs/reference.md) | Plain-language terms, then full terminology and conventions |

**Maintainer reference**

| | |
|---|---|
| [Summoning Contract](docs/summoning_contract.md) | Summoning Rite installer contract: install/update modes, drift detection, fallbacks |
| [Agent Targets](docs/agent_targets.md) | Supported agent target registry |
| [Skill Schema](docs/skill_schema.md) | Command-family naming rules |
| [Script Vs Ai](docs/script_vs_ai.md) | When to use rites vs invocations |
| [Evals](docs/evals.md) | Model-in-the-loop behavioral coverage for invocations |
| [Governance](docs/governance.md) | Maintaining and versioning the framework |
| [Command Surface](docs/command_surface.md) | Public slash-command contract |
| [Rite Profiles](docs/rite_profiles.md) | Mutating-rite plan/apply/append contract |
| [Release](docs/release.md) | Release and publish workflow |
| [Architecture Backlog](docs/architecture_backlog.md) | Deferred architecture work queue |
| [Contributing](CONTRIBUTING.md) | How to contribute to the framework |
| [Grimoire hub](grimoire.md) | Navigate everything |
