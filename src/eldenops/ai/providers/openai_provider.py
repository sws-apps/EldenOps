"""OpenAI GPT provider."""

from __future__ import annotations

import time

import openai
import structlog

from eldenops.ai.base import AIMessage, AIProvider, AIResponse
from eldenops.config.constants import AIProvider as AIProviderEnum
from eldenops.config.settings import settings
from eldenops.core.exceptions import AIProviderError, RateLimitError

logger = structlog.get_logger()


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider implementation."""

    provider_name = AIProviderEnum.OPENAI

    # Available models
    MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ]

    # Pricing per 1M tokens (USD)
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. If None, uses default from settings.
        """
        self._api_key = api_key or settings.openai_api_key.get_secret_value()
        self._client: Optional[openai.AsyncOpenAI] = None
        self._default_model = settings.default_openai_model

    @property
    def client(self) -> openai.AsyncOpenAI:
        """Get or create the async client."""
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Generate a completion using OpenAI."""
        model = model or self._default_model
        start_time = time.monotonic()

        try:
            # Convert messages to OpenAI format
            openai_messages: list[dict] = []

            # Add system prompt if provided
            if system_prompt:
                openai_messages.append({"role": "system", "content": system_prompt})

            # Add conversation messages
            for msg in messages:
                if msg.role == "system" and not system_prompt:
                    openai_messages.append({"role": "system", "content": msg.content})
                elif msg.role != "system":
                    openai_messages.append({"role": msg.role, "content": msg.content})

            response = await self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=openai_messages,  # type: ignore
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract content
            content = ""
            if response.choices and response.choices[0].message.content:
                content = response.choices[0].message.content

            # Extract usage
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return AIResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                usage=usage,
                finish_reason=response.choices[0].finish_reason or "stop" if response.choices else "stop",
                latency_ms=latency_ms,
                raw_response=response.model_dump(),
            )

        except openai.RateLimitError as e:
            logger.warning("OpenAI rate limit hit", error=str(e))
            raise RateLimitError(
                "OpenAI rate limit exceeded",
                retry_after=60,
                details={"provider": self.provider_name},
            ) from e

        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise AIProviderError(
                f"OpenAI API error: {e}",
                details={"provider": self.provider_name, "error_type": type(e).__name__},
            ) from e

    async def validate_api_key(self, api_key: str) -> bool:
        """Validate an OpenAI API key."""
        try:
            temp_client = openai.AsyncOpenAI(api_key=api_key)
            await temp_client.models.list()
            return True
        except openai.AuthenticationError:
            return False
        except Exception as e:
            logger.warning("Error validating OpenAI API key", error=str(e))
            return False

    def get_available_models(self) -> list[str]:
        """Return available OpenAI models."""
        return self.MODELS.copy()

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model: Optional[str] = None
    ) -> float:
        """Estimate cost for an OpenAI request."""
        model = model or self._default_model
        pricing = self.PRICING.get(model, {"input": 2.50, "output": 10.0})

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
