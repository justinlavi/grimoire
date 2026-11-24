# Changelog

## [1.1.0] - 2026-11-24

An existing install needs nothing beyond the update itself: `/grm-update`, or the plugin's
automatic update. No grimoire changes. A library that recorded a link together with its
credential loses the credential the next time that grimoire is set up from its link.

### Added

- **Naming the access when setting up.** `/grm-setup <link> read` and `/grm-setup <link> edit`
  set a grimoire up with exactly that access and ask nothing first. The same line brings a
  grimoire that is already on the computer to that access and to that link.
- **Links that carry a credential.** A link such as `https://<token>@host/...` works as it is.
  Git keeps the credential with the copy; the library and everything Grimoire prints hold the
  address without it. Setting a grimoire up again from a link with a new credential gives the
  copy that credential once it is shown to work, with or without an access word.
- **A warning for unshared work in a copy for reading.** Setup says how many unsaved changes
  and unshared commits such a copy holds, since it takes in no updates while it holds them.

### Changed

- **Two links that differ only by their credential are one address.** Setup treats the second as
  a renewed sign-in and does not stop to ask about a change of address.
- **A link always goes through setup.** The playbook installs from a link also when the
  grimoire is already registered, so a renewed credential or a named access takes effect.

### Fixed

- **Credentials in output.** A rite's results, messages and terminal output show an address
  without the credential it carries.

## [1.0.1] - 2026-11-21

An existing install needs nothing beyond the update itself: `/grm-update`, or the plugin's
automatic update. No grimoire changes.

### Fixed

- **Installing through claude.ai, the Claude desktop app and Cowork.** Those apps refuse a plugin
  that has a top-level `bin/` folder, and the `grimoire` plugin had one. The plugin carries no
  `bin/` folder; its commands run the launcher of the installed framework,
  `~/.grimoire/bin/grimoire`.

### Changed

- **Plugin descriptions.** The marketplace entries of `grimoire` and `grimoire-dev` say what each
  plugin is and does.

### Removed

- **The bare `grimoire` command inside Claude Code.** The plugin's `bin/` folder put the launcher
  on the PATH of the Bash tool. Run it by its path: `~/.grimoire/bin/grimoire <rite>`.

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
