# ACTA — Agentic Crypto Trading Advisor

> **Human-in-the-Loop Multi-Agent Crypto Trading Advisory System**
>
> _Agents analyze. Agents advise. **Humans decide.**_

[![Tests](https://img.shields.io/badge/tests-247%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-≥3.12-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-≥0.115-green)]()
[![React](https://img.shields.io/badge/React-19-61dafb)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-6-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Overview

ACTA is a **paper trading advisory system** that uses a 5-agent AI pipeline to analyze cryptocurrency markets and generate human-reviewable trade proposals. Every trade requires **explicit human approval** through a cryptographically secured approval flow.

```
Binance Market Data (REST + WebSocket)
       │
       ▼
  5 AI Agents (Multi-LLM: Gemini → OpenAI → Ollama)
       │
       ▼
  Signal Aggregation + Risk Gate
       │
       ▼
  Trade Proposal (PENDING_REVIEW)
       │
       ▼
  Human Dashboard (Approve / Reject / Reconfirm)
       │
       ▼
  Paper Trade Execution (slippage + fees simulation)
```

## Key Features

| Feature | Description |
|---------|-------------|
| **5-Agent Pipeline** | Market Regime → Technical → Order Flow → Risk Analysis → Critic |
| **HITL Approval** | Every trade requires HMAC-signed token approval (30s TTL) |
| **Price Drift Guard** | Auto re-confirmation if price moves > 20bps after approval |
| **Paper Trading** | Full simulation with slippage, fees, position tracking |
| **Real-time Dashboard** | WebSocket-driven React 19 UI with live proposal updates |
| **Multi-LLM Fallback** | Gemini → OpenAI → Ollama (qwen2.5:14b) automatic failover |
| **Celery Task Queue** | Async analysis with worker + beat scheduler |
| **Security** | JWT + TOTP 2FA, encrypted API keys, import boundaries enforced |
| **Audit Trail** | Full version history for every proposal state change |
| **i18n** | Bilingual UI (English / Tiếng Việt) |
| **Monitoring** | Prometheus metrics + Grafana dashboards (3 pre-built) |
| **CI/CD** | GitHub Actions: lint → test → security scan |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  React 19 Frontend (Vite 8 + TypeScript 6)                   │
│  ├── 8 Pages (Dashboard, Market, Analysis, Orders, …)        │
│  ├── TradingView Lightweight Charts (candlestick + PnL)      │
│  ├── Zustand State Management                                │
│  ├── React Query (TanStack) for data fetching                │
│  └── WebSocket live events (ws://host/api/v1/ws/events)      │
└────────────────────────────────┬─────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────┐
│  FastAPI Backend (Python ≥3.12)                               │
│  ├── REST API  (/api/v1/*)                                   │
│  │   ├── auth, market, analysis, proposals, execution        │
│  │   ├── orders, audit, system, notifications, ai_chat       │
│  │   └── features (technical indicators)                     │
│  ├── WebSocket (/api/v1/ws/*)                                │
│  ├── Agents (5 AI agents + orchestrator + signal aggregator) │
│  ├── Risk Engine (deterministic position sizing + gate)      │
│  ├── Proposals (state machine + HMAC approval tokens)        │
│  ├── Execution (paper fill simulator)                        │
│  ├── Backtesting engine                                      │
│  ├── Analytics module                                        │
│  └── Scheduler (Celery worker + beat)                        │
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL 16  │  Redis 7  │  Prometheus  │  Grafana        │
│  Ollama (GPU)   │  Celery Worker  │  Celery Beat             │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
bot-finance/
├── apps/
│   ├── backend/                # FastAPI Python backend
│   │   ├── app/
│   │   │   ├── agents/         # 5 AI agents + orchestrator + LLM client
│   │   │   ├── analytics/      # Trading analytics
│   │   │   ├── api/            # REST (v1) + WebSocket + middleware
│   │   │   ├── approvals/      # HMAC token approval system
│   │   │   ├── backtesting/    # Backtesting engine
│   │   │   ├── core/           # Constants, logging, metrics
│   │   │   ├── database/       # SQLAlchemy async sessions
│   │   │   ├── execution/      # Paper trade fill simulator
│   │   │   ├── features/       # Technical indicators (pandas-ta)
│   │   │   ├── market_data/    # Binance REST + WebSocket clients
│   │   │   ├── models/         # SQLAlchemy ORM models
│   │   │   ├── proposals/      # Proposal state machine
│   │   │   ├── repositories/   # Data access layer
│   │   │   ├── risk/           # Deterministic risk engine
│   │   │   ├── scheduler/      # Celery worker + beat tasks
│   │   │   ├── schemas/        # Pydantic request/response schemas
│   │   │   ├── services/       # Business logic (Telegram, etc.)
│   │   │   └── strategies/     # Trading strategies
│   │   ├── alembic/            # Database migrations
│   │   ├── tests/
│   │   │   ├── unit/           # 7 test modules
│   │   │   ├── security/       # Security tests
│   │   │   └── integration/    # Integration tests
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── frontend/               # React 19 + Vite 8 frontend
│       └── src/
│           ├── pages/          # 8 pages (Dashboard, Market, Analysis, …)
│           ├── components/     # CandlestickChart, PnLChart, ProposalCard, …
│           ├── services/       # Axios API client
│           ├── stores/         # Zustand auth store
│           └── i18n/           # EN/VI translations
├── infrastructure/
│   ├── docker/                 # Docker build configs
│   ├── grafana/dashboards/     # 3 pre-built dashboards
│   └── prometheus/             # Prometheus config
├── packages/
│   └── agent-prompts/          # Shared agent prompt templates
├── scripts/                    # Admin tools, test scripts, DB backup
├── docs/                       # System workflow documentation
├── docker-compose.yml          # 7 services (full stack)
├── docker-compose.dev.yml      # Dev overrides
├── Makefile                    # 20+ development commands
├── start.sh                    # 1-click startup (native)
├── stop.sh                     # 1-click shutdown
├── RUNNING.md                  # Vietnamese startup guide
└── .github/workflows/ci.yml   # GitHub Actions CI pipeline
```

---

## Quick Start

### Prerequisites

- **Docker** + Docker Compose v2
- **Python** ≥ 3.12 (for local development)
- **Node.js** ≥ 18 (for frontend)
- **NVIDIA GPU** (optional, for Ollama local LLM)
- **Binance API keys** (read-only recommended for paper trading)

### Option 1: Docker (Full Stack)

```bash
# 1. Clone
git clone <repo-url>
cd bot-finance

# 2. Configure
cp .env.example .env
# Edit .env with your API keys (Binance, Gemini, etc.)

# 3. Start all 7 services
docker compose up -d

# 4. Create admin user
docker compose exec backend python scripts/create_admin.py

# 5. Access
# Frontend:   http://localhost:5173
# API docs:   http://localhost:8000/api/docs
# Grafana:    http://localhost:3001  (admin / acta_grafana)
# Prometheus: http://localhost:9090
```

### Option 2: Native (1-Click Script)

```bash
# Start everything (Docker infra + Ollama + Backend + Celery + Frontend)
./start.sh

# Stop everything
./stop.sh
```

### Option 3: Manual Development

```bash
# Backend
cd apps/backend
pip install -e ".[dev]"
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Celery Worker (separate terminal)
celery -A app.scheduler.worker worker --loglevel=info --concurrency=1

# Frontend (separate terminal)
cd apps/frontend
npm install
npm run dev -- --host 0.0.0.0

# Infrastructure (Docker)
docker compose up -d postgres redis prometheus grafana
```

---

## Makefile Commands

```bash
make help              # Show all available commands

# Docker
make up                # Start all services
make down              # Stop all services
make restart           # Restart all services
make logs              # Follow all logs
make build             # Build all images

# Database
make db-migrate msg="description"   # Create migration
make db-upgrade        # Apply pending migrations
make db-downgrade      # Rollback last migration
make db-reset          # Drop & recreate (DESTRUCTIVE)

# Testing
make test              # Run all tests
make test-unit         # Run unit tests only
make test-security     # Run security tests
make test-cov          # Tests with coverage report

# Code Quality
make lint              # Run Ruff linter
make lint-fix          # Linter with auto-fix
make format            # Format code with Ruff
make typecheck         # Run mypy type checker

# Development
make dev               # Backend dev server
make dev-frontend      # Frontend dev server
make shell             # Python shell in container
make create-admin      # Create admin user
make pull-model        # Pull Ollama LLM model
make clean             # Remove all containers + caches
```

---

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

---

## AI Agent Pipeline

| # | Agent | Role | Weight |
|---|-------|------|--------|
| 1 | **Market Regime** | Identifies market phase (trending, ranging, volatile) | 22% |
| 2 | **Technical** | Analyzes indicators (RSI, MACD, Bollinger, etc.) via pandas-ta | 33% |
| 3 | **Order Flow** | Evaluates order book depth and trade flow | 22% |
| 4 | **Risk Analysis** | Assesses risk/reward, position sizing, correlations | 12% |
| 5 | **Critic** | Challenges the consensus, flags overconfidence | 11% |

Agents run in parallel via the **Orchestrator**, outputs are merged by the **Signal Aggregator**, then validated by the deterministic **Risk Engine** before proposal creation.

### LLM Fallback Chain

```
Gemini (gemini-3.6-flash) → OpenAI (gpt-4o-mini) → Ollama (qwen2.5:14b local)
```

If the primary provider fails, the system automatically falls through to the next available provider.

---

## Configuration

Key settings in `.env` (see [.env.example](.env.example) for full reference):

```bash
# ── Application ──────────────────────────────────
APP_ENV=development          # development | testing | production
TRADING_MODE=PAPER           # PAPER | LIVE

# ── Binance API ──────────────────────────────────
BINANCE_READ_API_KEY=        # Read-only key (market data)
BINANCE_TRADE_API_KEY=       # Trading key (execution only)
BINANCE_TESTNET=true         # Use testnet by default

# ── LLM Providers ───────────────────────────────
GEMINI_API_KEY=              # Primary (recommended)
GEMINI_MODEL=gemini-3.6-flash
OPENAI_API_KEY=              # Fallback 2
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b    # Local fallback
LLM_FALLBACK_CHAIN=["gemini","openai","ollama"]

# ── Security (CHANGE IN PRODUCTION) ─────────────
JWT_SECRET=change-me-use-openssl-rand-hex-32
APPROVAL_TOKEN_SECRET=change-me-approval-token-secret
ENCRYPTION_KEY=change-me-32-byte-encryption-key

# ── Telegram Notifications ──────────────────────
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── MFA ──────────────────────────────────────────
MFA_ENABLED=true
```

---

## Testing

```bash
# All tests (247 tests)
cd apps/backend
python -m pytest tests/ -v

# Unit tests only (7 modules)
python -m pytest tests/unit/ -v

# Security tests
python -m pytest tests/security/ -v

# With coverage report
python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Import boundary enforcement
python scripts/check_import_boundaries.py

# Database backup
./scripts/backup_database.sh
```

### Test Modules

| Module | Coverage Area |
|--------|---------------|
| `test_agents.py` | 5 AI agents + orchestrator |
| `test_indicators.py` | Technical indicators (pandas-ta) |
| `test_market_data.py` | Binance REST + WebSocket clients |
| `test_paper_trading.py` | Paper fill simulation + PnL |
| `test_proposals.py` | Proposal state machine + approval flow |
| `test_risk_engine.py` | Position sizing, risk gate, limits |
| `test_system_and_auth.py` | Auth, JWT, system health |
| `test_security.py` | Security hardening (25 tests) |

---

## Docker Services

The `docker-compose.yml` defines **7 services**:

| Service | Image / Build | Port | Purpose |
|---------|---------------|------|---------|
| `backend` | Custom (FastAPI) | 8000 | REST API + WebSocket server |
| `celery-worker` | Custom | — | Async analysis task processing |
| `celery-beat` | Custom | — | Scheduled task orchestration |
| `postgres` | `postgres:16-alpine` | 5432 | Primary database |
| `redis` | `redis:7-alpine` | 6379 | Cache + Celery broker |
| `ollama` | `ollama/ollama:0.12.7` | 11434 | Local LLM (GPU-accelerated) |
| `prometheus` | `prom/prometheus:v3.13.1` | 9090 | Metrics collection |
| `grafana` | `grafana/grafana:13.1.1` | 3001 | Monitoring dashboards |

---

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | JWT authentication + TOTP 2FA |
| Dashboard | `/` | Main overview with live proposals |
| Market | — | Real-time candlestick charts (Lightweight Charts) |
| Analysis | — | AI agent analysis results |
| Orders | — | Order history and management |
| Audit Log | — | Full system audit trail |
| Settings | — | System configuration |
| License | — | License information |

---

## Security Measures

- **JWT + TOTP 2FA** — all API endpoints require authentication
- **HMAC-SHA256 approval tokens** — cryptographically bound to proposal payload
- **One-time token use** — replay attacks impossible
- **Import boundaries** — execution module cannot import agents (enforced by CI)
- **Encrypted API keys** — stored with Fernet symmetric encryption
- **Price drift guard** — prevents executing at significantly different price
- **Rate limiting** — all endpoints protected against brute force (slowapi)
- **Structured logging** — all security events logged with structlog
- **CI security scan** — automated secret detection in GitHub Actions

---

## Monitoring

| Service | URL | Credentials |
|---------|-----|-------------|
| **Prometheus** | http://localhost:9090 | — |
| **Grafana** | http://localhost:3001 | `admin` / `acta_grafana` |

### Pre-built Grafana Dashboards

1. **Trading Performance** (`acta-main`) — primary trading metrics
2. **LLM Cost & Performance** (`acta-llm-cost`) — token usage, latency, costs
3. **System Health** (`acta-system-health`) — service uptime, resource usage

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):

```
Push / PR → Lint (Ruff) → Format Check → Unit Tests (w/ PostgreSQL + Redis) → Coverage → Security Scan
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python ≥3.12, FastAPI ≥0.115, SQLAlchemy 2 (async), Alembic |
| **Frontend** | React 19, TypeScript 6, Vite 8, Zustand, TanStack Query |
| **Charting** | TradingView Lightweight Charts 5 |
| **Database** | PostgreSQL 16, Redis 7 |
| **Task Queue** | Celery 5 (Redis broker) |
| **AI/LLM** | Google Gemini, OpenAI, Ollama (local) |
| **Monitoring** | Prometheus, Grafana |
| **Security** | JWT (python-jose), TOTP (pyotp), Fernet encryption |
| **Notifications** | Telegram Bot API |
| **CI/CD** | GitHub Actions |
| **Code Quality** | Ruff (lint + format), mypy (types) |

---

## License

MIT License — see [LICENSE](LICENSE)

---

> ⚠️ **Disclaimer**: This system is for educational and paper trading purposes only.
> Do not use with real funds without extensive testing and risk management.