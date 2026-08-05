"""Base Agent — abstract class for all ACTA analysis agents.

Each agent:
1. Receives feature data + market context as input
2. Builds a structured prompt
3. Calls LLM via LLMClient (with fallback)
4. Parses and validates the response into a Pydantic model
5. Returns a typed AgentOutput

Retry logic: up to 2 retries for JSON parse failures.
Timeout: enforced via asyncio.wait_for (from config).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from app.agents.llm_client import LLMClient, LLMResponse, llm_client
from app.config import settings
from app.core.metrics import AGENT_RUN_DURATION

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentOutput(BaseModel):
    """Base output model that all agent outputs inherit from."""

    agent_name: str = ""
    provider: str = ""
    model: str = ""
    latency_ms: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: str = ""
    parse_retries: int = 0


class BaseAgent[T: BaseModel](ABC):
    """Abstract base class for all analysis agents.

    Subclasses must implement:
    - name: agent identifier
    - system_prompt: the LLM role/instruction
    - build_prompt(context): construct the user prompt from features
    - parse_response(text): parse LLM text → Pydantic output model
    """

    MAX_RETRIES = 2

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or llm_client

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System instruction that defines the agent's role."""
        ...

    @abstractmethod
    def build_prompt(self, context: dict[str, Any]) -> str:
        """Build the user-facing prompt from market context and features."""
        ...

    @abstractmethod
    def parse_response(self, text: str) -> T:
        """Parse and validate LLM response text into a typed output model."""
        ...

    async def run(
        self,
        context: dict[str, Any],
        preferred_provider: str | None = None,
    ) -> T:
        """Execute the agent with retry logic and timeout enforcement.

        Args:
            context: Feature data and market context dict
            preferred_provider: Force a specific LLM provider for this run

        Returns:
            Typed agent output (Pydantic model)

        Raises:
            RuntimeError: If all retries and providers fail
        """
        start = time.monotonic()
        prompt = self.build_prompt(context)
        retries = 0
        last_error: Exception | None = None
        llm_response: LLMResponse | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Enforce per-agent timeout
                llm_response = await asyncio.wait_for(
                    self._client.complete(
                        prompt=prompt,
                        system_prompt=self.system_prompt,
                        preferred_provider=preferred_provider,
                    ),
                    timeout=settings.agent_timeout_seconds,
                )

                parsed = self.parse_response(llm_response.content)

                # Inject metadata into output
                parsed.agent_name = self.name
                parsed.provider = llm_response.provider
                parsed.model = llm_response.model
                parsed.latency_ms = llm_response.latency_ms
                parsed.input_tokens = llm_response.input_tokens
                parsed.output_tokens = llm_response.output_tokens
                parsed.raw_response = llm_response.content[:500]  # Truncate for storage
                parsed.parse_retries = retries

                latency_s = time.monotonic() - start
                with contextlib.suppress(Exception):
                    AGENT_RUN_DURATION.labels(
                        agent_name=self.name,
                        provider=llm_response.provider,
                    ).observe(latency_s)

                logger.info(
                    "agent_run_complete",
                    agent=self.name,
                    provider=llm_response.provider,
                    latency_ms=round(llm_response.latency_ms),
                    retries=retries,
                )

                return parsed

            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                retries += 1
                last_error = e
                logger.warning(
                    "agent_parse_failed",
                    agent=self.name,
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self.MAX_RETRIES:
                    # Ask LLM to fix its output format
                    prompt = self._build_retry_prompt(prompt, str(e))
                    continue

            except TimeoutError:
                last_error = TimeoutError(
                    f"Agent {self.name} timed out after {settings.agent_timeout_seconds}s"
                )
                logger.error("agent_timeout", agent=self.name)
                break

            except Exception as e:
                last_error = e
                logger.error("agent_run_failed", agent=self.name, error=str(e))
                break

        raise RuntimeError(
            f"Agent {self.name} failed after {retries} retries. Last error: {last_error}"
        )

    def _build_retry_prompt(self, original_prompt: str, error_msg: str) -> str:
        """Augment prompt with format correction instruction on retry."""
        return (
            f"{original_prompt}\n\n"
            f"IMPORTANT: Your previous response could not be parsed. Error: {error_msg}\n"
            f"You MUST respond with valid JSON only. No markdown code blocks. No extra text."
        )

    @staticmethod
    def extract_json(text: str) -> str:
        """Extract JSON object from LLM response that may contain markdown or extra text."""
        # Try to find JSON in code block first
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            return code_block.group(1)

        # Try to find raw JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return text.strip()
