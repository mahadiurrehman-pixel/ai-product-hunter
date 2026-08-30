#!/usr/bin/env bash
set -e

echo "=== REHU Production Platform Starting ==="

# 1. Volume permissions
mkdir -p /app/data /app/data/cache /app/data/backups /app/logs
chmod -R 777 /app/data /app/data/cache /app/data/backups 2>/dev/null || true

# 2. Database init
echo "--> Initializing database..."
python -c "
import sys; sys.path.insert(0, '/app')
from database import init_db
init_db()
print('Database initialized.')
"

PIDS=""

cleanup() {
    echo "--> Shutting down all services..."
    for pid in $PIDS; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in $PIDS; do
        wait "$pid" 2>/dev/null || true
    done
    echo "--> All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# 3. Compliance Server (port 8080)
echo "--> Starting Compliance Server (port 8080)..."
python scripts/run_compliance_server.py &
PIDS="$PIDS $!"

# 4. Internal Engine API (port 8000) — Phase M1
echo "--> Starting Internal Python Engine (port 8000)..."
uvicorn engine_app:app --host 0.0.0.0 --port 8000 --log-level info &
PIDS="$PIDS $!"

# 5. Streamlit UI (port 8501)
echo "--> Starting Streamlit UI (port 8501)..."
streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --theme.primaryColor="#2563EB" \
    --theme.backgroundColor="#F8FAFC" &
PIDS="$PIDS $!"

echo "=== REHU Platform Ready ==="
echo "  UI:         http://0.0.0.0:8501"
echo "  Compliance: http://0.0.0.0:8080"
echo "  Engine API: http://0.0.0.0:8000"

# Wait for ANY child to exit (POSIX-compatible loop)
while true; do
    for pid in $PIDS; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "--> Process $pid exited unexpectedly."
            cleanup
        fi
    done
    sleep 2
done