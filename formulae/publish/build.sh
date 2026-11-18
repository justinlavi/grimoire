#!/usr/bin/env bash
# Builds this grimoire's site in four steps: stage, audit, generate, audit the
# output. The steps are the same on a person's computer and in CI. A blocker
# from either audit, or a failed step, ends the script with a non-zero exit.
#
#   bash publish/build.sh            # full build into publish/quartz/public
#   bash publish/build.sh --check    # stage and audit only, no generator
#
# Requirements: git and Python 3.10+; a full build also needs Node.js 22+ and
# npm, for Quartz.
#
# The framework is the one at $FRAMEWORK_HOME, else ~/.grimoire, else a clone
# in publish/.framework/ (the CI case). Quartz is a clone in publish/quartz/,
# made when absent or when QUARTZ_REPO or QUARTZ_REF differ from the ones the
# clone was made from; its node_modules/ and .quartz/ folders survive a new
# clone. publish/quartz.config.yaml is this grimoire's own configuration and
# replaces the clone's on every build.
#
# Environment: FRAMEWORK_HOME; FRAMEWORK_URL (the framework clone source,
# default https://github.com/justinlavi/grimoire.git); FRAMEWORK_REF (branch or
# tag, default main); QUARTZ_REPO (default
# https://github.com/jackyzha0/quartz.git); QUARTZ_REF (default v5.1.0).

set -euo pipefail

PUBLISH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRIMOIRE_ROOT="$(cd "$PUBLISH_ROOT/.." && pwd)"

CHECK_ONLY=""
case "$#:${1:-}" in
    0:) ;;
    1:--check) CHECK_ONLY=1 ;;
    *)
        echo "usage: bash publish/build.sh [--check]" >&2
        exit 2
        ;;
esac

: "${FRAMEWORK_URL:=https://github.com/justinlavi/grimoire.git}"
: "${FRAMEWORK_REF:=main}"
: "${QUARTZ_REPO:=https://github.com/jackyzha0/quartz.git}"
: "${QUARTZ_REF:=v5.1.0}"

# 1. Framework
if [[ -n "${FRAMEWORK_HOME:-}" && -d "${FRAMEWORK_HOME}/rites" ]]; then
    FRAMEWORK="$FRAMEWORK_HOME"
elif [[ -d "$HOME/.grimoire/rites" ]]; then
    FRAMEWORK="$HOME/.grimoire"
else
    FRAMEWORK="$PUBLISH_ROOT/.framework"
    if [[ ! -d "$FRAMEWORK/rites" ]]; then
        echo "  [INFO]  Cloning the framework into publish/.framework/"
        git clone --quiet --depth 1 --branch "$FRAMEWORK_REF" "$FRAMEWORK_URL" "$FRAMEWORK"
    fi
fi
LAUNCHER="$FRAMEWORK/bin/grimoire"
echo "  [OK]    Framework: $FRAMEWORK"

# 2. Stage and audit the content. The stage rite names the content directory
# in its JSON summary, relative to the grimoire.
if ! STAGE_JSON="$("$LAUNCHER" stage_publish --grimoire "$GRIMOIRE_ROOT" --apply --format json)"; then
    echo "  [ERROR] Staging was refused:" >&2
    echo "$STAGE_JSON" >&2
    exit 1
fi
CONTENT_REL="$(printf '%s\n' "$STAGE_JSON" | sed -n '/"content_dir"/{s/^[^:]*: *"\([^"]*\)".*$/\1/p;q;}')"
case "$CONTENT_REL" in
    ""|*\\*)
        echo "  [ERROR] The stage rite's summary does not hold a plain content_dir" >&2
        exit 1
        ;;
esac
CONTENT="$GRIMOIRE_ROOT/$CONTENT_REL"
echo "  [OK]    Staged into $CONTENT_REL"
"$LAUNCHER" audit_publish --grimoire "$GRIMOIRE_ROOT" --mode content

if [[ -n "$CHECK_ONLY" ]]; then
    echo "  [OK]    Check complete (no generator run)."
    exit 0
fi

# 3. Generator
QUARTZ="$PUBLISH_ROOT/quartz"
CONFIG="$PUBLISH_ROOT/quartz.config.yaml"
if [[ ! -f "$CONFIG" ]]; then
    echo "  [ERROR] publish/quartz.config.yaml is missing; run /grm-publish init to create it" >&2
    exit 1
fi
if grep -q '{{[^}]*}}' "$CONFIG"; then
    echo "  [ERROR] publish/quartz.config.yaml still holds a {{...}} placeholder; fill in pageTitle and baseUrl" >&2
    exit 1
fi

QUARTZ_SOURCE="$QUARTZ_REPO $QUARTZ_REF"
if [[ ! -f "$QUARTZ/package.json" || "$(cat "$QUARTZ/.grimoire-quartz-source" 2>/dev/null || true)" != "$QUARTZ_SOURCE" ]]; then
    echo "  [INFO]  Cloning Quartz ($QUARTZ_REF) into publish/quartz/"
    FRESH="$PUBLISH_ROOT/.quartz-clone"
    rm -rf "$FRESH"
    git clone --quiet --depth 1 --branch "$QUARTZ_REF" "$QUARTZ_REPO" "$FRESH"
    for kept in node_modules .quartz; do
        if [[ -d "$QUARTZ/$kept" ]]; then
            rm -rf "${FRESH:?}/$kept"
            mv "$QUARTZ/$kept" "$FRESH/$kept"
        fi
    done
    rm -rf "$QUARTZ"
    mv "$FRESH" "$QUARTZ"
    printf '%s\n' "$QUARTZ_SOURCE" > "$QUARTZ/.grimoire-quartz-source"
fi
cp "$CONFIG" "$QUARTZ/quartz.config.yaml"

command -v node >/dev/null 2>&1 || { echo "  [ERROR] Node.js 22 or later is required for Quartz" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "  [ERROR] npm is required for Quartz" >&2; exit 1; }
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$NODE_MAJOR" -lt 22 ]]; then
    echo "  [ERROR] Node.js $(node -v) found; Quartz 5 needs Node.js 22 or later (nvm/fnm: install 22, then re-run)" >&2
    exit 1
fi

(
    cd "$QUARTZ"
    if [[ -f package-lock.json ]]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
    npx quartz plugin install
    # Quartz reads its own content/ folder; a directory outside the clone
    # yields zero input files, so the staged copy is placed there.
    rm -rf content
    cp -R "$CONTENT" content
    npx quartz build
)

# 4. Audit the generated site
"$LAUNCHER" audit_publish --grimoire "$GRIMOIRE_ROOT" --mode static-output --target "$QUARTZ/public"
echo "  [OK]    Site built at $QUARTZ/public"
