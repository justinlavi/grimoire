#!/usr/bin/env bash
# Build this grimoire's site: stage, audit, generate, audit the output.
#
# Runs locally and in CI with the same steps. It needs git, Python 3.10+, and
# Node.js 22+ (for Quartz). The framework is taken from $FRAMEWORK_HOME,
# then ~/.grimoire, and otherwise cloned into publish/.framework/ (CI).
# Quartz is cloned into publish/quartz/ when absent; publish/quartz.config.yaml
# is this grimoire's own configuration and is copied over the clone's.
#
#   bash publish/build.sh            # full build into publish/quartz/public
#   bash publish/build.sh --check    # stage and audit only, no generator
#
# Environment: FRAMEWORK_HOME, FRAMEWORK_URL (framework clone source), FRAMEWORK_REF (branch or tag, default main),
# QUARTZ_REPO (default https://github.com/jackyzha0/quartz.git), QUARTZ_REF (default v5.1.0).

set -euo pipefail

PUBLISH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRIMOIRE_ROOT="$(cd "$PUBLISH_ROOT/.." && pwd)"
CHECK_ONLY="${1:-}"

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

# 2. Stage and audit the content
"$LAUNCHER" stage_publish --grimoire "$GRIMOIRE_ROOT" --apply
"$LAUNCHER" audit_publish --grimoire "$GRIMOIRE_ROOT" --mode content

if [[ "$CHECK_ONLY" == "--check" ]]; then
    echo "  [OK]    Check complete (no generator run)."
    exit 0
fi

# 3. Generator
QUARTZ="$PUBLISH_ROOT/quartz"
CONTENT="$PUBLISH_ROOT/content"
if [[ ! -f "$QUARTZ/package.json" ]]; then
    echo "  [INFO]  Cloning Quartz ($QUARTZ_REF) into publish/quartz/"
    rm -rf "$QUARTZ"
    git clone --quiet --depth 1 --branch "$QUARTZ_REF" "$QUARTZ_REPO" "$QUARTZ"
fi
if [[ ! -f "$PUBLISH_ROOT/quartz.config.yaml" ]]; then
    echo "  [ERROR] publish/quartz.config.yaml is missing; run /grm-publish init to create it" >&2
    exit 1
fi
cp "$PUBLISH_ROOT/quartz.config.yaml" "$QUARTZ/quartz.config.yaml"

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
