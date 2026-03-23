#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/with-local-node.sh"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-3003}"

exec "$WRAPPER" ./node_modules/.bin/next dev -H "$HOST" -p "$PORT"
