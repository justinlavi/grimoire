<!-- BEGIN GRIMOIRE KNOWLEDGE BASE -->
## Grimoire Knowledge Base

- **Library**: `~/grimoires/library.json` maps each grimoire key to its path on disk. Read it to resolve a grimoire.
- **Framework**: `FRAMEWORK_HOME` is `~/.grimoire/`, or the `FRAMEWORK_HOME` environment variable when set.
- **Skills**: the framework ships the `/grm-*` grimoire verbs in the table below, plus `/grm-dev-validate` and `/grm-dev-improve` for maintaining the framework. Each grimoire ships its own `/<skill prefix>-*` skills; its `grimoire.json` declares the prefix.

### Hub convention

The hub of a routing folder F is `F/<basename(F)>.md`. The grimoire root hub is `<grimoire>/<grimoire>.md`. A hub routes to sub-hubs, to leaf pages or to both, at any depth. Follow hubs depth-first until a leaf answers the question.

### Storage layers

- **`chapters/`**: LLM-authored knowledge pages. Every page carries YAML frontmatter (`type`, `title`, `tags`, `authority`, `sources`, `last_verified`); see `FRAMEWORK_HOME/docs/page_schema.md`.
- **`chapters/**/sources/`**: immutable source artifacts and source wrappers (articles, transcripts, papers, screenshots), beside the chapter material they support. File them during import, then only read them. Pages with `authority: external` cite paths here.
- **`inbox/`**: transient drop zone for unsorted content; `/grm-add` clears it. Never cite an `inbox/` path: its contents disappear once processed.
- **`publish/`**: publishing configuration and build output; present in every grimoire, idle until the grimoire is published. Validation and the knowledge graph exclude it. Never cite a `publish/` path; build output is disposable.

### Routing rules

1. Resolve the active grimoire from the working directory (its key in the library) or from the project context.
2. Open `<grimoire>/<grimoire>.md` to route.
3. Link Markdown pages inside a grimoire with full-path wikilinks (`[[chapters/path/to/page|label]]`). The label is the target filename, normalized for reading. Aliases are metadata, never link targets.
4. Refer across grimoires with path placeholders (`FRAMEWORK_HOME/...`, `<grimoire>/...`).
5. For knowledge about Grimoire itself, read `FRAMEWORK_HOME/grimoire.md`.
6. Modify framework and grimoire files only when a `/grm-dev-*` skill, a grimoire skill or an explicit instruction asks for it.
7. Name the files and folders you create in the grimoire's convention (`naming` in `grimoire.json`; `snake_case` when absent). Any casing is valid; consistency is the goal. Links match on-disk spelling exactly. Never rename imported material without asking.

### Text file standard

Framework and grimoire text files are UTF-8 without BOM, with LF line endings; preserve both when editing. Unicode is allowed; mojibake and repair artifacts are not. Check with `/grm-check encoding` in a grimoire and `/grm-dev-validate encoding` in the framework.

### Provenance

A page with `authority: external` or `hybrid` cites its `sources:` (paths under `chapters/**/sources/`, or external URLs); the `validate_provenance` rite enforces it. File the source with `/grm-add` before writing an external page.

### Operations vocabulary

| The user wants to | Skill |
|---|---|
| Use a grimoire they have a link to, turn a folder into one, or start their first one | `/grm-setup` |
| Create a grimoire from scratch | `/grm-create` |
| Put knowledge in: write up a topic, save a chat answer, or file a document, folder or `inbox/` as cited sources | `/grm-add` |
| Share what they changed (validate, commit, pull, push) | `/grm-save` |
| Pick up everyone else's changes and bring everything current | `/grm-update` |
| Check the grimoire: full health pass, or `quick`, a validator, `naming`, `boundaries`, `fix` | `/grm-check` |
| Rename, move or delete a page or chapter and fix every link | `/grm-move`, `/grm-remove` |
| Turn the grimoire into a website, or check what would be published | `/grm-publish` |
| List the commands they can run; `all` adds every registered grimoire's | `/grm-help` |
<!-- END GRIMOIRE KNOWLEDGE BASE -->
