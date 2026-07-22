# ACTA — Agentic Crypto Trading Advisor

> **Human-in-the-Loop Multi-Agent Crypto Trading Advisory System**
>
> _Agents analyze. Agents advise. **Humans decide.**_

[![Tests](https://img.shields.io/badge/tests-220%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Overview

ACTA is a **paper trading advisory system** that uses a 5-agent AI pipeline to analyze cryptocurrency markets and generate human-reviewable trade proposals. Every execution requires **explicit human approval** through a cryptographically secured approval flow.

```
Binance Market Data
       │
       ▼
  5 AI Agents (Multi-LLM)
       │
       ▼
  Trade Proposal (DRAFT)
       │
       ▼
  Human Dashboard (Approve/Reject)
       │
       ▼
  Paper Trade Execution
```

## Key Features

| Feature | Description |
|---------|-------------|
| **5-Agent Pipeline** | Market Regime → Technical → Order Flow → Risk Analysis → Critic |
| **HITL Approval** | Every trade requires HMAC-signed token approval (30s TTL) |
| **Price Drift Guard** | Auto re-confirmation if price moves > 20bps after approval |
| **Paper Trading** | Full simulation with slippage, fees, position tracking |
| **Real-time Dashboard** | WebSocket-driven React UI with live proposal updates |
| **Security** | JWT + TOTP 2FA, encrypted API keys, import boundaries enforced |
| **Audit Trail** | Full version history for every proposal state change |

## Architecture

```
┌─────────────────────────────────────────────┐
│  React Frontend (Vite + TypeScript)          │
│  ws://host/api/v1/ws/events                  │
└─────────────────────────────┬───────────────┘
                              │
┌─────────────────────────────▼───────────────┐
│  FastAPI Backend                             │
│  ├── REST API  (/api/v1/*)                  │
│  ├── WebSocket (/api/v1/ws/*)               │
│  ├── Agents    (5 AI agents + orchestrator) │
│  ├── Risk      (deterministic engine)        │
│  ├── Proposals (state machine + approval)   │
│  └── Execution (paper fill simulator)        │
├─────────────────────────────────────────────┤
│  PostgreSQL + Redis + Prometheus             │
└─────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker + Docker Compose v2
- NVIDIA GPU (optional, for Ollama local LLM)
- Binance API keys (read-only recommended for paper trading)

### Setup

```bash
# 1. Clone
git clone <repo-url>
cd bot-finance

# 2. Configure
cp apps/backend/.env.example apps/backend/.env
# Edit .env with your API keys

# 3. Start
docker compose up -d

# 4. Create admin user
docker compose exec backend python scripts/create_admin.py

# 5. Access
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/api/docs
# Grafana:  http://localhost:3000
```

### Development

```bash
# Backend
cd apps/backend
pip install -e ".[dev]"
uvicorn app.main:create_app --factory --reload

# Frontend
cd apps/frontend
npm install
npm run dev

# Run tests
cd apps/backend
PYTHONPATH=. pytest tests/unit/ tests/security/ -v

# Import boundary check
python scripts/check_import_boundaries.py
```

## Approval Flow

```
1. Analysis complete → Proposal created (PENDING_REVIEW)
2. Dashboard shows proposal with 10-minute expiry countdown
3. Human clicks [Approve]
   → System issues 30-second HMAC-signed token
   → Token binds: proposal_id + user_id + price + quantity + stop_loss
4. Human enters current market price + confirms
5. System validates:
   a. Token signature (HMAC-SHA256)
   b. Token not expired (< 30s)
   c. Token not previously used (one-time use)
   d. Price drift < 20bps (configurable)
6. If OK → APPROVED → Paper trade executed
7. If drift > threshold → RECONFIRM_REQUIRED → human must re-confirm
```

## Configuration

Key settings in `apps/backend/.env`:

```bash
# Trading
TRADING_MODE=PAPER              # PAPER | LIVE
TRADING_SYMBOLS=["BTCUSDT","ETHUSDT"]

# LLM (fallback chain: ollama → gemini → openai)
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key

# Risk
MAX_POSITION_SIZE_USD=1000
MAX_DAILY_LOSS_PCT=2.5
MIN_RISK_REWARD_RATIO=1.5

# Security
APPROVAL_TOKEN_SECRET=change-this-secret
APPROVAL_TOKEN_EXPIRATION_SECONDS=30
MAX_PRICE_DRIFT_BPS=20

# Telegram
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id
```

## Testing

```bash
# All unit tests (195 tests)
PYTHONPATH=. pytest tests/unit/ -v

# Security tests (25 tests)
PYTHONPATH=. pytest tests/security/ -v

# Import boundary enforcement
python scripts/check_import_boundaries.py

# Database backup
./scripts/backup_database.sh
```

## Phases Completed

| Phase | Description | Tests |
|-------|-------------|-------|
| 0 | Foundation (auth, DB, monitoring) | — |
| 1 | Market Data (Binance WS/REST) | — |
| 2 | Features + Strategy (indicators) | 43 |
| 3 | Risk Engine (position sizing, gate) | 60 |
| 4 | Multi-Agent (5 agents + orchestrator) | 22 |
| 5 | Proposal + Approval (HMAC tokens) | 42 |
| 6 | Paper Trading (fill simulation, PnL) | 28 |
| 7 | Dashboard + WebSocket (React UI) | — |
| 8 | Hardening (security, shutdown, docs) | 25 |

**Total: 220 tests passing**

## Security Measures

- **JWT + TOTP 2FA** — all API endpoints require authentication
- **HMAC-SHA256 approval tokens** — cryptographically bound to proposal payload
- **One-time token use** — replay attacks impossible
- **Import boundaries** — execution module cannot import agents (enforced by CI)
- **Encrypted API keys** — stored with Fernet symmetric encryption
- **Price drift guard** — prevents executing at significantly different price
- **Rate limiting** — all endpoints protected against brute force
- **Structured logging** — all security events logged with structlog

## Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
  - System Health dashboard
  - LLM Cost & Performance dashboard
  - Trading Performance dashboard (main)

## License

MIT License — see [LICENSE](LICENSE)

---

> ⚠️ **Disclaimer**: This system is for educational and paper trading purposes only.
> Do not use with real funds without extensive testing and risk management.