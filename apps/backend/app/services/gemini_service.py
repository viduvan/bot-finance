"""Gemini AI Service — wraps google-genai SDK for ACTA.

Provides:
  - Connection validation
  - Chat completions with tool-calling for financial analysis
  - Usage tracking
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class GeminiService:
    """Centralized Gemini AI service for chat and analysis."""

    SYSTEM_PROMPT = """You are ACTA AI Assistant, an expert crypto trading analyst.
You have access to real-time market data and trading tools.
Always provide data-driven insights with specific numbers.
When asked about prices, positions, or analysis, USE the available tools to fetch real data.
Respond concisely and professionally. Use markdown formatting for readability.
If the user speaks Vietnamese, respond in Vietnamese. If English, respond in English.
"""

    def __init__(self) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_status(self) -> dict[str, Any]:
        """Return current Gemini API configuration status."""
        return {
            "status": "connected" if self.is_configured else "not_configured",
            "model": self._model,
            "provider": "gemini",
            "api_key_set": bool(self._api_key),
            "rate_limits": {
                "rpm": 60,
                "tpm": 100_000,
                "rpd": 100,
            },
        }

    async def chat_with_tools(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        tools_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a chat message with tool-calling context.

        The tools_context provides pre-fetched data that the AI can reference.
        For Option B, we inject tool results directly into the prompt context.
        """
        if not self.is_configured:
            raise ValueError("Gemini API key not configured")

        try:
            import asyncio

            from google import genai

            client = genai.Client(api_key=self._api_key)

            # Build context-enriched prompt
            enriched_prompt = self._build_enriched_prompt(message, tools_context)

            # Build conversation contents
            contents: list[Any] = []
            if history:
                for msg in history[-10:]:  # Keep last 10 messages for context
                    contents.append(
                        genai.types.Content(
                            role="user" if msg["role"] == "user" else "model",
                            parts=[genai.types.Part(text=msg["content"])],
                        )
                    )
            contents.append(enriched_prompt)

            config = genai.types.GenerateContentConfig(
                temperature=0.3,  # Slightly creative for chat
                system_instruction=self.SYSTEM_PROMPT,
            )

            start = time.monotonic()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self._model,
                contents=contents,
                config=config,
            )
            latency_ms = (time.monotonic() - start) * 1000

            content = response.text or ""
            usage = response.usage_metadata

            logger.info(
                "gemini_chat_success",
                model=self._model,
                latency_ms=round(latency_ms),
                input_tokens=usage.prompt_token_count if usage else 0,
                output_tokens=usage.candidates_token_count if usage else 0,
            )

            return {
                "reply": content,
                "model": self._model,
                "provider": "gemini",
                "latency_ms": round(latency_ms, 1),
                "input_tokens": usage.prompt_token_count if usage else 0,
                "output_tokens": usage.candidates_token_count if usage else 0,
            }

        except ImportError:
            raise ValueError("google-genai package not installed. Run: pip install google-genai")
        except Exception as e:
            logger.error("gemini_chat_error", error=str(e))
            raise

    def _build_enriched_prompt(self, message: str, tools_context: dict[str, Any] | None) -> str:
        """Build a prompt enriched with tool data context."""
        if not tools_context:
            return message

        context_parts = [f"User question: {message}", "", "--- LIVE DATA CONTEXT ---"]

        for tool_name, tool_data in tools_context.items():
            context_parts.append(f"\n[{tool_name}]:")
            if isinstance(tool_data, dict):
                for key, value in tool_data.items():
                    context_parts.append(f"  {key}: {value}")
            elif isinstance(tool_data, list):
                for item in tool_data[:5]:  # Limit list items
                    context_parts.append(f"  - {item}")
            else:
                context_parts.append(f"  {tool_data}")

        context_parts.append("\n--- END DATA ---")
        context_parts.append("\nUse the above live data to answer the user's question accurately.")

        return "\n".join(context_parts)


# Singleton
gemini_service = GeminiService()
