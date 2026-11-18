# Contributing to Grimoire

This guide covers changing the framework: what each kind of change must include and which check enforces it. The framework keeps a small surface, so a change lands most easily when it follows a pattern that already exists.

## Where a change belongs

A change usually touches one layer. Read that layer's rules before you edit it.

| Layer | Holds | Read first |
|---|---|---|
| `docs/` | Documentation of the framework | [Writing standard](docs/writing_standard.md) |
| `formulae/` | Templates copied when a grimoire, chapter or page is created | [Formulae](formulae/README.md) |
| `invocations/` | Playbooks an assistant follows | [Invocation formula](formulae/invocation.formula.md) |
| `rites/` | Python automation: validators, registration, the installer | [rites/_lib.py](rites/_lib.py), [rite profiles](docs/rite_profiles.md) |
| `skills/` | Command sources, one `SKILL.md` per command | [Skill schema](docs/skill_schema.md) |
| `tests/` | The test suite and its fixture grimoires | `tests/conftest.py` |

Two trees are generated. Edit their sources and regenerate; never edit them by hand.

| Generated | Source | Regenerate with |
|---|---|---|
| `docs/skills.md` | `skills/*/*/SKILL.md` and `rites/data/command_surface.json` | `python rites/sync_docs.py --apply` |
| `plugins/` | `skills/*/*/SKILL.md` and the invocations they name | `python rites/build_plugins.py --apply` |

[Script vs AI](docs/script_vs_ai.md) decides whether a piece of work is a rite or a playbook. [Governance](docs/governance.md) decides whether it belongs in the framework at all.

## Set up

```bash
git clone https://github.com/justinlavi/grimoire
cd grimoire
python -m pip install -e '.[dev]'
```

The framework runs on the Python standard library alone, on Python 3.10 or newer. The `dev` extra adds `pytest`, the only dependency of the test suite.

## Run the checks

Both commands must pass before you open a pull request. CI runs the same two on Linux and Windows.

```bash
python rites/validate.py
python -m pytest -q
```

To run part of the validators while you work, name them:

```bash
python rites/validate.py links frontmatter
```

[Validators](invocations/validators/validators.md) lists every validator, its selector and what it checks.

## Add a validator

A validator is a rite named `rites/validate_<aspect>.py`. It must:

1. Import shared helpers from [rites/_lib.py](rites/_lib.py). Do not write a second frontmatter parser, manifest loader or root resolver.
2. Accept `--grimoire <path>` through `add_grimoire_arg(parser)` and resolve it with `resolve_grimoire_arg`. Without the flag it checks the framework.
3. Accept `--format` through `add_output_format_arg(parser)` and report every finding through a `DiagnosticReporter` from [rites/diagnostics.py](rites/diagnostics.py). The orchestrator runs each validator with `--format json` and reads that output.
4. Exit `0` when clean and `1` when it reports an error.
5. Be listed in [rites/data/validators.json](rites/data/validators.json) under `framework`, `grimoire` or both. [rites/validate.py](rites/validate.py) derives the selector from the file name.
6. Have a page under `invocations/validators/` and a row in the [validators hub](invocations/validators/validators.md).
7. Have a violating tree in `tests/fixtures/negative_specs.json` for every diagnostic code it can emit. `tests/test_negative_coverage.py` fails when a code has no fixture.

A validator needs no command of its own. `/grm-dev-validate <selector>` runs it on the framework and `/grm-check <selector>` runs it on a grimoire.

```python
import argparse

from _lib import add_grimoire_arg, resolve_grimoire_arg
from diagnostics import DiagnosticReporter, add_output_format_arg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_grimoire_arg(parser)
    add_output_format_arg(parser)
    args = parser.parse_args()
    root = resolve_grimoire_arg(args.grimoire)
    reporter = DiagnosticReporter("validate_<aspect>", root)
    # ... reporter.error("<CODE>", "<message>", path=<relative path>) per finding
    reporter.emit(args.format)
    return reporter.exit_code()
```

## Add a command

A command is a `SKILL.md` that points at a playbook or a rite. It holds no logic of its own. The [skill schema](docs/skill_schema.md) owns the command families, the naming rule and the `SKILL.md` fields.

1. Choose the family: `grm` for a command that acts on a grimoire or the install, `dev` for a command that maintains the framework.
2. Create `skills/<family>/<slug>/SKILL.md`. The folder name is the verb.
3. Write the `name:` line and the other frontmatter fields as the skill schema states. Set `disable-model-invocation: true` on a command that deletes.
4. Write the playbook under `invocations/<family>/`, in the shape of the [invocation formula](formulae/invocation.formula.md), and route to it from that folder's hub.
5. Add the command to [rites/data/command_surface.json](rites/data/command_surface.json). [Command surface](docs/command_surface.md) describes the fields.
6. Regenerate `docs/skills.md` and `plugins/` with the two commands in [Where a change belongs](#where-a-change-belongs).

`python rites/validate.py skill-refs naming` checks the command against the contract and the naming rule. The test suite fails when `plugins/` or `docs/skills.md` differs from its sources.

## Change documentation

- Every text follows the [writing standard](docs/writing_standard.md): documentation, playbooks, skills, source comments and the text a rite prints.
- State each fact at one owner and link to it from elsewhere. The documentation table in the [README](README.md) names what each page owns.
- A page under `docs/`, `invocations/` or `formulae/` carries the frontmatter the [page schema](docs/page_schema.md) defines. `rites/validate_frontmatter.py` enforces it. `README.md`, `UPDATE.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and every `SKILL.md` are exempt.
- A page under `docs/` is linked from `README.md` and routed from `grimoire.md`. `rites/validate_structure.py` enforces both.
- A folder of invocations has a hub named after the folder. `rites/validate_structure.py` enforces it.
- Pages under `docs/` and the four root files named above use relative Markdown links, so that they render on a git host. Pages under `invocations/` and `formulae/`, and the root hub, use full-path wikilinks. `rites/validate_links.py` enforces both.

## Code style

- Use the Python standard library only. Open an issue before you propose a dependency.
- Name `.py` and `.md` files in snake_case, and skill folders and commands in kebab-case. `rites/validate_naming.py` enforces it.
- Write comments and docstrings as the [writing standard](docs/writing_standard.md#source-comments) states.
- Put logic that two rites share in [rites/_lib.py](rites/_lib.py).
- Give a rite that writes a mutation profile in `rites/data/rite_profiles.json`. [Rite profiles](docs/rite_profiles.md) describes the profiles, and `tests/test_rite_profiles.py` fails when a rite that writes has none.

## Pull requests

- Keep one concern in a pull request. A documentation rewrite and a validator change are two pull requests.
- Record the change in [CHANGELOG.md](CHANGELOG.md). [Governance](docs/governance.md) states under which heading.
- State what the owner of an existing grimoire must do to adopt the change, when the change alters what a user sees.
- Change [VERSION](VERSION) only in a release pull request. [Governance](docs/governance.md) owns the compatibility rule that decides the number, and [release](docs/release.md) owns the steps.

Run `/grm-dev-validate` and `/grm-dev-improve` before a release.

## Report an issue

| Kind | Include |
|---|---|
| A bug | The validator or rite output, the framework version (`cat VERSION`) and the Python version |
| A confusing term or design | A link to the page that confused you |
| A feature | The use case, before any implementation. An addition must show why the framework needs it |
