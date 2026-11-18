---
type: reference
title: "VS Code Setup"
aliases: ["vscode", "vscode-setup", "editor-setup"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# VS Code Setup

How to set up VS Code so that a Ctrl-click on a link in a grimoire opens the right page. Do this
before you edit a grimoire in VS Code. Without it, a Ctrl-click on a link such as
`[[chapters/build_system/ci/gitlab_shell_ci|gitlab_shell_ci]]` can create an empty copy of the
folder tree inside the folder of the page you are reading, without asking.

## Why it happens

Links in a grimoire give the full path from the top folder of the grimoire. VS Code does not
follow `[[...]]` links by itself. The Markdown Preview Enhanced extension does, but it reads the
path as relative to the open page, and it creates the target when the path does not exist.
VS Code ignores the Obsidian settings in `.obsidian/app.json`, so the fix belongs in VS Code.

## Set up

1. Remove Markdown Preview Enhanced:

   ```
   code --uninstall-extension shd101wyy.markdown-preview-enhanced
   ```

   VS Code's own preview (`Ctrl+Shift+V`, or `Cmd+Shift+V` on a Mac) shows headings, tables and
   images, which is enough to read a grimoire.

2. Install Foam, which follows links from the top folder of the workspace:

   ```
   code --install-extension foam.foam-vscode
   ```

   Foam needs no settings.

3. Open the folder of the grimoire in VS Code, so that it is the top folder of the workspace.

## Check that it works

1. Open a page that contains a link, for example `chapters/build_system/ci/ci.md`.
2. Ctrl-click the link.
3. The linked page opens, and no folder named `chapters` appears inside the folder of the page
   you clicked from.

When a nested folder does appear, an extension that handles `[[...]]` links is still active.
Run `code --list-extensions`, confirm that `shd101wyy.markdown-preview-enhanced` is absent and
`foam.foam-vscode` is present, and restart VS Code.

## If you keep Markdown Preview Enhanced

Keep it only when you need what it adds, such as advanced math, PlantUML or running code blocks.
Turn off its link handling in your VS Code user settings:

```json
"markdown-preview-enhanced.enableWikiLinkSyntax": false
```

| System | User settings file |
|---|---|
| Windows | `%APPDATA%\Code\User\settings.json` |
| macOS | `~/Library/Application Support/Code/User/settings.json` |
| Linux | `~/.config/Code/User/settings.json` |

- Put the setting in the user settings, not in a `.vscode/settings.json` inside the grimoire. A
  workspace setting applies only when the grimoire is opened as its own workspace, and many
  people open `~/grimoires/` as a whole.
- With Foam installed, Foam follows the links. Without Foam, a Ctrl-click on a link does nothing.
- Removing the extension is the safer choice, because an update to it can change how it handles
  links.

## Clean up stray folders

A stray folder is a folder named `chapters` somewhere inside `chapters/`. It holds only empty
stub pages, so deleting it loses nothing.

1. List them, from the top folder of the grimoire:

   ```bash
   find chapters -mindepth 1 -type d -name chapters
   ```

2. Check each match, then delete it:

   ```bash
   rm -rf <path of the stray folder>
   ```

## Related

- The same setup for Obsidian: [Obsidian setup](obsidian.md#the-settings-files)
- How links are written in a grimoire: [operating model](operating_model.md#links)
- Repairing links: ask your assistant to run `/grm-check fix`
