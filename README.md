# ACTA — Human-in-the-Loop Multi-Agent Crypto Trading Advisory System

> **Agents analyze. Agents advise. Humans decide. Only approved orders may execute.**

## Overview

ACTA is a multi-agent cryptocurrency trading advisory system that analyzes market data, generates trade proposals, and presents them to a human trader for approval. **No trade is ever executed without explicit human confirmation.**

### Key Principles

- 🛡️ **Human-in-the-loop**: Every trade requires explicit human approval
- 🤖 **Multi-agent analysis**: 5 specialized AI agents analyze market conditions
- 📊 **Deterministic risk engine**: Position sizing and risk checks use pure Python (no LLM)
- 🔒 **Security-first**: Agent Service cannot access trading API keys
- 📝 **Full audit trail**: Every action is logged and traceable

### Architecture

```
Market Data → Feature Engine → Multi-Agent Analysis → Signal Aggregator
    → Risk Engine → Trade Proposal → Human Approval → Execution
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 |
| Frontend | Vite, React, TypeScript, Zustand |
| Database | PostgreSQL 16 |
| Cache/Queue | Redis 7, Celery |
| LLM | Ollama (local) + Gemini/OpenAI (fallback) |
| Monitoring | Prometheus, Grafana |
| Auth | JWT + TOTP 2FA |

## Quick Start

### Prerequisites

- Docker + Docker Compose
- NVIDIA GPU with drivers (for Ollama)
- Git

### Setup

```bash
# Clone repository
git clone <repo-url>
cd agentic-crypto-trading-advisor

# Copy environment file
cp .env.example .env

# Start all services
docker compose up -d

# Check services are healthy
docker compose ps

# Apply database migrations
make db-upgrade

# Create admin user
make create-admin

# Pull LLM model (first time only, ~8GB)
make pull-model
```

### Access

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| Frontend | http://localhost:5173 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |

### Development

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# View logs
make logs
```

## Trading Modes

| Mode | Description |
|------|-------------|
| `PAPER` (default) | Uses real market data, simulates order execution |
| `LIVE` | Submits orders to Binance (requires trading API key) |
| `BACKTEST` | Tests strategy against historical data |

⚠️ **System always starts in PAPER mode.** Live trading requires explicit configuration.

## Project Structure

```
apps/
├── backend/         # FastAPI + Celery backend
│   ├── app/
│   │   ├── agents/      # Multi-agent system (ISOLATED)
│   │   ├── risk/        # Deterministic risk engine
│   │   ├── proposals/   # Proposal lifecycle
│   │   ├── approvals/   # Human approval flow (ISOLATED)
│   │   ├── execution/   # Order execution (MOST ISOLATED)
│   │   └── ...
│   └── tests/
└── frontend/        # Vite + React dashboard
```

## License

MIT