#!/usr/bin/env bash
# Shared helpers for the packaging scripts. Source it, do not run it:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

# Absolute path of the repository root (this file lives in <root>/packaging/lib).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The application version; defined once, in core/version.py.
app_version() {
    local v
    v="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$REPO_ROOT/core/version.py")"
    [ -n "$v" ] || { echo "error: could not read the version from core/version.py" >&2; return 1; }
    printf '%s\n' "$v"
}

# Machine architecture in the spelling release files use: x86_64 | arm64 | aarch64 as `uname -m` says.
machine_arch() { uname -m; }

die() { echo "error: $*" >&2; exit 1; }
