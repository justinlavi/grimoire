---
type: playbook
title: "Add"
aliases: ["add", "add-content", "import", "file-a-source"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Add

Put knowledge into the active grimoire. What the user hands over decides the mode: a topic or an
answer from this chat is authored as a page or a chapter; a file, a folder or the inbox is filed as
cited sources, and the pages and hubs it affects are updated. `/grm-create` makes a grimoire;
`/grm-add` fills it.

## Trigger

```
/grm-add                       # ask what to add; or sweep inbox/ when it holds files
/grm-add <topic>               # author a page or chapter about the topic
/grm-add "this answer"         # capture the answer just given in chat
/grm-add <file>                # file one source artifact (PDF, article, transcript, screenshot)
/grm-add <folder>              # classify and file everything under a folder
/grm-add inbox                 # sweep the grimoire's inbox/
```

The user says "add a chapter for X", "document Y", "save this answer", "promote this to the wiki",
"import this PDF", "file this article", "process the inbox" or "sort this folder".

| A request that looks similar | Goes to |
|---|---|
| Start a whole grimoire | `/grm-create` |
| Rename or move a page or chapter | `/grm-move` |
| Delete a page or chapter | `/grm-remove` |
| Share what was added | `/grm-save` |

## Inputs

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above. The framework is not a grimoire.
- `$material`: the topic, the text, or the path the user gave.
- `naming` in `GRIMOIRE_ROOT/grimoire.json`: the convention for new file and folder names;
  `snake_case` when the key is absent.
- The root hub and the chapter hubs, to decide where new content belongs.
- The formulae `FRAMEWORK_HOME/formulae/page.formula.md`, `chapter_hub.formula.md` and
  `source.formula.md`.

[[docs/page_schema|page schema]] owns the frontmatter fields, the page types and the authority
models. [[docs/operating_model|operating model]] owns the storage layers, source wrappers, the hub
convention and naming.

## Never

- Never rename existing or imported files or folders to fit the naming convention without asking.
  The material may be linked from outside the grimoire, and its owner chose its names.
- Never edit a file under a `sources/` folder after it is filed, and never add backlinks to a source
  wrapper. Pages cite sources; a source that changes makes every citation unverifiable.
- Never cite or file anything under `inbox/` or `publish/`. Inbox files leave at the next sweep and
  `publish/` holds build output.
- Never create `invocations/`, `formulae/` or `rites/` inside a grimoire. Use practical folder names
  such as `templates/`, `scripts/` and `snippets/`; the system names belong to the framework.
- Never let a new page override an existing page silently. Surface every contradiction to the user;
  two pages that disagree leave the next reader with no way to tell which is true.
- Never delete a file you classified as junk or unclear. Only the user can say that it is worthless.
- Never copy the content of a source of truth into a page; link to it. A copy drifts.
- Never file a trivial one-liner. Add what compounds.

## Steps

### 1. Resolve the grimoire and its naming convention

Apply the guard in Inputs to set `GRIMOIRE_ROOT`, and run its check before a command changes the
grimoire. Read `naming` from `GRIMOIRE_ROOT/grimoire.json`.
Every path and chapter name you create follows that convention and is specific: `pto_policies`, not
`hr_stuff`.

- Done when: `GRIMOIRE_ROOT` is set, its access is `edit`, and you know the convention.
- Stop when: `naming` is not recorded and the material arrives in another casing. Ask the user once
  which convention the grimoire follows, record the answer as `naming` in `grimoire.json`, and
  continue.

### 2. Choose the mode

Take the first row that matches:

| What the user gave | Mode | Go to |
|---|---|---|
| A path to an existing file | File one source | Step 6 |
| A path to a folder, the word `inbox`, or nothing while `inbox/` holds files | Sweep a folder | Step 7 |
| Anything else: a topic, "this answer", pasted text | Author | Step 3 |

`inbox/` holds files when it contains anything other than hidden files, `.gitkeep` and its own
`README.md`.

- Done when: one mode is selected.
- Stop when: the user gave nothing and `inbox/` holds no files. Ask what to add.

### 3. Author: size the material

Establish what is being added: a topic the user describes, or a recent answer to capture ("save
this", "file the comparison we just did"). Then choose the smallest unit that fits:

| Unit | Fits | Go to |
|---|---|---|
| Page | One focused idea (a concept, an entity, a procedure, a reference) that belongs in an existing chapter | Step 4 |
| Chapter | A new area with several facets, or material that no existing chapter fits | Step 5 |

A captured answer is almost always a page. Choose a chapter only when the material opens a new area
that needs its own route.

- Done when: you know what is being added and whether it is a page or a chapter.
- Stop when: the material is unclear, or it fits both units. Ask the user.

### 4. Author: add a page

1. **Place it and type it.** Pick the most relevant chapter. When no chapter fits, make one (step 5).
   Pick a slug in the naming convention, and a `type`:

   | `type` | Use for |
   |---|---|
   | `concept` | A topic, a technique, an idea |
   | `entity` | A specific person, project or product |
   | `playbook` | A procedure; most "how do I X" answers |
   | `reference` | A comparison table, a glossary entry, a cheat sheet |

2. **Stamp the page**, so that it never carries a placeholder date. Run the command without
   `--apply` first to preview it.

   ```bash
   FRAMEWORK_HOME/bin/grimoire new_page \
     --grimoire GRIMOIRE_ROOT \
     --path chapters/<chapter>/<slug>.md \
     --type <concept|entity|playbook|reference> \
     --title "<Title>" \
     --apply
   ```

   The rite writes `authority: grimoire`, the value for authored material. It derives the
   `chapter/<chapter>` tag and refuses to overwrite a file. Add `--tags domain/<facet>` for extra
   facets. Use `--authority hybrid --sources <path-or-url>` only when the page synthesizes filed
   source material.
3. **Write the body.** When you capture an answer, the conversation is the source material. Distill
   it into clean prose under the formula's sections (`Purpose`, `When to Use`, the content,
   `Gotchas`, `Related`). Never go beyond what was established.
4. **Wire it in.** Add a full-path wikilink to the page under the chapter hub's `## Routes`.

Continue at step 9.

- Done when: the rite printed `Created chapters/<chapter>/<slug>.md`, the body is written, and the
  chapter hub links to the page.
- Stop when: the rite exits 1. It refuses an existing file, a path outside `chapters/`, an unknown
  type, and `external` or `hybrid` without `--sources`. Report its message; never overwrite a page.

### 5. Author: add a chapter

1. **Gather the inputs**, one question at a time: the chapter name (in the naming convention), a
   one-line purpose, when to route here, the knowledge sources to point at, and two to five
   sub-topics.
2. **Scaffold the hub from the formula.** A chapter hub is named after its folder and is
   `type: hub`.

   ```bash
   mkdir -p GRIMOIRE_ROOT/chapters/<chapter_name>
   cp FRAMEWORK_HOME/formulae/chapter_hub.formula.md GRIMOIRE_ROOT/chapters/<chapter_name>/<chapter_name>.md
   ```

3. **Fill the hub.** Replace `{{CHAPTER_TITLE}}` and `{{CHAPTER_NAME}}`, and replace every bracketed
   prompt with facts. The tag is `chapter/<chapter_name>`; use `hub/sub` in place of `hub/chapter`
   when the chapter is nested. Under `## Routes`, write one line with a full-path wikilink for each
   child that exists, and remove the formula's sample lines. Verify that no placeholder and no
   prompt remains; the command must print nothing:

   ```bash
   grep -nE '\{\{|^\[[^[]|^- \[[^[]' GRIMOIRE_ROOT/chapters/<chapter_name>/<chapter_name>.md
   ```

4. **Seed leaf pages (optional)** with `new_page` as in step 4, one per sub-topic. A stub with a
   TODO is fine.
5. **Register the chapter in its parent hub**: the root hub (`GRIMOIRE_ROOT/<grimoire>.md`, under
   `## Route By Chapter`) for a top-level chapter, or the containing chapter's hub for a
   sub-chapter. The label is the chapter's folder name with underscores as spaces.

   ```markdown
   - <chapter description>: [[chapters/<chapter_name>/<chapter_name>|<chapter name>]]
   ```

Continue at step 9.

- Done when: the `grep` prints nothing and the parent hub links to the chapter hub.

### 6. File: file one source

The argument is one immutable artifact: an article, a transcript, a paper, a screenshot, a PDF, a
dataset.

1. Identify the chapter, sub-chapter, project or package that the source supports. Use that
   package's `sources/` folder; create it when it is missing.
2. Pick a short slug in the naming convention. A raw artifact keeps its original filename unless
   the user asks to rename it.
3. File it in the form that fits:

   | Source | Write |
   |---|---|
   | A text source | `chapters/<path>/sources/<slug>.md`, made from `FRAMEWORK_HOME/formulae/source.formula.md`, with the cleaned plain text under `## Source Body` |
   | A binary or large source | The raw artifact at `chapters/<path>/sources/<slug>/<original-file>`, and a wrapper `chapters/<path>/sources/<slug>.md` that points at it |
   | A raw artifact that is ready to cite and needs no wrapper | The artifact at `chapters/<path>/sources/<slug>.<ext>`; pages cite that path |

Continue at step 8.

- Done when: the artifact, and its wrapper when it has one, exist under a chapter's `sources/`
  folder.
- Stop when: you cannot tell which chapter the source supports. Ask the user.

### 7. Sweep: classify a folder or the inbox

The folder holds mixed content. Classify every file before you do anything that cannot be undone.

1. List every file recursively. Skip hidden files, `.gitkeep` and the inbox's own `README.md`.
2. **Classify each file into one layer**, with the user, and confirm before acting:

   | Layer | The file is | Action |
   |---|---|---|
   | **Source** | An external artifact worth citing, authored elsewhere: a PDF, a transcript, an article, a screenshot, a dataset | Move it under the relevant `chapters/<path>/sources/` folder by the rules of step 6, then derive pages from it in step 8. |
   | **Chapter draft** | Authored prose meant to become a page: notes, drafts, half-finished chapters, generated docs | Promote it to `chapters/<chapter>/<page>.md` with frontmatter: `authority: grimoire`, and no `sources:` unless a filed artifact grounds it. Remove the original; its value lives in the page. |
   | **Junk or unclear** | A duplicate, superseded, ambiguous, off topic, or something you cannot decide | Leave it in place and flag it for the user. |

3. **Settle naming once.** When the material uses a casing other than the recorded convention, or
   none is recorded, ask once: apply the grimoire's convention to the promoted pages (recommended),
   keep the material's own casing (`preserve`), or decide case by case. Record a newly chosen
   convention as `naming` in `grimoire.json`.
4. Process the sources first, then the chapter drafts, and the junk last. Run step 8 for each batch
   before you start the next.

- Done when: every file has a layer, every source and chapter draft has left the swept folder, and
  the folder holds only the items the user still has to judge.
- Stop when: the user named no folder and `inbox/` does not exist. Ask whether to create it or to
  point at a specific path.

### 8. Derive pages from filed material

This step follows steps 6 and 7.

1. **Read each source end to end.** With the user, identify the existing pages that already cover
   the material (to update), the entities or concepts it mentions repeatedly that have no page (to
   propose), the claims that contradict existing pages (to flag), and the chapter the content fits.
   Wait for confirmation before writing.
2. **Update the affected pages.**

   | Page | Edit |
   |---|---|
   | An existing page | Edit it in place and keep its frontmatter. Set `last_verified` to today. Add the source path to `sources:` without duplicates. |
   | A new page derived from a source | Stamp it with `new_page` (or copy `FRAMEWORK_HOME/formulae/page.formula.md`) with the right `type`, `authority: external`, and the source path in `sources:`. |
   | A promoted draft | `authority: grimoire`, or `hybrid` with `sources:` when it cites a filed artifact. |

   Link related pages to each other with full-path wikilinks.
3. **Update the hubs.** Every chapter hub you touched gets a wikilink to each new page under
   `## Routes`.

- Done when: every filed source is cited by at least one page, or the user chose to file it without
  a page, and every new page is linked from its chapter hub.
- Stop when: a claim in the material contradicts an existing page. Show both claims with their
  pages and let the user decide; change neither page before they answer.

### 9. Validate

```bash
FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT structure frontmatter links provenance
```

Fix what the validators report and run the command again. `/grm-check quick` runs the whole
mechanical suite.

- Done when: the command exits 0.
- Stop when: a diagnostic remains that this run did not cause. Report it with its file and line.

## Evidence and checks

- `FRAMEWORK_HOME/bin/grimoire validate --grimoire GRIMOIRE_ROOT structure frontmatter links provenance`
  must exit 0 before you report success.
- Every new page carries the frontmatter the page schema requires: `type`, `title`, `tags`,
  `authority`, `sources` and `last_verified`.
- `authority` matches where the page's truth comes from: `grimoire` for authored material and
  promoted drafts, `external` (or `hybrid`) with a `sources:` entry for a page derived from a source.
- Every new page and chapter is reachable from a hub: a chapter hub's `## Routes`, or the root hub.
- Report each classification as you made it; never report a file as filed while it is still in the
  swept folder.

## Outputs

- New or updated pages under `chapters/`, sources under `chapters/<path>/sources/`, and updated hubs.
- `naming` in `grimoire.json`, when the user chose a convention during this run.
- A reply that states, in this order: the mode used; the pages and chapters added or updated, with
  paths; the sources filed, with paths; the hubs updated; the items left for the user to judge and
  why; the contradictions surfaced; and whether validation passed. End with the one next action:
  `/grm-save` to share the result.

## Related

- Page formula: `FRAMEWORK_HOME/formulae/page.formula.md`
- Source formula: `FRAMEWORK_HOME/formulae/source.formula.md`
- Chapter hub formula: `FRAMEWORK_HOME/formulae/chapter_hub.formula.md`
- Page stamping rite: `FRAMEWORK_HOME/rites/new_page.py`
- The drop zone's contract: `inbox/README.md` in the grimoire
- Start a grimoire: [[invocations/grm/create_grimoire|create grimoire]]
- Share the result: [[invocations/grm/save|save]]
- Evaluate afterwards: [[invocations/grm/check|check]]
