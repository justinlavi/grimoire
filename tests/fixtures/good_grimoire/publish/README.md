# `publish/`: the website of this grimoire

This folder holds what turns the grimoire into a website: the publishing settings, the build script and the built site. Publishing is optional. Until you type `/grm-publish init`, the folder holds only this page.

## Rules

- **Publishing makes the staged copy reachable.** Everyone who can open the site can read every page the build staged. Keep access control, a sign-in in front of the site, on for as long as the site is live.
- **Nothing here is knowledge.** No page cites a file in `publish/` or links into it. Its files carry no page header and follow no naming convention, and `/grm-check` checks nothing in the folder except this page.
- **Settings are saved with the grimoire; build output is not.** The table below says which is which.
- **Grimoire owns this page.** `/grm-update` restores Grimoire's copy, so an edit here does not last.

## Files

| Path | Holds | Saved with the grimoire |
|---|---|---|
| `publish/publish.json` | What this grimoire leaves out, and its extra audit patterns | Yes |
| `publish/build.sh` | The build script | Yes |
| `publish/quartz.config.yaml` | The site's title, address and appearance | Yes |
| `publish/wrangler.jsonc` | The Cloudflare deployment settings, for the `cloudflare` target only | Yes |
| `.gitlab-ci.yml` or `.github/workflows/pages.yml`, at the top of the grimoire | The instructions your host follows to rebuild the site each time changes are saved | Yes |
| `publish/content/` | The staged copy of the pages | No. Every build replaces it. |
| `publish/quartz/` | Quartz, the site generator, and the built site in `publish/quartz/public/` | No. The build fetches Quartz when the folder is absent. |
| `publish/.framework/` | A copy of Grimoire, fetched when the building computer has none | No |

## Commands

| Type | To |
|---|---|
| `/grm-publish init <target>` | Set the grimoire up to publish, once. `<target>` is `gitlab-pages`, `github-pages` or `cloudflare`. |
| `/grm-publish check` | Stage and audit the pages without building a site. It needs git and Python only. |
| `/grm-publish build` | Build the site on this computer. It also needs Node.js 22 or later and npm. |

`bash publish/build.sh` is the same build, and it is what your host runs. `bash publish/build.sh --check` stops after the first audit; any other argument is an error. A build stops while `publish/quartz.config.yaml` still holds a `{{...}}` placeholder.

## What a build does

1. **Stage.** The build copies the root hub to `publish/content/index.md` and each chapter to the top of `publish/content/`, so `chapters/travel/` becomes `travel/`. Each chapter's `sources/` folder goes with it, and links are rewritten to match. Folders named `templates`, `snippets`, `scripts`, `configs`, `assets` or `media` stay out, and so does every path under `exclude`.
2. **Audit the staged copy.** A blocker stops the build: a password, key or token; a full payment-card number or bank details; an identity number or a scan of an identity document; an authoring folder such as `inbox/` or `skills/`; a cited source that was not staged.
3. **Generate.** Quartz 5 builds the staged copy into `publish/quartz/public/`.
4. **Audit the built site.** The same search for secrets runs over the generated files, and a broken link to an image, a document or a video is a blocker.

A warning does not stop the build. It marks a link the audit could not resolve, or material that is acceptable only behind access control: a published document, image or email export, and a match for a pattern this grimoire adds.

## Settings in `publish/publish.json`

| Key | Sets |
|---|---|
| `exclude` | Paths under `chapters/` that never publish |
| `include_asset_folders` | `true` stages the folders that step 1 leaves out, and the audit then accepts them. Every file in them is published. |
| `audit.warning_patterns` | Named patterns that raise a warning, for private detail such as booking references and access codes |
| `audit.known_identifier_patterns` | Number formats that look like card numbers and are not, so the audit lets them pass |
| `audit.allow` | Blockers to accept as warnings: a list of `{"risk": "<risk name>", "path": "<staged path or glob>"}`. The risk name is the one the audit prints, such as `bank-account-data`; the path is relative to `publish/content/`, and `*` matches any characters, including `/`. The audit reports each waived finding as a warning that names the waiver. |

## Targets

| Target | `init` writes | Who can open the site |
|---|---|---|
| `gitlab-pages` | `.gitlab-ci.yml` | The project's members, once Pages access control in the project's settings is set to project members |
| `github-pages` | `.github/workflows/pages.yml` | Everyone, unless the repository's Pages visibility is private, which GitHub offers on some paid plans only |
| `cloudflare` | `publish/wrangler.jsonc`; you enter the build settings in Cloudflare | The addresses that Cloudflare Access allows on the site's hostname |

Quartz is the generator because it renders wikilinks, backlinks and full-text search from Markdown with little configuration. Another generator fits the same four steps: stage, audit, generate from `publish/content/`, audit the output.
