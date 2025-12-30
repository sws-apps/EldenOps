"""Claude (Anthropic) AI provider."""

from __future__ import annotations

import time

import anthropic
import structlog

from eldenops.ai.base import AIMessage, AIProvider, AIResponse
from eldenops.config.constants import AIProvider as AIProviderEnum
from eldenops.config.settings import settings
from eldenops.core.exceptions import AIProviderError, RateLimitError

logger = structlog.get_logger()


class ClaudeProvider(AIProvider):
    """Anthropic Claude provider implementation."""

    provider_name = AIProviderEnum.CLAUDE

    # Available models
    MODELS = [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
    ]

    # Pricing per 1M tokens (USD)
    PRICING = {
        "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    }

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key. If None, uses default from settings.
        """
        self._api_key = api_key or settings.anthropic_api_key.get_secret_value()
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self._default_model = settings.default_claude_model

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Get or create the async client."""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Generate a completion using Claude."""
        model = model or self._default_model
        start_time = time.monotonic()

        try:
            # Convert messages to Anthropic format
            anthropic_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
                if msg.role != "system"  # System handled separately
            ]

            # Build request kwargs
            kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": anthropic_messages,
            }

            # Add system prompt if provided
            if system_prompt:
                kwargs["system"] = system_prompt
            else:
                # Check if first message is system
                system_msgs = [m for m in messages if m.role == "system"]
                if system_msgs:
                    kwargs["system"] = system_msgs[0].content

            response = await self.client.messages.create(**kwargs)

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text if response.content[0].type == "text" else ""

            return AIResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason or "stop",
                latency_ms=latency_ms,
                raw_response=response.model_dump(),
            )

        except anthropic.RateLimitError as e:
            logger.warning("Claude rate limit hit", error=str(e))
            raise RateLimitError(
                "Claude rate limit exceeded",
                retry_after=60,
                details={"provider": self.provider_name},
            ) from e

        except anthropic.APIError as e:
            logger.error("Claude API error", error=str(e))
            raise AIProviderError(
                f"Claude API error: {e}",
                details={"provider": self.provider_name, "error_type": type(e).__name__},
            ) from e

    async def validate_api_key(self, api_key: str) -> bool:
        """Validate a Claude API key."""
        try:
            temp_client = anthropic.AsyncAnthropic(api_key=api_key)
            await temp_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except anthropic.AuthenticationError:
            return False
        except Exception as e:
            logger.warning("Error validating Claude API key", error=str(e))
            return False

    def get_available_models(self) -> list[str]:
        """Return available Claude models."""
        return self.MODELS.copy()

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model: Optional[str] = None
    ) -> float:
        """Estimate cost for a Claude request."""
        model = model or self._default_model
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
