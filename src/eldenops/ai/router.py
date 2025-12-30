"""AI provider router for selecting and managing providers."""

from __future__ import annotations

from functools import lru_cache

import structlog

from eldenops.ai.base import AIMessage, AIProvider, AIResponse
from eldenops.ai.providers.claude import ClaudeProvider
from eldenops.ai.providers.openai_provider import OpenAIProvider
from eldenops.config.constants import AIProvider as AIProviderEnum
from eldenops.core.exceptions import AIProviderError, ConfigurationError

logger = structlog.get_logger()


class AIRouter:
    """Routes AI requests to the appropriate provider."""

    def __init__(self) -> None:
        """Initialize the AI router."""
        self._providers: dict[str, AIProvider] = {}
        self._default_provider: Optional[str] = None

    def register_provider(self, provider: AIProvider) -> None:
        """Register an AI provider.

        Args:
            provider: The provider instance to register
        """
        self._providers[provider.provider_name] = provider
        logger.info("Registered AI provider", provider=provider.provider_name)

    def set_default_provider(self, provider_name: str) -> None:
        """Set the default provider.

        Args:
            provider_name: Name of the provider to set as default
        """
        if provider_name not in self._providers:
            raise ConfigurationError(f"Provider {provider_name} not registered")
        self._default_provider = provider_name
        logger.info("Set default AI provider", provider=provider_name)

    def get_provider(self, provider_name: Optional[str] = None) -> AIProvider:
        """Get a provider by name.

        Args:
            provider_name: Provider name, or None for default

        Returns:
            The requested AI provider

        Raises:
            ConfigurationError: If provider not found
        """
        name = provider_name or self._default_provider
        if name is None:
            raise ConfigurationError("No default AI provider configured")

        provider = self._providers.get(name)
        if provider is None:
            raise ConfigurationError(f"AI provider {name} not found")

        return provider

    def get_provider_for_tenant(
        self,
        tenant_provider_config: Optional[dict] = None,
        fallback_provider: Optional[str] = None,
    ) -> tuple[AIProvider, str]:
        """Get the appropriate provider for a tenant.

        Args:
            tenant_provider_config: Tenant's AI config from database
            fallback_provider: Provider to use if tenant has no config

        Returns:
            Tuple of (provider instance, api_key to use)
        """
        if tenant_provider_config:
            provider_name = tenant_provider_config.get("provider")
            api_key = tenant_provider_config.get("api_key")

            if provider_name and api_key:
                # Create provider with tenant's API key
                provider = self._create_provider_with_key(provider_name, api_key)
                return provider, api_key

        # Fall back to default provider with system key
        fallback = fallback_provider or self._default_provider
        if fallback is None:
            raise ConfigurationError("No AI provider available")

        return self.get_provider(fallback), ""

    def _create_provider_with_key(self, provider_name: str, api_key: str) -> AIProvider:
        """Create a provider instance with a specific API key."""
        if provider_name == AIProviderEnum.CLAUDE:
            return ClaudeProvider(api_key=api_key)
        elif provider_name == AIProviderEnum.OPENAI:
            return OpenAIProvider(api_key=api_key)
        else:
            raise ConfigurationError(f"Unsupported provider: {provider_name}")

    async def complete(
        self,
        messages: list[AIMessage],
        provider_name: Optional[str] = None,
        **kwargs,
    ) -> AIResponse:
        """Send a completion request to a provider.

        Args:
            messages: Conversation messages
            provider_name: Optional specific provider to use
            **kwargs: Additional arguments passed to provider.complete()

        Returns:
            AIResponse from the provider
        """
        provider = self.get_provider(provider_name)

        try:
            return await provider.complete(messages, **kwargs)
        except Exception as e:
            logger.error(
                "AI completion failed",
                provider=provider.provider_name,
                error=str(e),
            )
            raise

    def list_providers(self) -> list[str]:
        """List all registered providers."""
        return list(self._providers.keys())

    def list_models(self, provider_name: Optional[str] = None) -> dict[str, list[str]]:
        """List available models, optionally for a specific provider.

        Args:
            provider_name: Optional provider to filter by

        Returns:
            Dict mapping provider names to their available models
        """
        if provider_name:
            provider = self.get_provider(provider_name)
            return {provider_name: provider.get_available_models()}

        return {
            name: provider.get_available_models()
            for name, provider in self._providers.items()
        }


# Global router instance
_router: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    """Get or create the global AI router.

    Returns:
        The global AIRouter instance with default providers registered
    """
    global _router

    if _router is None:
        _router = AIRouter()

        # Register default providers
        _router.register_provider(ClaudeProvider())
        _router.register_provider(OpenAIProvider())

        # Set Claude as default
        _router.set_default_provider(AIProviderEnum.CLAUDE)

    return _router


async def analyze_with_ai(
    prompt: str,
    system_prompt: Optional[str] = None,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> AIResponse:
    """Convenience function for simple AI analysis.

    Args:
        prompt: The user prompt
        system_prompt: Optional system prompt
        provider_name: Optional specific provider
        model: Optional specific model
        max_tokens: Max tokens to generate
        temperature: Sampling temperature

    Returns:
        AIResponse with the analysis
    """
    router = get_ai_router()
    messages = [AIMessage(role="user", content=prompt)]

    return await router.complete(
        messages=messages,
        provider_name=provider_name,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
