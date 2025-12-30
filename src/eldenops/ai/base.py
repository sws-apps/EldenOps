"""Base AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional,  Any


@dataclass
class AIMessage:
    """A message in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class AIResponse:
    """Response from an AI provider."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    # Example: {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
    finish_reason: str = "stop"
    latency_ms: int = 0
    raw_response: Optional[dict[str, Any]] = None


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    provider_name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AIResponse:
        """Generate a completion from the AI provider.

        Args:
            messages: List of conversation messages
            model: Model to use (provider-specific), None for default
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt

        Returns:
            AIResponse with the generated content
        """
        pass

    @abstractmethod
    async def validate_api_key(self, api_key: str) -> bool:
        """Validate that an API key works.

        Args:
            api_key: The API key to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Return list of available models for this provider."""
        pass

    def estimate_cost(
        self, input_tokens: int, output_tokens: int, model: Optional[str] = None
    ) -> float:
        """Estimate cost for a request in USD.

        Override in subclasses with actual pricing.
        """
        return 0.0
