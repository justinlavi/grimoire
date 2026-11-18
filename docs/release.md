---
type: reference
title: "Release Workflow"
aliases: ["release", "tag-release"]
tags: [type/reference, framework/docs]
authority: grimoire
last_verified: 2026-11-14
---

# Release Guide

This page owns the steps that cut a release of the framework. A release is a tag on `main`. The
framework ships as source, so a release builds and uploads nothing: every install route reads the
repository.

Two facts shape the steps:

- **The number of the current release lives in [`VERSION`](../VERSION).** `pyproject.toml`
  repeats it, [`CHANGELOG.md`](../CHANGELOG.md) has an entry for it, and the tag is `v` followed
  by it.
- **`main` holds releases only.** The session hook fast-forwards every install to the head of
  `main`, and Claude Code updates a plugin when the `version` in its manifest changes. Work
  happens on a branch, and every merge into `main` is a release with its own number, so the
  commands a plugin carries always match the rites of the checkout beside it.
  [Plugin mode](agent_configuration.md#plugin-mode) owns the detail.

## Release steps

Write the release number wherever a step shows `X.Y.Z`.

1. **Choose the number.** Apply the compatibility rule in [governance](governance.md). The rule
   decides between PATCH, MINOR and MAJOR by what the release does to existing grimoires, not by
   its size. Governance also requires a person to approve a version change.
   - Done when: the number is chosen and approved.

2. **Pass the gate.** On the release branch, run:

   ```bash
   python -m pytest -q
   python rites/validate.py --summary
   ```

   Then run `/grm-dev-improve` in the assistant.
   - Done when: both commands exit 0 here, and CI is green for the branch on Linux and Windows.
   - Stop when: either command fails. Fix the cause on the branch; do not tag.

3. **Finish the changelog.** In `CHANGELOG.md`, replace `Unreleased` in the heading of this
   release's entry with the release date, so that it reads `## [X.Y.Z] - YYYY-MM-DD`. List every
   change a user can see under Added, Changed, Fixed or Removed, and state what an existing
   install or grimoire must do about it.
   - Done when: the first entry of the file carries the number and the date of this release.

4. **Set the version.** Write the number into `VERSION` and into the `version` field of
   `pyproject.toml`, then run `python rites/build_plugins.py --apply`, which writes it into both
   plugin manifests.
   - Done when: `python -m pytest -q tests/test_version_consistency.py` passes.

5. **Merge and tag.** Merge the release branch into `main`, then:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin main vX.Y.Z
   ```

   - Done when: the remote shows the tag on the head of `main`.

6. **Verify the install.** On a machine or in a scratch home folder that has no framework, run:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash
   ~/.grimoire/bin/grimoire summon --check
   cat ~/.grimoire/VERSION
   ```

   - Done when: the installer finishes, the check exits 0, and the last command prints the number
     of this release.
   - Stop when: the installer or the check fails. Do not announce the release.

7. **Announce.** State what a user does to receive the release: `/grm-update`. A Claude Code
   plugin install with auto-update on receives it by itself; one without runs
   `/plugin marketplace update grimoire`, then `/plugin update grimoire@grimoire`. [UPDATE.md](../UPDATE.md) owns what
   the update does.

## Forks and private mirrors

A mirror on a private host releases the same way: tag the mirror. Point an install at it with
`FRAMEWORK_URL`; [the installer](installation.md#the-installer) shows the command, and the
[summoning contract](summoning_contract.md#bootstrap-environment-controls) lists the variables.
