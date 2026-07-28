#!/usr/bin/env bash
# ==============================================================================
# ACTA Trading Advisory System — Quick Startup Script
# Usage: ./start.sh
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "[1/4] Starting Docker Infrastructure (PostgreSQL, Redis, Prometheus, Grafana)..."
docker compose up -d postgres redis prometheus grafana

echo "[2/4] Starting Ollama Server with qwen3:14b..."
if pgrep -x "ollama" > /dev/null; then
    echo "   ↳ Ollama server is already running."
else
    OLLAMA_MODELS=/usr/share/ollama/.ollama/models nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    echo "   ↳ Ollama started successfully."
fi

echo "[3/4] Starting Backend FastAPI Server (:8000)..."
if lsof -i:8000 > /dev/null 2>&1; then
    echo "   ↳ Backend port 8000 is already in use."
else
    cd "$PROJECT_ROOT/apps/backend"
    source .venv/bin/activate
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/acta_backend.log 2>&1 &
    cd "$PROJECT_ROOT"
    sleep 3
    echo "   ↳ Backend started successfully."
fi

echo "[4/4] Starting Frontend React Server (:5173)..."
if lsof -i:5173 > /dev/null 2>&1; then
    echo "   ↳ Frontend port 5173 is already in use."
else
    cd "$PROJECT_ROOT/apps/frontend"
    nohup npm run dev -- --host 0.0.0.0 > /tmp/acta_frontend.log 2>&1 &
    cd "$PROJECT_ROOT"
    sleep 3
    echo "   ↳ Frontend started successfully."
fi

echo ""
echo "=============================================================================="
echo "ALL ACTA SERVICES ARE UP AND RUNNING!"
echo "=============================================================================="
echo "Frontend Dashboard : http://localhost:5173"
echo "Backend API Docs   : http://localhost:8000/api/docs"
echo "Grafana Monitoring : http://localhost:3001 (admin/acta_grafana)"
echo "Prometheus Metrics : http://localhost:9090"
echo "Ollama Model Server: http://localhost:11434"
echo "=============================================================================="
echo " Logs location:"
echo "   - Backend  : tail -f /tmp/acta_backend.log"
echo "   - Frontend : tail -f /tmp/acta_frontend.log"
echo "   - Ollama   : tail -f /tmp/ollama.log"
echo "=============================================================================="
