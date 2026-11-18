---
type: playbook
title: "Review Framework Architecture"
aliases: ["architecture-review", "framework-architecture-review"]
tags: [framework/invocations, type/playbook, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Review Framework Architecture

Reviews the design of the whole framework: its layout, its names, the owner of each fact, its public commands, and how far an assistant must read before it can act. The validators say whether the tree obeys the known rules; this review judges whether those rules, the layout and the flow of information are still the right design.

## Trigger

Runs as step 3 of `/grm-dev-improve` ([[invocations/dev/improve_framework|improve framework]]). It has no command of its own. It fits these moments:

- Before a framework release.
- After a change to a command family, a manifest, the grimoire scaffold, the installer or a validator.
- When the documentation is correct but the system is harder to explain than it should be.
- When the same maintenance work keeps recurring, which suggests a fact with no single owner.

Requests that go elsewhere:

| Request | Owner |
|---|---|
| Does the tree obey the mechanical rules? | `/grm-dev-validate` |
| Is a rite script safe to run and rerun? | [[invocations/dev/quality/validate_rites|validate rites]] |
| Is a sentence in a machine contract true? | [[invocations/dev/quality/audit_contract_coherence|audit contract coherence]] |
| Is a page worded to the writing standard? | [[invocations/dev/quality/improve_documentation|improve documentation]] |
| Are a grimoire's names and vocabulary sound? | `/grm-check naming` and `/grm-check boundaries` |

## Inputs

Run every command from the framework directory, `FRAMEWORK_HOME`.

| Input | Read it with |
|---|---|
| The file map and the file counts by surface | The two commands below this table |
| The command families | `framework.json`, the `skill_families` object |
| The public commands | `rites/data/command_surface.json` |
| The lane contract, dispatch template and write-scope rule | [[invocations/meta/subagent_lanes|subagent lanes]] |
| The vocabulary | [[docs/reference|reference]] |
| Open deferred work | [[docs/architecture_backlog|architecture backlog]] |

```bash
# The file map: every tracked file, and every untracked file that git does not ignore
git ls-files --cached --others --exclude-standard

# File counts by surface: the number of files under each top-level entry
git ls-files --cached --others --exclude-standard | cut -d/ -f1 | sort | uniq -c
```

The review needs a tree that passes the validators: step 2 of [[invocations/dev/improve_framework|improve framework]] is done.

## Never

- Never let a lane validate, edit or decide. The main context owns validation, the final judgment, the edits and the synthesis; a lane that edits collides with the other lanes.
- Never edit before the lane reports are merged. Two lanes that report the same issue point at one missing owner, and an early edit fixes only a symptom.
- Never apply a change that the deferral rule in [[invocations/dev/improve_framework|improve framework]] covers: more than ten files, a public command name, a file path, release behaviour or generated output.
- Never turn a subjective check into a validator after one observation. Codify a rule only when it is repeated and stable; a brittle validator fails good changes.
- Never merge files to have fewer of them when that makes routing less explicit.
- Never fold the pages about using a grimoire into the pages about maintaining the framework. They serve different tasks.
- Never rewrite working architecture for novelty. A recommendation must improve at least one of: deterministic read paths, the ownership of facts, testable contracts, portability across agents, or the resilience of release and update.
- Never recommend an abstraction ahead of need. It must remove real duplication, reduce repeated judgment, or keep a fact at one owner.
- Never require a hub for a folder of code, configuration, skills, fixtures, assets or hidden tool settings. Hubs belong to folders that route knowledge.

## Steps

### 1. Inventory every surface

List every file with the file-map command in Inputs, then assign each path to a surface. Review the whole repository, not only its Markdown.

| Surface | Review question |
|---|---|
| Root files: the paths in the file map that hold no `/` | Does each one have a single clear job? |
| `docs/` | Is each concept documented in exactly one place, with every other page linking to it? |
| `invocations/` | Do the family folders match `framework.json`, and do hubs route without repeating their leaf pages? |
| `formulae/` | Is each template treated as a contract, with its placeholders documented in one place? |
| `rites/` | Are the scripts deterministic, do they share helpers through `rites/_lib.py`, and is each small enough to audit? |
| `bin/` | Is the launcher the one way a rite is run? |
| `skills/` | Is each skill a short pointer, grouped by command family, with no logic copied from a playbook or a rite? |
| `plugins/` and `.claude-plugin/` | Is every file a render of its source? `FRAMEWORK_HOME/bin/grimoire build_plugins` exits 0 when it is. |
| `tests/` | Do the fixtures cover the invariants that the framework claims to enforce? |
| `.github/` | Does the automation match the release and build documentation? |
| `.obsidian/` and `resources/` | Is each tracked asset intentional, reusable, and documented only where a user needs it? |

A top-level entry that fits no row is a finding: either the table lacks its job, or the entry should not be tracked.

- Done when: every path from the file map belongs to a surface or is recorded as a finding, and you hold the count for each surface.

### 2. Review in lanes

Split the review into the lanes below so that each reviewer goes deep in one area. Dispatch them in parallel when subagents or parallel reviewers are available. Otherwise run the same lanes one after another and keep their notes apart until step 3.

| Lane | Scope | Primary question |
|---|---|---|
| Root and docs | `README.md`, `grimoire.md`, `UPDATE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/*.md` | Are the reader of each page, the owner of each fact, and the read paths for people and assistants obvious? |
| Invocations | `invocations/**/*.md` | Is each playbook short, routable and free of duplication, and clear about when a rite acts and when judgment does? |
| Rites | `rites/*.py`, `rites/templates/`, `rites/data/`, `bin/` | Is each script small enough to audit, deterministic and portable, and do the scripts share helpers well? |
| Formulae and tests | `formulae/**/*`, `tests/**/*` | Do the templates, the managed scaffold files, the fixtures and the tests encode the contracts that the framework claims? |
| Skills and agents | `skills/**/SKILL.md`, `plugins/`, the agent pages under `docs/`, the registration and update flows | Is each skill short, discoverable and portable across agents, and is every generated view current? |
| Release and install | `.github/`, `docs/release.md`, `docs/installation.md`, `rites/summon*` | Is install, update and release behaviour documented once, and does it hold on every platform? |
| Read paths | Every surface | For each common task, what is the shortest useful read path, and where does it force the assistant to infer? |

Give each lane the output contract, the dispatch template and the write-scope rule in [[invocations/meta/subagent_lanes|subagent lanes]]. Tell each lane to look for: a fact that drifted from its owner, a duplicated contract, friction in a read path, a missing test, an unsafe write, and unclear ownership. Send back a report that is prose in place of the contract; a finding without its evidence line cannot be merged.

- Done when: every lane has returned the output contract, or you have run every lane yourself.

### 3. Merge the lane reports

Merge the reports before any edit. Look for:

- The same issue from two surfaces. It usually means a fact has no single owner.
- Recommendations that conflict. They usually mean unclear ownership or an unclear reader.
- Items deferred more than once. They deserve a backlog item or a validator.
- A local edit that resolves findings in several lanes without changing public behaviour.

Record every finding in one matrix:

| Finding ID | Lanes | Owner | Apply, defer or codify | First step |
|---|---|---|---|---|
| `<stable-id>` | `<lanes>` | `<file or subsystem>` | `<decision>` | `<next action>` |

Grade the architecture:

| Grade | Meaning |
|---|---|
| A | Correct, coherent, clean under the validators, and maintainable by someone who already knows it |
| S | Explains itself to a person or an assistant who has never seen it, is driven by contracts, drifts little, is testable in depth, and scales without relying on one person's memory |

- Done when: every lane finding has a row in the matrix and the architecture has a grade.

### 4. Map each repeated fact to its owner

List the facts that the framework repeats most often and name the owner of each. Start from this map and correct it where the repository disagrees:

| Fact | Owner |
|---|---|
| Storage layers and routing | [[docs/operating_model|operating model]] |
| Page frontmatter | [[docs/page_schema|page schema]] |
| Vocabulary, the manifest, the library file | [[docs/reference|reference]] |
| Command families and command naming | [[docs/skill_schema|skill schema]] |
| The command catalog | [[docs/skills|skills]], generated from `skills/<family>/<slug>/SKILL.md` and `rites/data/command_surface.json` |
| The public command contract | `rites/data/command_surface.json`, described by [[docs/command_surface|command surface]] |
| Mutation profiles of rites | `rites/data/rite_profiles.json`, described by [[docs/rite_profiles|rite profiles]] |
| Supported agents | `rites/data/agent_targets.json`, described by [[docs/agent_targets|agent targets]] |
| The agent routing block | `rites/templates/grimoire_block.md` |
| The grimoire scaffold | `formulae/grimoire/` |
| What each validator checks | [[invocations/validators/validators|validators]] |
| The update procedure | [[UPDATE|UPDATE]] |
| Versioning and the release steps | [[docs/governance|governance]] and [[docs/release|release]] |
| What each release changed | `CHANGELOG.md`. It records history, so it never states a current rule; it links to the owner of that rule |
| How text is worded | [[docs/writing_standard|writing standard]] |

Then search for repetition that is likely to drift:

```bash
git grep -nIE "single source|canonical|source of truth|duplicate|drift|generated|do not edit"
git grep -nIE "Unreleased|legacy|deprecated|migration|old|stale|TODO|FIXME" -- docs invocations formulae skills rites README.md grimoire.md CHANGELOG.md CONTRIBUTING.md
```

Decide each repetition:

| Kind | Action |
|---|---|
| A short summary with a link, placed for navigation | Keep it |
| Detail that can drift from its owner | Replace the detail with a link to the owner |
| Structured information copied by hand | Prefer a rite that generates the view |
| A snapshot | Keep it only when the document says it is a release snapshot or an audit record |

- Done when: each repeated fact has one named owner, and each repetition found by the searches has a decision.

### 5. Review naming and boundaries

`/grm-dev-validate naming` enforces casing; [[invocations/validators/validate_naming|validate naming]] owns that check. This step judges meaning, which no validator can: flag a name that is valid in form but does not tell a user or an assistant where a thing lives.

Names:

| Check | Evidence |
|---|---|
| `skills/` holds one folder per command family, and `invocations/` holds the same folders | The keys of `skill_families` in `framework.json` |
| `invocations/` adds only `validators/`, for the pages both families share, and `meta/`, for shared fragments | `ls invocations` |
| `invocations/meta/` holds fragments that other playbooks include, and no operation a user runs | Each file under `invocations/meta/` |
| Authored documents and Python files use snake_case; skill folders use kebab-case | `FRAMEWORK_HOME/bin/grimoire validate naming` exits 0 |
| Each hub is named after its folder and only routes | Each `<folder>/<folder>.md` |
| Each name is specific, uses a term a reader would search for, explains itself, and is short for what it holds | The four dimensions and the grades of the naming review in [[invocations/grm/check|check]] |

Boundaries. System vocabulary (invocation, formula, rite, summoning) names the framework's own layer. The content of a grimoire uses practical vocabulary (templates, scripts, guides). [[docs/reference|reference]] owns the mapping. Every violation inside the framework is critical, because the framework must work for every domain.

1. The scaffold carries no system folder. This command prints nothing:

   ```bash
   find formulae/grimoire -type d \( -name invocations -o -name formulae -o -name rites \)
   ```

2. Text that becomes grimoire content uses practical vocabulary. This command prints nothing:

   ```bash
   grep -rniE 'invoke .*invocation|consult .*formula|perform .*rite|cast .*spell' formulae/grimoire
   ```

   Read the content examples under `docs/` for the same leak. A passage that explains the boundary may name the system terms.

3. Shared text assumes no vendor and no department:

   ```bash
   git grep -nIiE '\b(Slack|Teams|Discord|SharePoint|Confluence|Google Drive|Jira|Bitbucket)\b' -- docs invocations formulae skills README.md
   git grep -nIE '\b(HR|Legal|Marketing|Sales|Finance)\b|\b(VP|Director|Manager) of\b' -- docs invocations formulae skills README.md
   ```

   A hit is a finding unless the page documents an integration with that platform, or holds the term as a search pattern, as `invocations/grm/check.md` and this page do.

4. Examples use only the generic names: `cooking-grimoire`, `dnd-grimoire`, `Alice`, `Bob`, `Project Alpha` and `{your-grimoire}`. A real company, product or person used as an example is a finding.
5. No file serves one domain. [[docs/governance|governance]] lists what belongs in the framework.

- Done when: every row of the names table has a verdict, and each boundary check has a count of violations, each with its file, line, offending text and fix.

### 6. Review the read paths

For each common task, count the files an assistant must read before it can act:

- Install Grimoire.
- Create a grimoire.
- Add a chapter.
- Import a source.
- Validate the framework.
- Improve the framework.
- Check a grimoire.
- Update the framework from a grimoire.
- Register skills.
- Refresh an agent routing block.
- Diagnose a validator failure.

The target is one hub, one playbook and the reference pages that playbook names. Record the shortest useful path for each task in this form:

```text
task -> entry file -> playbook or rite -> reference pages and templates -> validation
```

Flag:

- A hub that summarizes in place of routing.
- A playbook that repeats a long policy section in place of linking to it.
- A skill that holds logic in place of pointing to a playbook or a rite.
- A path that makes the assistant compare two pages to learn the current rule.
- A path that treats a generated view as the text to edit.
- A page for people that reads well and is a poor place to start a task.

The "Skills and agents" and "Invocations" lanes also audit `rites/data/command_surface.json` against the skills, playbooks and rites on disk, along this chain:

```text
command -> skill source -> playbook -> rite or judgment owner ->
guard and preconditions -> mutation and log behaviour -> validation profile ->
generated docs affected
```

Every public command has exactly one playbook in that contract. Skills stay short, hubs route, rites own the deterministic mechanics, and a judgment step is named as judgment. After any change to a public command, run `FRAMEWORK_HOME/bin/grimoire validate skill-refs`.

- Done when: every task in the list has a recorded path, and every public command is traced along the chain.

### 7. Review how the design scales

Look for places where the design gets expensive as the framework grows:

- A list kept by hand that a rite could generate.
- Rites that repeat helper code that `rites/_lib.py` should hold.
- A large script whose user interface, transport and domain logic can be separated.
- Validator diagnostics that are not structured enough for an editor, an issue report or an assistant's repair loop.
- Test fixtures that encode only the successful path.
- Examples that narrow the framework to one domain.
- Release instructions that assume one person's machine.
- A review that depends on one assistant context where lanes and a merge would do.
- A managed scaffold contract repeated across documentation, formulae, validators and tests, where one machine-checkable file would do.
- A cleanup path in skill registration that can delete a skill the user wrote, or one whose prefix collides.
- A rite that writes and has no plan output, no explicit exit codes, or no test against a temporary home.
- Installer behaviour described in the shell script, the Python rites, the documentation or the release notes without deferring to the [[docs/summoning_contract|summoning contract]].

- Done when: each item has a verdict, with a file and line for every instance found.

### 8. Apply or defer

Apply a fix directly when it is local and low in risk:

- Clarify a stale instruction.
- Replace duplicated detail with a link.
- Update a hub route.
- Tighten a scope list.
- Rename a confusing heading without moving a file.

Defer every finding that the deferral rule in [[invocations/dev/improve_framework|improve framework]] covers. For each one, state the benefit, the files and surfaces it affects, and a first step. When the item must outlive this conversation, add it to the [[docs/architecture_backlog|architecture backlog]] with a stable ID, a priority, its owner surfaces, a first slice that can be implemented, and a validation profile. Small local cleanup never goes in the backlog.

- Done when: every row of the matrix from step 3 is applied or deferred.

## Evidence and checks

- Every finding cites a file and a line, in the lane output contract.
- The file counts by surface come from the command in Inputs, never from a count made by reading.
- A boundary count comes from the output of its command in step 5.
- After the fixes of step 8, `FRAMEWORK_HOME/bin/grimoire validate` exits 0. Step 7 of [[invocations/dev/improve_framework|improve framework]] runs it.

## Outputs

Files: the local fixes of step 8, and backlog items for deferred work that must outlive the conversation.

This review's part of the `/grm-dev-improve` reply:

1. The architecture grade before and after.
2. File counts by surface.
3. The lanes run, skipped or run in series, each with its reason.
4. Source-of-truth issues fixed.
5. Repetition removed, and repetition kept on purpose.
6. Naming and boundary findings.
7. The shortest useful read path for each common task.
8. Changes applied.
9. Deferred work, in priority order.
10. Backlog items added or changed.

## Related

- Orchestrator: [[invocations/dev/improve_framework|improve framework]]
- Lane protocol: [[invocations/meta/subagent_lanes|subagent lanes]]
- When a rite acts and when judgment does: [[docs/script_vs_ai|script vs ai]]
- Deferred work: [[docs/architecture_backlog|architecture backlog]]
