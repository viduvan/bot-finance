"""AI Chat API — Advanced chat with tool-calling for financial analysis.

Tools available:
  - get_ticker: Real-time price data
  - get_candles: OHLCV candle data
  - get_positions: Current open positions
  - get_proposals: Active trading proposals
  - get_technical_indicators: Computed technical indicators
  - get_pnl_summary: P&L performance summary
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.llm_client import llm_client
from app.config import settings
from app.dependencies import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict[str, Any]] = []
    model: str = ""
    provider: str = ""
    latency_ms: float = 0


# ── Tool Functions ────────────────────────────────────────────────


async def tool_get_ticker(symbol: str = "BTCUSDT") -> dict[str, Any]:
    """Fetch real-time ticker data for a symbol."""
    try:
        from app.market_data.binance_rest import binance_client

        ticker = await binance_client.get_ticker_24h(symbol)
        return {
            "symbol": str(ticker.get("symbol", symbol)),
            "price": str(ticker.get("price", "0")),
            "price_change_24h": str(ticker.get("price_change_24h", "0")),
            "price_change_pct_24h": str(ticker.get("price_change_pct_24h", "0")),
            "volume_24h": str(ticker.get("quote_volume_24h", "0")),
            "high_24h": str(ticker.get("high_price", "0")),
            "low_24h": str(ticker.get("low_price", "0")),
            "bid": str(ticker.get("bid", "0")),
            "ask": str(ticker.get("ask", "0")),
        }
    except Exception as e:
        logger.warning("tool_get_ticker_error", error=str(e), symbol=symbol)
        return {"error": f"Failed to fetch ticker for {symbol}: {str(e)}"}


async def tool_get_positions() -> dict[str, Any]:
    """Fetch current open positions from database."""
    try:
        from app.database.session import get_session
        from app.repositories.position_repo import PositionRepository

        async for session in get_session():
            repo = PositionRepository(session)
            positions = await repo.get_open_positions()
            return {
                "count": len(positions),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "side": p.side,
                        "entry_price": str(p.entry_price),
                        "quantity": str(p.quantity),
                        "unrealized_pnl": str(getattr(p, "unrealized_pnl", "0")),
                    }
                    for p in positions[:10]
                ],
            }
    except Exception as e:
        logger.warning("tool_get_positions_error", error=str(e))
        return {"count": 0, "positions": [], "note": "No positions data available"}


async def tool_get_proposals() -> dict[str, Any]:
    """Fetch active trading proposals."""
    try:
        from app.database.session import get_session
        from app.repositories.proposal_repo import ProposalRepository

        async for session in get_session():
            repo = ProposalRepository(session)
            proposals = await repo.list_active()
            return {
                "count": len(proposals),
                "proposals": [
                    {
                        "id": str(p.id),
                        "symbol": p.symbol,
                        "direction": p.direction,
                        "confidence": str(
                            getattr(p, "confidence", getattr(p, "consensus_score", "0"))
                        ),
                        "status": p.status,
                        "created_at": str(p.created_at) if p.created_at else "",
                    }
                    for p in proposals[:10]
                ],
            }
    except Exception as e:
        logger.warning("tool_get_proposals_error", error=str(e))
        return {"count": 0, "proposals": [], "note": "No proposals data available"}


async def tool_get_pnl_summary() -> dict[str, Any]:
    """Fetch PnL performance summary."""
    try:
        from app.database.session import get_session
        from app.repositories.trade_repo import TradeRepository

        async for session in get_session():
            repo = TradeRepository(session)
            summary = await repo.get_pnl_summary()
            return summary
    except Exception as e:
        logger.warning("tool_get_pnl_error", error=str(e))
        return {
            "total_trades": 0,
            "total_net_pnl": "0",
            "win_rate": 0,
            "note": "No PnL data available",
        }


async def tool_get_technical_indicators(symbol: str = "BTCUSDT") -> dict[str, Any]:
    """Fetch computed technical indicators."""
    try:
        from app.features.indicator_engine import compute_indicators

        indicators = await compute_indicators(symbol)
        if isinstance(indicators, dict):
            # Return a summary of key indicators
            return {
                "symbol": symbol,
                "rsi": indicators.get("rsi_14", "N/A"),
                "macd": indicators.get("macd", "N/A"),
                "macd_signal": indicators.get("macd_signal", "N/A"),
                "bb_upper": indicators.get("bb_upper", "N/A"),
                "bb_lower": indicators.get("bb_lower", "N/A"),
                "sma_20": indicators.get("sma_20", "N/A"),
                "ema_50": indicators.get("ema_50", "N/A"),
                "atr_14": indicators.get("atr_14", "N/A"),
                "volume_sma": indicators.get("volume_sma_20", "N/A"),
            }
        return {"symbol": symbol, "note": "Indicators not yet computed"}
    except Exception as e:
        logger.warning("tool_get_indicators_error", error=str(e))
        return {"symbol": symbol, "note": f"Failed to compute indicators: {str(e)}"}


# ── Tool Routing ──────────────────────────────────────────────────

TOOL_PATTERNS: list[tuple[str, str, Any]] = [
    # (pattern, tool_name, tool_func)
    (r"(?i)(price|giá|ticker|quote|bao nhiêu)", "get_ticker", tool_get_ticker),
    (r"(?i)(position|vị thế|holding|đang giữ)", "get_positions", tool_get_positions),
    (r"(?i)(proposal|đề xuất|recommend|khuyến nghị|signal)", "get_proposals", tool_get_proposals),
    (
        r"(?i)(pnl|profit|loss|lãi|lỗ|performance|hiệu suất)",
        "get_pnl_summary",
        tool_get_pnl_summary,
    ),
    (
        r"(?i)(indicator|chỉ số|rsi|macd|bollinger|sma|ema|technical|kỹ thuật)",
        "get_technical_indicators",
        tool_get_technical_indicators,
    ),
]


def _extract_symbol(message: str) -> str:
    """Extract crypto symbol from message, default BTCUSDT."""
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
    msg_upper = message.upper()

    for sym in symbols:
        if sym in msg_upper or sym.replace("USDT", "") in msg_upper:
            return sym

    # Check for common names
    name_map = {
        "BITCOIN": "BTCUSDT",
        "BTC": "BTCUSDT",
        "ETHEREUM": "ETHUSDT",
        "ETH": "ETHUSDT",
        "SOLANA": "SOLUSDT",
        "SOL": "SOLUSDT",
        "BNB": "BNBUSDT",
        "BINANCE COIN": "BNBUSDT",
    }
    for name, sym in name_map.items():
        if name in msg_upper:
            return sym

    return "BTCUSDT"


async def _detect_and_call_tools(message: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Detect which tools to call based on message content."""
    tool_calls: list[dict[str, Any]] = []
    tools_context: dict[str, Any] = {}
    symbol = _extract_symbol(message)

    for pattern, tool_name, tool_func in TOOL_PATTERNS:
        if re.search(pattern, message):
            try:
                if tool_name in ("get_ticker", "get_technical_indicators"):
                    result = await tool_func(symbol)
                    args = {"symbol": symbol}
                else:
                    result = await tool_func()
                    args = {}

                tool_calls.append(
                    {
                        "name": tool_name,
                        "args": args,
                        "result": result,
                    }
                )
                tools_context[tool_name] = result
            except Exception as e:
                logger.warning("tool_call_error", tool=tool_name, error=str(e))
                tools_context[tool_name] = {"error": str(e)}

    # If no specific tool matched but it's a general question, provide ticker context
    if not tool_calls:
        try:
            ticker_data = await tool_get_ticker(symbol)
            tools_context["get_ticker"] = ticker_data
            tool_calls.append(
                {
                    "name": "get_ticker",
                    "args": {"symbol": symbol},
                    "result": ticker_data,
                }
            )
        except Exception:
            pass

    return tool_calls, tools_context


# ── API Endpoints ─────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    _user: Any = Depends(get_current_user),
) -> ChatResponse:
    """ACTA Chat with tool-calling capabilities.

    Detects relevant tools from user message, fetches live data,
    then sends enriched context to the active LLM (Ollama-first).
    """
    try:
        # Step 1: Detect and call relevant tools
        tool_calls, tools_context = await _detect_and_call_tools(req.message)

        logger.info(
            "acta_chat_tools_called",
            tools=[tc["name"] for tc in tool_calls],
            message_preview=req.message[:80],
        )

        # Step 2: Build enriched prompt with tool context
        enriched_prompt = req.message
        if tools_context:
            context_lines = [f"User question: {req.message}", "", "--- LIVE DATA CONTEXT ---"]
            for tool_name, tool_data in tools_context.items():
                context_lines.append(f"\n[{tool_name}]:")
                if isinstance(tool_data, dict):
                    for key, value in tool_data.items():
                        context_lines.append(f"  {key}: {value}")
                elif isinstance(tool_data, list):
                    for item in tool_data[:5]:
                        context_lines.append(f"  - {item}")
                else:
                    context_lines.append(f"  {tool_data}")
            context_lines.append("\n--- END DATA ---")
            context_lines.append(
                "\nUse the above live data to answer the user's question accurately."
            )
            enriched_prompt = "\n".join(context_lines)

        system_prompt = (
            "You are ACTA Trading Assistant, an expert crypto trading analyst.\n"
            "You have access to real-time market data.\n"
            "Always provide data-driven insights with specific numbers.\n"
            "Respond concisely and professionally. Use markdown for readability.\n"
            "If the user speaks Vietnamese, respond in Vietnamese."
        )

        # Step 3: Send to LLMClient (Ollama-first via fallback chain)
        result = await llm_client.complete(
            prompt=enriched_prompt,
            system_prompt=system_prompt,
        )

        return ChatResponse(
            reply=result.content,
            tool_calls=tool_calls,
            model=result.model,
            provider=result.provider,
            latency_ms=round(result.latency_ms, 1),
        )

    except Exception as e:
        logger.error("acta_chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def ai_status() -> dict[str, Any]:
    """Check LLM service status and configuration."""
    primary_provider = (
        settings.llm_fallback_chain_list[0] if settings.llm_fallback_chain_list else "ollama"
    )
    return {
        "status": "connected",
        "provider": primary_provider,
        "model": settings.ollama_model if primary_provider == "ollama" else settings.gemini_model,
        "fallback_chain": settings.llm_fallback_chain_list,
    }
