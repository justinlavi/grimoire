---
type: reference
title: "Writing Standard"
aliases: ["writing-standard", "plain-language"]
tags: [type/reference, framework/docs, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Writing Standard

How everything written for a reader in the framework is worded: documentation, playbooks, skills,
templates, source comments, the text a rite prints and the replies an assistant gives. It adapts
[ISO 24495-1:2023, Plain language, Part 1: Governing principles and guidelines](https://www.iso.org/standard/78907.html)
to this repository. Pages inside a grimoire follow their own [page schema](page_schema.md); this
standard governs the framework.

| Section | Answers |
|---|---|
| [The four principles](#the-four-principles) | What plain language means here and how it is judged |
| [Readers](#readers) | Who reads which text, and which words each one gets |
| [Documentation](#documentation) | How pages, sections and sentences are written |
| [Current state](#current-state) | Where history goes, so everything else describes the present |
| [Playbooks, skills and templates](#playbooks-skills-and-templates) | How text an assistant follows is worded |
| [What the user sees](#what-the-user-sees) | How command descriptions, rite output and replies are worded |
| [Source comments](#source-comments) | What a comment says and how |
| [Review questions](#review-questions) | The check a reviewer applies and how findings are fixed |
| [What this standard leaves alone](#what-this-standard-leaves-alone) | Limits, so it stays usable |

## The four principles

A text is in plain language when its readers, on first reading, get what they need, can find it,
can understand it and can use it. The four principles are judged together; familiar words that leave
out a condition fail the first principle as surely as jargon fails the third.

1. **Relevant: readers get what they need.** Decide who reads the text and what they must do with
   it. Give them every condition, exception and consequence that act needs, and nothing that serves
   the writer instead: history, attribution, narration of the work, or a restatement of what the
   code or the heading already says.
2. **Findable: readers can find what they need.** Put the most important statement first: the rule,
   then its reason, then its exceptions. State each fact at one owner and link to it from elsewhere.
   Name sections after the rule or concept they hold, so a reader scanning headings finds the one
   they want. Use a table for comparable items and a numbered list for an order.
3. **Understandable: readers can understand what they find.** Write in the order people speak: who,
   then the verb, then its object. Use the active voice, one idea per sentence and everyday words.
   Use the [vocabulary](reference.md) and the code's own names, each in one sense; explain a term
   of art once, where it first matters, rather than avoiding it. Give numbers their units and limits
   their scope.
4. **Usable: readers can act on it.** A procedure names its exact commands, their order, the expected
   result and what a failure looks like. A rule names what to do, not only what to avoid. A reader
   should be able to act without the conversation that produced the text, its author or the git
   history at hand. The test is the reader. When one of them stumbles, the text changes, not the
   reader.

## Readers

Every text has one of four readers. Decide which before writing; the reader fixes the words.

| Reader | Reads | Needs |
|---|---|---|
| A person using a grimoire | [Getting started](getting_started.md), a grimoire's README, command descriptions, what a rite prints, what the assistant says | What to type or say, what happens next, what to do when it goes wrong |
| An assistant following a playbook | Invocations, `SKILL.md` files, the routing block, formulae | Exact commands and paths, the order, when a step is done, when to stop and ask |
| A maintainer of the framework | [Contributing](../CONTRIBUTING.md), the contract pages, source comments | The rule, its owner, and the check that enforces it |
| The owner deciding what to do next | Replies and reports | The outcome, the single next action, and what did not run |

Write for the reader without describing them. A page says what it covers and is written plainly
enough for anyone to follow; it does not say who it is for or who it is not for ("for people who are
not engineers"), and it does not sort readers into groups. A grimoire serves one person or many
people equally, so text says "you", "anyone who uses the grimoire" and "everyone else's changes",
not "your team" or "a teammate".

Word choice follows the reader:

- Text for a person using a grimoire says "assistant", "command", "page" and "save". It never needs
  "agent", "routing block", "library", "registration" or git vocabulary; describe the outcome
  ("your assistant is set up to use the cooking grimoire") in place of the mechanism.
- Text for an assistant or a maintainer uses the system's own names from the
  [reference](reference.md), each in one sense: "the framework" is the software, "a grimoire" is a
  knowledge base, "Grimoire" is the product.
- A command is written the way its reader types it. Flat registration names it `/grm-add`; a Claude
  Code plugin install names it `/grimoire:add`. Sources write the flat name, and
  `rites/build_plugins.py` renders the plugin name.

## Documentation

- Open a page with its purpose and reader in one or two sentences, then a contents table when the
  page is long. The [operating model](operating_model.md) owns the structural rules: hubs, routing
  and where a page lives.
- Lead each section with the rule. Reasons follow; exceptions come last and name their condition.
- Prefer a short sentence that states the case over a long one that hedges. Put qualifiers after
  the main point, and keep them short.
- Present comparable things as a table and ordered steps as a numbered list; keep prose for
  reasoning.
- State each fact once, at its owner, and link to it. A hub routes; it does not restate the pages it
  routes to. The contract pages ([command surface](command_surface.md),
  [rite profiles](rite_profiles.md), [agent targets](agent_targets.md),
  [summoning contract](summoning_contract.md)) each describe one JSON contract under `rites/data/`
  and defer to it.
- Name a changing value by its role and link its owner: "the current release" with a link to
  `VERSION`, not a version number.
- Write a path, command, identifier or value exactly as the reader will type or see it, in code
  formatting.

## Current state

Every text describes the framework as it is now. The words "formerly", "previously", "no longer",
"now", "new" and "renamed from" mark a sentence that describes a change instead; rewrite it as a
fact about the present.

History has three owners, and nothing else carries it:

| Record | Holds |
|---|---|
| [`CHANGELOG.md`](../CHANGELOG.md) | What each release changed, and what an existing install or grimoire must do about it |
| Git history | Why and when each change was made |
| [Architecture backlog](architecture_backlog.md) | Work that is still open, and decisions that still bind; a finished item is removed |

## Playbooks, skills and templates

An assistant follows text literally and fills every gap with a guess, and two assistants guess
differently. A gap costs a wrong result or a question the playbook should have answered.

- Write instructions as imperatives addressed to the reader ("Run
  `FRAMEWORK_HOME/bin/grimoire validate --summary`"), one rule per sentence, the rule before its
  reason.
- State each rule once, at its owner, and route to it from everywhere else. A `SKILL.md` is a
  pointer to its invocation; a hub carries routes, not restatements.
- Name the files, commands and sections exactly.
- A template's prompts say what a section must answer, and the finished document replaces every
  prompt with facts.

### Deterministic procedures

A playbook for a recurring task can be followed from start to finish without guessing.
Deterministic means the same inputs lead every assistant through the same decisions to the same
kind of result; it does not mean identical output. A followable playbook states:

1. **Trigger:** when it runs, and which requests go elsewhere.
2. **Inputs:** what it reads, by exact path or command.
3. **Never:** the boundaries it holds, each with the reason breaking it costs more than the task
   saves.
4. **Steps:** in order, each an action with the observable result that ends it (_done when_) and
   the condition that sends a question to the user instead of a guess (_stop when_).
5. **Evidence and checks:** what each claim must cite (a rite's own JSON envelope, never a count the
   assistant made) and which validators must pass.
6. **Outputs:** the exact files, records and reply it leaves.

Where a step is mechanical, cheap to automate and reliable, a rite performs it, and judgment stays
in the steps, bounded by their stop conditions; [script vs AI](script_vs_ai.md) owns that boundary.
The [invocation formula](../formulae/invocation.formula.md) holds this shape. A playbook missing a
part is a finding for [improve documentation](../invocations/dev/quality/improve_documentation.md).

## What the user sees

Three kinds of text reach a person using a grimoire: a command's description in the picker, the
lines a rite prints, and the assistant's reply. All three follow the first row of
[Readers](#readers).

- A skill's `description` says what the command does for the user, in their words, in one
  sentence. Its `when_to_use` lists what the user says or wants, not how the command works. The
  [skill schema](skill_schema.md) owns the fields.
- A rite prints what it did and what is left to do. A failure line names the thing that failed, the
  reason, and the command that fixes it. Machine output (`--format json`) is the contract for
  assistants and stays stable; human output is for reading.
- A reply leads with the outcome and the single next action. It says plainly what ran, what passed,
  what failed and what still has to run, and never rounds a partial run up to a pass. It counts
  things the way the user meets them: the commands they can type in this assistant, not the
  registrations a rite made across assistants.
- A question to the user comes one at a time, with the context needed to answer it and a
  recommendation beside it.

## Source comments

These rules apply in every language (Python, shell, YAML) and to the authored text of
configuration, such as a JSON `description`, `summary` or `reason` field.

- A comment states intent, a constraint, an invariant, a unit, an order or an external reason that
  the code cannot show. It never restates the code; a clearer name comes first.
- The first sentence carries the point. A reader who stops there knows why the code is as it is.
- Write it as a present-tense fact about the system ("A folder holding a framework checkout is
  never a grimoire"), not as a note to a colleague, a question or an instruction to the reader.
- A module docstring states what the rite does, its mutation profile, its usage line and its exit
  codes. A function docstring states what the function represents and the hidden rule a caller
  could break: ownership, failure, ordering, idempotency. Parameters that the signature already
  explains get no line.
- A platform branch states what it does, where it applies and why the other platforms are exempt.
- A number without an obvious source carries its source in the comment.

## Review questions

Ask these of any text before it lands, in the reader's place:

1. Who reads this, and can they act on it without asking anyone?
2. Is the first sentence the point?
3. Does every condition, exception and consequence the act needs appear, and nothing the writer
   needed instead?
4. Is each term used in one sense, and does it match the [reference](reference.md) and the code?
5. Could a table or list replace this prose, or a name replace this comment?
6. Is each fact stated once, at its owner, and linked from here?
7. Does it state what the system is now, not how it came to be?

The reader is the test. A finding is text that a person using a grimoire, an assistant or a
maintainer could not act on, not prose the reviewer would have phrased differently; the reviewer
names the principle it fails, and the author fixes it before the change lands. Typical findings are
a rule missing its condition, exception or consequence; a section that leads away from its rule; a
sentence that hides who acts; a term used in two senses or never explained; and a playbook step
with no expected result or failure. Fix each by rewriting to the failing principle: lead with the
rule, name the actor, add the missing condition or result, or define the term once at its owner.

## What this standard leaves alone

It bans no words, sets no sentence length and adds no readability score; those measure a part of
clarity and miss the rest. It adds no validator: the existing validators keep their scope (links,
frontmatter, format, naming, structure), and review applies the rest with judgment. It changes how
information is written, not which information a page owns; placement and ownership stay with the
[operating model](operating_model.md) and [governance](governance.md).
