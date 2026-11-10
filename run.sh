#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== CareerOS (interniq) Intelligent Job Discovery Engine ==="

# Check Ollama
if command -v ollama >/dev/null 2>&1; then
    echo "✓ Ollama is available."
fi

# Start Backend on Port 8005
echo "Starting FastAPI Backend on http://127.0.0.1:8005..."
export PYTHONPATH=.
backend/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8005 &
BACKEND_PID=$!

# Start Frontend on Port 5174
echo "Starting Vite Frontend on http://127.0.0.1:5174..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174 &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT

wait
