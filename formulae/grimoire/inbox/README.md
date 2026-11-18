# `inbox/`: files waiting to be sorted

Put anything here that belongs in this grimoire and is not sorted yet: documents, notes, drafts, screenshots, whole folders. Your assistant sorts it into the right chapter when you type `/grm-add inbox`.

## Rules

- **Nothing stays here.** After a sort, the only files left are the ones the assistant asked you about.
- **Any file is welcome, in any shape.** A file here needs no page header, no naming convention and no folder.
- **No page cites a file in `inbox/`.** A file here moves or is removed at the next sort, so a page that listed it under `sources:` would point at nothing.

## Put files in

Save, drag or extract files into `inbox/`. A tool that saves into this folder, such as a web clipper or a screenshot tool, works the same way.

## Sort them

Type `/grm-add inbox` in your assistant. `/grm-add` with nothing after it does the same while `inbox/` holds files. The assistant proposes a place for each file and waits for your answer before it moves anything.

| The file is | It goes to | What happens |
|---|---|---|
| A document from elsewhere that is worth citing: an article, a PDF, a transcript, a screenshot, a dataset | `chapters/<chapter>/sources/` | It is filed unchanged and never edited again. Pages cite it, and the assistant updates the pages it affects. |
| Notes or a draft meant to become a page | `chapters/<chapter>/<page>.md` | It becomes a page linked from its chapter hub, and the original leaves `inbox/`. |
| A duplicate, out of date, off topic or unclear | `inbox/` | It stays. The assistant names it and asks you; it never deletes a file here by itself. |

The assistant ends by listing each file and where it went. The grimoire's history keeps that record.

## What goes elsewhere

| You have | Put it |
|---|---|
| One document to file under a chapter you already know | `/grm-add <file>` files it without a stop here |
| A finished page that already carries its page header | Under its chapter in `chapters/`, with a line in the chapter hub |
| Files another program generates and reads back, such as caches, indexes and build output | Outside `inbox/`; a sort would try to file them |

The assistant follows `FRAMEWORK_HOME/invocations/grm/add.md` for a sort. `FRAMEWORK_HOME` is the folder Grimoire is installed in, `~/.grimoire/`.
