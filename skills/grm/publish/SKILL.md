---
name: {{SKILL_PREFIX}}-publish
description: Turn your grimoire into a website by setting up publishing once, building the site, or checking what would be published
when_to_use: The user wants a web version of the grimoire, wants it on GitLab Pages, GitHub Pages or Cloudflare, or asks whether anything private would be exposed. The user says "publish the grimoire", "make a website", "set up pages", "build the site" or "is it safe to publish".
argument-hint: "[init <gitlab-pages|github-pages|cloudflare> | build | check]"
arguments: scope
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Publish

Turn the active grimoire into a website, or check what would be published. Follow the playbook below exactly. The scope, if given: **$scope**

## Precondition

!`cat {{FRAMEWORK_PATH}}/invocations/meta/grimoire_directory_guard.md`

## Invocation

!`cat {{FRAMEWORK_PATH}}/invocations/grm/publish.md`
