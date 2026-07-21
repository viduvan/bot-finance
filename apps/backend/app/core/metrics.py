"""Prometheus metrics for ACTA monitoring.

Metrics are organized by domain: proposals, orders, risk, agents, market data, LLM.
All counters include relevant labels for dimensional analysis.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Proposals ────────────────────────────────────────────────────

PROPOSALS_CREATED = Counter(
    "acta_proposals_created_total",
    "Total trade proposals created",
    ["symbol", "recommendation"],
)

PROPOSALS_APPROVED = Counter(
    "acta_proposals_approved_total",
    "Total proposals approved by human",
    ["symbol"],
)

PROPOSALS_REJECTED = Counter(
    "acta_proposals_rejected_total",
    "Total proposals rejected by human",
    ["symbol"],
)

PROPOSALS_EXPIRED = Counter(
    "acta_proposals_expired_total",
    "Total proposals expired without action",
    ["symbol"],
)

PROPOSALS_ACTIVE = Gauge(
    "acta_proposals_active",
    "Currently active proposals (waiting for human)",
)

# ── Orders ───────────────────────────────────────────────────────

ORDERS_SUBMITTED = Counter(
    "acta_orders_submitted_total",
    "Total orders submitted to exchange",
    ["symbol", "side", "environment"],
)

ORDERS_FILLED = Counter(
    "acta_orders_filled_total",
    "Total orders fully filled",
    ["symbol", "side", "environment"],
)

ORDERS_FAILED = Counter(
    "acta_orders_failed_total",
    "Total orders that failed",
    ["symbol", "reason"],
)

# ── Risk ─────────────────────────────────────────────────────────

RISK_REJECTIONS = Counter(
    "acta_risk_rejections_total",
    "Total risk gate rejections",
    ["event_type"],
)

DAILY_DRAWDOWN = Gauge(
    "acta_daily_drawdown_percent",
    "Current daily drawdown percentage",
)

TOTAL_EXPOSURE = Gauge(
    "acta_total_exposure_percent",
    "Current total position exposure percentage",
)

# ── Agents ───────────────────────────────────────────────────────

AGENT_WORKFLOW_DURATION = Histogram(
    "acta_agent_workflow_duration_seconds",
    "Agent workflow total execution time",
    ["symbol"],
    buckets=[5, 10, 20, 30, 45, 60, 90, 120],
)

AGENT_RUN_DURATION = Histogram(
    "acta_agent_run_duration_seconds",
    "Individual agent execution time",
    ["agent_name", "provider"],
    buckets=[1, 2, 5, 10, 15, 20, 30],
)

AGENT_WORKFLOW_FAILURES = Counter(
    "acta_agent_workflow_failures_total",
    "Total agent workflow failures",
    ["symbol", "reason"],
)

# ── LLM ──────────────────────────────────────────────────────────

LLM_TOKENS_TOTAL = Counter(
    "acta_llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "direction"],  # direction: input/output
)

LLM_COST_TOTAL = Counter(
    "acta_llm_cost_usd_total",
    "Estimated total LLM cost in USD",
    ["provider"],
)

LLM_REQUESTS = Counter(
    "acta_llm_requests_total",
    "Total LLM API requests",
    ["provider", "status"],  # status: success/error/timeout
)

LLM_FALLBACK = Counter(
    "acta_llm_fallback_total",
    "Times LLM fallback was triggered",
    ["from_provider", "to_provider"],
)

# ── Market Data ──────────────────────────────────────────────────

BINANCE_WS_CONNECTED = Gauge(
    "acta_binance_ws_connected",
    "Binance WebSocket connection status (1=connected, 0=disconnected)",
)

MARKET_DATA_STALENESS = Gauge(
    "acta_market_data_staleness_seconds",
    "Seconds since last market data update",
    ["symbol"],
)

MARKET_DATA_GAPS = Counter(
    "acta_market_data_gaps_total",
    "Total detected gaps in market data",
    ["symbol", "timeframe"],
)

# ── HTTP ─────────────────────────────────────────────────────────

HTTP_REQUESTS = Counter(
    "acta_http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "acta_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ── System ───────────────────────────────────────────────────────

SYSTEM_UP = Gauge(
    "acta_system_up",
    "System uptime indicator (1=up)",
)

CELERY_TASKS_ACTIVE = Gauge(
    "acta_celery_tasks_active",
    "Number of currently active Celery tasks",
)

CELERY_TASKS_TOTAL = Counter(
    "acta_celery_tasks_total",
    "Total Celery tasks executed",
    ["task_name", "status"],
)
