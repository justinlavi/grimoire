---
type: reference
title: "Governance"
aliases: ["governance", "release-policy"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# Governance

How the framework is maintained, versioned and changed, so that every grimoire that references it
stays valid. It covers maintaining the framework; everyday use of a grimoire needs none of it.

| Section | Answers |
|---|---|
| [Core Principle](#core-principle) | What the framework is to a grimoire |
| [Framework Maintainer](#framework-maintainer) | What maintaining the framework involves, and who does it |
| [Autonomous Maintainer](#autonomous-maintainer) | What an assistant may change without approval, with one confirmation, or never |
| [What Belongs in the Framework](#what-belongs-in-the-framework) | Which content the framework holds and which a grimoire holds |
| [Versioning](#versioning) | How a change maps to PATCH, MINOR or MAJOR |
| [Change Workflow](#change-workflow) | The steps for each kind of bump |
| [Deprecation Policy](#deprecation-policy) | How content is removed |
| [Quality Standards](#quality-standards) | What every framework file must meet |
| [Grimoire Responsibilities](#grimoire-responsibilities) | What a grimoire owes the framework |
| [Security](#security) | What never enters the repository |

## Core Principle

The framework is the single source of truth for the system. A grimoire references the framework
and never copies it. A change to the framework therefore reaches every grimoire that points at the
same install, and a change that breaks grimoires follows the
[deprecation policy](#deprecation-policy) so that they can adapt.

## Framework Maintainer

Whoever owns a fork of the framework maintains it. A fork may be one person's or shared; when it
is shared, the people who contribute to it agree on who maintains it.

Maintaining the framework means:

- Keeping the invocations, formulae, rites and documentation current.
- Reviewing and approving changes to the framework.
- Cutting versioned releases and keeping `CHANGELOG.md`.
- Providing a migration guide for every breaking change.
- Triaging feedback from anyone who uses a grimoire, and acting on it.

The role can be handed over. Record the handover in `CHANGELOG.md`.

## Autonomous Maintainer

An assistant may maintain the framework without prior approval when a change passes the gate
below. The framework makes that safe by letting the assistant verify its own work: validators
emit diagnostics, mutating rites emit a result envelope with `--format json`, and the
[contract-coherence audit](../invocations/dev/quality/audit_contract_coherence.md) compares the
contracts with the code.

Autonomous means that no approval comes first. It never means invisible. Every unattended action
is recorded: a change to the framework in `CHANGELOG.md` under `[Unreleased]`, and an operation
on a grimoire in that grimoire's git history.

### The unattended-safe gate

An assistant acts unattended only when all four conditions hold.

1. **Deterministic.** The change is mechanical: a fix with one correct form. A fix to contract
   prose also qualifies when the contract-coherence audit flagged it, the claim about the code
   can be verified, and the edit touches contract data only. A finding that the code is wrong is
   deferred. A content change that needs a judgment call is not deterministic.
2. **Verifiable.** Afterwards `python rites/validate.py` exits with code 0, or the rite's
   `--format json` envelope reports the expected `status` and `mutations`.
3. **Non-destructive.** The change deletes no content that the framework does not own, and git
   can reverse it.
4. **Not on the list under [Human sign-off required](#human-sign-off-required).**

When any condition fails, the assistant proposes the change and does not apply it. It asks for
one confirmation, as `/grm-check` does, or hands the change to the person who maintains the
framework.

### Unattended

| Action | How | Verified by |
|---|---|---|
| Run the validator suite | `/grm-dev-validate`, or `python rites/validate.py` | Exit code 0 |
| Apply a mechanical fix: a broken link the rite located, format, frontmatter, encoding, `snake_case` | A `/grm-dev-validate` finding, then a direct edit | The validator, run again, exits with code 0 |
| Repair unambiguous wikilinks | `/grm-check fix` | The envelope's `status` is `ok`. An ambiguous link is reported, never guessed. |
| Regenerate the generated catalog | `python rites/sync_docs.py --apply` | `python rites/sync_docs.py` reports that `docs/skills.md` is up to date |
| Correct contract prose that is wrong | The contract-coherence audit | The probe that found it, and a validator pass |
| Add to the changelog | Edit `CHANGELOG.md` under `[Unreleased]` | - |

### Propose, then apply on one confirmation

These changes are reversible, but they need judgment or they write outside the repository.

- Wiring an orphan page, standardizing terminology, promoting a page, merging duplicates.
- Any change that touches more than ten files.
- Reconciling the library, or registering skills into agent directories under the user's home:
  `/grm-update`, `/grm-update library` and `/grm-update skills`.

A command in this tier stays open to automatic invocation. The confirmation gates the apply
step, not whether an assistant may offer the command.

### Human sign-off required

- **A version bump or a release tag.** The [Compatibility Rule](#the-compatibility-rule) decides
  the number across `VERSION`, `CHANGELOG.md` and the git tag.
- **A breaking change or a deprecation.** No grimoire breaks without a
  [deprecation cycle](#deprecation-policy).
- **Deleting or removing content,** changing the public command surface, or any forced overwrite.
- **Running the installer against a real environment.**
- **Transferring the maintainer role.**

### In every tier

- **Never delete content outside a managed namespace.** Skill cleanup touches only directories
  under a managed prefix: `grm-`, or the `skill_prefix` of a grimoire. The
  [rite profiles](rite_profiles.md#rules) own the rule.
- **Leave the tree green.** A pass that cannot bring `python rites/validate.py` back to exit
  code 0 reverts its change and reports the problem.
- **Record what was done.** Unattended does not mean unlogged.

The skills carry part of this policy. A skill that is destructive or that changes the framework
sets `disable-model-invocation: true`, so an assistant does not run it on its own; the
[skill schema](skill_schema.md#skillmd-structure) owns the field. The
[command surface](command_surface.md) and the [rite profiles](rite_profiles.md) record how every
command and rite writes.

## What Belongs in the Framework

Content belongs in the framework when it applies to every grimoire that references it.

| In the framework | Examples |
|---|---|
| Documentation | README, installation, operating model, reference, governance |
| Invocations | Grimoire operations in `invocations/grm/`, framework maintenance in `invocations/dev/`, validator pages in `invocations/validators/`, shared fragments in `invocations/meta/` |
| Formulae | The grimoire scaffold, chapter hubs, pages, source wrappers, the invocation template, the publishing files |
| Rites | Validation, registration, library sync, install, update |
| Resources | Branding assets |

Content that belongs to one subject stays in its grimoire, under `chapters/` or `skills/`.

| Not in the framework | Where it goes |
|---|---|
| A chapter about one subject: recipes, campaign lore, the structure of a codebase | `<grimoire>/chapters/` |
| A skill for one subject | `<grimoire>/skills/`, named with the grimoire's skill prefix |
| A rite that one grimoire uses | That grimoire |
| Real-world data: names of companies, projects, employees or customers | The grimoire that is about them. Credentials go in neither; see [Security](#security). |
| The storage layers of a grimoire: `chapters/`, `sources/`, `inbox/`, `publish/` | Each grimoire. The framework holds only their templates, under `formulae/grimoire/`. The [operating model](operating_model.md#storage-layers) owns the layers. |

## Versioning

The framework follows [Semantic Versioning 2.0.0](https://semver.org/), `MAJOR.MINOR.PATCH`. It
generates grimoires, so a change is judged by its effect on grimoires: the ones on disk, and the
ones an assistant will create. The size or ambition of the change does not enter into it.

### The Compatibility Rule

Compatibility decides the bump. Answer two questions, in order.

1. **Do existing grimoires stay valid?** Does any grimoire on disk break, fail validation, or
   need a migration by hand that self-healing cannot perform?
2. **Does future generation change?** Does the framework generate, validate or guide grimoires
   differently from here on?

| Existing grimoires | Future generation | Bump |
|---|---|---|
| Stay valid, with no migration | Unchanged | **PATCH** |
| Stay valid, with no migration | Improves or changes | **MINOR** |
| Would break, and the framework can heal them automatically: a rite, `/grm-update`, or a documented step in [Update](../UPDATE.md) | Either | **MINOR**, and the release ships the heal |
| Break, and need a migration by hand, with judgment, that self-healing cannot perform | Either | **MAJOR** |

Three points follow from the rule.

- **"Existing grimoires" means every grimoire the change could affect,** not only the ones you
  can see. Compatibility is about the outcome of validation: a grimoire that validated yesterday
  and fails today is broken, even when no file or schema changed. A fork that others use often
  cannot list the private grimoires that depend on it. When that is so, treat a check that starts
  to enforce as potentially breaking: ship it as a warning first, or choose MAJOR.
- **Many minors do not add up to a major.** A run of compatible releases, `v1.0.0` to `v1.17.0`,
  can leave the framework far more capable and still be `1.x`, as long as every existing grimoire
  stayed valid throughout. A major version marks one event: a compatibility break. Announce a
  large step in `CHANGELOG.md` and the release notes, never by raising MAJOR.
- **A smarter future grimoire is usually MINOR.** Better formulae, improved standards, better
  guidance for assistants, and validators that are added or made stricter without failing any
  existing grimoire all change future grimoires and leave existing ones valid.

### Self-healing and the compatibility line

A grimoire is brought current by the framework's update path, not by hand: the repair rites,
`/grm-update`, and the [Update](../UPDATE.md) procedure for an install whose skills are too old
to run. The update pulls every grimoire in the library first and heals only those it confirmed
current, so a grimoire whose fix already exists upstream receives that fix instead of a local
copy of it.

That is why "migration" in the table means migration by hand.

- **An automatic, deterministic transition is not a manual migration.** Syncing the managed
  scaffold again, refreshing the update block in a README and repairing wikilinks are examples.
  When every existing grimoire can be healed with no human judgment, the change is MINOR, even
  though files in the grimoire change.
- **The author of the change ships the heal with it.** A change that would otherwise break
  grimoires lands together with the heal: the update rite's mechanical pass, the grimoire
  formula, or both. A heal that has not shipped does not count, and the change is MAJOR.
- **A change is MAJOR only when the heal needs human judgment:** content or meaning that a rite
  cannot supply. When the heal can be automated, automate it and ship MINOR.
- **Make the update rite reach the changed state.** Whenever a change alters what a current grimoire
  must look like, extend the mechanical heal and the formula so that any grimoire reaches that
  state from the source tree alone, even when its installed skills are too old to run. Record
  what changed in [the changelog](../CHANGELOG.md), not as steps in the update procedure.

### What each bump means for the framework

| Bump | Meaning | Changes of this kind |
|---|---|---|
| **PATCH** (`v1.0.0` to `v1.0.1`) | No change in behavior. Neither existing nor future grimoires change in substance. | Typo and wording fixes, repairs to broken links, small clarifications. A fix to a bug in a validator or rite that restores the intended behavior without changing the pass or fail result of any existing grimoire. |
| **MINOR** (`v1.0.0` to `v1.1.0`) | Existing grimoires stay valid. Future grimoires improve or change. | A formula, an optional skill or a validator that is added. A stricter check that every grimoire on disk still passes. Improved standards, better guidance, a sharper convention that grimoires created afterwards follow. |
| **MAJOR** (`v1.0.0` to `v2.0.0`) | A compatibility break. Existing grimoires become invalid, or must be migrated by hand because self-healing cannot bring them current. | Removing a concept, renaming a required file, or changing a schema (page frontmatter, the manifest, a contract) so that existing grimoires fail validation and no rite can migrate them. Any change that forces a hand edit with judgment. A validator or check, added or made stricter, that makes any existing grimoire fail. Removing a deprecated capability. |

Three cases are easy to misjudge.

- **A bug fix that flips a result is MAJOR.** A fix that makes the validator start failing a
  grimoire it never truly evaluated, for example after a crash is repaired, is a break.
- **An optional addition is MINOR.** The manifest's `naming` field is the model: a grimoire
  without the field stays valid, because an absent field means `snake_case`, and a grimoire
  created afterwards records its convention.
- **Tighten validation in two steps.** To add a stricter check without a break, ship it as a
  warning in a MINOR release and enforce it in the next MAJOR. That is the deprecation cycle
  applied to validation.

### Before you change the version

A version bump needs human sign-off. Before anyone, person or assistant, touches `VERSION`,
`CHANGELOG.md` or the release notes, they reason the bump through.

1. Look at what the change does to the framework's behavior, not at its size.
2. Answer the two questions of the [Compatibility Rule](#the-compatibility-rule) and read the
   bump from its table.
3. When the choice is between MINOR and MAJOR, decide by how the heal happens. No migration, or a
   heal the framework performs through the update rite or the formula, is MINOR. A migration that
   needs human judgment is MAJOR.

The version is recorded in four places, and they agree.

| Place | Role |
|---|---|
| `VERSION` | The source of truth |
| `version` in `pyproject.toml` | The same number; `tests/test_version_consistency.py` fails when they differ |
| `CHANGELOG.md` | One entry for each release |
| Git tag | `vX.Y.Z` |

## Change Workflow

Decide the bump with the [Compatibility Rule](#the-compatibility-rule), then follow the steps for
that bump. The [release guide](release.md) owns the steps that tag and publish a release.

### Patch or minor

1. Make the change. Run `/grm-dev-validate`, or `python rites/validate.py`.
2. Update `CHANGELOG.md`. Until a version has its first tag, edit that version's entry so that it
   describes the release as it stands. Once a version is tagged, collect changes under
   `[Unreleased]` until the next release entry is cut.
3. Commit, with the prefix `fix:` for a patch and `feat:` for a minor.
4. Tag and push when the release is cut.

### Major

1. Document the proposed change and the migration path before implementing it.
2. Mark whatever will be removed as deprecated for at least one minor release first.
3. Implement the change. Run the full validator suite.
4. Add the `CHANGELOG.md` entry under the heading `### Removed (breaking)`, with the migration
   recipe in the entry.
5. When the user must act, for example by running a migration rite, state the exact command.
6. Commit with the prefix `BREAKING:`, then tag and push.

## Deprecation Policy

Content leaves the framework in three steps.

1. **Mark it deprecated** in a minor release. Add a note at the top of the file, or a
   `Deprecated:` row in the relevant table, that names the replacement and the version planned
   for removal.
2. **Announce it** in the `CHANGELOG.md` entry, under `### Deprecated`, with the migration path.
3. **Remove it** in a major release. Delete the content, update every reference, and document
   the removal under `### Removed (breaking)`.

At least one minor release separates the deprecation from the removal.

## Quality Standards

Every framework file:

- Applies to every grimoire; see [What Belongs in the Framework](#what-belongs-in-the-framework).
- Uses generic names in examples: `cooking-grimoire`, `dnd-grimoire`, `Domain A`,
  `Project Alpha`, `Alice` and `Bob`. A real product, company or person is named only where the
  file documents an actual integration.
- Uses paths relative to the repository. A skill file writes `{{FRAMEWORK_PATH}}` and
  `{{GRIMOIRE_PATH}}`, which registration resolves.
- Follows the [text file standard](reference.md#text-file-standard).
- Passes the full validator suite, `/grm-dev-validate`, before it is committed.

No framework file:

- Holds a hardcoded user path or a value specific to one machine.
- Holds content from a real grimoire: chapter text, policy text, recipes.
- Holds a secret, a credential, personal data or proprietary data.
- Breaks existing grimoires without a deprecation cycle.

## Grimoire Responsibilities

Each grimoire:

1. **Owns its content:** its chapters, skills and manifest. It adds pages with `/grm-add`.
2. **Stays in step with the framework.** Run `/grm-update` regularly, and `/grm-check quick`
   after it.
3. **Reports problems in the framework:** a broken invocation, a bug in a formula, a validator
   that flags a correct page.

A grimoire never:

- Copies framework files into its own repository. It references them.
- Edits framework files. It proposes the change to whoever maintains the fork it uses.
- Creates an `invocations/`, `formulae/` or `rites/` folder. Those names are reserved for the
  framework; the [reference](reference.md#the-magical-boundary) owns the rule.
- Ignores the announcement of a breaking change. Run `/grm-check quick` again after a major
  version of the framework.

## Security

The framework is fit to be public. The same rules apply whether a fork lives on a public host, a
private one or a host inside a company.

- Never commit a credential, a token, an API key, personal data, customer data or proprietary
  information to the framework.
- When a page must say where sensitive data lives, name the external system and the location,
  and never include the data:

  ```markdown
  ## Primary Sources
  - Production credentials: secrets manager → path/to/secret (auth required)
  - User contact data: CRM / identity provider (auth required)
  ```

- The git host of a fork enforces who can read and write the repository. Whoever maintains the
  fork decides who can merge.
