---
type: reference
title: "Cloudflare Build Settings"
aliases: ["cloudflare-pages", "cloudflare-publish"]
tags: [type/reference, framework/formula, scope/publish]
authority: grimoire
last_verified: 2026-11-14
---

# Cloudflare: build settings

The values a grimoire's owner enters in Cloudflare so that Workers Builds (or
Pages) builds the site on every push and serves `publish/quartz/public`.
`/grm-publish init cloudflare` shows this page and writes
`publish/wrangler.jsonc`; [[invocations/grm/publish|publish]] owns that
procedure.

## Build settings

| Setting | Value |
|---|---|
| Framework preset | None |
| Production branch | The repository's default branch |
| Build command | `bash publish/build.sh` |
| Deploy command | `cd publish && npx wrangler deploy` |
| Build output directory | `publish/quartz/public` |
| Root directory | The repository root |

| Environment variable | Value |
|---|---|
| `NODE_VERSION` | `22` |
| `FRAMEWORK_URL` | The framework repository the build clones. Set it only for a mirror. |
| `FRAMEWORK_REF` | The framework branch or tag. Default `main`. |
| `QUARTZ_REPO`, `QUARTZ_REF` | The Quartz repository and tag. Set them only to pin or mirror Quartz. |

## `publish/wrangler.jsonc`

The file names the Worker, the directory of static assets and the custom
domains. `assets.directory` is relative to `publish/`.

```jsonc
{
  "name": "<grimoire-name>",
  "compatibility_date": "2026-01-01",
  "assets": { "directory": "./quartz/public" },
  "routes": [
    { "pattern": "<your-domain>", "custom_domain": true }
  ]
}
```

## Access control

Put Cloudflare Access in front of the site before sharing its address, and
keep it on while the site is deployed. The audit passes its warnings on the
condition that the site sits behind access control.

1. In Cloudflare Zero Trust, create a self-hosted application for the site's
   hostname.
2. Choose an identity provider. The email one-time PIN needs nothing but an
   inbox.
3. Add an Allow policy for the approved addresses.
4. Open the site with an address that is not approved. Done when Cloudflare
   refuses it.
