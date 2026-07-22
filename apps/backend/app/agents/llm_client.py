"""Multi-provider LLM Client with automatic fallback chain.

Provider priority (from config): ollama → gemini → openai
If primary provider fails or times out, automatically falls over to next.

Usage:
    client = LLMClient()
    response = await client.complete(prompt, system_prompt=...)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from app.config import settings
from app.core.metrics import LLM_COST_TOTAL, LLM_FALLBACK, LLM_REQUESTS, LLM_TOKENS_TOTAL

logger = structlog.get_logger(__name__)

# Cost per 1M tokens (USD) — approximate
COST_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "ollama": {"input": 0.0, "output": 0.0},              # Local — free
    "gemini": {"input": 0.075, "output": 0.30},           # gemini-2.0-flash
    "openai": {"input": 0.15, "output": 0.60},            # gpt-4o-mini
}


class LLMResponse:
    """Structured LLM response."""

    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0,
    ) -> None:
        self.content = content
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms

    @property
    def estimated_cost_usd(self) -> float:
        costs = COST_PER_1M_TOKENS.get(self.provider, {})
        return (
            self.input_tokens / 1_000_000 * costs.get("input", 0)
            + self.output_tokens / 1_000_000 * costs.get("output", 0)
        )


class LLMProviderError(Exception):
    """Raised when a provider fails to return a valid response."""


class OllamaProvider:
    """Ollama local LLM provider."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    async def complete(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": settings.llm_temperature},
                },
            )
            resp.raise_for_status()

        data = resp.json()
        latency_ms = (time.monotonic() - start) * 1000
        content = data.get("message", {}).get("content", "")
        usage = data.get("prompt_eval_count", 0), data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            provider="ollama",
            model=self.model,
            input_tokens=usage[0],
            output_tokens=usage[1],
            latency_ms=latency_ms,
        )


class GeminiProvider:
    """Google Gemini API provider."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = settings.gemini_timeout

    async def complete(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("Gemini API key not configured")

        parts = []
        if system_prompt:
            parts.append({"text": f"{system_prompt}\n\n{prompt}"})
        else:
            parts.append({"text": prompt})

        url = self.API_URL.format(model=self.model)
        start = time.monotonic()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                url,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {"temperature": settings.llm_temperature},
                },
            )
            resp.raise_for_status()

        data = resp.json()
        latency_ms = (time.monotonic() - start) * 1000

        content = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        usage = data.get("usageMetadata", {})

        return LLMResponse(
            content=content,
            provider="gemini",
            model=self.model,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            latency_ms=latency_ms,
        )


class OpenAIProvider:
    """OpenAI API provider (gpt-4o-mini)."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout

    async def complete(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("OpenAI API key not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": settings.llm_temperature,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        latency_ms = (time.monotonic() - start) * 1000
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            provider="openai",
            model=self.model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )


class LLMClient:
    """Multi-provider LLM client with automatic fallback chain.

    Tries providers in order from config.llm_fallback_chain.
    On failure, falls over to the next provider automatically.
    """

    _PROVIDERS: dict[str, type] = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
    }

    def __init__(self) -> None:
        self._fallback_chain = settings.llm_fallback_chain

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        preferred_provider: str | None = None,
    ) -> LLMResponse:
        """Send prompt to LLM with automatic fallback.

        Args:
            prompt: User message
            system_prompt: System instruction / role context
            preferred_provider: Override provider order for this call

        Returns:
            LLMResponse from the first successful provider
        """
        chain = [preferred_provider] + [
            p for p in self._fallback_chain if p != preferred_provider
        ] if preferred_provider else self._fallback_chain

        last_error: Exception | None = None

        for i, provider_name in enumerate(chain):
            provider_cls = self._PROVIDERS.get(provider_name)
            if provider_cls is None:
                logger.warning("unknown_llm_provider", provider=provider_name)
                continue

            provider = provider_cls()
            try:
                logger.debug("llm_attempt", provider=provider_name, attempt=i + 1)
                response = await provider.complete(prompt, system_prompt)

                # Metrics — successful call
                self._record_metrics(response)

                if i > 0:
                    from_provider = chain[0]
                    try:
                        LLM_FALLBACK.labels(
                            from_provider=from_provider,
                            to_provider=provider_name,
                        ).inc()
                    except Exception:
                        pass

                logger.info(
                    "llm_success",
                    provider=provider_name,
                    latency_ms=round(response.latency_ms),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=round(response.estimated_cost_usd, 6),
                )
                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    "llm_provider_timeout",
                    provider=provider_name,
                    error=str(e),
                )
                try:
                    LLM_REQUESTS.labels(provider=provider_name, status="timeout").inc()
                except Exception:
                    pass

            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_provider_error",
                    provider=provider_name,
                    error=str(e),
                )
                try:
                    LLM_REQUESTS.labels(provider=provider_name, status="error").inc()
                except Exception:
                    pass

        raise LLMProviderError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    def _record_metrics(self, response: LLMResponse) -> None:
        """Record Prometheus metrics for a successful LLM call."""
        try:
            LLM_REQUESTS.labels(provider=response.provider, status="success").inc()
            LLM_TOKENS_TOTAL.labels(
                provider=response.provider, direction="input"
            ).inc(response.input_tokens)
            LLM_TOKENS_TOTAL.labels(
                provider=response.provider, direction="output"
            ).inc(response.output_tokens)
            LLM_COST_TOTAL.labels(provider=response.provider).inc(
                response.estimated_cost_usd
            )
        except Exception:
            pass  # Metrics must never block core logic


# Shared singleton
llm_client = LLMClient()
