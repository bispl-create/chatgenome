#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/with-local-node.sh"

exec "$WRAPPER" ./node_modules/.bin/next build
