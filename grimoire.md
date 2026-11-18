---
type: hub
title: "Grimoire"
aliases: ["framework-root", "grimoire-framework"]
tags: [framework/root, type/hub, hub/root]
---

# Grimoire

Root hub of the framework. It routes to the framework's documentation, invocations, formulae, skills and rites. For knowledge inside a grimoire, open that grimoire's own root hub.

## Start

- What Grimoire is and the shortest install -> [[README|README]]
- Install, set up a grimoire, everyday commands -> [[docs/getting_started|getting started]]
- Update when the installed commands cannot be trusted -> [[UPDATE|UPDATE]]
- How to contribute -> [[CONTRIBUTING|CONTRIBUTING]]
- What each release changed -> [[CHANGELOG|CHANGELOG]]

## Documentation

**Use**

- Every install route, smoke test, troubleshooting -> [[docs/installation|installation]]
- Command catalog -> [[docs/skills|skills]]
- Storage layers, hub routing, naming and depth -> [[docs/operating_model|operating model]]
- Page frontmatter -> [[docs/page_schema|page schema]]
- Vocabulary, manifest, library file, path keys -> [[docs/reference|reference]]
- Obsidian setup -> [[docs/obsidian|obsidian]]
- VS Code wikilink setup -> [[docs/vscode|vscode]]

**Agents and install**

- Per-agent setup, plugin mode, skill registration -> [[docs/agent_configuration|agent configuration]]
- Supported agents -> [[docs/agent_targets|agent targets]]
- Installer contract -> [[docs/summoning_contract|summoning contract]]

**Contracts and rules**

- Command families, naming, `SKILL.md` structure -> [[docs/skill_schema|skill schema]]
- Public command contract -> [[docs/command_surface|command surface]]
- Mutation profiles of rites -> [[docs/rite_profiles|rite profiles]]
- Rite or playbook -> [[docs/script_vs_ai|script vs ai]]
- Tests that run a playbook with a model -> [[docs/evals|evals]]
- Versioning, compatibility rule, framework scope -> [[docs/governance|governance]]
- How text is worded -> [[docs/writing_standard|writing standard]]
- Release steps -> [[docs/release|release]]
- Open architecture work -> [[docs/architecture_backlog|architecture backlog]]

## Invocations

- Grimoire verbs (`/grm-*`) -> [[invocations/grm/grm|grm]]
- Verbs for maintaining the framework (`/grm-dev-*`) -> [[invocations/dev/dev|dev]]
- Quality reviews behind `/grm-dev-improve` -> [[invocations/dev/quality/quality|quality]]
- Validators, one page each -> [[invocations/validators/validators|validators]]
- Shared fragments -> [[invocations/meta/meta|meta]]

## Formulae

- Overview of the templates -> [[formulae/README|README]]
- Grimoire scaffold -> [[formulae/grimoire/README|README]]
- Root hub -> [[formulae/grimoire/root_hub.formula|root hub.formula]]
- Chapter hub -> [[formulae/chapter_hub.formula|chapter hub.formula]]
- Page -> [[formulae/page.formula|page.formula]]
- Source wrapper -> [[formulae/source.formula|source.formula]]
- Invocation -> [[formulae/invocation.formula|invocation.formula]]
- Scaffold contract: `formulae/grimoire/scaffold_contract.json`
- Publishing templates: `formulae/publish/`

## Skills

- Command sources: `skills/grm/` and `skills/dev/`
- Rendered Claude Code plugins: `plugins/`

## Rites

- Every rite, by name: `FRAMEWORK_HOME/bin/grimoire --list`
- Installer: `rites/summon.sh`
- Validator orchestrator: `rites/validate.py`
- Skill registration: `rites/sync_skills.py`
- Library reconciliation: `rites/sync_library.py`
- Agent routing block: `rites/inject_agent_file.py`
- Generated documentation: `rites/sync_docs.py`
- Plugin render: `rites/build_plugins.py`
- A grimoire's history from git: `rites/recent_changes.py`
- Shared helpers: `rites/_lib.py`
- JSON contracts: `rites/data/`

## Resources

- Branding images: `resources/`
