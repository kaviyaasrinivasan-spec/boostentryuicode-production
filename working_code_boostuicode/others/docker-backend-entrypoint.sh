#!/usr/bin/env bash
set -euo pipefail

# PDF Storage Path
export PDF_STORAGE_PATH="${PDF_STORAGE_PATH:-/app/pdf_storage}"
mkdir -p "$PDF_STORAGE_PATH"

echo "🔵 Starting FastAPI (watch_and_send.py) on port 30011..."
python watch_and_send.py --port 30011 > /app/fastapi.log 2>&1 &
FASTAPI_PID=$!
sleep 2

echo "🟢 Starting Flask API on port 30010..."
python app.py > /app/flask.log 2>&1 &
API_PID=$!
sleep 3

echo "📱 Starting Telegram Listener..."
python telegram_user_client.py > /app/telegram.log 2>&1 &
TELEGRAM_PID=$!

echo ""
echo "============================================"
echo "✅ All services started!"
echo "   FastAPI:   PID $FASTAPI_PID (port 30011)"
echo "   Flask API: PID $API_PID (port 30010)"
echo "   Telegram:  PID $TELEGRAM_PID"
echo "============================================"
echo ""
echo "📁 PDF Storage: $PDF_STORAGE_PATH"
echo ""
echo "📋 Logs available at:"
echo "   /app/fastapi.log"
echo "   /app/flask.log"
echo "   /app/telegram.log"
echo ""
echo "🔄 Container is running. Press Ctrl+C to stop."

# Graceful shutdown handler
cleanup() {
  echo ""
  echo "🔻 Stopping services..."
  kill -TERM "$FASTAPI_PID" 2>/dev/null || true
  kill -TERM "$API_PID" 2>/dev/null || true
  kill -TERM "$TELEGRAM_PID" 2>/dev/null || true
  wait
  echo "✅ Services stopped."
}
trap cleanup SIGINT SIGTERM

# Wait for processes
wait $FASTAPI_PID $API_PID $TELEGRAM_PID
