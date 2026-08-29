#!/usr/bin/env bash
set -e

echo "=== REHU Production Platform Starting ==="

# 1. Create and grant permissions on volume mount
mkdir -p /app/data /app/data/cache /app/data/backups /app/logs
chmod -R 777 /app/data /app/data/cache /app/data/backups 2>/dev/null || true

# 2. Initialize database schema
echo "--> Initializing database..."
python -c "
import sys
sys.path.insert(0, '/app')
from database import init_db
init_db()
print('Database initialized.')
"

# 3. Start eBay Compliance Server in background
echo "--> Starting Compliance Server (port 8080)..."
python scripts/run_compliance_server.py &
COMPLIANCE_PID=$!

# 4. Start Streamlit UI in foreground
echo "--> Starting Streamlit UI (port 8501)..."
streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --theme.primaryColor="#2563EB" \
    --theme.backgroundColor="#F8FAFC" &
STREAMLIT_PID=$!

cleanup() {
    echo "--> Shutting down..."
    kill -TERM "$COMPLIANCE_PID" 2>/dev/null || true
    kill -TERM "$STREAMLIT_PID" 2>/dev/null || true
    wait "$COMPLIANCE_PID" 2>/dev/null || true
    wait "$STREAMLIT_PID" 2>/dev/null || true
    echo "--> All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "=== REHU Platform Ready ==="
echo "  UI:         http://0.0.0.0:8501"
echo "  Compliance: http://0.0.0.0:8080"

wait -n "$COMPLIANCE_PID" "$STREAMLIT_PID"
EXIT_CODE=$?
echo "--> A service exited unexpectedly (code $EXIT_CODE). Shutting down."
cleanup