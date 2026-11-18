#!/bin/bash
# rites/summon.sh
# Grimoire Summoning Rite - Bootstrap (Linux / macOS / Windows Git Bash)
#
# Thin source bootstrap: find Python 3.10+, fetch the dispatcher and its companion
# files when run from the public one-liner (a local checkout uses its own
# files), then hand off to rites/summon.py, which installs the framework, configures
# agents, and registers skills in the terminal, from source on a stock Python.
#
# FRAMEWORK_URL reaches the dispatcher only when the caller set it, so a local
# checkout's own origin stays detectable there. This script uses the public
# default for its own raw downloads.
#
# One-liner entry point:
#   curl -fsSL https://raw.githubusercontent.com/justinlavi/grimoire/main/rites/summon.sh | bash

set -euo pipefail

DEFAULT_FRAMEWORK_URL="https://github.com/justinlavi/grimoire.git"
DEFAULT_FRAMEWORK_REF="main"

: "${FRAMEWORK_REF:=$DEFAULT_FRAMEWORK_REF}"
: "${GRIMOIRE_SUMMON_CONNECT_TIMEOUT:=20}"
: "${GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS:=3}"
: "${GRIMOIRE_SUMMON_RETRY_DELAY:=2}"

SOURCE_URL="${FRAMEWORK_URL:-$DEFAULT_FRAMEWORK_URL}"
TEMP_DIR=""
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

echo "  [INFO]  Grimoire Summoning Rite bootstrap starting"

derive_raw_base() {
    local repo_url="$1"
    local ref="$2"

    if [[ "$repo_url" =~ ^https://github.com/([^/]+)/([^/.]+)(\.git)?$ ]]; then
        echo "https://raw.githubusercontent.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/$ref"
    else
        echo "https://raw.githubusercontent.com/justinlavi/grimoire/$ref"
    fi
}

: "${FRAMEWORK_RAW_BASE:=$(derive_raw_base "$SOURCE_URL" "$FRAMEWORK_REF")}"

# The same search bin/grimoire and session_context.sh run: the first of python3,
# python, py -3 that proves it is Python 3.10 or newer.
find_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    if command -v py >/dev/null 2>&1; then
        if py -3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            echo "py -3"
            return 0
        fi
    fi
    return 1
}

python_download_file() {
    local url="$1"
    local dest="$2"
    local py

    py="$(find_python)" || return 1

    # shellcheck disable=SC2086  # py may be "py -3"
    $py - "$url" "$dest" "$GRIMOIRE_SUMMON_CONNECT_TIMEOUT" <<'PY'
import sys
from urllib.request import urlopen

url, dest, timeout = sys.argv[1], sys.argv[2], int(sys.argv[3])
with urlopen(url, timeout=timeout) as response, open(dest, "wb") as out:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        out.write(chunk)
PY
}

download_with_retries() {
    local url="$1"
    local dest="$2"
    local label="${3:-$(basename "$dest")}"
    local attempt=1
    local temp_dest="$dest.part"
    local output=""

    rm -f "$temp_dest"
    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        echo "  [INFO]  Neither curl nor wget is installed; downloading $label with Python"
        attempt=$((GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS + 1))
    fi
    while (( attempt <= GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS )); do
        output=""
        echo "  [INFO]  Download attempt $attempt/$GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS: $label"

        if command -v curl &>/dev/null; then
            output="$(curl -fsSL --connect-timeout "$GRIMOIRE_SUMMON_CONNECT_TIMEOUT" \
                "$url" -o "$temp_dest" 2>&1)" && {
                mv "$temp_dest" "$dest"
                return 0
            }
        elif command -v wget &>/dev/null; then
            output="$(wget -q --timeout="$GRIMOIRE_SUMMON_CONNECT_TIMEOUT" --tries=1 \
                -O "$temp_dest" "$url" 2>&1)" && {
                mv "$temp_dest" "$dest"
                return 0
            }
        fi

        rm -f "$temp_dest"
        if [[ -n "$output" ]]; then
            echo "  [WARN]  Download failed: $output"
        else
            echo "  [WARN]  Download failed: $label"
        fi

        if (( attempt < GRIMOIRE_SUMMON_DOWNLOAD_ATTEMPTS )); then
            echo "  [INFO]  Retrying in ${GRIMOIRE_SUMMON_RETRY_DELAY}s..."
            sleep "$GRIMOIRE_SUMMON_RETRY_DELAY"
        fi
        attempt=$((attempt + 1))
    done

    echo "  [INFO]  Trying Python download fallback for $label..."
    if python_download_file "$url" "$temp_dest"; then
        mv "$temp_dest" "$dest"
        return 0
    fi
    rm -f "$temp_dest"

    echo "  [WARN]  Exhausted download attempts for $label"
    return 1
}

download_file() {
    download_with_retries "$1" "$2" "${3:-$(basename "$2")}"
}

# ---------------------------------------------------------------------------
# 1. Locate the dispatcher: local checkout, or fetch the companion scripts
# ---------------------------------------------------------------------------

if [[ -n "$SCRIPT_SOURCE" && -f "$SCRIPT_SOURCE" && -f "$(dirname "$SCRIPT_SOURCE")/summon.py" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
else
    TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/grimoire-summon.XXXXXX")"
    SCRIPT_DIR="$TEMP_DIR/rites"
    mkdir -p "$SCRIPT_DIR/templates" "$SCRIPT_DIR/data"
    echo "  [INFO]  Downloading summoning companion scripts..."
    # summon.py is the dispatcher and summon_core.py is the install core.
    # The agent-target registry and the Grimoire routing block template must
    # travel with a source bootstrap install.
    download_file "$FRAMEWORK_RAW_BASE/rites/summon.py" "$SCRIPT_DIR/summon.py"
    download_file "$FRAMEWORK_RAW_BASE/rites/summon_core.py" "$SCRIPT_DIR/summon_core.py"
    download_file "$FRAMEWORK_RAW_BASE/rites/agent_targets.py" "$SCRIPT_DIR/agent_targets.py"
    download_file "$FRAMEWORK_RAW_BASE/rites/data/agent_targets.json" "$SCRIPT_DIR/data/agent_targets.json"
    download_file "$FRAMEWORK_RAW_BASE/rites/templates/grimoire_block.md" "$SCRIPT_DIR/templates/grimoire_block.md"
fi

# ---------------------------------------------------------------------------
# 2. Find or install Python 3.10+ (install only with explicit consent)
# ---------------------------------------------------------------------------

detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf &>/dev/null; then echo "dnf"
    elif command -v pacman &>/dev/null; then echo "pacman"
    elif command -v brew &>/dev/null; then echo "brew"
    else echo ""; fi
}

install_packages() {
    local mgr="$1"; shift
    case "$mgr" in
        apt)    sudo apt-get update -qq && sudo apt-get install -y "$@" ;;
        dnf)    sudo dnf install -y "$@" ;;
        pacman) sudo pacman -S --needed --noconfirm "$@" ;;
        brew)   brew install "$@" ;;
        *)      return 1 ;;
    esac
}

prompt_yes() {
    local prompt="$1"
    local response=""

    if [[ -t 0 ]]; then
        read -r -p "$prompt [y/N]: " response || response=""
    elif [[ -r /dev/tty && -w /dev/tty ]]; then
        printf "%s [y/N]: " "$prompt" > /dev/tty
        IFS= read -r response < /dev/tty || response=""
    else
        echo "  [WARN]  No interactive terminal available - not installing dependencies"
        return 1
    fi

    [[ "$response" == [yY] ]]
}

PYTHON=""
if ! PYTHON=$(find_python); then
    echo ""
    echo "  Python 3.10 or newer is required but not found."
    echo ""

    PKG_MGR=$(detect_pkg_manager)
    if [[ -z "$PKG_MGR" ]]; then
        echo "  Could not detect a package manager. Install Python 3 from python.org and re-run."
        exit 1
    fi

    if ! prompt_yes "  Install Python 3 now? (requires sudo)"; then
        echo "  Install Python 3 manually and re-run."
        exit 1
    fi

    case "$PKG_MGR" in
        apt)    install_packages "$PKG_MGR" python3 ;;
        dnf)    install_packages "$PKG_MGR" python3 ;;
        pacman) install_packages "$PKG_MGR" python ;;
        brew)   install_packages "$PKG_MGR" python3 ;;
    esac

    if ! PYTHON=$(find_python); then
        echo "  [ERROR] Python 3 installation failed. Install manually and re-run."
        exit 1
    fi
    echo "  [OK]    Python 3 installed: $($PYTHON --version 2>&1)"
fi

echo "  [OK]    Using $($PYTHON --version 2>&1)"
echo ""

# ---------------------------------------------------------------------------
# 3. Hand off to the dispatcher
# ---------------------------------------------------------------------------

# Not exec: the EXIT trap removes the downloaded companion files after the
# dispatcher returns. The whole line is read before it runs, so a dispatcher that
# reads stdin cannot swallow the rest of a piped script.
# shellcheck disable=SC2086  # PYTHON may be "py -3"
status=0; $PYTHON "$SCRIPT_DIR/summon.py" "$@" || status=$?; exit "$status"
