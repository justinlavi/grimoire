---
type: playbook
title: "Improve Documentation"
aliases: ["improve-documentation", "doc-quality"]
tags: [framework/invocations, type/playbook, scope/quality]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Improve Framework Documentation

Applies the [[docs/writing_standard|writing standard]] to a set of framework pages. It searches for facts stated twice, asks the standard's seven review questions of each page, and checks that every playbook has its six parts.

## Trigger

Runs as step 6 of `/grm-dev-improve` ([[invocations/dev/improve_framework|improve framework]]). It has no command of its own. It also fits before a framework release, after bulk changes to documentation or features, and when a page reads as repetitive, unclear or hard to navigate.

Requests that go elsewhere:

| Request | Owner |
|---|---|
| Check links, frontmatter, format, naming or structure | `/grm-dev-validate` ([[invocations/validators/validators|validators]]) |
| Review the docstrings and the printed output of a rite | [[invocations/dev/quality/validate_rites|validate rites]] |
| Decide which page owns a fact, or move a page | [[invocations/dev/quality/review_architecture|review architecture]] |
| Review the pages of a grimoire | `/grm-check` |

## Inputs

Run every command from the framework directory, `FRAMEWORK_HOME`.

| Input | Read it with |
|---|---|
| The standard | `docs/writing_standard.md`, in full, before step 1. It owns the principles, the readers, the review questions and how a finding is fixed |
| The pages in scope | The pages the user names. With none named, every authored page: `git ls-files --cached --others --exclude-standard "*.md" ":!plugins" ":!docs/skills.md"` |
| The playbooks | `grep -rl "^type: playbook" invocations` |
| The playbook shape | `formulae/invocation.formula.md` |
| The owner of each repeated fact | The map from step 4 of [[invocations/dev/quality/review_architecture|review architecture]], when that review ran in this pass |

`plugins/` and `docs/skills.md` are generated and out of scope: a finding there is fixed in the source they are rendered from.

## Never

- Never restate the standard, in a page or in a finding. Name the principle or the question that the text fails and link to the standard; a second copy of a rule drifts from the first.
- Never report text that you would only have phrased differently. A finding is text that its reader could not act on.
- Never remove a duplicate before you have named the owner of the fact. Deleting the owner's copy leaves the fact nowhere.
- Never edit a generated file. Change its source and run its rite: `FRAMEWORK_HOME/bin/grimoire sync_docs --apply` for `docs/skills.md`.
- Never add a validator check for a rule you have seen broken fewer than three times. This review is judgment; a rule earns a mechanical check only by recurring.
- Never apply a change that the deferral rule in [[invocations/dev/improve_framework|improve framework]] covers, such as a rewrite across more than ten files.

## Steps

### 1. Fix the scope

List the pages in scope with the command in Inputs, or take the pages the user named.

- Done when: you hold the list of pages and have read the standard in full.

### 2. Search for facts stated twice

The same fact in two places is a maintenance defect. Common forms: a command list, a file tree or a schema example copied across pages; one concept explained twice in different words; one block of text, such as an instruction template or a code snippet, in several files.

```bash
# Lines of 40 characters or more that appear in more than one authored page
find . -name "*.md" -not -path "./formulae/*" -not -path "./plugins/*" -exec cat {} \; \
  | grep -v '^#' | grep -E '.{40,}' | sort | uniq -cd | sort -rn | head -20

# The same heading in more than one page
grep -rh "^## " --include="*.md" --exclude-dir=plugins . | sort | uniq -cd | sort -rn | head -20
```

Decide each hit:

| Kind | Action |
|---|---|
| Intended: two readers need the same information | Keep both, and link them so that an edit to one reaches the other |
| Drift risk: the data has one source | Move it to the owner and link from the rest, or generate the view with a rite. `rites/sync_docs.py` is the pattern |
| Stale: one copy is wrong | Fix or delete the wrong copy |

- Done when: every hit that falls in scope has a decision.

### 3. Ask the seven review questions of each page

For each page in scope, name its reader from the "Readers" table of the standard. Then ask the seven questions of "Review questions" in the standard, in order, in that reader's place. The table lists what each question most often finds in this repository; it adds to the standard and does not replace it.

| Question | Look for |
|---|---|
| 1, the reader can act | A sentence that hides who acts. A pronoun with no clear antecedent. A page that does two jobs for two readers: split it |
| 2, the first sentence | An opening that describes the page in place of stating its purpose. A section that leads away from its rule |
| 3, complete and no more | A code or configuration example without the context needed to read it. A section that answers no question its reader would ask. A page that no other page needs: consider deleting it |
| 4, one sense per term | A term of art used before it is explained. A term that differs from [[docs/reference|reference]] or from the code |
| 5, table or list | A long paragraph that holds comparable items or an order |
| 6, one owner | A hit from step 2. A reference that takes several hops to reach the answer. A hub that restates the pages it routes to |
| 7, present state | A sentence that describes a change |

Two searches list candidates for questions 4 and 7:

```bash
# Question 4: capitalized abbreviations under docs/, to check for a first-use explanation
grep -rhoE '\b[A-Z][A-Z]+\b' --include="*.md" docs | sort | uniq -c | sort -rn | head

# Question 7: words that mark a sentence about a change
grep -rnE "\b(formerly|previously|no longer|renamed from)\b" --include="*.md" \
  --exclude-dir=plugins --exclude=CHANGELOG.md .
```

A hit is a candidate, not a finding: read the sentence before you record it. `CHANGELOG.md` records history, so question 7 does not apply to it.

- Done when: every page in scope has an answer to each question, and each finding names its file, its line and the question it fails.

### 4. Check that every playbook has its six parts

```bash
FRAMEWORK_HOME/bin/grimoire validate format
```

The format validator reports `FORMAT_MISSING_INVOCATION_SECTION` for a playbook that lacks one of the six required headings. Then check what it does not:

```bash
# A second-level heading outside the seven that a playbook may have
grep -n "^## " $(grep -rl "^type: playbook" invocations) \
  | grep -vE ":## (Trigger|Inputs|Never|Steps|Evidence and checks|Outputs|Related)$"

# Playbooks with no step that states its result
grep -L "Done when:" $(grep -rl "^type: playbook" invocations)
```

Read each playbook against "Deterministic procedures" in the standard and against `formulae/invocation.formula.md`. A part that exists and leaves its reader to guess is a finding: a step with no "Done when:", an input with no path or command, a "Never" line with no reason, a check that cites no command.

- Done when: you hold the output of all three commands, and each playbook is read. Every line of output is a finding for step 6.

### 5. Check the indexes

- `docs/skills.md` is generated. `FRAMEWORK_HOME/bin/grimoire sync_docs` exits 0 when it is current and 1, with a diff, when it is stale. Step 8 of [[invocations/dev/improve_framework|improve framework]] applies the fix.
- The root hub [[grimoire|grimoire]] and the folder hubs are written by hand. Confirm that each page in scope has a route from its hub, and that no route points at a page that is gone.

- Done when: `sync_docs` has an exit code on record, and every hub in scope is checked.

### 6. Apply the fixes

For each finding:

1. Name the owner of the content.
2. Edit the owner, and replace each duplicate with a link to it.
3. Rewrite to the principle the text fails, as "Review questions" in the standard describes.
4. When a section moved, update every page that linked to its old anchor.

Then run the validators:

```bash
FRAMEWORK_HOME/bin/grimoire validate
```

- Done when: each finding is fixed or deferred, and the command exits 0.
- Stop when: a fix would change which page owns a fact, and the map from [[invocations/dev/quality/review_architecture|review architecture]] does not settle it. Ask the user which page owns the fact; this review changes how a fact is written, not where it lives.

## Evidence and checks

- Each finding cites a file, a line, and the question or principle of the standard that the text fails.
- Each duplicate cites both locations and names the owner.
- `FRAMEWORK_HOME/bin/grimoire validate` exits 0 before this review reports success. The validators check links, frontmatter, format, naming and structure; this review does not replace them.

## Outputs

Files: the edited pages.

This review's part of the `/grm-dev-improve` reply:

1. The number of pages reviewed, from the list of step 1.
2. Duplicates removed, each with the owner that keeps the fact.
3. Findings by question, with the count fixed and the count deferred.
4. Playbooks that lack a part, each with the part.
5. Whether `docs/skills.md` is stale.

## Related

- The standard: [[docs/writing_standard|writing standard]]
- The playbook template: [[formulae/invocation.formula|invocation.formula]]
- Orchestrator: [[invocations/dev/improve_framework|improve framework]]
- Validators: [[invocations/validators/validators|validators]]
