#!/usr/bin/env bash
set -euo pipefail

API_DIR="${API_DIR:-/app}"
UI_DIR="${UI_DIR:-/app}"
API_CMD="${API_CMD:-python app.py}"

# Change UI port here if needed
UI_PORT="${UI_PORT:-30012}"
UI_DEV_CMD="${UI_DEV_CMD:-npm run dev -- --host 0.0.0.0 --port ${UI_PORT}}"

export PATH="$UI_DIR/node_modules/.bin:$PATH"

echo "🟢 Starting Flask API on port 30010..."
cd "$API_DIR"

# Start API SAFELY and capture PID properly
$API_CMD > /app/flask.log 2>&1 &
API_PID=$!

sleep 2

echo "🟣 Starting React UI (Vite) on port ${UI_PORT}..."
cd "$UI_DIR"

# If node_modules was replaced (e.g., volume), reinstall
if [ ! -d node_modules ]; then
  echo "📦 node_modules missing — running npm ci..."
  npm ci
fi

# Graceful shutdown handler
cleanup() {
  echo "🔻 Stopping API..."
  if ps -p "$API_PID" > /dev/null 2>&1; then
     kill -TERM "$API_PID" || true
     wait "$API_PID" || true
  fi
}
trap cleanup SIGINT SIGTERM

exec $UI_DEV_CMD
