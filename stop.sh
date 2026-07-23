#!/usr/bin/env bash
# ==============================================================================
# ACTA Trading Advisory System — Quick Stop Script
# Usage: ./stop.sh
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "🛑 Stopping ACTA services..."

# Kill backend
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "   ↳ Backend stopped." || echo "   ↳ Backend was not running."

# Kill frontend
pkill -f "vite --host" 2>/dev/null && echo "   ↳ Frontend stopped." || echo "   ↳ Frontend was not running."

# Kill Ollama (optional)
# pkill -f "ollama serve" 2>/dev/null && echo "   ↳ Ollama stopped." || echo "   ↳ Ollama was not running."

# Stop Docker containers
docker compose stop postgres redis prometheus grafana && echo "   ↳ Docker containers stopped."

echo "✅ All ACTA services stopped successfully!"
