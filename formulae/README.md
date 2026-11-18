# Formulae

The templates that playbooks and rites copy to make a page, a hub, a source wrapper, a playbook or a whole grimoire. This index says what each template produces, what uses it, and how to change one.

## Templates

| Template | Produces | Used by |
|---|---|---|
| [`page.formula.md`](page.formula.md) | A knowledge page under `chapters/`, of type `concept`, `entity`, `playbook` or `reference` | `/grm-add`, through `FRAMEWORK_HOME/bin/grimoire new_page` |
| [`chapter_hub.formula.md`](chapter_hub.formula.md) | The hub of a chapter or sub-chapter, `<folder>/<folder>.md` | `/grm-add`, `/grm-move` |
| [`source.formula.md`](source.formula.md) | A source wrapper, `chapters/<chapter>/sources/<slug>.md` | `/grm-add` |
| [`invocation.formula.md`](invocation.formula.md) | A playbook under `invocations/` | Copied by hand when a playbook is added to the framework |
| [`grimoire/`](grimoire/README.md) | The scaffold of a grimoire: root hub, README, manifest, `chapters/`, `inbox/`, `publish/`, `.obsidian/` and the support files | `/grm-create`; `/grm-update` restores the managed files; `/grm-check structure` compares them |
| [`grimoire/scaffold_contract.json`](grimoire/scaffold_contract.json) | The inventory of the scaffold: each directory and file, whether it is required, and whether the framework manages it | The same three commands, and the tests |
| [`publish/`](publish/build.sh) | The publishing files of a grimoire: `publish.json`, `build.sh`, `quartz.config.yaml` and the CI templates for GitLab Pages, GitHub Pages and [Cloudflare](publish/ci/cloudflare_pages.md) | `/grm-publish init` |

## Conventions

- **A `{{TOKEN}}` is replaced by a rite or a playbook.** The [reference](../docs/reference.md#placeholders-in-formulae) owns each token and its meaning. A token used in a formula and missing from that table fails `tests/test_reference_placeholders.py`.
- **A bracketed prompt such as `[Title]` is replaced by the author.** Each prompt says what its section must answer, and the finished document holds facts in its place. The [writing standard](../docs/writing_standard.md#playbooks-skills-and-templates) owns this rule.
- **Frontmatter in a formula is a placeholder.** `validate_frontmatter` checks only `type` under `formulae/`. The document made from a formula must pass the full [page schema](../docs/page_schema.md).
- **`grimoire/scaffold_contract.json` lists every file and directory under `grimoire/`.** Change the contract in the same edit that adds, removes or moves a scaffold file; `tests/test_grimoire_scaffold_formula.py` fails on a path the contract does not cover.

## Changing a formula

A formula is a contract: every document made from it must pass the validators. A change reaches every document made afterwards, and a change to a managed scaffold file reaches every existing grimoire at its next `/grm-update`.

1. Edit the formula.
2. When the file is a managed scaffold file (`grimoire/inbox/README.md`, `grimoire/publish/README.md`, `grimoire/.editorconfig`, `grimoire/.gitattributes` and `grimoire/.obsidian/app.json`), copy it over its twin in `tests/fixtures/good_grimoire/`.
3. Run `python rites/validate.py` and `python -m pytest -q` from the repository root. Both pass before the change lands.
