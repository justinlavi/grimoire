---
type: playbook
title: "Publish"
aliases: ["publish", "grm-publish", "site", "static-site"]
tags: [framework/invocations, type/playbook, scope/grimoire]
authority: grimoire
last_verified: 2026-11-14
---

# Invocation: Publish

Give a grimoire a website that its readers open in a browser, built the same way on the user's
computer and in CI, with an audit that runs before anything is exposed. `publish/build.sh` runs
four steps everywhere: `rites/stage_publish.py` copies the publishable content into
`publish/content/`, `rites/audit_publish.py` refuses blockers, Quartz renders the site into
`publish/quartz/public/`, and the audit runs again over the generated HTML.

## Trigger

```
/grm-publish init <target>     # target: gitlab-pages | github-pages | cloudflare
/grm-publish build             # stage, audit, generate, audit the output, on this computer
/grm-publish check             # stage and audit only; no generator, no Node needed
```

The user says "publish the grimoire", "make a website", "set up pages", "build the site", or asks
whether it is safe to publish.

| A request that looks similar | Goes to |
|---|---|
| Share the publishing configuration | `/grm-save` |
| Find broken links or stale pages in the grimoire itself | `/grm-check` |

## Inputs

!`cat FRAMEWORK_HOME/invocations/meta/grimoire_directory_guard.md`

- `GRIMOIRE_ROOT`, resolved by the guard above.
- The scope: `init <target>`, `build` or `check`.
- The formulae under `FRAMEWORK_HOME/formulae/publish/`.
- `GRIMOIRE_ROOT/publish/publish.json`, the grimoire's publishing choices.
- The JSON envelope of `audit_publish`: `status`, `summary.errors` (blockers), `summary.warnings`,
  and `diagnostics` (`code`, `message`, `path`).

`check` needs Python and git. `build` also needs Node.js 22 or later and npm on the machine.

## Never

- Never bypass a blocker. A blocker is a credential, a card number, an identity document, or an
  authoring folder in the staged copy; publishing makes whatever is staged reachable.
- Never tell the user that a site with warnings is safe before you confirm that it will sit behind
  access control: GitLab Pages access control, Cloudflare Access, or a private GitHub Pages site. A
  warning means "fine behind access control".
- Never run a full build unless the user asked for the `build` scope. CI builds the site on every
  push, and a build on this computer clones Quartz and installs its Node packages. Use `check` to
  answer what would be published.
- Never commit generated output. The committed files are the configuration: `publish.json`,
  `build.sh`, `quartz.config.yaml`, the CI file and any `wrangler.jsonc`.

## Steps

### 1. Route on the scope

Read the scope and run only its section below.

- Done when: one scope is selected.
- Stop when: no scope was given, or `init` has no valid target. Ask which the user wants. Recommend
  `init` when `GRIMOIRE_ROOT/publish/build.sh` does not exist and `check` when it does.

### Scope: `init <target>`

Set the grimoire up to publish, once.

#### 1. Ask for what the formulae cannot guess

Ask for the site title; the default is the grimoire's name. For `cloudflare`, also ask for the
hostname. GitLab Pages and GitHub Pages derive their URL from the project.

- Done when: you have the title and, for `cloudflare`, the hostname, and the guard's check for a
  command that changes the grimoire reports `edit`.
- Stop when: the copy stays set up for reading. Write nothing.

#### 2. Copy the publishing formulae

```bash
cp FRAMEWORK_HOME/formulae/publish/publish.json GRIMOIRE_ROOT/publish/publish.json
cp FRAMEWORK_HOME/formulae/publish/build.sh GRIMOIRE_ROOT/publish/build.sh
cp FRAMEWORK_HOME/formulae/publish/quartz.config.yaml GRIMOIRE_ROOT/publish/quartz.config.yaml
```

Fill `{{SITE_TITLE}}` and `{{BASE_URL}}` in `quartz.config.yaml`, keeping the quotes around each; write a
`"` or `\` in the title with a backslash before it. `build.sh` refuses to build while a `{{...}}`
placeholder remains. `baseUrl` is the hostname without
a scheme, for example `docs.pages.example.com`. For GitLab Pages under a group path, include the
path: `group.pages.example.com/grimoire`.

- Done when: the three files exist, and `pageTitle` and `baseUrl` hold real values.

#### 3. Add the CI file for the target

| Target | Copy | Tell the user |
|---|---|---|
| `gitlab-pages` | `FRAMEWORK_HOME/formulae/publish/ci/gitlab-pages.yml` to `GRIMOIRE_ROOT/.gitlab-ci.yml` | Set "Pages access control: project members" in the project's Pages settings. |
| `github-pages` | `FRAMEWORK_HOME/formulae/publish/ci/github-pages.yml` to `GRIMOIRE_ROOT/.github/workflows/pages.yml` | The repository's Pages source must be "GitHub Actions". Say plainly that a site on a free plan is public. |
| `cloudflare` | Write `GRIMOIRE_ROOT/publish/wrangler.jsonc` from the sample in `FRAMEWORK_HOME/formulae/publish/ci/cloudflare_pages.md`, with the user's Worker name and hostname | Show the build settings from that page. |

When the grimoire lives on a private host, set `FRAMEWORK_URL` in the CI file to the framework
mirror that the runner can reach.

- Done when: the CI file or `wrangler.jsonc` is in place and the user has the setting for their host.

#### 4. Keep generated output out of git

Make sure `GRIMOIRE_ROOT/.gitignore` ignores `publish/content/`, `publish/quartz/` and
`publish/.framework/`. The ignore file a grimoire is created with already does.

- Done when: `.gitignore` lists the three paths.

#### 5. Record what must stay out

Write the grimoire's choices in `publish/publish.json`:

| Key | Holds |
|---|---|
| `exclude` | Paths under `chapters/` that must never publish, such as a trip template package |
| `audit.warning_patterns` | Patterns that mark private detail specific to this grimoire |
| `audit.known_identifier_patterns` | Number formats that look like card numbers and are not |
| `audit.allow` | Blockers to accept as warnings, each `{"risk": "<risk name>", "path": "<staged path or glob>"}`. Use it only after the user has read the blocker and confirmed that the page is safe to publish; the audit reports the finding as a warning that names the waiver |

- Done when: the user has named what to exclude, or said that nothing needs excluding.

#### 6. Check before the first push

Run the `check` scope and report its findings before the user pushes.

- Done when: the `check` scope is done.

### Scope: `build`

#### 1. Build the site

```bash
bash GRIMOIRE_ROOT/publish/build.sh
```

- Done when: the script exits 0 and prints `Site built at` with the path of
  `publish/quartz/public`.
- Stop when: the script exits with an error. Report its `[ERROR]` line: an audit blocker (handle it
  as the `check` scope does), a missing `publish/quartz.config.yaml` (run the `init` scope), one that still holds a `{{...}}`
  placeholder (fill in the title and address), or
  Node.js missing or older than 22.

#### 2. Report

Report the audit's blocker and warning counts and where the site landed
(`publish/quartz/public/`). Remind the user that the committed files are the configuration, never
the output.

- Done when: the user has the counts and the location.

### Scope: `check`

#### 1. Stage and audit

```bash
FRAMEWORK_HOME/bin/grimoire stage_publish --grimoire GRIMOIRE_ROOT --apply
FRAMEWORK_HOME/bin/grimoire audit_publish --grimoire GRIMOIRE_ROOT --mode content --format json
```

- Done when: `stage_publish` exits 0 and `audit_publish` prints its envelope (exit 0 = no blocker,
  exit 1 = blockers).
- Stop when: `stage_publish` exits 1. It refuses an unreadable `publish/publish.json`, a grimoire with no root hub or no
  `chapters/`, and a content directory that is not a folder below `publish/` or that holds publishing
  settings; report its reason. Also stop when `audit_publish` exits 2:
  the staged copy is missing, or `publish/publish.json` is unusable.

#### 2. Report the findings

Read `diagnostics`. Every `PUBLISH_BLOCKER` is a stop: give its file and the action its message
names. List the `PUBLISH_WARNING` entries by risk, with a count for each risk. Offer the three
fixes: move the material outside the publish boundary, add an exclusion to `publish/publish.json`,
or turn an unlinked source path into a Markdown link.

- Done when: the user has every blocker with its file and action, the warning counts by risk, and
  the fixes on offer.
- Stop when: a blocker remains. Do not build or push until the user has resolved it and the audit
  exits 0.

## Evidence and checks

- Blocker and warning counts come from the audit: `summary.errors` and `summary.warnings` in the
  envelope, or the `Findings: BLOCKER=<n>, WARNING=<n>` line that `build.sh` prints. Never count
  findings yourself.
- A grimoire is clear to publish only when
  `FRAMEWORK_HOME/bin/grimoire audit_publish --grimoire GRIMOIRE_ROOT --mode content` exits 0, and
  safe with warnings only behind access control.
- A build is complete only when `publish/build.sh` exits 0; its last step audits the generated site
  with `--mode static-output`.

## Outputs

- `init`: `publish/publish.json`, `publish/build.sh`, `publish/quartz.config.yaml`, the CI file for
  the target or `publish/wrangler.jsonc`, and the three ignore lines in `.gitignore`.
- `check`: the staged copy in `publish/content/`, which is disposable.
- `build`: the staged copy, the Quartz clone in `publish/quartz/`, and the site in
  `publish/quartz/public/`. None of it is committed.
- A reply that leads with whether the grimoire can be published, then the blockers, then the one
  next action: fix a blocker, turn on access control, or `/grm-save` to share the configuration.

## Related

- Staging rite: `FRAMEWORK_HOME/rites/stage_publish.py`
- Audit rite: `FRAMEWORK_HOME/rites/audit_publish.py`
- Formulae: `FRAMEWORK_HOME/formulae/publish/`
- The publish layer's contract: `publish/README.md` in the grimoire
- Share the configuration: [[invocations/grm/save|save]]
