---
type: reference
title: "Getting Started"
aliases: ["getting-started", "start-here", "grimoire-for-everyone"]
tags: [type/reference, framework/docs, scope/onboarding]
authority: grimoire
last_verified: 2026-11-14
---

# Getting Started with Grimoire

This page covers installing Grimoire, setting up a grimoire, and the everyday commands.

A grimoire is a knowledge base, for one person or for many, that your AI assistant reads and
keeps up to date with you. What you know is written down once, and the assistant opens the right
page instead of guessing. Grimoire is also the name of the program that makes this work. You
install it once.

## What you need

- **An AI coding assistant, signed in.** Claude Code (in a terminal, the desktop app or the VS
  Code extension) or Codex.
- **git and Python 3.10 or newer** on your computer. On Windows, install Python from python.org
  and tick "Add to PATH".
- **To use an existing grimoire: its link, and access to the place it is kept** (for example
  GitHub or GitLab), with the sign-in you normally use there.

## Install

### Claude Code

Type these two lines in a Claude Code session, one after the other:

```text
/plugin marketplace add justinlavi/grimoire
/plugin install grimoire@grimoire
```

Then start a new session. That session installs Grimoire on your computer and tells you so.

The first line names Grimoire's public repository. When you were given another address for
Grimoire, use that address in its place, for example
`/plugin marketplace add https://gitlab.example.com/tools/grimoire.git`. Such an address is a
mirror: a copy of Grimoire kept somewhere else. Grimoire then installs from the mirror and takes
its updates from it.

The same two steps have two other forms:

- **In the VS Code extension**, type `/plugins`. On the **Marketplaces** tab, enter
  `justinlavi/grimoire` or the address you were given. On the **Plugins** tab, install `grimoire`.
- **In a terminal where the `claude` command is installed**, run the two lines below. The VS Code
  extension alone does not give you a `claude` command in a terminal.

  ```text
  claude plugin marketplace add justinlavi/grimoire
  claude plugin install grimoire@grimoire
  ```

When Grimoire is already installed on your computer, skip this step.

### Codex, or another assistant

Run the installer in a terminal, then start a new session in your assistant.
[Installation](installation.md#the-installer) has the one line to run, and the form that installs
from a mirror.

## Set up

In a new session, type:

```text
/grm-setup
```

The assistant asks what you want to do:

- **Use an existing grimoire.** Paste the link you were given.
- **Start a new grimoire.**
- **Turn a folder of notes you already have into a grimoire.**

The first time, the place that keeps the grimoire may ask you to sign in. When setup finishes,
start one more new session so that the assistant sees the grimoire's own commands.

A grimoire you join from a link is set up for reading. Your copy stays up to date and nothing you
do changes it. The first time you ask to change something, the assistant asks whether to switch
your copy to editing; say yes and carry on. A grimoire you start or make from a folder is set up
for editing from the beginning.

Claude Code, installed as above, spells the commands `/grimoire:setup`, `/grimoire:add` and so on.
Every other assistant spells them `/grm-setup`, `/grm-add`. This page writes the `/grm-` form.

## Everyday use

Most of the time you type no command. You ask a question, and the assistant finds the answer in
the grimoire and names the page it read. When you want to change something, say it in plain words
or type the command:

| You want to | Say | Command |
|---|---|---|
| Write something down, or keep a good answer the assistant just gave | "add this to the grimoire" | `/grm-add` |
| File a document, a PDF or a folder of notes | "file this in the grimoire" | `/grm-add <path>` |
| Share your changes | "save" | `/grm-save` |
| Pick up everyone else's changes | "update" | `/grm-update` |
| Find out whether the grimoire is in good shape | "check the grimoire" | `/grm-check` |
| Turn the grimoire into a website | "publish" | `/grm-publish` |
| Rename, move or delete a page | "move X under Y", "remove X" | `/grm-move`, `/grm-remove` |
| See the commands | "help" | `/grm-help` |

## Save and update

A grimoire has one home online, and each computer that uses it holds a copy. Two commands keep
your copy and that home in step:

- **`/grm-save` shares your changes.** It checks the grimoire, shows you a one-line description
  of your changes to approve, brings in what everyone else saved in the meantime, and sends
  yours. If you and someone else changed the same lines, it stops. Your work stays safe on your
  computer, and the assistant names the pages and helps you choose what to keep.
- **`/grm-update` picks up everyone else's changes.** It also keeps Grimoire and your commands
  current. Claude Code, installed as above, brings Grimoire and every grimoire up to date at the
  start of each session, so you rarely need the command. A copy that holds changes you have not
  saved is left as it is, and the assistant says so.

## Publish a website

Type `/grm-publish init gitlab-pages`, `/grm-publish init github-pages` or
`/grm-publish init cloudflare`, depending on where the site will live. From then on the website
is rebuilt each time changes are saved. Before each build a check refuses to publish passwords,
card numbers and identity documents.

Put a sign-in in front of the site before you share its link. The assistant explains how for your
host.

## When something looks wrong

1. Start a new session. Assistants read the list of commands once, when a session starts.
2. If it is still wrong, type `/grm-update`. It repairs missing commands, a grimoire the
   assistant cannot find, and an assistant that guesses instead of reading pages.
3. If the assistant says that Python is not installed, install Python as
   [What you need](#what-you-need) describes and start a new session.
4. For anything else, see [troubleshooting](installation.md#troubleshooting).
