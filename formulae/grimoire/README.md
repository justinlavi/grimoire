# {{GRIMOIRE_NAME}} Grimoire

This repository is a grimoire: a knowledge base that an AI assistant reads and keeps current with you. It holds {{GRIMOIRE_PURPOSE}}.

{{GRIMOIRE_PURPOSE_DETAILED}}

You ask your assistant a question and it answers from these pages, naming the page it read. The assistant reaches a grimoire through Grimoire, a program you install once.

## Installation

You need an AI coding assistant that is signed in (Claude Code or Codex), `git`, Python 3.10 or later, and access to this repository.

### Claude Code

1. In a Claude Code session, type these two lines:

   ```text
   /plugin marketplace add justinlavi/grimoire
   /plugin install grimoire@grimoire
   ```

   The first line names Grimoire's public repository. When you were given another address for Grimoire (a mirror), use it in place of `justinlavi/grimoire`.

2. Start another session and type the line below. The plugin lists this command as `/grimoire:setup`.

   ```text
   /grm-setup {{GRIMOIRE_REPO_URL}}
   ```

### Codex and other assistants

1. In a terminal, run the line below. On Windows the terminal is Git Bash.

   ```bash
   curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash -s -- --scope {{GRIMOIRE_REPO_URL}}
   ```

   To install Grimoire from a mirror, put `FRAMEWORK_URL=<mirror address>` in front of `bash`.

2. The installer lists this grimoire. Type its number to install it.

To find a private repository the installer needs a credential: the one git stores for the host, or a token in `GITLAB_TOKEN` or `GITHUB_TOKEN`.

### After either route

Grimoire is installed in `~/.grimoire/`, this grimoire is in `~/grimoires/{{GRIMOIRE_DIRECTORY}}/`, and your assistant is set up to use it. Start another session so the assistant sees this grimoire's commands. Then ask it a question, or type `/grm-help` to see the commands.

Your copy is set up for reading and stays up to date. The first time you ask your assistant to change something, it asks whether to switch your copy to editing.

Every other install route, private hosts and troubleshooting are in `FRAMEWORK_HOME/docs/installation.md`, which is also [online](https://github.com/justinlavi/grimoire/blob/main/docs/installation.md). `FRAMEWORK_HOME` is the folder Grimoire is installed in, `~/.grimoire/`.

<!-- BEGIN GRIMOIRE UPDATE -->
## Update when something looks wrong

Update brings Grimoire, your commands and every grimoire on this computer up to date, then checks them. Run it when a command is missing, when your assistant cannot find a grimoire, or when this page looks out of date.

1. Type `/grm-update` in your assistant. The Claude Code plugin lists this command as `/grimoire:update`.
2. If that command is missing or fails, tell your assistant:

   > Pull the latest framework, then read `~/.grimoire/UPDATE.md` from that checkout and follow its instructions exactly.
<!-- END GRIMOIRE UPDATE -->

## Layout

```
{{GRIMOIRE_DIRECTORY}}/
|-- {{GRIMOIRE_DIRECTORY}}.md     # Root hub: the index every question starts from
|-- README.md                     # This page
|-- grimoire.json                 # Identity: name, description, command prefix, naming convention
|-- inbox/                        # Files waiting to be sorted into chapters
|-- chapters/                     # The knowledge pages, one folder per chapter
{{CHAPTER_TREE}}
|-- publish/                      # Website settings and the built site
|-- skills/<command>/SKILL.md     # This grimoire's own commands, one folder each
|-- .obsidian/                    # Shared settings for opening the grimoire in Obsidian
```

- **Every folder of pages has an index page, called a hub, named after the folder**: `chapters/<chapter>/<chapter>.md`. Hubs link to pages and to other hubs, so every page is reachable from the root hub.
- **A chapter keeps the documents its pages cite in its own `sources/` folder.** A file there is never edited after it is filed.
- **`inbox/` and `publish/` each explain themselves** in `inbox/README.md` and `publish/README.md`.
- **`grimoire.json` records two conventions.** This grimoire's own commands start with `/{{SKILL_PREFIX}}-`, and files and folders follow the `{{NAMING}}` naming convention.
- **The history of this repository is the record of changes.** The grimoire keeps no log file.
- **`.editorconfig`, `.gitattributes` and `.gitignore` are settings files.** They keep text files in one format on every computer and name the files that are not shared.

The rules behind this layout are in `FRAMEWORK_HOME/docs/operating_model.md`. The header at the top of each page is defined in `FRAMEWORK_HOME/docs/page_schema.md`.

## Help

| You want | Go to |
|---|---|
| The commands you can run here | Type `/grm-help`. `/grm-help all` adds the commands of every grimoire on this computer. |
| A short guide to everyday use: adding, saving, checking, publishing | `FRAMEWORK_HOME/docs/getting_started.md` |
| Help with installing | `FRAMEWORK_HOME/docs/installation.md` |
| A fix for something that stopped working | [Update when something looks wrong](#update-when-something-looks-wrong) |
| An answer about what this grimoire says | The people who maintain this repository |
