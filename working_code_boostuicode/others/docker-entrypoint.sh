#!/usr/bin/env bash
set -euo pipefail

API_DIR="${API_DIR:-/app}"
UI_DIR="${UI_DIR:-/app}"
API_CMD="${API_CMD:-python app.py}"

# Ports
UI_PORT="${UI_PORT:-30012}"
FASTAPI_PORT="${FASTAPI_PORT:-30011}"
UI_DEV_CMD="${UI_DEV_CMD:-npm run dev -- --host 0.0.0.0 --port ${UI_PORT}}"

# PDF Storage Path (inside container - maps to /root/boostentry_pdf via volume)
export PDF_STORAGE_PATH="${PDF_STORAGE_PATH:-/app/pdf_storage}"
mkdir -p "$PDF_STORAGE_PATH"

export PATH="$UI_DIR/node_modules/.bin:$PATH"

# ========================================
# 1. Start FastAPI (watch_and_send.py) on port 30011
# ========================================
echo "🔵 Starting FastAPI on port ${FASTAPI_PORT}..."
cd "$API_DIR"
python3 watch_and_send.py --port ${FASTAPI_PORT} > /app/fastapi.log 2>&1 &
FASTAPI_PID=$!
sleep 2

# ========================================
# 2. Start Flask API (includes WhatsApp webhook + reminder scheduler)
# ========================================
echo "🟢 Starting Flask API on port 30010..."
echo "   📱 WhatsApp webhook: /api/whatsapp/webhook"
echo "   ⏰ Reminder scheduler: Active (3 hours)"
cd "$API_DIR"
$API_CMD > /app/flask.log 2>&1 &
API_PID=$!
sleep 3

# ========================================
# 3. Start React Frontend (Vite)
# ========================================
echo "🟣 Starting React UI (Vite) on port ${UI_PORT}..."
cd "$UI_DIR"

# If node_modules was replaced (e.g., volume), reinstall
if [ ! -d node_modules ]; then
  echo "📦 node_modules missing — running npm ci..."
  npm ci
fi

echo ""
echo "============================================"
echo "✅ All services started!"
echo "   FastAPI:    http://0.0.0.0:${FASTAPI_PORT} (PID: $FASTAPI_PID)"
echo "   Flask API:  http://0.0.0.0:30010 (PID: $API_PID)"
echo "   Frontend:   http://0.0.0.0:${UI_PORT}"
echo "============================================"
echo ""
echo "📁 PDF Storage: ${PDF_STORAGE_PATH}"
echo ""
echo "📱 WhatsApp Integration:"
echo "   - Webhook URL: http://YOUR_SERVER_IP:30010/api/whatsapp/webhook"
echo "   - Reminders: Automatic (every 3 hours)"
echo "============================================"
echo ""
echo "📋 Log files:"
echo "   - Flask:   /app/flask.log"
echo "   - FastAPI: /app/fastapi.log"
echo "============================================"

# Graceful shutdown handler
cleanup() {
  echo ""
  echo "🔻 Stopping services..."
  if ps -p "$FASTAPI_PID" > /dev/null 2>&1; then
     kill -TERM "$FASTAPI_PID" || true
     wait "$FASTAPI_PID" 2>/dev/null || true
  fi
  if ps -p "$API_PID" > /dev/null 2>&1; then
     kill -TERM "$API_PID" || true
     wait "$API_PID" 2>/dev/null || true
  fi
  echo "✅ Services stopped."
}
trap cleanup SIGINT SIGTERM

# Run frontend in foreground (keeps container alive)
exec $UI_DEV_CMD
