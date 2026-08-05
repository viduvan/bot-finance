"""Multi-provider LLM Client with automatic fallback chain.

Provider priority (from config): ollama → gemini → openai
If primary provider fails or times out, automatically falls over to next.

Usage:
    client = LLMClient()
    response = await client.complete(prompt, system_prompt=...)
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import httpx
import structlog

from app.config import settings
from app.core.metrics import LLM_COST_TOTAL, LLM_FALLBACK, LLM_REQUESTS, LLM_TOKENS_TOTAL

logger = structlog.get_logger(__name__)

# Cost per 1M tokens (USD) — approximate
COST_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "ollama": {"input": 0.0, "output": 0.0},  # Local — free
    "gemini": {"input": 0.10, "output": 0.40},  # gemini-2.5-flash
    "openai": {"input": 0.15, "output": 0.60},  # gpt-4o-mini
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
        return self.input_tokens / 1_000_000 * costs.get(
            "input", 0
        ) + self.output_tokens / 1_000_000 * costs.get("output", 0)


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
    """Google Gemini API provider using official google-genai SDK."""

    def __init__(self) -> None:
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = settings.gemini_timeout

    async def complete(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("Gemini API key not configured")

        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)

            config = genai.types.GenerateContentConfig(
                temperature=settings.llm_temperature,
            )
            if system_prompt:
                config.system_instruction = system_prompt

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    start = time.monotonic()
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )
                    latency_ms = (time.monotonic() - start) * 1000

                    content = response.text or ""
                    usage = response.usage_metadata
                    input_tokens = usage.prompt_token_count if usage else 0
                    output_tokens = usage.candidates_token_count if usage else 0

                    return LLMResponse(
                        content=content,
                        provider="gemini",
                        model=self.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 15s, 30s
                            delay = 15 * (attempt + 1)
                            logger.warning(
                                "gemini_rate_limited",
                                attempt=attempt + 1,
                                retry_delay=delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                    raise LLMProviderError(f"429 RESOURCE_EXHAUSTED. {error_str}")

        except ImportError:
            raise LLMProviderError(
                "google-genai package not installed. Run: pip install google-genai"
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
        self._fallback_chain = settings.llm_fallback_chain_list

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
        chain = (
            [preferred_provider] + [p for p in self._fallback_chain if p != preferred_provider]
            if preferred_provider
            else self._fallback_chain
        )

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
                    with contextlib.suppress(Exception):
                        LLM_FALLBACK.labels(
                            from_provider=from_provider,
                            to_provider=provider_name,
                        ).inc()

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
                with contextlib.suppress(Exception):
                    LLM_REQUESTS.labels(provider=provider_name, status="timeout").inc()

            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_provider_error",
                    provider=provider_name,
                    error=str(e),
                )
                with contextlib.suppress(Exception):
                    LLM_REQUESTS.labels(provider=provider_name, status="error").inc()

        raise LLMProviderError(f"All LLM providers failed. Last error: {last_error}")

    def _record_metrics(self, response: LLMResponse) -> None:
        """Record Prometheus metrics for a successful LLM call."""
        try:
            LLM_REQUESTS.labels(provider=response.provider, status="success").inc()
            LLM_TOKENS_TOTAL.labels(provider=response.provider, direction="input").inc(
                response.input_tokens
            )
            LLM_TOKENS_TOTAL.labels(provider=response.provider, direction="output").inc(
                response.output_tokens
            )
            LLM_COST_TOTAL.labels(provider=response.provider).inc(response.estimated_cost_usd)
        except Exception:
            pass  # Metrics must never block core logic


# Shared singleton
llm_client = LLMClient()
