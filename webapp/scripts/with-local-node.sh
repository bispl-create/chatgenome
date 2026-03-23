#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBAPP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_NODE_BIN="/Users/jongcye/Documents/Codex/.local/node/node-v22.22.1-darwin-arm64/bin"

if [ ! -x "$LOCAL_NODE_BIN/node" ]; then
  echo "Local node binary not found at: $LOCAL_NODE_BIN/node" >&2
  exit 1
fi

export PATH="$LOCAL_NODE_BIN:$PATH"
cd "$WEBAPP_DIR"
exec "$@"
