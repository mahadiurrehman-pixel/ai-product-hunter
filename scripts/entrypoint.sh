#!/usr/bin/env bash
set -euo pipefail

echo "=== REHU Production Platform Starting ==="

echo "--> Preparing persistent storage..."

mkdir -p /app/data/cache
mkdir -p /app/data/exports
mkdir -p /app/logs

chown -R rehu:rehu /app/data /app/logs

echo "--> Storage permissions ready."

echo "--> Initializing database..."

su -s /bin/bash rehu -c '
python -c "
import sys
sys.path.insert(0, \"/app\")
from database import init_db
init_db()
print(\"Database initialized.\")
"
'

echo "--> Starting Compliance Server (port 8080)..."
su -s /bin/bash rehu -c \
    "python scripts/run_compliance_server.py" &
COMPLIANCE_PID=$!

echo "--> Starting Streamlit UI (port 8501)..."
su -s /bin/bash rehu -c \
    "streamlit run app.py \
        --server.port=8501 \
        --server.address=0.0.0.0 \
        --server.headless=true \
        --browser.gatherUsageStats=false" &
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