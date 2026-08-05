"""Application constants.

Centralized constants that are NOT configurable (unlike settings).
These are system invariants.
"""

from __future__ import annotations

# ── Application ──────────────────────────────────────────────────

APP_NAME = "ACTA"
APP_DESCRIPTION = "Human-in-the-Loop Multi-Agent Crypto Trading Advisory System"
APP_VERSION = "0.1.0"

# ── API ──────────────────────────────────────────────────────────

API_V1_PREFIX = "/api/v1"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

# ── Client Order ID ──────────────────────────────────────────────

CLIENT_ORDER_ID_PREFIX = "ACTA"
CLIENT_ORDER_ID_TEMPLATE = f"{CLIENT_ORDER_ID_PREFIX}-{{proposal_id}}-{{version}}"

# ── Timeframes ───────────────────────────────────────────────────

ENTRY_TIMEFRAME = "15m"
TREND_CONFIRMATION_TIMEFRAME = "1h"
MACRO_TREND_TIMEFRAME = "4h"

# ── Supported Symbols (MVP) ─────────────────────────────────────

MVP_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT"})

# ── Agent Weights (defaults, overridden by config) ───────────────

DEFAULT_AGENT_WEIGHTS: dict[str, float] = {
    "market_regime": 0.22,
    "technical": 0.33,
    "order_flow": 0.22,
    "risk_analysis": 0.12,
    "critic": 0.11,
}

# ── Data Staleness Thresholds (seconds) ──────────────────────────

MAX_DATA_STALENESS_SECONDS = 120  # 2 minutes
MAX_SNAPSHOT_AGE_SECONDS = 60  # 1 minute

# ── WebSocket ────────────────────────────────────────────────────

WS_PING_INTERVAL = 20  # seconds
WS_PING_TIMEOUT = 10  # seconds
WS_RECONNECT_DELAY = 5  # seconds
WS_MAX_RECONNECT_DELAY = 300  # 5 minutes

# ── Rate Limiting ────────────────────────────────────────────────

BINANCE_RATE_LIMIT_WEIGHT_PER_MINUTE = 1200
BINANCE_RATE_LIMIT_ORDERS_PER_SECOND = 10

# ── Audit Log ────────────────────────────────────────────────────

AUDIT_LOG_MAX_DETAIL_LENGTH = 10_000  # Truncate very long details
