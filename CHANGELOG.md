# Changelog

## [1.0.0] - 2026-11-18

The first release of Grimoire: a framework, installed once, that lets an AI assistant build and
maintain grimoires. A grimoire is a knowledge base for one person or for many, kept as Markdown
pages in a git repository and routed through hubs so the assistant opens the right page instead
of searching.

### Added

- **Grimoires.** A scaffold with a root hub, `chapters/` with chapter-local `sources/`, an
  `inbox/`, a `publish/` layer, a manifest (`grimoire.json`) and a per-grimoire naming convention.
  Pages carry frontmatter that states their type, authority, sources and when they were last
  verified.
- **Ten commands for everyday use.** `/grm-setup`, `/grm-create`, `/grm-add`, `/grm-save`,
  `/grm-update`, `/grm-check`, `/grm-publish`, `/grm-move`, `/grm-remove` and `/grm-help`. Each is a
  playbook the assistant follows, backed by deterministic rites for the mechanical steps.
- **Two commands for maintaining the framework.** `/grm-dev-validate` runs the framework's
  validators and `/grm-dev-improve` runs the quality review.
- **Install for Claude Code as plugins.** The repository is its own marketplace with the
  `grimoire` and `grimoire-dev` plugins. A session-start hook installs the framework at
  `~/.grimoire/`, keeps it current, and gives the assistant its routing context.
- **Install for any other assistant.** A one-line installer registers the same commands as
  skills and writes the routing block into the assistant's instruction file. It configures only
  the assistants that are installed.
- **Mirrors.** An install keeps the place it came from. A plugin added from a mirror of this
  repository, or an installer run with `FRAMEWORK_URL`, clones the framework from that address
  and takes its updates from it.
- **Sharing.** `/grm-save` validates, records, brings in everyone else's changes and sends
  yours. A conflict pauses the save with the pages marked; the next save finishes it, and
  `--abandon` ends it with your work kept.
- **Reading and editing.** A grimoire joined from a link is a copy for reading: no command
  changes it, and the first request to change something asks whether to switch the copy to
  editing. Joining with `--access read` or `--access edit` records that choice, also for a
  grimoire that is already on the computer.
- **Moving a grimoire to another address.** `/grm-setup` with a new link for a grimoire that is
  already on the computer changes nothing until the user agrees. The join then points the copy
  at the new address, after checking that both addresses hold the same grimoire, and the library
  records the address the copy fetches from.
- **Staying current.** On a Claude Code plugin install, each session starts by bringing every
  grimoire up to date. A grimoire with unsaved changes is left alone. A host that cannot be
  reached is tried once per session; a grimoire whose remote refuses the update says so and does
  not hold back the others.
- **Validation.** Fourteen validators cover structure, links, frontmatter, provenance, orphans,
  encoding, portability, format, tree diagrams, naming, security, semantics and command
  references. They run on a grimoire through `/grm-check` and on the framework through
  `/grm-dev-validate`, on Windows and Linux.
- **Publishing.** `/grm-publish` stages a grimoire for a static site generator, audits what would
  be exposed, and sets up builds for GitLab Pages, GitHub Pages or Cloudflare.
- **A writing standard.** `docs/writing_standard.md` governs how documentation, playbooks,
  comments and replies are worded.
