#!/usr/bin/env bash
set -euo pipefail

echo "=== REHU Production Platform Starting ==="

mkdir -p /app/data

echo "--> Initializing database..."
python -c "
import sys; sys.path.insert(0, '/app')
from database import init_db
init_db()
print('Database initialized.')
"

echo "--> Starting Compliance Server (port 8080)..."
python scripts/run_compliance_server.py &
COMPLIANCE_PID=$!

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
echo "  UI:         http://localhost:8501"
echo "  Compliance: http://localhost:8080"

wait -n "$COMPLIANCE_PID" "$STREAMLIT_PID"
EXIT_CODE=$?
echo "--> A service exited unexpectedly (code $EXIT_CODE). Shutting down."
cleanup